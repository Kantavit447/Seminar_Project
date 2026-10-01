"""ตรวจ prompt/context/schema ของ CoT หรือ IRAC บน engineering โดยไม่เรียกโมเดลหรือเครือข่าย."""

import argparse
import atexit
import asyncio
from copy import deepcopy
import importlib.abc
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
CUE = "Let's think step by step. "
ENGINEERING = ["0000", "0001", "0002", "0003", "0008", "0023", "0026", "0036", "0041", "0046"]
FORBIDDEN = ("sentence_transformers", "transformers", "FlagEmbedding",
             "llama_index.embeddings.huggingface", "lrg.retrieval.retrieval_init")


def blocked(*args, **kwargs):
    raise AssertionError("Offline validation forbids network, live retrieval, and LLM clients.")


class NoLiveImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == prefix or fullname.startswith(prefix + ".") for prefix in FORBIDDEN):
            raise AssertionError(f"Unexpected live retrieval import: {fullname}")
        return None


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def expect_value_error(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError("Unsupported configuration unexpectedly succeeded.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-prompt-manager", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dump-prompts", action="store_true")
    parser.add_argument("--method", choices=("zero_shot_cot", "irac"), default="zero_shot_cot")
    args = parser.parse_args()
    check(Path.cwd().resolve() == ROOT, "Run from the clean project root.")
    # Windows ต้องสร้างช่องทางภายในของ event loop ก่อนปิดกั้นการเชื่อมต่อในการตรวจ
    offline_loop = asyncio.new_event_loop()
    atexit.register(offline_loop.close)
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    sys.meta_path.insert(0, NoLiveImports())

    import yaml
    from pydantic import ValidationError
    import script.response_e2e as entry
    from lrg.prompting import PromptManager

    entry.init_llm = blocked
    entry.init_retriever = blocked
    shared = dict(prompt_version="v3", citation_mode="provision_id", citation_constraint_mode="enum")
    direct = PromptManager(reasoning_method="direct", **shared)
    candidate = PromptManager(reasoning_method=args.method, **shared)
    old_direct = None
    old_cot = None
    unchanged_cot = PromptManager(reasoning_method="zero_shot_cot", **shared)
    if args.baseline_prompt_manager:
        spec = importlib.util.spec_from_file_location("pre_change_prompt_manager", args.baseline_prompt_manager)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Resolve the unchanged schemas beside the real module, not beside the temporary snapshot.
        module.__file__ = str(ROOT / "lrg/prompting/prompt_manager.py")
        old_direct = module.PromptManager(template_dir=str(ROOT / "lrg/prompting/templates"), reasoning_method="direct", **shared)
        if args.method == "irac":
            old_cot = module.PromptManager(template_dir=str(ROOT / "lrg/prompting/templates"), reasoning_method="zero_shot_cot", **shared)

    expect_value_error(lambda: PromptManager(reasoning_method="unsupported", **shared))
    for key, value in (("prompt_version", "v2"), ("citation_mode", "inline"), ("citation_constraint_mode", "none")):
        invalid = dict(shared, **{key: value})
        expect_value_error(lambda: PromptManager(reasoning_method=args.method, **invalid))
    expect_value_error(lambda: candidate.get_prompt_rendered("coverage-contradiction", "tax", "offline"))
    expect_value_error(lambda: candidate.get_prompt_rendered("response", "wangchan", "offline"))

    specs = [
        ("golden", "golden_qwen", "16384"),
        ("retrieved", "section_based_rag_qwen", "32768"),
    ]
    checks = []
    for context, prefix, window in specs:
        base_path = ROOT / f"config/local/response/{prefix}_direct_v3_citation_id_enum_engineering_10_ctx{window}.yaml"
        candidate_path = ROOT / f"config/local/response/{prefix}_{args.method}_v3_citation_id_enum_engineering_10_ctx{window}.yaml"
        baseline = yaml.safe_load(base_path.read_text(encoding="utf-8"))
        config = yaml.safe_load(candidate_path.read_text(encoding="utf-8"))
        comparable = deepcopy(config)
        comparable["reasoning_method"] = baseline["reasoning_method"]
        comparable["output_path"] = baseline["output_path"]
        comparable["diagnostic"]["failure_output_dir"] = baseline["diagnostic"]["failure_output_dir"]
        check(comparable == baseline, "Method changes configuration beyond method/output paths.")
        check(config["output_path"] != baseline["output_path"], "Results would overwrite Direct.")
        check(config["reasoning_method"] == args.method, "Wrong method in config.")
        check(config["data_config"]["chunk"]["tax_data_path"] == "data_splits/tax_engineering_10.csv", "Only engineering data is allowed.")
        dataset = entry.EvalDataset(**config["data_config"]["chunk"])
        check([entry.canonical_idx(v) for v in dataset.tax_df["source_idx"]] == ENGINEERING, "Engineering IDs/order changed.")
        for column in dataset.tax_df.columns:
            if "answer" in column.lower():
                dataset.tax_df[column] = "OFFLINE_REFERENCE_MUST_NOT_REACH_PROMPT"
        augmenter = entry.NitiLinkAugmenter(dataset=dataset, config=entry.NitiLinkAugmenterConfig(
            **config["augmenter_config"]["no-ref"], strat_name=dataset.strat_name))
        retriever = entry.init_saved_retriever(dataset, config["saved_retrieval_path"]) if context == "retrieved" else None

        def make_ragger(manager):
            return entry.Ragger(dataset=dataset, prompt_manager=manager,
                llm=entry.PromptDumpLLM(config["llm_config"]["qwen"]["model"]),
                augmenter=augmenter, retriever=retriever, context_source=context)

        direct_ragger, candidate_ragger = make_ragger(direct), make_ragger(candidate)
        old_ragger = make_ragger(old_direct) if old_direct else None
        old_cot_ragger = make_ragger(old_cot) if old_cot else None
        unchanged_cot_ragger = make_ragger(unchanged_cot) if old_cot else None
        for _, row in dataset.tax_df.iterrows():
            call = dict(query=row["question"], dataset_name="tax",
                        relevant_laws=row["relevant_laws"] if context == "golden" else None)
            direct_prompt, direct_structure, direct_nodes, _ = direct_ragger.get_prompt_structure(**call)
            candidate_prompt, candidate_structure, candidate_nodes, _ = candidate_ragger.get_prompt_structure(**call)
            check(direct_structure.model_json_schema() == candidate_structure.model_json_schema(), "Response schema changed.")
            check(direct_prompt["messages"][0] == candidate_prompt["messages"][0], "System prompt changed.")
            check(direct_prompt["messages"][-1] == candidate_prompt["messages"][-1], "Question/legal context changed.")
            check(len(direct_prompt["messages"]) == len(candidate_prompt["messages"]), "Examples or extra messages were added.")
            changed = [i for i, (a, b) in enumerate(zip(direct_prompt["messages"], candidate_prompt["messages"])) if a != b]
            check(len(changed) == 1, "Expected exactly one changed instruction message.")
            index = changed[0]
            cleaned = deepcopy(candidate_prompt)
            check(cleaned["messages"][index]["role"] == "user", "Cue must be in the user instruction.")
            instruction = cleaned["messages"][index]["content"]
            if args.method == "zero_shot_cot":
                check(instruction.startswith(CUE), "Missing CoT cue.")
                cleaned["messages"][index]["content"] = instruction[len(CUE):]
            else:
                instruction_prefix = "Analyze the final QUESTION using IRAC."
                labels = ("I — Issue:", "R — Rule:", "A — Application:", "C — Conclusion:")
                check(instruction.startswith(instruction_prefix) and CUE not in instruction, "Wrong IRAC instruction.")
                positions = [instruction.index(label) for label in labels]
                check(positions == sorted(positions), "IRAC sections are out of order.")
                check(all(instruction.count(label) == 1 for label in labels), "Repeated IRAC section.")
                suffix = direct_prompt["messages"][index]["content"]
                check(instruction.endswith(suffix), "Shared Direct instruction changed.")
                check([message["role"] for message in candidate_prompt["messages"]] == ["system", "user", "user"], "IRAC must remain zero-shot.")
                cleaned["messages"][index]["content"] = suffix
            check(cleaned == direct_prompt, "Method differs from Direct outside its instruction.")
            check("OFFLINE_REFERENCE_MUST_NOT_REACH_PROMPT" not in json.dumps(candidate_prompt), "Reference leaked into prompt.")
            direct_map = entry.Ragger.build_provision_map(direct_nodes)
            candidate_map = entry.Ragger.build_provision_map(candidate_nodes)
            check(direct_map == candidate_map, "Provision IDs/order/mapping changed.")
            check(bool(candidate_map), "Missing context.")
            if context == "retrieved":
                check(len(candidate_map) == 10, "Saved context must retain Top 10.")
            else:
                check(not candidate_ragger.resolve_gold_provisions(row["relevant_laws"])[1], "Unresolved golden provision.")
            allowed = [p["provision_id"] for p in candidate_map]
            schema = candidate.build_citation_id_enum_structure(allowed)
            check(schema.model_json_schema() == direct.build_citation_id_enum_structure(allowed).model_json_schema(), "Dynamic enum changed.")
            payload = dict(analysis="offline", answer="offline", citation_ids=list(dict.fromkeys((allowed[0], allowed[-1]))))
            schema.model_validate(payload)
            try:
                schema.model_validate(dict(payload, citation_ids=["P999999"]))
            except ValidationError:
                pass
            else:
                raise AssertionError("Enum accepted an ID outside context.")
            mapped, invalid_ids, duplicate_ids, errors = entry.Ragger.map_citation_ids(payload, candidate_map)
            check(not invalid_ids and not duplicate_ids and not errors, "Deterministic mapping failed.")
            check(mapped["citations"] == [{"law": item["law"], "section": item["section"]} for item in candidate_map if item["provision_id"] in payload["citation_ids"]], "Final citations changed.")
            if old_ragger:
                old_prompt, old_structure, old_nodes, _ = old_ragger.get_prompt_structure(**call)
                check(old_prompt == direct_prompt, "Direct prompt regressed against pre-change implementation.")
                check(old_structure.model_json_schema() == direct_structure.model_json_schema(), "Direct schema regressed.")
                check(entry.Ragger.build_provision_map(old_nodes) == direct_map, "Direct mapping regressed.")
            if old_cot_ragger:
                old_prompt, old_structure, old_nodes, _ = old_cot_ragger.get_prompt_structure(**call)
                current_prompt, current_structure, current_nodes, _ = unchanged_cot_ragger.get_prompt_structure(**call)
                check(old_prompt == current_prompt, "CoT prompt regressed against pre-change implementation.")
                check(old_structure.model_json_schema() == current_structure.model_json_schema(), "CoT schema regressed.")
                check(entry.Ragger.build_provision_map(old_nodes) == entry.Ragger.build_provision_map(current_nodes), "CoT mapping regressed.")
            checks.append(dict(context=context, source_idx=entry.canonical_idx(row["source_idx"]),
                               provisions=len(candidate_map), status="PASS"))

        smoke_path = ROOT / f"config/local/response/{prefix}_{args.method}_v3_citation_id_enum_diagnostic_source_0008_ctx{window}.yaml"
        smoke = yaml.safe_load(smoke_path.read_text(encoding="utf-8"))
        if args.method == "irac":
            for irac_path in (candidate_path, smoke_path):
                previous_path = irac_path.with_name(irac_path.name.replace("_irac_", "_zero_shot_cot_"))
                expected = previous_path.read_text(encoding="utf-8").replace("zero_shot_cot", "irac")
                check(irac_path.read_text(encoding="utf-8") == expected, "IRAC config differs from CoT beyond method/output paths.")
        check(smoke["diagnostic"]["runtime_idx"] == "0004" and smoke["diagnostic"]["source_idx"] == "0008", "Smoke source mapping changed.")
        check(dataset.tax_df.iloc[4]["source_idx"] == "0008" or entry.canonical_idx(dataset.tax_df.iloc[4]["source_idx"]) == "0008", "Runtime 0004 must resolve to source 0008.")
        if args.dump_prompts:
            offline_loop.run_until_complete(entry.main(argparse.Namespace(config_path=str(smoke_path),
                saved_retrieval_smoke_test=False, dump_final_prompt=True)))
            label = "golden" if context == "golden" else "section_based"
            dump_path = ROOT / f"results/current/debug_prompts/{label}_{args.method}_v3_citation_id_enum_runtime_0004_source_0008_final_prompt.txt"
            dump_text = dump_path.read_text(encoding="utf-8")
            marker = CUE if args.method == "zero_shot_cot" else "Analyze the final QUESTION using IRAC."
            check(dump_text.count(marker) == 1 and "RESPONSE_FORMAT" in dump_text and "PROVISION_MAP" in dump_text, "CLI prompt dump incomplete or misnamed.")
        if context == "retrieved":
            live_config = deepcopy(config)
            del live_config["saved_retrieval_path"]
            with tempfile.TemporaryDirectory(prefix="candidate-offline-guard-") as temporary:
                path = Path(temporary) / "invalid_live.yaml"
                path.write_text(yaml.safe_dump(live_config), encoding="utf-8")
                expect_value_error(lambda: offline_loop.run_until_complete(entry.main(argparse.Namespace(
                    config_path=str(path), saved_retrieval_smoke_test=False, dump_final_prompt=False))))

    check(not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules for prefix in FORBIDDEN), "Live dependencies loaded.")
    report = dict(status="PASS", method=args.method, engineering_prompt_pairs=len(checks), llm_calls=0,
                  live_retrieval_calls=0, external_network_calls=0,
                  direct_pre_change_regression_checked=bool(old_direct),
                  cli_prompt_dumps_checked=args.dump_prompts,
                  cot_pre_change_regression_checked=bool(old_cot),
                  instruction_only_difference=True, unchanged_schema_and_mapping=True,
                  forbidden_imports_absent=True, checks=checks)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

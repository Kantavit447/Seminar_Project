"""ตรวจ prompt/schema/feedback ของ Proposed กับร่าง IRAC engineering โดยปิด LLM และ network."""

import argparse
import asyncio
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dump-dir", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    candidate = (args.candidate_root or root).resolve()
    if Path.cwd().resolve() != root:
        raise ValueError("Run from the clean project root.")
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "tools/validation"))
    from validate_zero_shot_cot_offline import ENGINEERING, NoLiveImports, check

    # สร้าง event loop ก่อนปิด socket เพราะ Windows ใช้ socket ภายใน loop
    loop = asyncio.new_event_loop()
    attempts = {"network": 0, "llm_or_live_retrieval": 0}

    def no_network(*args, **kwargs):
        attempts["network"] += 1
        raise AssertionError("Network is forbidden in offline validation.")

    def no_generation(*args, **kwargs):
        attempts["llm_or_live_retrieval"] += 1
        raise AssertionError("LLM clients, generation and live retrieval are forbidden.")

    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    socket.create_connection = no_network
    sys.meta_path.insert(0, NoLiveImports())
    try:
        import yaml
        import openai
        import script.response_e2e as entry
        from lrg.prompting import PromptManager

        entry.init_llm = entry.init_retriever = no_generation
        entry.Ragger.rag = entry.Ragger.rag_multi = no_generation
        openai.OpenAI = openai.AsyncOpenAI = no_generation
        name = "lrg.prompting.proposed"
        module_path = candidate / "lrg/prompting/proposed.py"
        spec = importlib.util.spec_from_file_location(name, module_path)
        proposed = importlib.util.module_from_spec(spec)
        sys.modules[name] = proposed
        spec.loader.exec_module(proposed)
        templates = candidate / "lrg/prompting/templates"
        shared_system = (root / "lrg/prompting/templates/system_prompt_tax_v3_citation_id_enum.md").read_text(encoding="utf-8").strip()
        manager = PromptManager(prompt_version="v3", reasoning_method="irac",
                                citation_mode="provision_id", citation_constraint_mode="enum")
        report = dict(llm_calls=0, feedback_origin="synthetic_for_interface_only",
                      token_budget_verified=False, cases=[], rejections=[])

        def reject(label, action):
            try:
                action()
            except ValueError:
                report["rejections"].append(label)
            else:
                raise AssertionError(f"Expected rejection: {label}")

        def all_pass():
            return {"checks": [dict(axis=axis, verdict="PASS", reason="Offline fixture only.", issues=[])
                               for axis in proposed.AXES]}

        def failing(question, nodes, draft):
            feedback = all_pass()
            law = nodes[0].node if hasattr(nodes[0], "node") else nodes[0]
            feedback["checks"][2].update(verdict="FAIL", issues=[dict(
                draft_field="analysis", draft_quote=draft["analysis"][:40],
                problem="Synthetic interface test, not a legal judgment.",
                evidence=[dict(source="QUESTION", quote=question[:40]),
                          dict(source="P1", quote=law.text[:40])],
                revision="Synthetic test only: preserve the supplied draft.")])
            return feedback

        canary = "OFFLINE_REFERENCE_MUST_NOT_REACH_PROPOSED"
        first_inputs = None
        for context, prefix, window, result_folder in (
            ("golden", "golden_qwen", "16384", "golden_irac_citation_id_enum_engineering_10_ctx16384/chunk-golden-no-ref-qwen"),
            ("retrieved", "section_based_rag_qwen", "32768", "section_based_irac_citation_id_enum_engineering_10_ctx32768/chunk-human-finetuned-bge-m3-no-ref-qwen"),
        ):
            config_path = root / f"config/local/response/{prefix}_irac_v3_citation_id_enum_engineering_10_ctx{window}.yaml"
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            check(config["data_config"]["chunk"]["tax_data_path"] == "data_splits/tax_engineering_10.csv", "Engineering only.")
            directory = root / "results/current/common_interface_v3" / result_folder
            records = json.loads((directory / "tax_response.json").read_text(encoding="utf-8"))
            status = json.loads((directory / "tax_run_status.json").read_text(encoding="utf-8"))
            by_source = {entry.canonical_idx(record["source_idx"]): record for record in records}
            states = {entry.canonical_idx(item["source_idx"]): item for item in status["items"]}
            check(len(by_source) == len(records), "Duplicate draft source ID.")
            check(set(states) == set(ENGINEERING) and len(states) == len(status["items"]), "Wrong status IDs.")
            check(set(by_source) == {key for key, item in states.items() if item["status"] == "success"}, "Draft/status mismatch.")
            dataset = entry.EvalDataset(**config["data_config"]["chunk"])
            for column in dataset.tax_df.columns:
                if "answer" in column.lower():
                    dataset.tax_df[column] = canary
            augmenter = entry.NitiLinkAugmenter(dataset=dataset, config=entry.NitiLinkAugmenterConfig(
                **config["augmenter_config"]["no-ref"], strat_name=dataset.strat_name))
            retriever = entry.init_saved_retriever(dataset, config["saved_retrieval_path"]) if context == "retrieved" else None
            if context == "retrieved":
                dataset.tax_df["relevant_laws"] = canary
            ragger = entry.Ragger(dataset=dataset, prompt_manager=manager,
                llm=entry.PromptDumpLLM(config["llm_config"]["qwen"]["model"]),
                augmenter=augmenter, retriever=retriever, context_source=context)
            check([entry.canonical_idx(value) for value in dataset.tax_df["source_idx"]] == ENGINEERING, "Engineering order changed.")
            for runtime, (_, row) in enumerate(dataset.tax_df.iterrows()):
                source = entry.canonical_idx(row["source_idx"])
                check(entry.canonical_idx(states[source]["runtime_idx"]) == f"{runtime:04d}", "Status runtime mismatch.")
                if source not in by_source:
                    check(states[source]["status"] == "generation_failure", "Missing draft is not a known failure.")
                    report["cases"].append(dict(context=context, source_idx=source, status="draft_failed", prompts=0))
                    continue
                record = by_source[source]
                check(entry.canonical_idx(record["idx"]) == f"{runtime:04d}", "Draft runtime mismatch.")
                baseline, _, nodes, _ = ragger.get_prompt_structure(
                    query=row["question"], dataset_name="tax",
                    relevant_laws=row["relevant_laws"] if context == "golden" else None)
                mapping = entry.Ragger.build_provision_map(nodes)
                check(mapping == record["provision_map"], "P-ID mapping no longer matches saved draft.")
                check([item["retrieved_node_id"] for item in mapping] == record["retrieved_ids"], "Context IDs/order changed.")
                if context == "retrieved":
                    check(len(nodes) == 10, "Expected saved Top 10.")
                else:
                    check(not ragger.resolve_gold_provisions(row["relevant_laws"])[1], "Golden unresolved.")
                record["reference_answer"] = record["relevant_laws"] = canary
                draft = deepcopy(record["model_content"])
                before_draft = deepcopy(draft)
                inputs = dict(question=row["question"], nodes=nodes, draft=draft)
                feedback = failing(**inputs)
                before_feedback = deepcopy(feedback)
                if first_inputs is None:
                    first_inputs = inputs
                verdict = proposed.validate_verifier_feedback(feedback, **inputs)
                check(verdict == feedback, "Feedback validation altered text.")
                sizes = {}
                for stage in ("verifier", "corrector"):
                    prompt, structure = proposed.build_proposed_prompt(stage, **inputs,
                        feedback=feedback if stage == "corrector" else None, template_dir=templates)
                    messages = prompt["messages"]
                    check([message["role"] for message in messages] == ["system", "user"], "Unexpected examples or roles.")
                    expected_context = baseline["messages"][-1]["content"]
                    prefix_text = expected_context + "\n\n[DRAFT_JSON]\n"
                    check(messages[-1]["content"].startswith(prefix_text), "Original question/context text changed.")
                    expected_tail = json.dumps(draft, ensure_ascii=False, indent=2) + "\n[/DRAFT_JSON]"
                    if stage == "corrector":
                        expected_tail += "\n\n[FEEDBACK_JSON]\n" + json.dumps(feedback, ensure_ascii=False, indent=2) + "\n[/FEEDBACK_JSON]"
                        check(messages[0]["content"].startswith(shared_system + "\n\n"), "Shared answer instructions changed.")
                        original = manager.build_citation_id_enum_structure([item["provision_id"] for item in mapping])
                        check(structure.model_json_schema() == original.model_json_schema(), "Corrector output schema changed.")
                        mapped, invalid, _, _ = entry.Ragger.map_citation_ids(structure.model_validate(draft).model_dump(), mapping)
                        check(not invalid and mapped == record["content"], "Citation mapping changed.")
                    else:
                        structure.model_validate(feedback)
                    check(messages[-1]["content"] == prefix_text + expected_tail, "Unexpected metadata in model input.")
                    check(canary not in json.dumps(prompt, ensure_ascii=False), "Reference/gold metadata leaked.")
                    sizes[stage + "_characters"] = sum(len(message["content"]) for message in messages)
                    if args.dump_dir:
                        args.dump_dir.mkdir(parents=True, exist_ok=True)
                        dump = args.dump_dir / f"{context}_source_{source}_{stage}_offline.txt"
                        header = "ตัวอย่างประกอบ prompt แบบ offline; ไม่ได้เรียกโมเดล\nFeedback ของ corrector เป็นข้อมูลสมมติสำหรับตรวจ interface ไม่ใช่คำวินิจฉัยจริง\nจำนวนอักษรไม่ใช่จำนวน tokens และไม่ยืนยันว่า context window เพียงพอ\n\n"
                        dump.write_text(header + "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in messages)
                            + "\n\n[response_schema]\n" + json.dumps(structure.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
                check(draft == before_draft and feedback == before_feedback, "Prompt building mutated draft or feedback.")
                report["cases"].append(dict(context=context, source_idx=source, status="PASS", prompts=2,
                    context_sha256=hashlib.sha256(expected_context.encode("utf-8")).hexdigest(), **sizes))

        inputs = first_inputs
        passed = all_pass()
        check(proposed.validate_verifier_feedback(passed, **inputs) == passed, "PASS rejected.")
        reject("PASS cannot enter corrector", lambda: proposed.build_proposed_prompt("corrector", **inputs, feedback=passed, template_dir=templates))
        uncertain = all_pass()
        uncertain["checks"][0]["verdict"] = "UNCERTAIN"
        check(proposed.validate_verifier_feedback(uncertain, **inputs) == uncertain, "UNCERTAIN rejected.")
        reject("UNCERTAIN alone cannot enter corrector", lambda: proposed.build_proposed_prompt("corrector", **inputs, feedback=uncertain, template_dir=templates))
        valid = failing(**inputs)
        mixed = deepcopy(valid)
        mixed["checks"][0]["verdict"] = "UNCERTAIN"
        proposed.build_proposed_prompt("corrector", **inputs, feedback=mixed, template_dir=templates)
        omission = deepcopy(valid)
        omission["checks"][2]["issues"][0]["draft_quote"] = None
        omission["checks"][2]["issues"][0]["problem"] = "Synthetic omission fixture only; no draft passage to quote."
        proposed.validate_verifier_feedback(omission, **inputs)
        draft_evidence = deepcopy(valid)
        draft_evidence["checks"][2]["issues"][0]["evidence"] = [dict(source="DRAFT_ANSWER", quote=inputs["draft"]["answer"][:30])]
        proposed.validate_verifier_feedback(draft_evidence, **inputs)

        mutations = [
            ("missing axis", lambda f: f["checks"].pop()),
            ("duplicate axis", lambda f: f["checks"][1].update(axis="I")),
            ("out of order axes", lambda f: f["checks"].reverse()),
            ("invalid verdict", lambda f: f["checks"][0].update(verdict="MAYBE")),
            ("FAIL without issues", lambda f: f["checks"][2].update(issues=[])),
            ("PASS with issues", lambda f: f["checks"][2].update(verdict="PASS")),
            ("blank reason", lambda f: f["checks"][0].update(reason=" ")),
            ("unknown evidence P-ID", lambda f: f["checks"][2]["issues"][0]["evidence"][0].update(source="P999999")),
            ("wrong evidence source", lambda f: f["checks"][2]["issues"][0]["evidence"][0].update(source="DRAFT_ANSWER", quote=inputs["question"])),
            ("invented quote", lambda f: f["checks"][2]["issues"][0]["evidence"][0].update(quote="FABRICATED_QUOTE_7e831d")),
            ("blank quote", lambda f: f["checks"][2]["issues"][0]["evidence"][0].update(quote=" ")),
            ("invented draft quote", lambda f: f["checks"][2]["issues"][0].update(draft_quote="FABRICATED_DRAFT_7e831d")),
            ("missing evidence", lambda f: f["checks"][2]["issues"][0].update(evidence=[])),
            ("blank revision", lambda f: f["checks"][2]["issues"][0].update(revision=" ")),
            ("extra top-level score", lambda f: f.update(coverage=100)),
            ("extra issue field", lambda f: f["checks"][2]["issues"][0].update(reference_answer=canary)),
        ]
        for label, mutate in mutations:
            bad = deepcopy(valid)
            mutate(bad)
            reject(label, lambda: proposed.validate_verifier_feedback(bad, **inputs))
        reject("truncated JSON", lambda: json.loads(json.dumps(valid)[:-2]))
        reject("missing draft", lambda: proposed.build_proposed_prompt("verifier", **dict(inputs, draft=None), template_dir=templates))
        reject("metadata in draft", lambda: proposed.build_proposed_prompt("verifier", **dict(inputs, draft=dict(inputs["draft"], reference_answer=canary)), template_dir=templates))
        reject("blank answer", lambda: proposed.build_proposed_prompt("verifier", **dict(inputs, draft=dict(inputs["draft"], answer=" ")), template_dir=templates))
        reject("invalid draft citation", lambda: proposed.build_proposed_prompt("verifier", **dict(inputs, draft=dict(inputs["draft"], citation_ids=["P999999"])), template_dir=templates))
        reject("feedback supplied to verifier", lambda: proposed.build_proposed_prompt("verifier", **inputs, feedback=valid, template_dir=templates))
        reject("unknown stage", lambda: proposed.build_proposed_prompt("rewrite", **inputs, template_dir=templates))
        duplicate = dict(inputs["draft"], citation_ids=["P1", "P1"])
        _, answer_schema = proposed.build_proposed_prompt("corrector", **dict(inputs, draft=duplicate), feedback=valid, template_dir=templates)
        mapped, invalid, repeated, errors = entry.Ragger.map_citation_ids(answer_schema.model_validate(duplicate).model_dump(), entry.Ragger.build_provision_map(inputs["nodes"]))
        check(not invalid and repeated == ["P1"] and errors == ["duplicate_provision_ids_preserve_first"], "Existing duplicate policy changed.")
        check(len(mapped["citations"]) == 1, "Duplicate mapping changed.")
        reject("extra corrector output field", lambda: answer_schema.model_validate(dict(inputs["draft"], verdict="PASS")))
        reject("out-of-context corrector citation", lambda: answer_schema.model_validate(dict(inputs["draft"], citation_ids=["P999999"])))
        check(not any(attempts.values()), "Offline protection was triggered.")
        report.update(protected_attempts=attempts, engineering_items=len(report["cases"]),
            valid_drafts=sum(item["status"] == "PASS" for item in report["cases"]),
            prompt_count=sum(item["prompts"] for item in report["cases"]),
            rejected_cases=len(report["rejections"]), status="PASS")
        report["candidate_hashes"] = {str(path.relative_to(candidate)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (module_path, Path(__file__).resolve(), templates / "proposed-tax-v1/verifier.md", templates / "proposed-tax-v1/corrector.md")}
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: report[key] for key in ("status", "engineering_items", "valid_drafts", "prompt_count", "rejected_cases", "llm_calls", "token_budget_verified")}, ensure_ascii=False))
    finally:
        loop.close()


if __name__ == "__main__":
    main()

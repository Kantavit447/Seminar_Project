"""รัน IRAC → verifier → conditional corrector ด้วยร่างและ context ที่บันทึกไว้."""

import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import yaml

from script.response_e2e import (EvalDataset, NitiLinkAugmenter,
    NitiLinkAugmenterConfig, PromptDumpLLM, PromptManager, Ragger,
    canonical_idx, init_saved_retriever, write_response_results)
from lrg.prompting.proposed import build_proposed_prompt, validate_verifier_feedback, _prepare
from lrg.prompting.proposed_v5 import selected_ids
from lrg.prompting.proposed_evidence import build_evidence_index, resolve_evidence


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_WINDOWS = {"qwen2.5-16k:7b": 16384, "qwen2.5-32k:7b": 32768}
FINAL_STATES = {"draft_failed", "kept_pass", "kept_uncertain", "corrected",
                "verifier_failed", "correction_failed"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def tokenizer_file(path=None):
    if path:
        found = Path(path).expanduser().resolve()
        if not found.is_file():
            raise FileNotFoundError(found)
        return found
    cache = Path.home() / ".cache/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots"
    matches = list(cache.glob("*/tokenizer.json"))
    if len(matches) != 1:
        raise ValueError("Specify --tokenizer-path for one local Qwen2.5-7B-Instruct tokenizer.json")
    return matches[0]


class Budget:
    def __init__(self, path, window, margin=512):
        try:
            from tokenizers import Tokenizer
        except ImportError as error:
            raise RuntimeError("Install standalone tokenizers==0.21.4 in the clean venv; transformers is not needed.") from error
        self.tokenizer = Tokenizer.from_file(str(path))
        self.window = window
        self.margin = margin

    def check(self, prompt, structure, output_tokens):
        messages = prompt["messages"]
        if [item["role"] for item in messages] != ["system", "user"]:
            raise ValueError("Expected Qwen system/user messages.")
        chat = "".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages)
        chat += "<|im_start|>assistant\n"
        # The backend may add structured-output instructions. Reserve the full schema
        # plus an additional fixed margin; actual prompt usage is recorded afterwards.
        schema = json.dumps(structure.model_json_schema(), ensure_ascii=False, separators=(",", ":"))
        message_tokens = len(self.tokenizer.encode(chat, add_special_tokens=False).ids)
        schema_tokens = len(self.tokenizer.encode(schema, add_special_tokens=False).ids)
        total = message_tokens + schema_tokens + output_tokens + self.margin
        record = dict(message_tokens=message_tokens, schema_tokens=schema_tokens,
                      output_limit=output_tokens, margin=self.margin,
                      required=total, context_window=self.window)
        if total > self.window:
            raise ValueError(f"Input budget exceeded: {record}")
        return record


def load_inputs(settings):
    version = settings.get("proposed_prompt_version", "proposed-tax-v1")
    baseline_path = ROOT / settings["irac_config_path"]
    baseline = yaml.safe_load(baseline_path.read_text(encoding="utf-8"))
    context = baseline.get("context_source", "retrieved")
    if context not in ("golden", "retrieved") or (context == "retrieved" and not baseline.get("saved_retrieval_path")):
        raise ValueError("Only Golden and Saved Retrieved contexts are supported.")
    if baseline["reasoning_method"] != "irac" or baseline["citation_constraint_mode"] != "enum":
        raise ValueError("Expected unchanged IRAC citation-enum baseline.")
    model = baseline["llm_config"]["qwen"]["model"]
    if model not in CONTEXT_WINDOWS or baseline["data_config"]["chunk"]["tax_data_path"] != "data_splits/tax_engineering_10.csv":
        raise ValueError("Unexpected model or dataset; this runner is for the current engineering 10 only.")
    source = ROOT / baseline["output_path"] / ("chunk-golden-no-ref-qwen" if context == "golden" else "chunk-human-finetuned-bge-m3-no-ref-qwen")
    responses_path, status_path = source / "tax_response.json", source / "tax_run_status.json"
    records = json.loads(responses_path.read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8"))
    by_source = {canonical_idx(item["source_idx"]): item for item in records}
    states = {canonical_idx(item["source_idx"]): item for item in status["items"]}
    if len(by_source) != len(records) or len(states) != len(status["items"]) or len(states) != 10:
        raise ValueError("Duplicate/missing IRAC source IDs.")
    if set(by_source) != {key for key, item in states.items() if item["status"] == "success"}:
        raise ValueError("IRAC results and run status disagree.")
    if any(item["status"] not in ("success", "generation_failure") for item in states.values()):
        raise ValueError("IRAC has pending or unsupported states.")
    dataset = EvalDataset(**baseline["data_config"]["chunk"])
    augmenter = NitiLinkAugmenter(dataset=dataset, config=NitiLinkAugmenterConfig(
        **baseline["augmenter_config"]["no-ref"], strat_name=dataset.strat_name))
    retriever = init_saved_retriever(dataset, baseline["saved_retrieval_path"]) if context == "retrieved" else None
    manager = PromptManager(prompt_version="v3", reasoning_method="irac",
                            citation_mode="provision_id", citation_constraint_mode="enum")
    ragger = Ragger(dataset=dataset, prompt_manager=manager,
                    llm=PromptDumpLLM(model), augmenter=augmenter,
                    retriever=retriever, context_source=context)
    rows = []
    for runtime, (_, row) in enumerate(dataset.tax_df.iterrows()):
        sid, rid = canonical_idx(row["source_idx"]), f"{runtime:04d}"
        if canonical_idx(row["idx"]) != rid or canonical_idx(states[sid]["runtime_idx"]) != rid:
            raise ValueError("Dataset and IRAC status IDs disagree.")
        base = by_source.get(sid)
        if base is None:
            rows.append(dict(source_idx=sid, runtime_idx=rid, question=row["question"],
                             draft=None, baseline_status=states[sid]))
            continue
        if canonical_idx(base["idx"]) != rid:
            raise ValueError(f"IRAC runtime mismatch: {sid}")
        _, _, nodes, _ = ragger.get_prompt_structure(query=row["question"], dataset_name="tax",
            relevant_laws=row["relevant_laws"] if context == "golden" else None)
        mapping = Ragger.build_provision_map(nodes)
        if mapping != base["provision_map"] or [m["retrieved_node_id"] for m in mapping] != base["retrieved_ids"]:
            raise ValueError(f"Context/P-ID mismatch: {sid}")
        if context == "golden" and ragger.resolve_gold_provisions(row["relevant_laws"])[1]:
            raise ValueError(f"Unresolved Golden provision: {sid}")
        if context == "retrieved" and len(nodes) != 10:
            raise ValueError(f"Saved Retrieved is not Top 10: {sid}")
        draft = deepcopy(base["model_content"])
        prompt, structure = build_proposed_prompt("verifier", question=row["question"], nodes=nodes, draft=draft, version=version)
        rows.append(dict(source_idx=sid, runtime_idx=rid, question=row["question"],
                         draft=draft, base=base, nodes=nodes, mapping=mapping,
                         verifier_prompt=prompt, verifier_structure=structure))
        if version in ("proposed-tax-v4", "proposed-tax-v5", "proposed-tax-v6"):
            rows[-1]["evidence_index"] = build_evidence_index(_prepare(row["question"], nodes, draft)[3])
    if {r["source_idx"] for r in rows} != set(states) or len(rows) != len(states):
        raise ValueError("Dataset and IRAC status source IDs disagree.")
    files = [baseline_path, responses_path, status_path,
             ROOT / baseline["data_config"]["chunk"]["tax_data_path"],
             ROOT / baseline["data_config"]["chunk"]["node_path"],
             ROOT / f"lrg/prompting/templates/{version}/verifier.md",
             ROOT / f"lrg/prompting/templates/{version if version in ('proposed-tax-v4', 'proposed-tax-v5', 'proposed-tax-v6') else 'proposed-tax-v1'}/corrector.md",
             ROOT / "lrg/prompting/templates/system_prompt_tax_v3_citation_id_enum.md"]
    if context == "retrieved":
        files.append(ROOT / baseline["saved_retrieval_path"])
    if version in ("proposed-tax-v4", "proposed-tax-v5", "proposed-tax-v6"):
        files.extend([ROOT / "lrg/prompting/proposed_evidence.py", ROOT / "lrg/prompting/proposed.py"])
    if version in ("proposed-tax-v5", "proposed-tax-v6"):
        files.append(ROOT / "lrg/prompting/proposed_v5.py")
    provenance = {str(path.relative_to(ROOT)): digest(path) for path in files}
    return baseline, context, model, rows, provenance


def final_response(base, model_content, nodes, stage_result=None):
    result = deepcopy(base)
    mapped, invalid, duplicates, errors = Ragger.map_citation_ids(model_content, base["provision_map"])
    if invalid:
        raise ValueError("Corrector used a P-ID outside the original enum.")
    errors += Ragger.validate_citations(mapped, nodes)
    result.update(content=mapped, model_content=deepcopy(model_content),
                  model_citation_ids=deepcopy(model_content["citation_ids"]),
                  invalid_provision_ids=invalid, duplicate_provision_ids=duplicates,
                  citation_validation_errors=errors)
    if stage_result is not None:
        result["usage"] = stage_result.get("usage")
        result["llm_time"] = stage_result.get("llm_time")
        result["tries"] = 1
    return result


def write_reports(folder, trace, rows):
    by_id = {item["source_idx"]: item for item in rows}
    results = []
    lines = ["# ผล Proposed", "", "ผลนี้ใช้ร่าง IRAC ที่บันทึกไว้ ไม่ใช่คะแนนการประเมิน", ""]
    for item in trace["items"]:
        sid = item["source_idx"]
        lines.extend([f"## source {sid} / runtime {item['runtime_idx']}", "",
                      f"สถานะ: `{item['status']}` | คำตอบสุดท้าย: `{item.get('final_source', 'ยังไม่มี')}`", ""])
        if item.get("draft"):
            lines.extend(["### การวิเคราะห์ในร่าง IRAC", "", item["draft"]["analysis"], "",
                          "### คำตอบในร่าง IRAC", "", item["draft"]["answer"], "",
                          f"P-ID ในร่าง: {', '.join(item['draft']['citation_ids']) or 'ไม่มี'}", ""])
        if item.get("feedback"):
            lines.extend(["### ผลตรวจ", ""])
            for check in item["feedback"]["checks"]:
                lines.append(f"- {check['axis']}: {check['verdict']} — {check['reason']}")
                if check.get("assessment"):
                    for key, label in (("claim", "ข้อกล่าวอ้างในร่าง"), ("criterion", "เงื่อนไขที่ตรวจ"), ("comparison", "ผลเทียบหลักฐาน")):
                        lines.append(f"  - {label}: {check['assessment'][key]}")
                for evidence in item.get("resolved_evidence", {}).get(check["axis"], []):
                    lines.append(f"  - หลักฐาน {evidence['evidence_id']} ({evidence['source']}):")
                    lines.append("\n> " + evidence['quote'].replace("\n", "\n> ") + "\n")
                for evidence in check.get("evidence", []):
                    quote = evidence['quote'].replace("\n", " ")
                    lines.append(f"  - หลักฐาน {evidence['source']}: {quote}")
                if check.get("revision"):
                    lines.append(f"  - คำแนะนำแก้: {check['revision']}")
                for issue in check.get("issues", []):
                    lines.append(f"  - {issue['problem']} → {issue['revision']}")
            lines.append("")
        if item.get("final_content"):
            lines.extend(["### การวิเคราะห์สุดท้าย", "", item["final_content"]["analysis"], "",
                          "### คำตอบสุดท้าย", "", item["final_content"]["answer"], "",
                          f"P-ID สุดท้าย: {', '.join(item['final_content']['citation_ids']) or 'ไม่มี'}", "",
                          f"เปลี่ยนจากร่าง: {item.get('changed')}", ""])
        if item.get("error"):
            lines.extend(["### ข้อผิดพลาด", "", str(item["error"]), ""])
        if item.get("budget") or item.get("usage"):
            lines.extend(["### งบและการใช้ tokens", "", "```json",
                          json.dumps({"budget": item.get("budget"), "usage": item.get("usage")}, ensure_ascii=False, indent=2),
                          "```", ""])
        if item["status"] in FINAL_STATES - {"draft_failed"}:
            row = by_id[sid]
            result = final_response(row["base"], item["final_content"], row["nodes"],
                                    item.get("corrector_result") if item["status"] == "corrected" else None)
            results.append(result)
    atomic_json(folder / "tax_response.json", results)
    questions = {item["runtime_idx"]: by_id[item["source_idx"]]["question"] for item in trace["items"]}
    write_response_results(folder / "tax_response.json", results, questions)
    (folder / "tax_proposed_trace.md").write_text("\n".join(lines), encoding="utf-8")
    atomic_json(folder / "tax_run_status.json", {"total": len(trace["items"]),
        "counts": {state: sum(i["status"] == state for i in trace["items"])
                   for state in sorted({i["status"] for i in trace["items"]})},
        "items": [{"runtime_idx": i["runtime_idx"], "source_idx": i["source_idx"], "status": i["status"]}
                  for i in trace["items"]]})


async def execute(settings, *, source_idx=None, dry_run=False, tokenizer_path=None):
    version = settings.get("proposed_prompt_version", "proposed-tax-v1")
    baseline, context, model, rows, provenance = load_inputs(settings)
    path = tokenizer_file(tokenizer_path)
    budget = Budget(path, CONTEXT_WINDOWS[model], settings.get("safety_margin_tokens", 512))
    identity = dict(context=context, model=model, baseline_files=provenance,
                    tokenizer_sha256=digest(path), settings=settings)
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    folder = ROOT / settings["output_path"]
    if source_idx:
        source_idx = canonical_idx(source_idx)
        if source_idx not in {item["source_idx"] for item in rows}:
            raise ValueError("Source ID is outside engineering 10.")
        folder = folder / "diagnostics" / f"source_{source_idx}"
    trace_path = folder / "tax_proposed_trace.json"
    if trace_path.is_file():
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        if trace.get("fingerprint") != fingerprint or [i["source_idx"] for i in trace["items"]] != [r["source_idx"] for r in rows]:
            raise ValueError("Proposed checkpoint fingerprint/IDs changed; inspect before resuming.")
    else:
        existing = {path.name for path in folder.iterdir()} if folder.exists() else set()
        if existing - ({"diagnostics"} if source_idx is None else set()):
            raise ValueError("Output directory already contains files without a Proposed trace.")
        trace = dict(fingerprint=fingerprint, identity=identity, items=[dict(
            source_idx=row["source_idx"], runtime_idx=row["runtime_idx"],
            status="draft_failed" if row["draft"] is None else "pending",
            draft=deepcopy(row["draft"]), draft_sha256=(hashlib.sha256(json.dumps(row["draft"],
                ensure_ascii=False, sort_keys=True).encode()).hexdigest() if row["draft"] else None),
            context_ids=[m["retrieved_node_id"] for m in row.get("mapping", [])],
            provision_map=row.get("mapping"), baseline_status=row.get("baseline_status")) for row in rows])
    selected = [row for row in rows if not source_idx or row["source_idx"] == source_idx]
    for row in selected:
        item = next(i for i in trace["items"] if i["source_idx"] == row["source_idx"])
        if item["status"] == "in_flight":
            raise ValueError(f"Previous request outcome unknown for source {row['source_idx']}; do not retry automatically.")
        if row["draft"] is None or item["status"] in FINAL_STATES:
            continue
        if item["status"] not in ("pending", "verified_fail_pending_correction", "input_blocked"):
            raise ValueError(f"Unexpected checkpoint state: {item['status']}")
        if item["status"] == "pending" or (item["status"] == "input_blocked" and item.get("blocked_stage") == "verifier"):
            prompt, structure, stage, limit = row["verifier_prompt"], row["verifier_structure"], "verifier", settings["verifier_max_tokens"]
        else:
            prompt, structure = build_proposed_prompt("corrector", question=row["question"], nodes=row["nodes"],
                draft=row["draft"], feedback=item["feedback"], version=version)
            stage, limit = "corrector", settings["corrector_max_tokens"]
        try:
            item.setdefault("budget", {})[stage] = budget.check(prompt, structure, limit)
        except ValueError as error:
            item.update(status="input_blocked", blocked_stage=stage, error=str(error))
            if not dry_run:
                atomic_json(trace_path, trace)
                write_reports(folder, trace, rows)
            print(f"source={row['source_idx']} stage={stage} input_blocked: {error}")
            return trace
        if dry_run:
            print(f"source={row['source_idx']} stage={stage} budget={item['budget'][stage]}")
            continue
        from lrg.llm import init_llm  # no client during input validation or dry run
        model_settings = dict(baseline["llm_config"]["qwen"], max_tokens=limit)
        llm = init_llm(model_settings)

        async def call(name, current_prompt, current_structure, current_limit):
            item.update(status="in_flight", in_flight_stage=name, error=None)
            atomic_json(trace_path, trace)
            try:
                response = await llm.complete(**current_prompt, structure=current_structure,
                                              diagnostic={"save_raw_on_parse_failure": True})
                item.setdefault("usage", {})[name] = response.get("usage")
                item.setdefault("llm_seconds", {})[name] = response.get("llm_time")
                return response
            except Exception as error:
                item.setdefault("failure", {})[name] = getattr(error, "diagnostic_record", None)
                item.update(status="verifier_failed" if name == "verifier" else "correction_failed",
                            error=f"{type(error).__name__}: {error}", final_source="irac_draft",
                            final_content=deepcopy(row["draft"]), changed=False)
                atomic_json(trace_path, trace)
                write_reports(folder, trace, rows)
                return None

        if stage == "verifier":
            response = await call("verifier", prompt, structure, limit)
            if response is None:
                continue
            try:
                feedback = validate_verifier_feedback(response["content"], question=row["question"],
                                                       nodes=row["nodes"], draft=row["draft"], version=version)
            except (ValueError, TypeError, KeyError) as error:
                item.update(status="verifier_failed", error=f"Invalid verifier feedback: {error}",
                            raw_feedback=response["content"], final_source="irac_draft",
                            final_content=deepcopy(row["draft"]), changed=False)
                atomic_json(trace_path, trace)
                write_reports(folder, trace, rows)
                continue
            item["feedback"] = feedback
            if version in ("proposed-tax-v4", "proposed-tax-v5", "proposed-tax-v6"):
                item["evidence_index"] = row["evidence_index"]
                item["resolved_evidence"] = resolve_evidence({"checks": [dict(check, evidence_ids=selected_ids(check)) for check in feedback["checks"]]}, row["evidence_index"])
            verdicts = [check["verdict"] for check in feedback["checks"]]
            if "FAIL" not in verdicts:
                item.update(status="kept_uncertain" if "UNCERTAIN" in verdicts else "kept_pass",
                            final_source="irac_draft", final_content=deepcopy(row["draft"]), changed=False)
                atomic_json(trace_path, trace)
                write_reports(folder, trace, rows)
                continue
            item["status"] = "verified_fail_pending_correction"
            atomic_json(trace_path, trace)
            prompt, structure = build_proposed_prompt("corrector", question=row["question"], nodes=row["nodes"],
                                                      draft=row["draft"], feedback=feedback, version=version)
            try:
                item["budget"]["corrector"] = budget.check(prompt, structure, settings["corrector_max_tokens"])
            except ValueError as error:
                item.update(status="input_blocked", blocked_stage="corrector", error=str(error))
                atomic_json(trace_path, trace)
                write_reports(folder, trace, rows)
                print(f"source={row['source_idx']} stage=corrector input_blocked: {error}")
                return trace
        llm.config["max_tokens"] = settings["corrector_max_tokens"]
        response = await call("corrector", prompt, structure, settings["corrector_max_tokens"])
        if response is None:
            continue
        try:
            revised = structure.model_validate(response["content"], strict=True).model_dump()
            if not revised["analysis"].strip() or not revised["answer"].strip():
                raise ValueError("Empty correction.")
            candidate = final_response(row["base"], revised, row["nodes"], response)
            if candidate["invalid_provision_ids"]:
                raise ValueError("Invalid citation ID.")
        except (ValueError, TypeError, KeyError) as error:
            item.update(status="correction_failed", error=f"Invalid corrector output: {error}",
                        raw_correction=response["content"], final_source="irac_draft",
                        final_content=deepcopy(row["draft"]), changed=False)
        else:
            item.update(status="corrected", corrected=deepcopy(revised),
                        corrector_result={"usage": response.get("usage"), "llm_time": response.get("llm_time")},
                        final_source="corrector", final_content=deepcopy(revised),
                        changed=revised != row["draft"])
        atomic_json(trace_path, trace)
        write_reports(folder, trace, rows)
        print(f"source={row['source_idx']} status={item['status']}")
    if not dry_run:
        atomic_json(trace_path, trace)
        write_reports(folder, trace, rows)
    if dry_run:
        print("dry_run=true llm_calls=0")
    else:
        counts = {state: sum(i["status"] == state for i in trace["items"])
                  for state in sorted({i["status"] for i in trace["items"]})}
        print(f"proposed_status={counts}")
        print(f"output_path={folder}")
    return trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--source-idx")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and token budgets without LLM calls or output files")
    parser.add_argument("--tokenizer-path")
    args = parser.parse_args()
    if Path.cwd().resolve() != ROOT:
        parser.error("Run from the clean project root.")
    settings = yaml.safe_load(Path(args.config_path).read_text(encoding="utf-8"))
    asyncio.run(execute(settings, source_idx=args.source_idx, dry_run=args.dry_run,
                        tokenizer_path=args.tokenizer_path))


if __name__ == "__main__":
    main()

"""Audit Direct v3 citation-by-ID records without calling models or retrieval."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_FINAL_KEYS = {"analysis", "answer", "citations"}
EXPECTED_MODEL_KEYS = {"analysis", "answer", "citation_ids"}
SCHEMA_ERROR_CODES = {
    "response_content_not_json_object",
    "top_level_keys",
    "citations_not_list",
    "citation_schema",
    "citation_non_string",
    "model_schema_invalid",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--engineering-data", type=Path, default=Path("data_splits/tax_engineering_10.csv"))
    parser.add_argument("--saved-retrieval", type=Path, default=Path("results/current/retrieval_evaluation/section_based_no_ref/retrieval_results.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def canonical_idx(value: Any) -> str:
    return f"{int(str(value).strip()):04d}"


def final_errors(content: Any, allowed_pairs: set[tuple[str, str]]) -> list[str]:
    errors: list[str] = []
    if not isinstance(content, dict):
        return ["response_content_not_json_object"]
    if set(content) != EXPECTED_FINAL_KEYS:
        errors.append("top_level_keys")
    if not isinstance(content.get("answer"), str) or not content["answer"].strip():
        errors.append("empty_answer")
    citations = content.get("citations")
    if not isinstance(citations, list):
        return errors + ["citations_not_list"]
    for citation in citations:
        if not isinstance(citation, dict) or set(citation) != {"law", "section"}:
            errors.append("citation_schema")
            continue
        law, section = citation.get("law"), citation.get("section")
        if not isinstance(law, str) or not isinstance(section, str):
            errors.append("citation_non_string")
            continue
        if re.search(r"มาตรา|<[^>]+>|\n", law):
            errors.append("law_includes_section")
        if re.search(r"มาตรา|<[^>]+>|\n", section) or len(section.strip()) > 64 or len(section.split()) > 3:
            errors.append("section_is_long_text")
        if (law, section) not in allowed_pairs:
            errors.append("final_citation_not_in_context")
    return errors


def main() -> None:
    args = parse_args()
    responses = json.loads(args.responses.read_text(encoding="utf-8"))
    with args.engineering_data.open(encoding="utf-8-sig", newline="") as handle:
        engineering_rows = list(csv.DictReader(handle))
    if len(engineering_rows) != 10:
        raise ValueError(f"Expected 10 engineering rows, found {len(engineering_rows)}.")
    uses_retrieved_context = any(item.get("context_source", "retrieved") != "golden" for item in responses)
    saved_by_source = {}
    if uses_retrieved_context:
        saved = json.loads(args.saved_retrieval.read_text(encoding="utf-8"))
        saved_by_source = {canonical_idx(item["idx"]): item for item in saved}
        if len(saved_by_source) != 50:
            raise ValueError("Saved retrieval must have 50 unique entries.")

    totals: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for response in responses:
        runtime_idx = canonical_idx(response.get("idx"))
        if int(runtime_idx) >= len(engineering_rows):
            raise ValueError(f"Response idx {runtime_idx} is outside the engineering dataset.")
        source_idx = canonical_idx(engineering_rows[int(runtime_idx)]["source_idx"])
        context_source = response.get("context_source", "retrieved")
        if context_source == "golden":
            context_node_ids = response.get("gold_node_ids", response.get("gold_provision_ids", []))
            unresolved_gold = response.get("unresolved_gold_provisions", [])
            unresolved_count = len(unresolved_gold) if isinstance(unresolved_gold, list) else int(bool(unresolved_gold))
            context_ids_match = response.get("retrieved_ids") == context_node_ids
        else:
            context_node_ids = saved_by_source[source_idx]["retrieved_ids"]
            unresolved_gold = []
            unresolved_count = 0
            context_ids_match = response.get("retrieved_ids") == context_node_ids
        allowed_pairs = {tuple(node_id.rsplit("-", 1)) for node_id in context_node_ids}
        provision_map = response.get("provision_map")
        expected_map = [
            {"provision_id": f"P{rank}", "law": law, "section": section, "retrieved_node_id": node_id}
            for rank, node_id in enumerate(context_node_ids, start=1)
            for law, section in [node_id.rsplit("-", 1)]
        ]
        mapping_failure = provision_map != expected_map
        model_content = response.get("model_content")
        model_ids = response.get("model_citation_ids")
        model_schema_invalid = (
            not isinstance(model_content, dict)
            or set(model_content) != EXPECTED_MODEL_KEYS
            or not isinstance(model_ids, list)
            or model_content.get("citation_ids") != model_ids
        )
        invalid_ids = response.get("invalid_provision_ids", [])
        duplicate_ids = response.get("duplicate_provision_ids", [])
        errors = final_errors(response.get("content"), allowed_pairs)
        if mapping_failure:
            errors.append("mapping_failure")
        if model_schema_invalid:
            errors.append("model_schema_invalid")
        if invalid_ids:
            errors.append("invalid_provision_ids")
        if duplicate_ids:
            errors.append("duplicate_provision_ids")
        if unresolved_gold:
            errors.append("unresolved_gold_provisions")
        if context_source == "golden" and not context_node_ids:
            errors.append("gold_context_empty")
        schema_errors = [error for error in errors if error in SCHEMA_ERROR_CODES]
        validation_errors = [error for error in errors if error not in SCHEMA_ERROR_CODES]
        final_citations = response.get("content", {}).get("citations", []) if isinstance(response.get("content"), dict) else []
        xml_copied = any(
            isinstance(item, dict) and ("<" in str(item.get("law", "")) or "<" in str(item.get("section", "")))
            for item in final_citations
        )
        totals.update(errors)
        if unresolved_count > 1:
            totals["unresolved_gold_provisions"] += unresolved_count - 1
        totals["total_selected_ids"] += len(model_ids) if isinstance(model_ids, list) else 0
        totals["total_final_citations"] += len(final_citations) if isinstance(final_citations, list) else 0
        if not model_ids:
            totals["questions_without_citation_ids"] += 1
        rows.append({
            "runtime_idx": runtime_idx,
            "source_idx": source_idx,
            "context_source": context_source,
            "gold_provisions": len(context_node_ids) if context_source == "golden" else 0,
            "unresolved_gold": unresolved_count,
            "selected_ids": len(model_ids) if isinstance(model_ids, list) else 0,
            "final_citations": len(final_citations) if isinstance(final_citations, list) else 0,
            "errors": ";".join(errors),
            "schema_errors": ";".join(schema_errors),
            "validation_errors": ";".join(validation_errors),
            "xml_copied": xml_copied,
            "context_ids_match_record": context_ids_match,
        })

    summary = {
        "total_answers": len(rows),
        "schema_invalid": sum(bool(row["schema_errors"]) for row in rows),
        "empty_answers": totals["empty_answer"],
        "questions_without_citation_ids": totals["questions_without_citation_ids"],
        "invalid_provision_ids": totals["invalid_provision_ids"],
        "duplicate_provision_ids": totals["duplicate_provision_ids"],
        "mapping_failures": totals["mapping_failure"],
        "final_citation_not_in_context": totals["final_citation_not_in_context"],
        "unresolved_gold_provisions": totals["unresolved_gold_provisions"],
        "gold_context_empty": totals["gold_context_empty"],
        "law_includes_section": totals["law_includes_section"],
        "section_is_long_text": totals["section_is_long_text"],
        "xml_copied": sum(row["xml_copied"] for row in rows),
        "total_selected_ids": totals["total_selected_ids"],
        "total_final_citations": totals["total_final_citations"],
        "mean_citations_per_question": totals["total_final_citations"] / len(rows) if rows else 0,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "response_quality.md").write_text(
        "# Common Interface v3 Citation-by-ID Response Quality\n\n"
        + "\n".join(f"- {key}: {value}" for key, value in summary.items())
        + "\n\n## Per-response errors\n\n| Runtime idx | Source idx | Context | Gold provisions | Selected IDs | Final citations | Unresolved gold | Schema errors | Validation errors | Context IDs match |\n|---|---|---|---:|---:|---:|---:|---|---|---:|\n"
        + "\n".join(
            f"| {row['runtime_idx']} | {row['source_idx']} | {row['context_source']} | {row['gold_provisions']} | {row['selected_ids']} | {row['final_citations']} | {row['unresolved_gold']} | {row['schema_errors'] or 'none'} | {row['validation_errors'] or 'none'} | {row['context_ids_match_record']} |"
            for row in rows
        )
        + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "response_quality.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

"""Audit Common Prompt Interface v3 responses without calling models or retrieval."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_KEYS = {"analysis", "answer", "citations"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--engineering-data", type=Path, default=Path("data_splits/tax_engineering_10.csv"))
    parser.add_argument("--saved-retrieval", type=Path, default=Path("results/current/retrieval_evaluation/section_based_no_ref/retrieval_results.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def canonical_idx(value: Any) -> str:
    return f"{int(str(value).strip()):04d}"


def validation_errors(content: Any, allowed_pairs: set[tuple[str, str]]) -> list[str]:
    errors: list[str] = []
    if not isinstance(content, dict):
        return ["response_content_not_json_object"]
    if set(content) != EXPECTED_KEYS:
        errors.append("top_level_keys")
    if not isinstance(content.get("answer"), str) or not content["answer"].strip():
        errors.append("empty_answer")
    citations = content.get("citations")
    if not isinstance(citations, list):
        return errors + ["citations_not_list"]
    seen: set[tuple[str, str]] = set()
    for citation in citations:
        if not isinstance(citation, dict) or set(citation) != {"law", "section"}:
            errors.append("citation_schema")
            continue
        law, section = citation.get("law"), citation.get("section")
        if not isinstance(law, str) or not isinstance(section, str):
            errors.append("citation_non_string")
            continue
        if re.search(r"มาตรา|<[^>]+>|\n", law):
            errors.append("law_includes_section_or_xml")
        if re.search(r"มาตรา|<[^>]+>|\n", section) or len(section.strip()) > 64 or len(section.split()) > 3:
            errors.append("section_is_long_text_or_xml")
        pair = (law, section)
        if pair not in allowed_pairs:
            errors.append("citation_not_in_context")
        if pair in seen:
            errors.append("duplicate_citation")
        seen.add(pair)
    return errors


def main() -> None:
    args = parse_args()
    responses = json.loads(args.responses.read_text(encoding="utf-8"))
    saved = json.loads(args.saved_retrieval.read_text(encoding="utf-8"))
    with args.engineering_data.open(encoding="utf-8-sig", newline="") as handle:
        engineering_rows = list(csv.DictReader(handle))
    if len(engineering_rows) != 10:
        raise ValueError(f"Expected 10 engineering rows, found {len(engineering_rows)}.")
    by_source_idx = {canonical_idx(item["idx"]): item for item in saved}
    if len(by_source_idx) != 50:
        raise ValueError("Saved retrieval must have 50 unique idx entries.")

    report_rows: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()
    for response in responses:
        runtime_idx = canonical_idx(response.get("idx"))
        if int(runtime_idx) >= len(engineering_rows):
            raise ValueError(f"Response idx {runtime_idx} is outside the engineering dataset.")
        source_idx = canonical_idx(engineering_rows[int(runtime_idx)]["source_idx"])
        expected_ids = by_source_idx[source_idx]["retrieved_ids"]
        allowed_pairs = {tuple(node_id.rsplit("-", 1)) for node_id in expected_ids}
        content = response.get("content")
        errors = validation_errors(content, allowed_pairs)
        citations = content.get("citations", []) if isinstance(content, dict) else []
        answer = content.get("answer", "") if isinstance(content, dict) else ""
        xml_copied = any(
            isinstance(citation, dict)
            and ("<" in str(citation.get("law", "")) or "<" in str(citation.get("section", "")))
            for citation in citations
        ) if isinstance(citations, list) else False
        english_chars = len(re.findall(r"[A-Za-z]", answer))
        thai_chars = len(re.findall(r"[ก-๙]", answer))
        report_rows.append({
            "runtime_idx": runtime_idx,
            "source_idx": source_idx,
            "citation_count": len(citations) if isinstance(citations, list) else 0,
            "errors": ";".join(errors),
            "english_dominant_answer": english_chars > thai_chars,
            "xml_copied": xml_copied,
            "retrieved_ids_match_saved": response.get("retrieved_ids") == expected_ids,
        })
        totals.update(errors)
        totals["total_citations"] += len(citations) if isinstance(citations, list) else 0
        if not citations:
            totals["questions_without_citations"] += 1
        if english_chars > thai_chars:
            totals["english_dominant_final_answers"] += 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    schema_invalid = sum(bool(row["errors"]) for row in report_rows)
    summary = {
        "total_answers": len(report_rows),
        "schema_invalid": schema_invalid,
        "empty_answers": totals["empty_answer"],
        "english_dominant_final_answers": totals["english_dominant_final_answers"],
        "questions_without_citations": totals["questions_without_citations"],
        "law_includes_section": totals["law_includes_section_or_xml"],
        "section_is_long_text": totals["section_is_long_text_or_xml"],
        "xml_copied": sum(row["xml_copied"] for row in report_rows),
        "citation_not_in_context": totals["citation_not_in_context"],
        "duplicate_citations": totals["duplicate_citation"],
        "total_citations": totals["total_citations"],
        "mean_citations_per_question": totals["total_citations"] / len(report_rows) if report_rows else 0,
    }
    with (args.output_dir / "response_quality.md").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Common Interface v3 Response Quality\n\n")
        for key, value in summary.items():
            handle.write(f"- {key}: {value}\n")
        handle.write("\n## Per-response errors\n\n| Runtime idx | Source idx | Citations | Errors | Saved IDs match |\n|---|---|---:|---|---:|\n")
        for row in report_rows:
            handle.write(f"| {row['runtime_idx']} | {row['source_idx']} | {row['citation_count']} | {row['errors'] or 'none'} | {row['retrieved_ids_match_saved']} |\n")
    with (args.output_dir / "response_quality.json").open("w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "rows": report_rows}, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

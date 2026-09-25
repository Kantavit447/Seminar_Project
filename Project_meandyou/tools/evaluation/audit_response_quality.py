"""Offline structural and quality audit for existing E2E response JSON files."""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
ENGLISH_RE = re.compile(r"[A-Za-z]")
XML_RE = re.compile(r"<\s*/?\s*(?:law|related_law)\b", re.IGNORECASE)
LAW_WITH_SECTION_RE = re.compile(r"(?:มาตรา|\bsection\s+\d)", re.IGNORECASE)


def find_project_root(start_path: Path) -> Path:
    for candidate in (start_path, *start_path.parents):
        if all((candidate / directory).is_dir() for directory in ("lrg", "config", "test_data")):
            return candidate
    raise RuntimeError("Could not find project root containing lrg/, config/, and test_data/.")


PROJECT_DIR = find_project_root(Path(__file__).resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit existing E2E response files without calling a model or API.")
    parser.add_argument(
        "--no-rag-input",
        type=Path,
        default=PROJECT_DIR / "results" / "current" / "parametric_qwen_controlled" / "parametric-qwen" / "tax_response.json",
    )
    parser.add_argument(
        "--vanilla-rag-input",
        type=Path,
        default=PROJECT_DIR / "results" / "current" / "vanilla_rag_qwen_controlled" / "chunk-human-finetuned-bge-m3-no-ref-qwen" / "tax_response.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "results" / "current" / "audits",
    )
    return parser.parse_args()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} does not exist or is not a file: {path}")


def language_stats(answer: str) -> tuple[int, int, str]:
    thai_count = len(THAI_RE.findall(answer))
    english_count = len(ENGLISH_RE.findall(answer))
    language_characters = thai_count + english_count
    if language_characters == 0:
        return thai_count, english_count, "Unknown"
    thai_ratio = thai_count / language_characters
    if thai_ratio >= 0.70:
        return thai_count, english_count, "Thai-dominant"
    if thai_ratio <= 0.30:
        return thai_count, english_count, "English-dominant"
    return thai_count, english_count, "Mixed"


def citation_errors(citation: Any) -> list[str]:
    if not isinstance(citation, dict):
        return ["ambiguous"]

    law = str(citation.get("law", "")).strip()
    section = str(citation.get("section", "")).strip()
    errors: list[str] = []

    if not law:
        errors.append("empty_law")
    if not section:
        errors.append("empty_section")
    if law and XML_RE.search(law):
        errors.append("xml_copied_into_law")
    if law and LAW_WITH_SECTION_RE.search(law):
        errors.append("law_includes_section")
    if len(section) > 80:
        errors.append("section_is_long_text")
    if section and (XML_RE.search(section) or "," in section or ";" in section):
        errors.append("ambiguous")
    return errors


def audit_response_file(input_path: Path, system_name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with input_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    top_level_valid = isinstance(payload, list)
    entries = payload if top_level_valid else []
    rows: list[dict[str, Any]] = []
    problem_indices: dict[str, list[str]] = defaultdict(list)
    field_missing_counts = Counter()
    citation_error_counts = Counter()
    language_counts = Counter()
    answer_lengths: list[int] = []
    total_citations = 0
    malformed_citations = 0
    empty_answers = 0
    no_citation_questions = 0
    schema_invalid_questions = 0
    observed_indices: list[int] = []

    for position, item in enumerate(entries):
        item_errors: list[str] = []
        if not isinstance(item, dict):
            item_errors.append("item_not_object")
            item = {}

        raw_idx = item.get("idx")
        idx = str(raw_idx).zfill(4) if raw_idx is not None else f"position-{position:04d}"
        try:
            observed_indices.append(int(str(raw_idx)))
        except (TypeError, ValueError):
            item_errors.append("invalid_or_missing_idx")

        content = item.get("content")
        if not isinstance(content, dict):
            item_errors.append("missing_or_invalid_content")
            content = {}

        missing_fields = [field for field in ("analysis", "answer", "citations") if field not in content]
        for field in missing_fields:
            field_missing_counts[field] += 1
            item_errors.append(f"missing_{field}")

        analysis = content.get("analysis")
        answer_value = content.get("answer")
        citations_value = content.get("citations")
        if analysis is not None and not isinstance(analysis, str):
            item_errors.append("invalid_analysis_type")
        if answer_value is not None and not isinstance(answer_value, str):
            item_errors.append("invalid_answer_type")
        if citations_value is not None and not isinstance(citations_value, list):
            item_errors.append("invalid_citations_type")

        answer = answer_value.strip() if isinstance(answer_value, str) else ""
        thai_count, english_count, language = language_stats(answer)
        answer_lengths.append(len(answer))
        language_counts[language] += 1
        if not answer:
            empty_answers += 1
            item_errors.append("empty_answer")

        citations = citations_value if isinstance(citations_value, list) else []
        total_citations += len(citations)
        if not citations:
            no_citation_questions += 1
            item_errors.append("no_citations")

        row_citation_errors: list[str] = []
        for citation in citations:
            errors = citation_errors(citation)
            row_citation_errors.extend(errors)
            citation_error_counts.update(errors)
            if errors:
                malformed_citations += 1

        schema_valid = not any(
            error in item_errors
            for error in (
                "item_not_object",
                "invalid_or_missing_idx",
                "missing_or_invalid_content",
                "missing_analysis",
                "missing_answer",
                "missing_citations",
                "invalid_analysis_type",
                "invalid_answer_type",
                "invalid_citations_type",
            )
        )
        if not schema_valid:
            schema_invalid_questions += 1
            problem_indices["schema_invalid"].append(idx)

        for error in set(item_errors + row_citation_errors):
            problem_indices[error].append(idx)

        rows.append(
            {
                "idx": idx,
                "schema_valid": schema_valid,
                "missing_fields": ";".join(missing_fields),
                "answer_empty": not bool(answer),
                "answer_language": language,
                "thai_characters": thai_count,
                "english_characters": english_count,
                "answer_length": len(answer),
                "citation_count": len(citations),
                "citation_errors": ";".join(sorted(set(row_citation_errors))),
                "schema_errors": ";".join(sorted(set(item_errors))),
                "has_any_problem": bool(item_errors or row_citation_errors),
            }
        )

    expected_indices = set(range(max(observed_indices) + 1)) if observed_indices else set()
    missing_indices = sorted(expected_indices - set(observed_indices))
    for missing_index in missing_indices:
        problem_indices["missing_index"].append(f"{missing_index:04d}")

    lengths = answer_lengths or [0]
    summary: dict[str, Any] = {
        "system": system_name,
        "input_file": str(input_path),
        "top_level_json_valid": top_level_valid,
        "total_answers": len(rows),
        "missing_indices": [f"{index:04d}" for index in missing_indices],
        "missing_index_count": len(missing_indices),
        "empty_answers": empty_answers,
        "schema_invalid_questions": schema_invalid_questions,
        "missing_required_fields": dict(field_missing_counts),
        "answer_language_counts": dict(language_counts),
        "answer_character_counts": {
            "thai": sum(row["thai_characters"] for row in rows),
            "english": sum(row["english_characters"] for row in rows),
        },
        "answer_length": {
            "mean": statistics.mean(lengths) if rows else 0,
            "median": statistics.median(lengths) if rows else 0,
            "min": min(lengths) if rows else 0,
            "max": max(lengths) if rows else 0,
        },
        "total_citations": total_citations,
        "mean_citations_per_question": total_citations / len(rows) if rows else 0,
        "questions_without_citations": no_citation_questions,
        "malformed_citations": malformed_citations,
        "citation_error_counts": dict(citation_error_counts),
        "problem_indices": {key: sorted(set(value)) for key, value in sorted(problem_indices.items())},
    }
    return summary, rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "idx", "schema_valid", "missing_fields", "answer_empty", "answer_language",
        "thai_characters", "english_characters", "answer_length", "citation_count",
        "citation_errors", "schema_errors", "has_any_problem",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def comparison_markdown(no_rag: dict[str, Any], vanilla_rag: dict[str, Any]) -> str:
    rows = [
        ("Total answers", "total_answers"),
        ("Missing indices", "missing_index_count"),
        ("Empty answers", "empty_answers"),
        ("Schema-invalid questions", "schema_invalid_questions"),
        ("English-dominant answers", "answer_language_counts.English-dominant"),
        ("Malformed citation errors", "malformed_citations"),
        ("Questions without citations", "questions_without_citations"),
        ("Total citations", "total_citations"),
        ("Mean citations per question", "mean_citations_per_question"),
    ]
    def value(data: dict[str, Any], key: str) -> Any:
        current: Any = data
        for part in key.split("."):
            current = current.get(part, 0) if isinstance(current, dict) else 0
        return current
    lines = ["# Offline response-quality comparison", "", "| Measure | No-RAG | Vanilla RAG |", "|---|---:|---:|"]
    lines.extend(f"| {label} | {value(no_rag, key)} | {value(vanilla_rag, key)} |" for label, key in rows)
    lines.extend(["", "## Problem question IDs", ""])
    for label, data in (("No-RAG", no_rag), ("Vanilla RAG", vanilla_rag)):
        lines.append(f"### {label}")
        problems = data["problem_indices"]
        if not problems:
            lines.append("No flagged question IDs.")
        else:
            for problem, indices in problems.items():
                lines.append(f"- `{problem}`: {', '.join(indices)}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    print("Offline response-quality audit paths")
    print(f"No-RAG input    : {args.no_rag_input}")
    print(f"Vanilla RAG input: {args.vanilla_rag_input}")
    print(f"Output directory : {args.output_dir}")
    require_file(args.no_rag_input, "No-RAG input")
    require_file(args.vanilla_rag_input, "Vanilla RAG input")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    no_rag, no_rag_rows = audit_response_file(args.no_rag_input, "no_rag")
    vanilla_rag, vanilla_rag_rows = audit_response_file(args.vanilla_rag_input, "vanilla_rag")
    outputs = {
        args.output_dir / "no_rag_response_quality.json": no_rag,
        args.output_dir / "vanilla_rag_response_quality.json": vanilla_rag,
    }
    for path, data in outputs.items():
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(args.output_dir / "no_rag_response_quality_per_question.csv", no_rag_rows)
    write_csv(args.output_dir / "vanilla_rag_response_quality_per_question.csv", vanilla_rag_rows)
    (args.output_dir / "response_quality_comparison.md").write_text(
        comparison_markdown(no_rag, vanilla_rag), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

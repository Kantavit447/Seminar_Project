import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def find_project_root(start_path: Path) -> Path:
    """Find the repository root from the required NitiBench directories."""
    for candidate in (start_path, *start_path.parents):
        if all(
            (candidate / directory).is_dir()
            for directory in ("lrg", "config", "test_data")
        ):
            return candidate

    raise RuntimeError(
        "Could not find the project root. Expected parent directories "
        "containing lrg/, config/, and test_data/."
    )


PROJECT_DIR = find_project_root(Path(__file__).resolve())


def parse_args() -> argparse.Namespace:
    default_input = (
        PROJECT_DIR
        / "results"
        / "current"
        / "vanilla_rag_qwen_controlled"
        / "chunk-human-finetuned-bge-m3-no-ref-qwen"
        / "tax_response.json"
    )
    parser = argparse.ArgumentParser(
        description="Audit the citation field formats in an E2E response JSON."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help="Response JSON to audit (default: controlled Vanilla RAG result).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Audit JSON path (default: citation_format_audit.json beside input).",
    )
    return parser.parse_args()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            f"{label} does not exist or is not a file: {path}"
        )


def classify_format(law: str, section: str) -> str:
    law = str(law).strip()
    section = str(section).strip()

    if not law:
        return "empty_law"

    if "มาตรา" in law and section and section in law:
        return "law_contains_word_mattra_and_section"

    if "มาตรา" in law:
        return "law_contains_word_mattra"

    if section and section in law:
        return "law_contains_section"

    if law.startswith("มาตรา"):
        return "law_starts_with_mattra"

    return "clean_or_other"


def main() -> None:
    args = parse_args()
    result_path = args.input
    output_path = (
        args.output
        if args.output is not None
        else result_path.parent / "citation_format_audit.json"
    )

    print("Citation format audit paths")
    print(f"Input response : {result_path}")
    print(f"Output audit   : {output_path}")

    require_file(result_path, "Input response file")

    with result_path.open("r", encoding="utf-8") as file:
        results = json.load(file)

    format_counts = Counter()
    exact_law_counts = Counter()
    examples = defaultdict(list)

    total_citations = 0
    questions_without_citations = 0

    for item in results:
        idx = str(item.get("idx", ""))
        content = item.get("content", {})

        if not isinstance(content, dict):
            questions_without_citations += 1
            continue

        citations = content.get("citations", [])

        if not citations:
            questions_without_citations += 1
            continue

        for citation in citations:
            law = str(citation.get("law", "")).strip()
            section = str(citation.get("section", "")).strip()

            category = classify_format(law, section)

            total_citations += 1
            format_counts[category] += 1
            exact_law_counts[law] += 1

            if len(examples[category]) < 10:
                examples[category].append(
                    {
                        "idx": idx,
                        "law": law,
                        "section": section,
                    }
                )

    audit = {
        "questions": len(results),
        "questions_without_citations": questions_without_citations,
        "total_citations": total_citations,
        "format_counts": dict(format_counts),
        "examples": dict(examples),
        "most_common_exact_law_values": [
            {
                "law": law,
                "count": count,
            }
            for law, count in exact_law_counts.most_common(50)
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(audit, file, ensure_ascii=False, indent=2)

    print("\nCitation Format Audit")
    print("=" * 60)
    print(f"Questions              : {len(results)}")
    print(f"Total citations        : {total_citations}")
    print(f"Questions without cites: {questions_without_citations}")
    print()

    for category, count in format_counts.most_common():
        percentage = (
            count / total_citations * 100
            if total_citations
            else 0
        )
        print(f"{category:40} {count:4d} ({percentage:6.2f}%)")

    print("=" * 60)
    print(f"Audit file: {output_path}")


if __name__ == "__main__":
    main()

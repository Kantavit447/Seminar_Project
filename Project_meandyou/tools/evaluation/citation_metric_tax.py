import ast
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Optional

import pandas as pd


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
        description="Calculate Tax citation metrics from an E2E response JSON."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help="Response JSON to score (default: controlled Vanilla RAG result).",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_DIR / "test_data" / "hf_tax.csv",
        help="Tax CSV containing relevant_laws (default: project test data).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Global metric JSON path (default: tax_citation_metrics.json beside input).",
    )
    parser.add_argument(
        "--per-question-output",
        type=Path,
        default=None,
        help=(
            "Per-question metric JSON path "
            "(default: tax_citation_metrics_per_question.json beside input)."
        ),
    )
    return parser.parse_args()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            f"{label} does not exist or is not a file: {path}"
        )

def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_reference(citation: dict) -> tuple[str, str]:
    law = clean_text(citation.get("law", ""))
    section = clean_text(citation.get("sections", ""))
    return law, section


def strict_generated(citation: dict) -> tuple[str, str]:
    law = clean_text(citation.get("law", ""))
    section = clean_text(citation.get("section", ""))
    return law, section


def extract_xml_citation(
    law: str,
    section: str,
) -> Optional[tuple[str, str]]:
    """
    Recover citations copied from tags such as:
    <law section="82/7" law_name="ประมวลรัษฎากร">
    """
    if not law.startswith("<law"):
        return None

    law_match = re.search(
        r'(?:law_name|name)\s*=\s*["\']([^"\']+)["\']',
        law,
        flags=re.IGNORECASE,
    )
    section_match = re.search(
        r'section\s*=\s*["\']?([^"\'>]+)',
        law,
        flags=re.IGNORECASE,
    )

    if not law_match:
        return None

    recovered_law = clean_text(law_match.group(1))
    recovered_section = (
        clean_text(section_match.group(1))
        if section_match
        else clean_text(section)
    )

    recovered_section = re.sub(
        r"^มาตรา\s*",
        "",
        recovered_section,
    ).strip()

    if recovered_law and recovered_section:
        return recovered_law, recovered_section

    return None


def extract_law_and_section_from_law_field(
    law: str,
) -> Optional[tuple[str, str]]:
    """
    Recover:
    ประมวลรัษฎากร มาตรา 80/1
    ประมวลรัษฎากร มาตรา 69 ทวิ
    พระราชบัญญัติ... มาตรา 33/5

    Does not recover values containing multiple sections separated by commas.
    """
    match = re.match(
        r"^(.*?)\s+มาตรา\s+(.+?)$",
        law,
    )

    if not match:
        return None

    recovered_law = clean_text(match.group(1))
    recovered_section = clean_text(match.group(2))

    # Avoid silently splitting one citation containing several sections.
    if "," in recovered_section or ";" in recovered_section:
        return None

    if recovered_law and recovered_section:
        return recovered_law, recovered_section

    return None


def looks_like_section_content(section: str) -> bool:
    """
    Detect when the section field contains copied legal prose rather than
    a section identifier.
    """
    if not section:
        return True

    if len(section) > 80:
        return True

    prose_markers = [
        "ในกรณี",
        "ระบุว่า",
        "ผู้ประกอบการ",
        "เงินได้",
        "ให้กรม",
        "การคำนวณ",
        "ไม่ใช่",
        "</law>",
    ]

    return any(marker in section for marker in prose_markers)


def conservative_generated(
    citation: dict,
) -> tuple[Optional[tuple[str, str]], str]:
    """
    Return:
      normalized citation or None,
      classification: clean / recovered_xml / recovered_law_field /
                      ambiguous / invalid
    """
    law = clean_text(citation.get("law", ""))
    section = clean_text(citation.get("section", ""))

    if not law:
        return None, "invalid"

    xml_result = extract_xml_citation(law, section)
    if xml_result:
        return xml_result, "recovered_xml"

    law_field_result = extract_law_and_section_from_law_field(law)

    if law_field_result:
        recovered_law, recovered_section = law_field_result

        # Safe case: section repeats the same identifier.
        normalized_section = re.sub(
            r"^มาตรา\s*",
            "",
            section,
        ).strip()

        if normalized_section == recovered_section:
            return (
                recovered_law,
                recovered_section,
            ), "recovered_law_field"

        # Safe-ish recovery when section contains copied prose rather than
        # a usable section identifier.
        if looks_like_section_content(section):
            return (
                recovered_law,
                recovered_section,
            ), "recovered_law_field"

        # Example:
        # law = มาตรา 91/5 (7), section = (7)
        # The relationship is ambiguous, so do not repair automatically.
        return None, "ambiguous"

    # Already close to the expected schema.
    section = re.sub(r"^มาตรา\s*", "", section).strip()

    if not section:
        return None, "invalid"

    if looks_like_section_content(section):
        return None, "ambiguous"

    return (law, section), "clean"


def score_citations(
    references: list[list[dict]],
    generated: list[list[dict]],
    normalized: bool,
) -> tuple[dict, list[dict], Counter]:
    total_tp = 0
    total_fp = 0
    total_fn = 0

    local_results = []
    category_counts = Counter()

    for index, (reference_list, generated_list) in enumerate(
        zip(references, generated)
    ):
        reference_set = {
            normalize_reference(citation)
            for citation in reference_list
            if normalize_reference(citation)[0]
            and normalize_reference(citation)[1]
        }

        generated_set = set()
        item_categories = Counter()

        for citation in generated_list:
            if normalized:
                normalized_citation, category = conservative_generated(
                    citation
                )
                category_counts[category] += 1
                item_categories[category] += 1

                if normalized_citation:
                    generated_set.add(normalized_citation)
            else:
                strict_citation = strict_generated(citation)
                if strict_citation[0] and strict_citation[1]:
                    generated_set.add(strict_citation)

        tp = len(reference_set & generated_set)
        fp = len(generated_set - reference_set)
        fn = len(reference_set - generated_set)

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        total_tp += tp
        total_fp += fp
        total_fn += fn

        local_results.append(
            {
                "idx": f"{index:04d}",
                "true_positive": tp,
                "false_positive": fp,
                "false_negative": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "reference_citations": sorted(reference_set),
                "generated_citations": sorted(generated_set),
                "normalization_categories": dict(item_categories),
            }
        )

    micro_precision = (
        total_tp / (total_tp + total_fp)
        if total_tp + total_fp
        else 0.0
    )
    micro_recall = (
        total_tp / (total_tp + total_fn)
        if total_tp + total_fn
        else 0.0
    )
    micro_f1 = (
        2
        * micro_precision
        * micro_recall
        / (micro_precision + micro_recall)
        if micro_precision + micro_recall
        else 0.0
    )

    question_count = len(local_results)

    summary = {
        "questions": question_count,
        "true_positive": total_tp,
        "false_positive": total_fp,
        "false_negative": total_fn,
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": micro_f1,
        "macro_precision": (
            sum(item["precision"] for item in local_results)
            / question_count
        ),
        "macro_recall": (
            sum(item["recall"] for item in local_results)
            / question_count
        ),
        "macro_f1": (
            sum(item["f1"] for item in local_results)
            / question_count
        ),
    }

    return summary, local_results, category_counts


def main() -> None:
    args = parse_args()
    result_path = args.input
    dataset_path = args.dataset
    output_global_path = (
        args.output
        if args.output is not None
        else result_path.parent / "tax_citation_metrics.json"
    )
    output_local_path = (
        args.per_question_output
        if args.per_question_output is not None
        else result_path.parent / "tax_citation_metrics_per_question.json"
    )

    print("Tax citation metric paths")
    print(f"Input response : {result_path}")
    print(f"Input dataset  : {dataset_path}")
    print(f"Output global  : {output_global_path}")
    print(f"Output local   : {output_local_path}")

    require_file(result_path, "Input response file")
    require_file(dataset_path, "Input dataset file")

    tax_df = pd.read_csv(
        dataset_path,
        encoding="utf-8-sig",
        converters={"relevant_laws": ast.literal_eval},
    )

    with result_path.open("r", encoding="utf-8") as file:
        results = json.load(file)

    results_by_idx = {
        str(item.get("idx", "")).zfill(4): item
        for item in results
    }

    references = []
    generated = []
    missing = []

    for index, row in tax_df.iterrows():
        idx = f"{index:04d}"
        item = results_by_idx.get(idx)

        if item is None:
            missing.append(idx)
            continue

        content = item.get("content", {})
        if not isinstance(content, dict):
            content = {}

        references.append(row["relevant_laws"])
        generated.append(content.get("citations", []))

    strict_summary, strict_local, _ = score_citations(
        references,
        generated,
        normalized=False,
    )

    normalized_summary, normalized_local, categories = score_citations(
        references,
        generated,
        normalized=True,
    )

    output = {
        "result_file": str(result_path),
        "missing_indices": missing,
        "strict": strict_summary,
        "conservative_normalized": normalized_summary,
        "normalization_categories": dict(categories),
    }

    local_output = {
        "strict": strict_local,
        "conservative_normalized": normalized_local,
    }

    output_global_path.parent.mkdir(parents=True, exist_ok=True)
    output_local_path.parent.mkdir(parents=True, exist_ok=True)

    with output_global_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    with output_local_path.open("w", encoding="utf-8") as file:
        json.dump(local_output, file, ensure_ascii=False, indent=2)

    print("\nTax Citation Metrics")
    print("=" * 68)

    print("STRICT")
    print(
        f"Micro P/R/F1 : "
        f"{strict_summary['micro_precision']:.4f} / "
        f"{strict_summary['micro_recall']:.4f} / "
        f"{strict_summary['micro_f1']:.4f}"
    )
    print(
        f"Macro P/R/F1 : "
        f"{strict_summary['macro_precision']:.4f} / "
        f"{strict_summary['macro_recall']:.4f} / "
        f"{strict_summary['macro_f1']:.4f}"
    )

    print("\nCONSERVATIVE NORMALIZED")
    print(
        f"Micro P/R/F1 : "
        f"{normalized_summary['micro_precision']:.4f} / "
        f"{normalized_summary['micro_recall']:.4f} / "
        f"{normalized_summary['micro_f1']:.4f}"
    )
    print(
        f"Macro P/R/F1 : "
        f"{normalized_summary['macro_precision']:.4f} / "
        f"{normalized_summary['macro_recall']:.4f} / "
        f"{normalized_summary['macro_f1']:.4f}"
    )

    print("\nNORMALIZATION CATEGORIES")
    for category, count in categories.most_common():
        print(f"{category:25} : {count}")

    print("=" * 68)
    print(f"Global result: {output_global_path}")
    print(f"Per-question : {output_local_path}")


if __name__ == "__main__":
    main()

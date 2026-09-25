"""Evaluate saved NitiBench retrieval IDs without running a retriever or an API.

This adapter follows the repository's chunk-evaluation convention: a retrieved
chunk is relevant when ``chunk_to_gold_mapping.json`` maps it to one of the
dataset's ``law-sections`` gold identifiers.  It intentionally does not load a
model, initialise a retriever, or modify any input artifact.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def find_project_root(start_path: Path) -> Path:
    for candidate in (start_path, *start_path.parents):
        if all((candidate / name).is_dir() for name in ("lrg", "config", "test_data")):
            return candidate
    raise RuntimeError("Could not find project root containing lrg/, config/, and test_data/.")


PROJECT_DIR = find_project_root(Path(__file__).resolve())
DEFAULT_RESPONSE = PROJECT_DIR / "results/current/vanilla_rag_qwen_controlled/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response.json"
DEFAULT_DATASET = PROJECT_DIR / "test_data/hf_tax.csv"
DEFAULT_NODES = PROJECT_DIR / "chunking/553_50_line/nodes.json"
DEFAULT_GOLD_NODES = PROJECT_DIR / "chunking/golden/nodes.json"
DEFAULT_MAPPING = PROJECT_DIR / "chunking/553_50_line/chunk_to_gold_mapping.json"
DEFAULT_OUTPUT = PROJECT_DIR / "results/current/retrieval_evaluation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline evaluation of saved top-k retrieval IDs.")
    parser.add_argument("--response", type=Path, default=DEFAULT_RESPONSE, help="Saved E2E response JSON containing retrieved_ids.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Tax CSV containing relevant_laws.")
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES, help="Retrieved chunk nodes.json.")
    parser.add_argument("--gold-nodes", type=Path, default=DEFAULT_GOLD_NODES, help="Golden nodes.json used to validate gold IDs.")
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING, help="Chunk-to-golden-node mapping JSON.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Directory for JSON, Markdown, and CSV outputs.")
    return parser.parse_args()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} does not exist or is not a file: {path}")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collapse_space(value: Any) -> str:
    return " ".join(str(value).strip().split())


def normalize_gold_id(value: str) -> str:
    """Conservative supplemental normalisation; never used for primary metrics."""
    law, separator, section = value.rpartition("-")
    if not separator:
        return collapse_space(value)
    section = collapse_space(section)
    section = re.sub(r"^(?:มาตรา|section)\s+", "", section, flags=re.IGNORECASE)
    return f"{collapse_space(law)}-{section}"


def gold_ids(row: dict[str, str]) -> list[str]:
    try:
        citations = ast.literal_eval(row["relevant_laws"])
    except (KeyError, ValueError, SyntaxError) as exc:
        raise ValueError(f"Invalid relevant_laws: {row.get('relevant_laws')!r}") from exc
    if not isinstance(citations, list):
        raise ValueError("relevant_laws must decode to a list")
    output = []
    for citation in citations:
        if not isinstance(citation, dict) or "law" not in citation or "sections" not in citation:
            raise ValueError(f"Invalid gold citation: {citation!r}")
        output.append(f"{collapse_space(citation['law'])}-{collapse_space(citation['sections'])}")
    return list(dict.fromkeys(output))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def mapped_gold_ids(retrieved_id: str, mapping: dict[str, list[str]], normalized: bool) -> set[str]:
    mapped = mapping.get(retrieved_id, [])
    return {normalize_gold_id(value) if normalized else value for value in mapped}


def metric_row(gold: list[str], retrieved: list[str], mapping: dict[str, list[str]], normalized: bool) -> dict[str, Any]:
    expected = {normalize_gold_id(value) if normalized else value for value in gold}
    found: set[str] = set()
    relevant_ranks: list[int] = []
    novel_ranks: list[int] = []
    for rank, retrieved_id in enumerate(retrieved[:10], start=1):
        matched = mapped_gold_ids(retrieved_id, mapping, normalized) & expected
        if matched:
            relevant_ranks.append(rank)
            if not matched <= found:
                novel_ranks.append(rank)
                found.update(matched)
    first = relevant_ranks[0] if relevant_ranks else None
    reciprocal = 1 / first if first else 0.0
    recall = len(found) / len(expected) if expected else 0.0
    dcg = sum(1 / math.log2(rank + 1) for rank in novel_ranks)
    ideal_count = min(len(expected), 10)
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return {
        "gold_found": sorted(found), "relevant_ranks": relevant_ranks,
        "novel_relevant_ranks": novel_ranks, "first_relevant_rank": first,
        "reciprocal_rank": reciprocal, "recall_at_10": recall,
        "ndcg_at_10": dcg / idcg if idcg else 0.0,
    }


def readable_node(node: dict[str, Any] | None, node_id: str) -> str:
    if not node:
        return f"{node_id} [unmapped node]"
    metadata = node.get("metadata", {}) if isinstance(node.get("metadata"), dict) else {}
    law = metadata.get("law_name", "")
    sections = metadata.get("sections_covered", "")
    return f"{node_id} | law={law} | sections={sections}"


def model_citation_ids(entry: dict[str, Any]) -> tuple[list[str], list[str]]:
    content = entry.get("content")
    citations = content.get("citations", []) if isinstance(content, dict) else []
    if not isinstance(citations, list):
        return [], []
    strict, normalized = [], []
    for citation in citations:
        if isinstance(citation, dict) and citation.get("law") is not None and citation.get("section") is not None:
            value = f"{collapse_space(citation['law'])}-{collapse_space(citation['section'])}"
            strict.append(value)
            normalized.append(normalize_gold_id(value))
    return list(dict.fromkeys(strict)), list(dict.fromkeys(normalized))


def supplemental_diagnosis(entry: dict[str, Any], gold: list[str], primary: dict[str, Any]) -> str:
    if not primary["gold_found"]:
        return "retrieval_issue"
    strict, normalized = model_citation_ids(entry)
    expected = set(gold)
    if expected & set(strict):
        return "model_cites_gold_strictly"
    if {normalize_gold_id(item) for item in expected} & set(normalized):
        return "formatting_or_normalization_issue"
    return "generation_or_context_use_issue"


def markdown_report(result: dict[str, Any]) -> str:
    strict = result["metrics"]["strict_primary"]
    normal = result["metrics"]["normalized_supplemental"]
    validation = result["validation"]
    return f"""# Saved Retrieval Evaluation — Tax 50

## Scope

Offline evaluation only: the script reads saved `retrieved_ids` and does not initialise a retriever, model, or API. Relevance follows NitiBench's existing chunk-evaluation convention: a chunk is relevant when `chunk_to_gold_mapping.json` maps it to one of the question's `law-sections` gold IDs.

## Primary metrics — strict

| Metric | Value |
|---|---:|
| Recall@10 (macro) | {strict['recall_at_10_macro']:.6f} |
| Recall@10 (micro) | {strict['recall_at_10_micro']:.6f} |
| MRR | {strict['mrr']:.6f} |
| NDCG@10 | {strict['ndcg_at_10']:.6f} |
| Questions with any gold in top-10 | {strict['questions_with_gold_in_top_10']} / {strict['question_count']} |
| Retrieval failures | {strict['diagnosis_counts']['retrieval_failure']} |
| Ranking issues (first gold rank 6–10) | {strict['diagnosis_counts']['ranking_issue']} |
| Retrieval successes (first gold rank 1–5) | {strict['diagnosis_counts']['retrieval_success']} |

## Supplemental conservative normalisation

Whitespace is collapsed and only a leading `มาตรา` / `section` prefix is removed from the section part. No number extraction, fuzzy law matching, or name guessing is used. These values are supplemental only.

| Metric | Value |
|---|---:|
| Recall@10 (macro) | {normal['recall_at_10_macro']:.6f} |
| MRR | {normal['mrr']:.6f} |
| NDCG@10 | {normal['ndcg_at_10']:.6f} |

## Definitions

- Recall@10 is the fraction of unique gold IDs found through the top-10 chunk-to-gold mappings (macro is averaged per question; micro pools all gold IDs).
- MRR is the reciprocal rank of the first retrieved chunk that maps to a gold ID.
- NDCG@10 uses binary, novelty-based relevance: a rank contributes only when it adds at least one previously unseen gold ID. This prevents duplicate chunks for the same gold section from inflating the score; ideal DCG contains `min(number of gold IDs, 10)` relevant ranks.
- The official repository retrieval evaluator has Recall/MRR support but reruns retrieval. This adapter preserves its mapping convention and adds offline NDCG@10.

## Validation and limitations

- Response entries: {validation['response_count']}; dataset rows: {validation['dataset_count']}; expected: 50.
- Missing indices: {validation['missing_indices'] or 'none'}; duplicate indices: {validation['duplicate_indices'] or 'none'}.
- Entries not containing exactly 10 retrieved IDs: {validation['non_top_10_indices'] or 'none'}.
- Retrieved node IDs not found in `nodes.json`: {validation['unmapped_retrieved_node_ids'] or 'none'}.
- Gold IDs not found in `golden/nodes.json`: {validation['unmapped_gold_ids'] or 'none'}.
- Normalisation collisions (mapping ambiguity): {validation['normalization_collision_count']}.

The result measures alignment with dataset gold citations via the repository mapping, not semantic relevance beyond those annotations. The supplemental model-citation diagnosis in the CSV is not a retrieval metric and does not establish generation failure.
"""


def main() -> None:
    args = parse_args()
    for path, label in ((args.response, "Response JSON"), (args.dataset, "Dataset CSV"), (args.nodes, "Chunk nodes"), (args.gold_nodes, "Golden nodes"), (args.mapping, "Chunk mapping")):
        require_file(path, label)
    print(f"response: {args.response.resolve()}")
    print(f"dataset: {args.dataset.resolve()}")
    print(f"nodes: {args.nodes.resolve()}")
    print(f"gold nodes: {args.gold_nodes.resolve()}")
    print(f"mapping: {args.mapping.resolve()}")
    print(f"output directory: {args.output_dir.resolve()}")

    response = load_json(args.response)
    nodes_list = load_json(args.nodes)
    gold_nodes_list = load_json(args.gold_nodes)
    mapping = load_json(args.mapping)
    if not isinstance(response, list) or not isinstance(nodes_list, list) or not isinstance(gold_nodes_list, list) or not isinstance(mapping, dict):
        raise ValueError("Unexpected JSON schema: response/nodes must be lists and mapping must be an object.")
    with args.dataset.open("r", encoding="utf-8-sig", newline="") as handle:
        dataset = list(csv.DictReader(handle))
    required_columns = {"question", "answer", "relevant_laws", "reference_answer"}
    if not dataset or not required_columns <= set(dataset[0]):
        raise ValueError(f"Dataset must contain columns: {sorted(required_columns)}")

    nodes = {str(item.get("id_")): item for item in nodes_list if isinstance(item, dict) and item.get("id_") is not None}
    gold_node_ids = {str(item.get("id_")) for item in gold_nodes_list if isinstance(item, dict) and item.get("id_") is not None}
    expected_indices = [f"{number:04d}" for number in range(len(dataset))]
    seen_indices = [str(item.get("idx")) for item in response if isinstance(item, dict)]
    duplicates = sorted(index for index, count in Counter(seen_indices).items() if count > 1)
    missing = sorted(set(expected_indices) - set(seen_indices))
    by_index = {str(item.get("idx")): item for item in response if isinstance(item, dict)}
    if len(dataset) != 50 or len(response) != 50 or missing or duplicates or set(seen_indices) != set(expected_indices):
        raise ValueError(f"Expected exactly Tax indices 0000–0049; rows={len(dataset)}, responses={len(response)}, missing={missing}, duplicates={duplicates}.")

    mapped_gold_values = {value for values in mapping.values() if isinstance(values, list) for value in values}
    normalized_index: dict[str, set[str]] = defaultdict(set)
    for value in mapped_gold_values:
        normalized_index[normalize_gold_id(value)].add(value)
    collision_count = sum(1 for values in normalized_index.values() if len(values) > 1)
    rows: list[dict[str, Any]] = []
    unmapped_retrieved: set[str] = set()
    unmapped_gold: set[str] = set()
    non_top_10: list[str] = []

    for offset, dataset_row in enumerate(dataset):
        idx = f"{offset:04d}"
        entry = by_index[idx]
        retrieved = entry.get("retrieved_ids", [])
        if not isinstance(retrieved, list) or not all(isinstance(value, str) for value in retrieved):
            raise ValueError(f"idx {idx} has invalid retrieved_ids; expected list[str].")
        if len(retrieved) != 10:
            non_top_10.append(idx)
        retrieved = retrieved[:10]
        gold = gold_ids(dataset_row)
        unmapped_retrieved.update(value for value in retrieved if value not in nodes)
        unmapped_gold.update(value for value in gold if value not in gold_node_ids)
        strict = metric_row(gold, retrieved, mapping, normalized=False)
        normalized = metric_row(gold, retrieved, mapping, normalized=True)
        first = strict["first_relevant_rank"]
        diagnosis = "retrieval_failure" if first is None else ("retrieval_success" if first <= 5 else "ranking_issue")
        rows.append({
            "idx": idx, "question": dataset_row["question"], "gold_citations": gold,
            "retrieved_top_10": retrieved,
            "retrieved_law_section": [readable_node(nodes.get(value), value) for value in retrieved],
            "relevant_ranks": strict["relevant_ranks"], "novel_relevant_ranks": strict["novel_relevant_ranks"],
            "gold_found": strict["gold_found"], "gold_found_in_top_10": bool(strict["gold_found"]),
            "all_gold_found_in_top_10": len(strict["gold_found"]) == len(gold),
            "first_relevant_rank": first, "reciprocal_rank": strict["reciprocal_rank"],
            "recall_at_10": strict["recall_at_10"], "ndcg_at_10": strict["ndcg_at_10"],
            "normalized_gold_found": normalized["gold_found"], "normalized_recall_at_10": normalized["recall_at_10"],
            "normalized_mrr": normalized["reciprocal_rank"], "normalized_ndcg_at_10": normalized["ndcg_at_10"],
            "retrieval_diagnosis": diagnosis,
            "supplemental_model_citation_diagnosis": supplemental_diagnosis(entry, gold, strict),
        })

    def aggregate(prefix: str) -> dict[str, Any]:
        recalls = [row[f"{prefix}recall_at_10"] for row in rows]
        mrrs = [row["normalized_mrr"] if prefix else row["reciprocal_rank"] for row in rows]
        ndcgs = [row[f"{prefix}ndcg_at_10"] for row in rows]
        found_total = sum(len(row["normalized_gold_found"] if prefix else row["gold_found"]) for row in rows)
        gold_total = sum(len(row["gold_citations"]) for row in rows)
        diagnoses = Counter(row["retrieval_diagnosis"] for row in rows) if not prefix else Counter()
        return {"question_count": len(rows), "recall_at_10_macro": mean(recalls), "recall_at_10_micro": found_total / gold_total if gold_total else 0.0, "mrr": mean(mrrs), "ndcg_at_10": mean(ndcgs), "questions_with_gold_in_top_10": sum(bool(row["normalized_gold_found"] if prefix else row["gold_found"]) for row in rows), "gold_citation_count": gold_total, "gold_citation_found_count": found_total, "diagnosis_counts": dict(diagnoses)}

    validation = {"response_count": len(response), "dataset_count": len(dataset), "expected_index_count": len(expected_indices), "missing_indices": missing, "duplicate_indices": duplicates, "non_top_10_indices": non_top_10, "unmapped_retrieved_node_ids": sorted(unmapped_retrieved), "unmapped_gold_ids": sorted(unmapped_gold), "normalization_collision_count": collision_count}
    result = {"evaluation": {"name": "saved_retrieval_evaluation", "offline": True, "top_k": 10, "primary_matching": "strict exact gold-ID match through chunk_to_gold_mapping.json", "supplemental_matching": "conservative whitespace + leading section-prefix normalisation", "official_evaluator_basis": "lrg/retrieval/retrieval_evaluation.py / chunk_to_gold_mapping.json"}, "inputs": {"response": str(args.response), "dataset": str(args.dataset), "nodes": str(args.nodes), "gold_nodes": str(args.gold_nodes), "mapping": str(args.mapping)}, "metrics": {"strict_primary": aggregate(""), "normalized_supplemental": aggregate("normalized_")}, "validation": validation, "per_question": rows}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "retrieval_metrics.json"
    csv_path = args.output_dir / "retrieval_per_question.csv"
    md_path = args.output_dir / "retrieval_metrics.md"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    with csv_path.open("w", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})
    md_path.write_text(markdown_report(result), encoding="utf-8")
    strict = result["metrics"]["strict_primary"]
    print(f"Strict Recall@10={strict['recall_at_10_macro']:.6f}; MRR={strict['mrr']:.6f}; NDCG@10={strict['ndcg_at_10']:.6f}")


if __name__ == "__main__":
    main()

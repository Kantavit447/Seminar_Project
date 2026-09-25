"""Run offline section-based retrieval for NitiBench-Tax without an LLM or API.

The adapter deliberately uses the repository's BGEM3Index settings but bypasses
the E2E response pipeline.  ``type: golden`` selects the section-based corpus;
gold citations are read only after retrieval to calculate metrics.
"""

from __future__ import annotations

import argparse
import ast
import csv
import gc
import json
import math
import os
import re
import site
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

# Prevent model/config downloads even when a dependency would otherwise attempt one.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")


def find_project_root(start_path: Path) -> Path:
    for candidate in (start_path, *start_path.parents):
        if all((candidate / name).is_dir() for name in ("lrg", "config", "test_data")):
            return candidate
    raise RuntimeError("Could not find project root containing lrg/, config/, and test_data/.")


PROJECT_DIR = find_project_root(Path(__file__).resolve())


def bootstrap_project_venv() -> None:
    """Allow a system Python to use the project's installed dependencies safely."""
    site_packages = PROJECT_DIR / ".venv" / "Lib" / "site-packages"
    if site_packages.is_dir():
        site.addsitedir(str(site_packages))


bootstrap_project_venv()

import yaml  # noqa: E402
from llama_index.core.schema import TextNode  # noqa: E402
from llama_index.indices.managed.bge_m3 import BGEM3Index  # noqa: E402
import torch  # noqa: E402


MODEL_NAME = "VISAI-AI/nitibench-ccl-human-finetuned-bge-m3"
WEIGHTS = [0.4, 0.2, 0.4]  # dense, sparse, multi-vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve NitiBench Tax questions from the section-based corpus only.")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_DIR / "config" / "local" / "retrieval" / "proposed_tax_retrieval.yaml",
    )
    parser.add_argument("--output-dir", type=Path, default=None, help="Override config output_path.")
    parser.add_argument("--resume", action="store_true", help="Resume from retrieval_results.json if it is valid.")
    parser.add_argument("--smoke-nodes", type=int, default=None, help="Build/query only the first N nodes; validation only, no metrics.")
    parser.add_argument("--validate-sharding", action="store_true", help="Compare a 128-node single index with 64-node shards for all Tax queries.")
    parser.add_argument("--finalize-only", action="store_true", help="Merge existing shard checkpoints and write outputs without building an index.")
    return parser.parse_args()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} does not exist or is not a file: {path}")


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_DIR / path


def collapse_space(value: Any) -> str:
    return " ".join(str(value).strip().split())


def normalize_gold_id(value: str) -> str:
    law, separator, section = value.rpartition("-")
    if not separator:
        return collapse_space(value)
    section = re.sub(r"^(?:มาตรา|section)\s+", "", collapse_space(section), flags=re.IGNORECASE)
    return f"{collapse_space(law)}-{section}"


def gold_ids(row: dict[str, str]) -> list[str]:
    citations = ast.literal_eval(row["relevant_laws"])
    if not isinstance(citations, list):
        raise ValueError("relevant_laws must decode to a list.")
    values = []
    for citation in citations:
        if not isinstance(citation, dict) or "law" not in citation or "sections" not in citation:
            raise ValueError(f"Invalid gold citation: {citation!r}")
        values.append(f"{collapse_space(citation['law'])}-{collapse_space(citation['sections'])}")
    return list(dict.fromkeys(values))


def metric_row(gold: list[str], retrieved: list[str], normalized: bool) -> dict[str, Any]:
    expected = {normalize_gold_id(item) if normalized else item for item in gold}
    found: set[str] = set()
    relevant_ranks: list[int] = []
    novel_ranks: list[int] = []
    for rank, item in enumerate(retrieved[:10], start=1):
        candidate = normalize_gold_id(item) if normalized else item
        if candidate in expected:
            relevant_ranks.append(rank)
            if candidate not in found:
                found.add(candidate)
                novel_ranks.append(rank)
    first_rank = relevant_ranks[0] if relevant_ranks else None
    dcg = sum(1 / math.log2(rank + 1) for rank in novel_ranks)
    ideal_count = min(len(expected), 10)
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return {
        "gold_found": sorted(found),
        "relevant_ranks": relevant_ranks,
        "novel_relevant_ranks": novel_ranks,
        "first_relevant_rank": first_rank,
        "reciprocal_rank": 1 / first_rank if first_rank else 0.0,
        "recall_at_10": len(found) / len(expected) if expected else 0.0,
        "ndcg_at_10": dcg / idcg if idcg else 0.0,
    }


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate(rows: list[dict[str, Any]], normalized: bool) -> dict[str, Any]:
    prefix = "normalized_" if normalized else ""
    found_key = "normalized_gold_found" if normalized else "gold_found"
    found_total = sum(len(row[found_key]) for row in rows)
    gold_total = sum(len(row["gold_citations"]) for row in rows)
    return {
        "question_count": len(rows),
        "recall_at_10_macro": average([row[f"{prefix}recall_at_10"] for row in rows]),
        "recall_at_10_micro": found_total / gold_total if gold_total else 0.0,
        "mrr": average([row["normalized_mrr"] if normalized else row["reciprocal_rank"] for row in rows]),
        "ndcg_at_10": average([row[f"{prefix}ndcg_at_10"] for row in rows]),
        "questions_with_gold_in_top_10": sum(bool(row[found_key]) for row in rows),
        "gold_citation_count": gold_total,
        "gold_citation_found_count": found_total,
        "diagnosis_counts": dict(Counter(row["retrieval_diagnosis"] for row in rows)) if not normalized else {},
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_outputs(output_dir: Path, raw_results: list[dict[str, Any]], rows: list[dict[str, Any]], result: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "retrieval_results.json", raw_results)
    write_json(output_dir / "retrieval_metrics.json", result)
    with (output_dir / "retrieval_per_question.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})
    strict = result["metrics"]["strict_primary"]
    baseline = result["naive_comparison"]["naive"]
    differences = result["naive_comparison"]["differences"]
    required = ("recall_at_10_macro", "recall_at_10_micro", "mrr", "ndcg_at_10", "questions_with_gold_in_top_10")
    missing = [key for key in required if key not in baseline or key not in differences]
    if missing:
        raise ValueError(f"Naive comparison missing keys {missing}; baseline keys={sorted(baseline)}, difference keys={sorted(differences)}")
    markdown = f"""# Section-based Retrieval Evaluation - NitiBench Tax

## Scope

This run retrieves every Tax query from all 5,127 section-based nodes in `chunking/golden/nodes.json`. It initialises only the human-finetuned hybrid BGE-M3 retriever; it does not initialise an LLM, Ollama client, augmenter, NitiLink, or external API. `type: golden` is used solely as the repository's section-based corpus strategy.

## Strict primary metrics

| Metric | Section-based no-ref | Naive 553/50 | Absolute difference |
|---|---:|---:|---:|
| Recall@10 macro | {strict['recall_at_10_macro']:.6f} | {baseline['recall_at_10_macro']:.6f} | {differences['recall_at_10_macro']:+.6f} |
| Recall@10 micro | {strict['recall_at_10_micro']:.6f} | {baseline['recall_at_10_micro']:.6f} | {differences['recall_at_10_micro']:+.6f} |
| MRR | {strict['mrr']:.6f} | {baseline['mrr']:.6f} | {differences['mrr']:+.6f} |
| NDCG@10 | {strict['ndcg_at_10']:.6f} | {baseline['ndcg_at_10']:.6f} | {differences['ndcg_at_10']:+.6f} |
| Any gold in top-10 | {strict['questions_with_gold_in_top_10']}/50 | {baseline['questions_with_gold_in_top_10']}/50 | {differences['questions_with_gold_in_top_10']:+d} |

## Validation

- Dataset rows: {result['validation']['dataset_count']}; result entries: {result['validation']['result_count']}.
- Missing indices: {result['validation']['missing_indices'] or 'none'}; duplicate indices: {result['validation']['duplicate_indices'] or 'none'}.
- Non-top-10 entries: {result['validation']['non_top_10_indices'] or 'none'}.
- Retrieved IDs absent from the section corpus: {result['validation']['unmapped_retrieved_node_ids'] or 'none'}.
- Gold IDs absent from the section corpus: {result['validation']['unmapped_gold_ids'] or 'none'}.

Strict matching is primary. Supplemental normalisation only collapses whitespace and removes a leading Thai legal-section prefix or English `section` prefix; it never affects the primary metrics.
"""
    (output_dir / "retrieval_metrics.md").write_text(markdown, encoding="utf-8")


def deterministic_top_k(candidates: list[dict[str, Any]], k: int = 10) -> list[dict[str, Any]]:
    return sorted(candidates, key=lambda item: (-item["score"], item["id"]))[:k]


def build_index(nodes: list[TextNode], embedding_batch_size: int) -> BGEM3Index:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return BGEM3Index(nodes=nodes, model_name=MODEL_NAME, show_progress=True, batch_size=embedding_batch_size, weights_for_different_modes=WEIGHTS)


def retrieve_candidates(index: BGEM3Index, questions: list[str]) -> list[list[dict[str, Any]]]:
    retriever = index.as_retriever(similarity_top_k=10)
    return [[{"id": item.node.id_, "score": float(item.score)} for item in retriever.retrieve(question)] for question in questions]


def sharded_candidates(nodes: list[TextNode], questions: list[str], shard_size: int, embedding_batch_size: int, output_dir: Path, checkpoint: bool, finalize_only: bool = False) -> list[list[dict[str, Any]]]:
    merged = [[] for _ in questions]
    shard_count = math.ceil(len(nodes) / shard_size)
    seen_ids: set[str] = set()
    for shard_number in range(shard_count):
        shard_nodes = nodes[shard_number * shard_size:(shard_number + 1) * shard_size]
        if any(node.id_ in seen_ids for node in shard_nodes):
            raise ValueError("Duplicate node ID across shards.")
        seen_ids.update(node.id_ for node in shard_nodes)
        checkpoint_path = output_dir / f"shard_{shard_number + 1:03d}_candidates.json"
        if checkpoint and checkpoint_path.is_file():
            shard_results = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        else:
            if finalize_only:
                raise FileNotFoundError(f"Finalize-only requires checkpoint: {checkpoint_path}")
            print(f"Shard {shard_number + 1}/{shard_count}: indexing {len(shard_nodes)} nodes")
            index = build_index(shard_nodes, embedding_batch_size)
            shard_results = retrieve_candidates(index, questions)
            if checkpoint:
                write_json(checkpoint_path, shard_results)
            del index
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        for question_number, candidates in enumerate(shard_results):
            merged[question_number].extend(candidates)
    return [deterministic_top_k(candidates) for candidates in merged]


def main() -> None:
    args = parse_args()
    require_file(args.config, "Config YAML")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Config must parse to a mapping.")
    strategies = config.get("chunking_strategy", [])
    if strategies != [{"type": "golden"}]:
        raise ValueError("This adapter only accepts chunking_strategy: [{type: golden}].")
    if config.get("model_names") != ["wangchan-rerank-multi"]:
        raise ValueError("This adapter requires model_names: [wangchan-rerank-multi].")
    if config.get("k") != [10]:
        raise ValueError("This adapter requires k: [10].")
    embedding_batch_size = config.get("embedding_batch_size", 32)
    if not isinstance(embedding_batch_size, int) or embedding_batch_size < 1:
        raise ValueError("embedding_batch_size must be a positive integer.")
    shard_size = config.get("retrieval_shard_size", 256)
    if not isinstance(shard_size, int) or shard_size < 10:
        raise ValueError("retrieval_shard_size must be an integer of at least 10.")

    dataset_path = resolve_path(config["tax_data_path"])
    nodes_path = PROJECT_DIR / "chunking" / "golden" / "nodes.json"
    output_dir = args.output_dir or resolve_path(config["output_path"])
    require_file(dataset_path, "Tax dataset")
    require_file(nodes_path, "Section-based nodes")
    print(f"config: {args.config.resolve()}")
    print(f"dataset: {dataset_path}")
    print(f"corpus: {nodes_path}")
    print(f"output: {output_dir}")
    print(f"model: {MODEL_NAME}; weights (dense/sparse/multi-vector): {WEIGHTS}; top-k: 10; embedding batch size: {embedding_batch_size}; shard size: {shard_size}")
    print("offline mode: HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1; no LLM/augmenter is imported")

    with dataset_path.open("r", encoding="utf-8-sig", newline="") as handle:
        dataset = list(csv.DictReader(handle))
    if len(dataset) != 50:
        raise ValueError(f"Expected 50 Tax rows, found {len(dataset)}.")
    raw_nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
    if not isinstance(raw_nodes, list) or len(raw_nodes) != 5127:
        raise ValueError(f"Expected 5,127 section nodes, found {len(raw_nodes) if isinstance(raw_nodes, list) else 'non-list'}.")
    nodes = [TextNode(**item) for item in raw_nodes]
    node_ids = {node.id_ for node in nodes}
    if len(node_ids) != len(nodes):
        raise ValueError("Section corpus contains duplicate node IDs.")

    if args.smoke_nodes is not None:
        if args.smoke_nodes < 1 or args.smoke_nodes > len(nodes):
            raise ValueError(f"--smoke-nodes must be between 1 and {len(nodes)}.")
        nodes = nodes[:args.smoke_nodes]
        node_ids = {node.id_ for node in nodes}
        print(f"SMOKE TEST: building/querying {len(nodes)} nodes only; no retrieval metrics will be written.")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "retrieval_results.json"
    raw_results: list[dict[str, Any]] = []
    if args.resume and raw_path.is_file():
        candidate = json.loads(raw_path.read_text(encoding="utf-8"))
        if isinstance(candidate, list):
            raw_results = candidate
    completed = {str(item.get("idx")) for item in raw_results if isinstance(item, dict)}
    if completed and not completed <= {f"{number:04d}" for number in range(50)}:
        raise ValueError("Resume file contains an invalid idx.")

    start = time.perf_counter()
    if args.smoke_nodes is not None:
        index = build_index(nodes, embedding_batch_size)
        retriever = index.as_retriever(similarity_top_k=10)
        smoke_results = retriever.retrieve(dataset[0]["question"])
        if len(smoke_results) != 10 or any(item.node.id_ not in node_ids for item in smoke_results):
            raise RuntimeError("Smoke test failed: expected 10 retrieved IDs from the smoke corpus.")
        write_json(output_dir / "smoke_test.json", {"node_count": len(nodes), "embedding_batch_size": embedding_batch_size, "weights_dense_sparse_multi_vector": WEIGHTS, "top_k": 10, "retrieved_ids": [item.node.id_ for item in smoke_results], "cuda_memory_allocated_bytes": torch.cuda.memory_allocated() if torch.cuda.is_available() else 0, "cuda_memory_reserved_bytes": torch.cuda.memory_reserved() if torch.cuda.is_available() else 0})
        print("Smoke test passed: dense/sparse/multi-vector BGEM3Index returned 10 in-corpus IDs.")
        return
    questions = [row["question"] for row in dataset]
    if args.validate_sharding:
        validation_nodes = nodes[:128]
        single_index = build_index(validation_nodes, embedding_batch_size)
        single = retrieve_candidates(single_index, questions)
        del single_index
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        sharded = sharded_candidates(validation_nodes, questions, 64, embedding_batch_size, output_dir, checkpoint=False)
        expected = [deterministic_top_k(items) for items in single]
        id_mismatches = [number for number, (left, right) in enumerate(zip(expected, sharded)) if [item["id"] for item in left] != [item["id"] for item in right]]
        score_deltas = [abs(left_item["score"] - right_item["score"]) for left, right in zip(expected, sharded) for left_item, right_item in zip(left, right) if left_item["id"] == right_item["id"]]
        diagnostic = {"subset_nodes": 128, "shard_size": 64, "queries": 50, "id_mismatch_indices": id_mismatches, "max_same_id_score_delta": max(score_deltas, default=0.0), "first_single": expected[0], "first_sharded": sharded[0]}
        write_json(output_dir / "sharding_validation.json", diagnostic)
        if id_mismatches or diagnostic["max_same_id_score_delta"] > 1e-6:
            raise RuntimeError("Sharding validation failed; see sharding_validation.json for IDs and score deltas.")
        print("Sharding validation passed: IDs match and score delta is within 1e-6 for all 50 queries.")
        return
    candidates = sharded_candidates(nodes, questions, shard_size, embedding_batch_size, output_dir, checkpoint=True, finalize_only=args.finalize_only)
    raw_results = [{"idx": f"{number:04d}", "question": row["question"], "retrieved_ids": [item["id"] for item in candidates[number]], "scores": [item["score"] for item in candidates[number]]} for number, row in enumerate(dataset)]
    write_json(raw_path, raw_results)
    elapsed_seconds = time.perf_counter() - start

    by_idx = {str(item["idx"]): item for item in raw_results}
    seen = [str(item.get("idx")) for item in raw_results]
    expected = [f"{number:04d}" for number in range(50)]
    duplicate = sorted(index for index, count in Counter(seen).items() if count > 1)
    missing = sorted(set(expected) - set(seen))
    if len(raw_results) != 50 or missing or duplicate:
        raise ValueError(f"Incomplete retrieval output: rows={len(raw_results)}, missing={missing}, duplicate={duplicate}.")
    rows: list[dict[str, Any]] = []
    unmapped_retrieved: set[str] = set()
    unmapped_gold: set[str] = set()
    non_top_10: list[str] = []
    for number, dataset_row in enumerate(dataset):
        idx = f"{number:04d}"
        retrieved = by_idx[idx]["retrieved_ids"]
        if len(retrieved) != 10:
            non_top_10.append(idx)
        unmapped_retrieved.update(item for item in retrieved if item not in node_ids)
        gold = gold_ids(dataset_row)
        unmapped_gold.update(item for item in gold if item not in node_ids)
        strict = metric_row(gold, retrieved, normalized=False)
        normalized = metric_row(gold, retrieved, normalized=True)
        first = strict["first_relevant_rank"]
        diagnosis = "retrieval_failure" if first is None else ("retrieval_success" if first <= 5 else "ranking_issue")
        rows.append({"idx": idx, "question": dataset_row["question"], "gold_citations": gold, "retrieved_top_10": retrieved, "relevant_ranks": strict["relevant_ranks"], "novel_relevant_ranks": strict["novel_relevant_ranks"], "gold_found": strict["gold_found"], "gold_found_in_top_10": bool(strict["gold_found"]), "all_gold_found_in_top_10": len(strict["gold_found"]) == len(gold), "first_relevant_rank": first, "reciprocal_rank": strict["reciprocal_rank"], "recall_at_10": strict["recall_at_10"], "ndcg_at_10": strict["ndcg_at_10"], "normalized_gold_found": normalized["gold_found"], "normalized_recall_at_10": normalized["recall_at_10"], "normalized_mrr": normalized["reciprocal_rank"], "normalized_ndcg_at_10": normalized["ndcg_at_10"], "retrieval_diagnosis": diagnosis})

    naive_metrics_path = PROJECT_DIR / "results" / "current" / "retrieval_evaluation" / "retrieval_metrics.json"
    require_file(naive_metrics_path, "Naive retrieval metrics")
    naive_document = json.loads(naive_metrics_path.read_text(encoding="utf-8"))
    try:
        naive = naive_document["metrics"]["strict_primary"]
    except (KeyError, TypeError) as exc:
        available = sorted(naive_document.keys()) if isinstance(naive_document, dict) else type(naive_document).__name__
        raise ValueError(f"Naive metrics schema must contain metrics.strict_primary; root keys={available}") from exc
    required_naive = ("recall_at_10_macro", "recall_at_10_micro", "mrr", "ndcg_at_10", "questions_with_gold_in_top_10")
    missing_naive = [key for key in required_naive if key not in naive]
    if missing_naive:
        raise ValueError(f"Naive metrics missing {missing_naive}; strict_primary keys={sorted(naive)}")
    naive = {key: naive[key] for key in required_naive}
    strict_metrics = aggregate(rows, normalized=False)
    naive_comparison = {"naive": naive, "differences": {key: strict_metrics[key] - value for key, value in naive.items()}}
    validation = {"dataset_count": len(dataset), "corpus_node_count": len(nodes), "result_count": len(raw_results), "missing_indices": missing, "duplicate_indices": duplicate, "non_top_10_indices": non_top_10, "unmapped_retrieved_node_ids": sorted(unmapped_retrieved), "unmapped_gold_ids": sorted(unmapped_gold), "gold_used_as_retrieval_input": False, "augmenter_or_nitilink_used": False, "llm_or_api_used": False, "offline_mode": True}
    result = {"evaluation": {"name": "section_based_no_ref", "corpus_strategy": "golden (section-based)", "model": MODEL_NAME, "weights_dense_sparse_multi_vector": WEIGHTS, "top_k": 10, "offline": True}, "inputs": {"config": str(args.config), "dataset": str(dataset_path), "nodes": str(nodes_path)}, "metrics": {"strict_primary": strict_metrics, "normalized_supplemental": aggregate(rows, normalized=True)}, "naive_comparison": naive_comparison, "validation": validation, "runtime": {"elapsed_seconds": elapsed_seconds}, "per_question": rows}
    write_outputs(output_dir, raw_results, rows, result)
    print(f"Completed in {elapsed_seconds:.1f}s")
    print(json.dumps(strict_metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

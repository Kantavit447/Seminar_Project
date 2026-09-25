"""Run selected NitiBench-Tax questions against OpenThai (when explicitly requested)."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys

from src.client import DEFAULT_OPTIONS, MODEL
from src.runner import load_questions, run_questions, select_questions


DATASET = Path("data/nitibench_tax_50.csv")
RESULTS = Path("results")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--limit", type=int, help="Run the first N questions.")
    mode.add_argument("--indices", help="Comma-separated source indexes, e.g. 0000,0001.")
    mode.add_argument("--all", action="store_true", help="Run all questions (explicit opt-in).")
    parser.add_argument("--run-name", required=True, help="Name for results/<run-name>/.")
    parser.add_argument("--dry-run", action="store_true", help="Preview selected requests without calling the API.")
    return parser


def print_dry_run(questions) -> None:
    """Print the exact request inputs without creating a client or output files."""
    system_prompt = None  # No system prompt is configured for the current request format.
    print("Dry run: no OpenThai API request will be made.")
    print(f"Model: {MODEL}")
    print("Settings: " + json.dumps(DEFAULT_OPTIONS, ensure_ascii=False))
    print("System prompt: " + (system_prompt or "(none)"))
    for row in questions.itertuples(index=False):
        request_preview = {"model": MODEL, "messages": [{"role": "user", "content": row.question}],
                           "temperature": DEFAULT_OPTIONS["temperature"],
                           "max_tokens": DEFAULT_OPTIONS["max_tokens"],
                           "extra_body": {"rag": DEFAULT_OPTIONS["rag"], "thinking": DEFAULT_OPTIONS["thinking"]}}
        print(f"\nsource_index: {row.source_index}")
        print(f"question: {row.question}")
        print("request_preview: " + json.dumps(request_preview, ensure_ascii=False))


def main() -> int:
    args = build_parser().parse_args()
    if args.limit is not None and args.limit < 1:
        print("--limit must be at least 1.", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.run_name):
        print("--run-name may contain letters, numbers, '.', '_', and '-'.", file=sys.stderr)
        return 2
    if not DATASET.is_file():
        print(f"Dataset not found: {DATASET}. Run scripts/import_tax.py first.", file=sys.stderr)
        return 1
    frame = load_questions(DATASET)
    indices = args.indices.split(",") if args.indices else None
    questions = select_questions(frame, limit=args.limit, indices=indices, all_rows=args.all)
    if questions.empty:
        print("No questions matched the selection.", file=sys.stderr)
        return 1
    if args.dry_run:
        print_dry_run(questions)
        return 0
    output_dir = RESULTS / args.run_name
    output_dir.mkdir(parents=True, exist_ok=True)
    config = {"run_name": args.run_name, "dataset": str(DATASET), "limit": args.limit,
              "indices": indices, "all": args.all, "selected": len(questions),
              "started_at": datetime.now(timezone.utc).isoformat()}
    (output_dir / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = run_questions(questions, output_dir)
    summary.update({"run_name": args.run_name, "completed_at": datetime.now(timezone.utc).isoformat()})
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

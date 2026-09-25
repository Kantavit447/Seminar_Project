"""Dataset selection and result writing for benchmark runs."""

import json
import time
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.client import complete
from src.parsing import parse_response

REQUEST_DELAY_SECONDS = 3.2


def load_questions(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"source_index": "string", "question": "string"})
    required = {"source_index", "question"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Dataset is missing columns: {', '.join(sorted(missing))}")
    frame["source_index"] = frame["source_index"].astype(str).str.zfill(4)
    return frame


def select_questions(frame: pd.DataFrame, *, limit: int | None, indices: Iterable[str] | None, all_rows: bool) -> pd.DataFrame:
    if indices:
        wanted = [str(index).strip().zfill(4) for index in indices if str(index).strip()]
        return frame[frame["source_index"].isin(wanted)].copy()
    if limit is not None:
        return frame.head(limit).copy()
    if all_rows:
        return frame.copy()
    raise ValueError("Choose --limit, --indices, or --all; full-dataset runs require --all.")


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_questions(questions: pd.DataFrame, output_dir: Path) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    responses_path = output_dir / "responses.jsonl"
    errors_path = output_dir / "errors.jsonl"
    # Create both artifacts even when a run has only successes or only failures.
    responses_path.touch(exist_ok=True)
    errors_path.touch(exist_ok=True)
    succeeded = failed = 0
    rows = list(questions.itertuples(index=False))
    for position, row in enumerate(rows):
        started = time.perf_counter()
        try:
            parsed = parse_response(complete(row.question))
            record = {"source_index": row.source_index, "question": row.question, **parsed,
                      "latency_seconds": round(time.perf_counter() - started, 6)}
            append_jsonl(responses_path, record)
            succeeded += 1
        except Exception as exc:
            append_jsonl(errors_path, {"source_index": row.source_index, "question": row.question,
                                       "error": str(exc), "latency_seconds": round(time.perf_counter() - started, 6)})
            failed += 1
        if position < len(rows) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)
    return {"requested": len(questions), "succeeded": succeeded, "failed": failed}

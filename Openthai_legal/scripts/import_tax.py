"""Create the inference-only NitiBench-Tax dataset without answer material."""

from pathlib import Path
import sys

import pandas as pd

SOURCE = Path(r"C:\NitiBench\Project_meandyou\test_data\hf_tax.csv")
DESTINATION = Path(__file__).resolve().parents[1] / "data" / "nitibench_tax_50.csv"


def main() -> int:
    if not SOURCE.is_file():
        print(f"Source dataset not found: {SOURCE}", file=sys.stderr)
        return 1
    data = pd.read_csv(SOURCE, dtype=str)
    if "question" not in data.columns:
        print("Source dataset has no 'question' column.", file=sys.stderr)
        return 1
    inference = pd.DataFrame({
        "source_index": [f"{index:04d}" for index in range(min(50, len(data)))],
        "question": data.loc[:49, "question"].fillna(""),
    })
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    inference.to_csv(DESTINATION, index=False, encoding="utf-8")
    print(f"Wrote {len(inference)} questions to {DESTINATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

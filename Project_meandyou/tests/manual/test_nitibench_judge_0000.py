import ast
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from openai import OpenAI

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

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from lrg.prompting import PromptManager

BASE_URL = "https://gen.ai.kku.ac.th/api/v1"
JUDGE_MODEL = "gpt-5.4-mini"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Judge one Tax item from a No-RAG and a Vanilla RAG response file."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_DIR / "test_data" / "hf_tax.csv",
        help="Tax CSV containing question and reference_answer.",
    )
    parser.add_argument(
        "--no-rag-input",
        type=Path,
        default=(
            PROJECT_DIR
            / "results"
            / "current"
            / "parametric_qwen_controlled"
            / "parametric-qwen"
            / "tax_response.json"
        ),
        help="No-RAG response JSON to judge.",
    )
    parser.add_argument(
        "--rag-input",
        type=Path,
        default=(
            PROJECT_DIR
            / "results"
            / "current"
            / "vanilla_rag_qwen_controlled"
            / "chunk-human-finetuned-bge-m3-no-ref-qwen"
            / "tax_response.json"
        ),
        help="Vanilla RAG response JSON to judge.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_DIR / "results" / "tests" / "judge" / "judge_test_0000.json",
        help="JSON file to write the judge result.",
    )
    parser.add_argument(
        "--idx",
        default="0000",
        help="Dataset/result index to judge (default: 0000).",
    )
    return parser.parse_args()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            f"{label} does not exist or is not a file: {path}"
        )


def load_result(path: Path, idx: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    for item in data:
        item_idx = str(item.get("idx", "")).zfill(4)
        if item_idx == idx:
            return item

    raise ValueError(f"Cannot find idx={idx} in {path}")


def extract_answer(item: dict[str, Any]) -> str:
    content = item.get("content", {})

    if not isinstance(content, dict):
        return ""

    return str(content.get("answer", "")).strip()


def build_query(
    question: str,
    reference_answer: str,
    student_answer: str,
) -> str:
    """
    ใช้ชื่อ tag แบบเดียวกับ prompt Tax เดิมของ NitiBench
    """
    return (
        f"<ข้อหารือ> {question} </ข้อหารือ>\n"
        f"<reference_answer> {reference_answer} </reference_answer>\n"
        f"<student_answer> {student_answer} </student_answer>"
    )


def clean_json_text(text: str) -> str:
    text = text.strip()

    # ลบ Markdown code fence หากโมเดลใส่มา
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    # ดึงเฉพาะ JSON object
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found:\n{text}")

    return match.group(0)

def normalize_judge_keys(result: dict[str, Any]) -> dict[str, Any]:
    """
    Prompt เดิมของ NitiBench มีชื่อ key ไม่สอดคล้องกัน:
    - บางส่วนใช้ student_points / reference_points
    - schema และตัวอย่างใช้ student_point / reference_point

    แปลงให้เป็นรูปแบบมาตรฐานของ system_eval.json
    """
    normalized = dict(result)

    if (
        "student_point" not in normalized
        and "student_points" in normalized
    ):
        normalized["student_point"] = normalized.pop(
            "student_points"
        )

    if (
        "reference_point" not in normalized
        and "reference_points" in normalized
    ):
        normalized["reference_point"] = normalized.pop(
            "reference_points"
        )

    return normalized

def validate_judge_output(result: dict[str, Any]) -> None:
    required_keys = {
        "point_thought",
        "student_point",
        "reference_point",
        "coverage",
        "contradiction",
    }

    missing = required_keys - set(result)
    if missing:
        raise ValueError(f"Missing keys: {sorted(missing)}")

    coverage_score = result["coverage"].get("score")
    contradiction_score = result["contradiction"].get("score")

    allowed_coverage = {
        "no-coverage",
        "partial-coverage",
        "full-coverage",
    }
    allowed_contradiction = {
        "no-contradiction",
        "contradiction",
    }

    if coverage_score not in allowed_coverage:
        raise ValueError(
            f"Invalid coverage score: {coverage_score}"
        )

    if contradiction_score not in allowed_contradiction:
        raise ValueError(
            f"Invalid contradiction score: {contradiction_score}"
        )


def prepare_messages(
    pm: PromptManager,
    query: str,
) -> list[dict[str, str]]:
    """
    ให้ PromptManager ประกอบ few-shot prompt เดิมของ NitiBench
    """
    formatted = pm.get_formatted_prompt(
        query=query,
        task="coverage-contradiction",
        dataset="tax",
        model=JUDGE_MODEL,
    )

    if "messages" not in formatted:
        raise KeyError(
            "PromptManager output does not contain 'messages'. "
            f"Available keys: {list(formatted.keys())}"
        )

    messages = list(formatted["messages"])

    # รองรับกรณี PromptManager แยก system prompt ออกมา
    system_text = formatted.get("system")
    if system_text:
        messages.insert(
            0,
            {
                "role": "system",
                "content": str(system_text),
            },
        )

    return messages


def evaluate_one(
    client: OpenAI,
    pm: PromptManager,
    label: str,
    question: str,
    reference_answer: str,
    student_answer: str,
    target_idx: str,
) -> dict[str, Any]:
    query = build_query(
        question=question,
        reference_answer=reference_answer,
        student_answer=student_answer,
    )

    messages = prepare_messages(pm=pm, query=query)

    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=messages,
        temperature=0,
        max_tokens=1800,
        stream=False,
    )

    raw_content = response.choices[0].message.content or ""
    parsed = json.loads(clean_json_text(raw_content))
    parsed = normalize_judge_keys(parsed)
    validate_judge_output(parsed)

    usage = (
        response.usage.model_dump()
        if response.usage is not None
        else {}
    )

    quota = getattr(response, "model_quota", None)

    return {
        "system": label,
        "idx": target_idx,
        "student_answer": student_answer,
        "judge_result": parsed,
        "usage": usage,
        "model_quota": quota,
        "raw_response": raw_content,
        "message_count": len(messages),
    }


def main() -> None:
    args = parse_args()
    target_idx = str(args.idx).zfill(4)

    print("NitiBench judge paths")
    print(f"Input dataset : {args.dataset}")
    print(f"Input No-RAG  : {args.no_rag_input}")
    print(f"Input RAG     : {args.rag_input}")
    print(f"Output        : {args.output}")
    print(f"Target index  : {target_idx}")

    require_file(args.dataset, "Input dataset file")
    require_file(args.no_rag_input, "No-RAG input file")
    require_file(args.rag_input, "Vanilla RAG input file")

    api_key = os.environ.get("KKU_API_KEY")
    if not api_key:
        raise RuntimeError(
            "KKU_API_KEY is missing. Set it in PowerShell first."
        )

    tax_df = pd.read_csv(
        args.dataset,
        encoding="utf-8-sig",
        converters={
            "relevant_laws": ast.literal_eval,
        },
    )

    try:
        row = tax_df.iloc[int(target_idx)]
    except (IndexError, ValueError) as error:
        raise ValueError(
            f"Target index {target_idx} is not available in dataset: {args.dataset}"
        ) from error

    question = str(row["question"])
    reference_answer = str(row["reference_answer"])

    no_rag_item = load_result(args.no_rag_input, target_idx)
    rag_item = load_result(args.rag_input, target_idx)

    no_rag_answer = extract_answer(no_rag_item)
    rag_answer = extract_answer(rag_item)

    client = OpenAI(
        api_key=api_key,
        base_url=BASE_URL,
    )

    pm = PromptManager()

    results = []

    print("Evaluating No-RAG...")
    results.append(
        evaluate_one(
            client=client,
            pm=pm,
            label="no-rag",
            question=question,
            reference_answer=reference_answer,
            student_answer=no_rag_answer,
            target_idx=target_idx,
        )
    )

    print("Evaluating Vanilla RAG...")
    results.append(
        evaluate_one(
            client=client,
            pm=pm,
            label="vanilla-rag",
            question=question,
            reference_answer=reference_answer,
            student_answer=rag_answer,
            target_idx=target_idx,
        )
    )

    output = {
        "judge_model": JUDGE_MODEL,
        "idx": target_idx,
        "question": question,
        "reference_answer": reference_answer,
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("\nJudge results")
    print("=" * 70)

    for item in results:
        judge = item["judge_result"]
        usage = item["usage"]

        print(f"\nSystem: {item['system']}")
        print(
            "Coverage:",
            judge["coverage"]["score"],
        )
        print(
            "Contradiction:",
            judge["contradiction"]["score"],
        )
        print(
            "Tokens:",
            usage.get("total_tokens", "unknown"),
        )
        print(
            "Quota:",
            item["model_quota"],
        )

    print("\n" + "=" * 70)
    print(f"Saved to: {args.output}")


if __name__ == "__main__":
    main()

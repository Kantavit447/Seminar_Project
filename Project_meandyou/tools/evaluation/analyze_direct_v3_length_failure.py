"""Read-only summary for a saved Direct v3 parse-failure artifact.

This utility never contacts an LLM or retriever.  It only analyzes the raw
completion written by the opt-in diagnostic hook.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path


DEFAULT_ARTIFACT = Path(
    "results/current/common_interface_v3/diagnostics/direct_v3_length_failure/"
    "runtime_0004_source_0008_attempt_1.json"
)
DEFAULT_PROMPT_DUMP = Path(
    "results/current/debug_prompts/"
    "section_based_direct_v3_runtime_0004_source_0008_final_prompt.txt"
)
DEFAULT_OUTPUT = Path(
    "results/current/common_interface_v3/diagnostics/direct_v3_length_failure/"
    "diagnostic_summary.md"
)


def load_prompt_question(prompt_path: Path) -> str | None:
    if not prompt_path.is_file():
        return None
    prompt = prompt_path.read_text(encoding="utf-8")
    match = re.search(r"\[QUESTION\]\s*(.*?)\s*\[/QUESTION\]", prompt, re.DOTALL)
    return match.group(1).strip() if match else None


def law_text_copy_count(raw: str, prompt_path: Path) -> int | None:
    if not prompt_path.is_file():
        return None
    prompt = prompt_path.read_text(encoding="utf-8")
    bodies = re.findall(
        r"LAW_TEXT:\s*(.*?)\s*\[/LEGAL_PROVISION_\d+\]", prompt, re.DOTALL
    )
    copies = 0
    for body in bodies:
        normalized = " ".join(body.split())
        # A 60-character prefix avoids false positives from ordinary law names.
        if len(normalized) >= 60 and normalized[:60] in " ".join(raw.split()):
            copies += 1
    return copies


def repeated_ngram_stats(raw: str, width: int = 8) -> tuple[int, int]:
    words = re.findall(r"\S+", raw)
    grams = [tuple(words[i : i + width]) for i in range(max(0, len(words) - width + 1))]
    if not grams:
        return 0, 0
    counts = Counter(grams)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return repeated, max(counts.values())


def active_field(raw: str) -> str:
    candidates = []
    for field in ("analysis", "answer", "citations"):
        match = list(re.finditer(rf'"{field}"\s*:', raw))
        if match:
            candidates.append((match[-1].start(), field))
    return max(candidates)[1] if candidates else "not_detected"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--prompt-dump", type=Path, default=DEFAULT_PROMPT_DUMP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    record = json.loads(args.artifact.read_text(encoding="utf-8"))
    raw = record.get("raw_response_content")
    if not isinstance(raw, str):
        raw_path = args.artifact.with_name(args.artifact.stem + "_raw.txt")
        raw = raw_path.read_text(encoding="utf-8") if raw_path.is_file() else ""

    stripped = raw.lstrip()
    starts_json = stripped.startswith("{")
    ends_json = raw.rstrip().endswith("}")
    try:
        json.loads(raw)
        valid_json = True
    except json.JSONDecodeError:
        valid_json = False

    paragraphs = [" ".join(item.split()) for item in re.split(r"\n\s*\n", raw) if item.strip()]
    duplicate_paragraphs = sum(count - 1 for count in Counter(paragraphs).values() if count > 1)
    repeated_ngrams, max_ngram_count = repeated_ngram_stats(raw)
    question = load_prompt_question(args.prompt_dump)
    question_repetitions = raw.count(question) if question else None
    usage = record.get("usage") or {}
    citation_start_count = len(re.findall(r'"law"\s*:', raw))

    lines = [
        "# Direct v3 length-failure diagnostic",
        "",
        f"- Artifact: `{args.artifact}`",
        f"- Runtime/source: `{record.get('runtime_idx')}` / `{record.get('source_idx')}`",
        f"- Retry attempt: {record.get('retry_attempt')}",
        f"- Finish reason: `{record.get('finish_reason')}`",
        f"- Exception: `{record.get('exception_type')}: {record.get('exception_message')}`",
        f"- Raw character count: {len(raw)}",
        f"- Prompt tokens: {record.get('prompt_tokens', usage.get('prompt_tokens'))}",
        f"- Completion tokens: {record.get('completion_tokens', usage.get('completion_tokens'))}",
        f"- Starts with JSON object: {starts_json}",
        f"- Ends with closing brace: {ends_json}",
        f"- Valid complete JSON: {valid_json}",
        f"- Field being written at cutoff (last observed): `{active_field(raw)}`",
        f"- Repeated paragraphs: {duplicate_paragraphs}",
        f"- Repeated {8}-grams (excess occurrences): {repeated_ngrams}",
        f"- Maximum identical {8}-gram count: {max_ngram_count}",
        f"- LAW_TEXT bodies with a copied 60-character prefix: {law_text_copy_count(raw, args.prompt_dump)}",
        f"- Full question repetitions in raw completion: {question_repetitions}",
        f"- Citation objects started (\"law\" keys): {citation_start_count}",
        "",
        "## Raw completion tail (maximum 500 characters)",
        "",
        "```text",
        raw[-500:],
        "```",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"diagnostic_summary_path={args.output}")


if __name__ == "__main__":
    main()

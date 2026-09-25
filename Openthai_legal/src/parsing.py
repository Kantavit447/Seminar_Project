"""Normalize OpenThai/OpenAI SDK responses for durable result storage."""

from typing import Any


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_dict(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)


def parse_response(response: Any) -> dict[str, Any]:
    """Extract answer, citations, retrieved documents, and token usage if present."""
    choices = _value(response, "choices", []) or []
    first_choice = choices[0] if choices else None
    message = _value(first_choice, "message", None)
    raw_content = _value(message, "content", "") if message else ""
    usage = _value(response, "usage", None)

    citations = _value(response, "citations", None)
    if citations is None:
        citations = _value(message, "citations", []) if message else []
    documents = _value(response, "retrieved_documents", None)
    if documents is None:
        documents = _value(response, "documents", None)

    return {
        "raw_content": raw_content or "",
        "answer": raw_content or "",
        "citations": _as_dict(citations) or [],
        "retrieved_documents": _as_dict(documents),
        "prompt_tokens": _value(usage, "prompt_tokens") if usage else None,
        "completion_tokens": _value(usage, "completion_tokens") if usage else None,
        "total_tokens": _value(usage, "total_tokens") if usage else None,
    }

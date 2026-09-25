"""OpenThai API client configuration.

This module only constructs a client.  A request is made only when
``complete`` is explicitly called by the benchmark runner.
"""

import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

BASE_URL = "https://api.iapp.co.th/v3/llm/openthai2p0-legal"
MODEL = "openthai2.0-legal"
DEFAULT_OPTIONS: dict[str, Any] = {
    "rag": True,
    "thinking": False,
    "temperature": 0.0,
    "max_tokens": 1024,
}


def create_client() -> OpenAI:
    """Create an SDK client using ``IAPP_API_KEY`` from the environment."""
    load_dotenv()
    api_key = os.getenv("IAPP_API_KEY")
    if not api_key:
        raise RuntimeError("IAPP_API_KEY is not set. Copy .env.example to .env first.")
    return OpenAI(api_key=api_key, base_url=BASE_URL)


def complete(question: str, **overrides: Any) -> Any:
    """Send one question to OpenThai. This is intentionally not called at import time."""
    options = {**DEFAULT_OPTIONS, **overrides}
    client = create_client()
    return client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": question}],
        temperature=options["temperature"],
        max_tokens=options["max_tokens"],
        extra_body={"rag": options["rag"], "thinking": options["thinking"]},
    )

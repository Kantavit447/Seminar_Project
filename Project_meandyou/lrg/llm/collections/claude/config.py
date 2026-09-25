from typing import Dict, List, Optional
from pydantic import BaseModel

# Define a model to represent the configuration
class ClaudeConfig(BaseModel):
    model: str = "claude-3-5-sonnet-20240620"
    max_tokens: int = 1024
    temperature: float = 0.5
    extra_headers: Optional[Dict[str, str]] = {"anthropic-beta": "prompt-caching-2024-07-31"}
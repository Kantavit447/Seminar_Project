from typing import Dict, List, Optional
from pydantic import BaseModel
import os

# Define a model to represent the configuration
class OpenAIConfig(BaseModel):
    model: str = "gpt-4o-2024-08-06"
    max_tokens: int = 2048
    n: int = 1
    temperature: float = 0.5
    seed: int = 69420
    base_url: str = "https://api.openai.com/v1"
    api_key: str = os.environ.get("OPENAI_API_KEY", "")
    
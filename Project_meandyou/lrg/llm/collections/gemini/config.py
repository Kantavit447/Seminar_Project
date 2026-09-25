from typing import Dict, List, Optional
from pydantic import BaseModel

class GeminiGenerationConfig(BaseModel):
    max_output_tokens: int = 1024
    temperature: float = 0.5
    candidate_count: int = 1
    response_mime_type: str = "application/json"
    # seed: int = 69420

# Define a model to represent the configuration
class GeminiConfig(BaseModel):
    model: str = "gemini-1.5-flash-002"
    generation_config: GeminiGenerationConfig= GeminiGenerationConfig()
    tools: List = []
    safety_settings: Dict[str, str] = {
        "HARM_CATEGORY_HARASSMENT": "block_none",
        "HARM_CATEGORY_HATE_SPEECH": "block_none",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "block_none",
        "HARM_CATEGORY_DANGEROUS_CONTENT": "block_none"
        }
    long_context: bool = False

    
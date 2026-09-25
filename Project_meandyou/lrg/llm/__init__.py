from typing import Dict

# ใช้เฉพาะ OpenAI-compatible model สำหรับ Ollama/Qwen
from .collections.openai import OpenAIConfig, OpenAIModel

# ส่วนที่ยังไม่ใช้ในงานนี้ คอมเมนต์ไว้ก่อน
# from .collections.claude import ClaudeConfig, ClaudeModel
# from .collections.gemini import GeminiConfig, GeminiModel


MAP_MODEL = {
    "qwen": (OpenAIConfig, OpenAIModel),

    # เก็บไว้ภายหลังถ้าต้องการทดลองโมเดลอื่น
    # "gpt": (OpenAIConfig, OpenAIModel),
    # "o1": (OpenAIConfig, OpenAIModel),
    # "claude": (ClaudeConfig, ClaudeModel),
    # "gemini": (GeminiConfig, GeminiModel),
    # "aisingapore/gemma2": (OpenAIConfig, OpenAIModel),
    # "typhoon": (OpenAIConfig, OpenAIModel),
}


def init_llm(config: Dict):
    model_name = config["model"]

    # qwen2.5:7b ต้องถูกจัดเข้ากลุ่ม "qwen"
    if model_name.lower().startswith("qwen"):
        name = "qwen"
    else:
        name = model_name.split("-")[0].lower()

    assert name in MAP_MODEL, (
        f"Unrecognized model name: {model_name}. "
        f"Available model groups: {list(MAP_MODEL.keys())}"
    )

    config_class, model_class = MAP_MODEL[name]

    model_config = config_class(**config)
    print(model_config.model_dump())

    model = model_class(config=model_config)
    return model
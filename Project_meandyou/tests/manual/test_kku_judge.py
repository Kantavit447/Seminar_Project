import json
import os

from openai import OpenAI


client = OpenAI(
    api_key=os.environ["KKU_API_KEY"],
    base_url="https://gen.ai.kku.ac.th/api/v1",
)

system_prompt = """
ประเมินคำตอบและตอบเป็น JSON เท่านั้น ห้ามใช้ Markdown

รูปแบบผลลัพธ์:
{
  "coverage": {
    "score": "full-coverage"
  },
  "contradiction": {
    "score": "no-contradiction"
  }
}

coverage.score เลือกได้เฉพาะ:
- full-coverage
- partial-coverage
- no-coverage

contradiction.score เลือกได้เฉพาะ:
- contradiction
- no-contradiction
""".strip()

user_prompt = """
คำตอบอ้างอิง: บริษัทมีสิทธิหักภาษีซื้อ
คำตอบที่ประเมิน: บริษัทมีสิทธิหักภาษีซื้อ
""".strip()

response = client.chat.completions.create(
    model="gpt-5.4-mini",
    messages=[
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ],
    temperature=0,
    max_tokens=200,
    stream=False,
)

content = response.choices[0].message.content

print("\nRaw response:")
print(content)

try:
    parsed = json.loads(content)
    print("\nParsed JSON:")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))
except json.JSONDecodeError as error:
    print("\nJSON parsing failed:")
    print(error)

print("\nUsage:")
print(response.usage)

print("\nQuota:")
print(getattr(response, "model_quota", None))
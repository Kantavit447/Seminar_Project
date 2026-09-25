import time
import json
import pandas as pd
import ollama

# =====================================================
# Configuration
# =====================================================

MODEL_NAME = "qwen2.5:7b"

DATASET_PATH = "test_data/hf_tax.csv"

OUTPUT_PATH = "results/legacy/baseline/baseline_qwen_tax_json.csv"

SYSTEM_PROMPT = """
คุณคือผู้เชี่ยวชาญด้านกฎหมายไทย

ตอบกลับเป็น JSON เท่านั้น

รูปแบบ

{
  "answer": "...",
  "citations": [
    {
      "law": "...",
      "section": "..."
    }
  ]
}

กฎ

1. answer เป็นภาษาไทย
2. citations เป็นมาตรากฎหมายที่อ้างอิงจริง
3. ถ้าไม่มี citation ให้เป็น []
4. ห้ามมีข้อความก่อน JSON
5. ห้ามมีข้อความหลัง JSON
6. ห้ามใช้ Markdown
7. ห้ามใช้ ```json
8. ตอบเป็น JSON เท่านั้น
"""

# =====================================================
# Load Dataset
# =====================================================

df = pd.read_csv(DATASET_PATH)

print("=" * 80)
print("Model      :", MODEL_NAME)
print("Dataset    :", DATASET_PATH)
print("Questions  :", len(df))
print("=" * 80)

results = []

# =====================================================
# Baseline Inference
# =====================================================

for idx, row in df.iterrows():

    print(f"[{idx+1}/{len(df)}] Running...")

    start = time.time()

    response = ollama.chat(
        model=MODEL_NAME,
        options={
            "temperature": 0,
            "seed": 42,
            "num_predict": 1024
        },
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": row["question"]
            }
        ]
    )

    raw = response.message.content.strip()

    prediction = raw
    citations = []
    parse_success = False

    try:

        obj = json.loads(raw)

        prediction = obj.get("answer", "").strip()

        citations = obj.get("citations", [])

        if not isinstance(citations, list):
            citations = []

        parse_success = True

    except json.JSONDecodeError:
        pass

    elapsed = time.time() - start

    print(prediction[:200].replace("\n", " "))
    print("Citations :", citations)
    print("Parse     :", parse_success)
    print("Time      :", round(elapsed,2), "sec")
    print("-"*80)

    results.append({

        "id": idx,

        "model": MODEL_NAME,

        "question": row["question"],

        "reference_answer": row["reference_answer"],

        "prediction": prediction,

        "raw_response": raw,

        "student_citations": json.dumps(
            citations,
            ensure_ascii=False
        ),

        "parse_success": parse_success,

        "relevant_laws": row["relevant_laws"],

        "response_time_sec": round(elapsed,2)

    })

# =====================================================
# Save
# =====================================================

result_df = pd.DataFrame(results)

result_df.to_csv(
    OUTPUT_PATH,
    index=False,
    encoding="utf-8-sig"
)

print()
print("="*80)
print("Finished")
print("Saved :", OUTPUT_PATH)
print("="*80)

print()

print("Parse Success :", result_df["parse_success"].sum(), "/", len(result_df))

print()

print(result_df.head())


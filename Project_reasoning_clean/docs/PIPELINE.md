# ลำดับการทำงานของระบบ Direct

> อัปเดต 18 กันยายน 2026: แก้ startup เป็น lazy import แล้ว และนำ dependencies ของ Live Retrieval ออกจาก requirements สำหรับ generation-only ตรวจ imports กับ Saved/Golden แบบ offline ผ่านแล้ว รายละเอียดอยู่ใน [รายงานการแก้ไข](LAZY_IMPORT_FIX_REPORT.md) ข้อความเรื่อง eager imports และข้อจำกัดการตรวจ imports ด้านล่างเป็นสถานะก่อนแก้ ไม่ใช่สถานะล่าสุด


โค้ดแอปพลิเคชัน config, prompt และข้อมูลที่คัดลอกมายังคงตรงกับต้นฉบับทุก byte ให้เรียกคำสั่งจากรากโปรเจกต์และเปิด UTF-8 การย้ายโปรเจกต์ไม่ได้เรียกโมเดลหรือรัน retrieval ใหม่

## การทำงานแบบ Retrieved Context

```text
YAML → script/response_e2e.py::main → EvalDataset
→ init_saved_retriever → SavedRetrievalRetriever.retrieve(question)
→ Ragger.get_prompt_structure
→ NitiLinkAugmenter.__call__/serialize_common_v3
→ PromptManager.get_formatted_prompt
→ Ragger.build_provision_map → build_citation_id_enum_structure
→ OpenAIModel.complete → client.beta.chat.completions.parse
→ ตรวจด้วย Pydantic → map_citation_ids → validate_citations
→ เพิ่ม metadata/usage/timing → evaluate_ragger → tax_response.json
```

อ่านผล retrieval ที่บันทึกไว้จาก `results/current/retrieval_evaluation/section_based_no_ref/retrieval_results.json` ไฟล์นี้เป็นข้อมูลนำเข้า ไม่ใช่ผล generation เก่า Adapter ต้องการ artifact ครบ 50 รายการ แต่ใช้เฉพาะ source ที่เลือกใน engineering split แต่ละข้อมี 10 IDs ไม่ซ้ำกัน รักษาลำดับและคะแนนเดิม ไม่มีการสร้าง embeddings หรือ index ในเส้นทางนี้

## การทำงานแบบ Golden Context

ใช้ลำดับหลักเหมือน Retrieved แต่ `main` กำหนด `retriever=None` และ `golden_retriever=True`

`Ragger.resolve_gold_provisions()` อ่าน `law` และ `sections` จาก `relevant_laws` ตัดช่องว่างรอบข้อความ แล้วสร้าง `law-section` เพื่อค้น node ID ที่ตรงกันทุกตัวอักษร ไม่มี fuzzy fallback และไม่เรียก retrieval หากหาไม่พบจะบันทึก unresolved โดยยังใช้รายการที่หาเจอได้

ส่งเข้า generation เฉพาะคำถามและข้อความกฎหมายที่เลือก ไม่ส่ง `answer` หรือ `reference_answer`

## รูปแบบการอ้างอิงร่วมด้วย P-ID

กำหนด `P1…Pn` ตามลำดับ nodes ด้วย `enumerate(start=1)` แต่ละบล็อกมี `[PROVISION P1]`, `PROVISION_ID`, `LAW_NAME`, `SECTION_ID`, `LAW_TEXT` และรายการ `[ALLOWED_CITATION_IDS]`

สร้าง `List[Literal[...]]` แบบ dynamic ต่อคำถามเพื่อจำกัด ID ที่เลือกได้

- โมเดลส่ง `analysis` ภาษาอังกฤษ, `answer` ภาษาไทย และ `citation_ids`
- ผลใน `response.content` มี `analysis`, `answer` และ `citations:[{law,section}]`
- Mapper ค้น metadata แบบตรงตัว ไม่แก้ความหมายหรือเลือกกฎหมายแทนโมเดล
- ID ซ้ำเก็บครั้งแรกและบันทึกเหตุการณ์
- ID ไม่ถูกต้องถูกบันทึกและไม่รวมในผลสุดท้าย โดยปกติ enum จะปฏิเสธก่อนถึงขั้น mapping
- อนุญาต `citation_ids` เป็นรายการว่าง

## Index และผลลัพธ์

Engineering ใช้ runtime `idx` เป็น `0000..0009` ส่วน `source_idx` รักษาตำแหน่งเดิมในชุด 50 ข้อ เช่น runtime `0004` คือ source `0008` และ runtime `0005` คือ source `0023`

Engineering อนุญาตสูงสุด 5 attempts ตามค่าเริ่มต้น ส่วน diagnostic ที่คัดลอกมาอนุญาต 1 attempt ผลใหม่เขียนตาม `output_path` ใน YAML ส่วนผลอ้างอิงแยกเก็บใต้ `reference_results/`

Resume อาศัยจำนวน responses เดิม ดังนั้นการ reproduce ใหม่ควรเริ่มในตำแหน่งผลลัพธ์ที่ยังว่าง

ยังไม่มี CoT, IRAC, verifier หรือ corrector ในโปรเจกต์นี้

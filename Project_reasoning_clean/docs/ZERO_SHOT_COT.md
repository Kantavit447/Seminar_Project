# Zero-shot CoT แบบหนึ่งรอบ

วันที่: 26 กันยายน 2026

แผนหลักอยู่ใน [RESEARCH_PROTOCOL.md](RESEARCH_PROTOCOL.md) ตามข้อตกลงล่าสุดจะสร้างผลของทุกวิธีก่อน แล้วจึงเตรียม evaluator และประเมินภายหลัง

## สิ่งที่เพิ่ม

- `reasoning_method: zero_shot_cot` สำหรับ Tax, prompt v3, provision_id และ enum
- ใช้ system prompt ของ Direct เดิมทุกตัวอักษร เพิ่มเพียง `Let's think step by step.` ใน user instruction
- เรียกโมเดลหนึ่งรอบเพื่อคืน `analysis`, `answer`, `citation_ids` ตาม schema เดิม ไม่มีตัวอย่าง ไม่มี IRAC และไม่มี verifier
- มี engineering 10 และ diagnostic source `0008` (runtime `0004`) สำหรับทั้ง Saved Retrieved และ Golden
- ชื่อ output, failure directory และ prompt dump แยกจาก Direct
- หาก CoT แบบ Retrieved ไม่มี saved artifact จะหยุดก่อนเข้าสู่ live retrieval

ไม่มีการแก้ SavedRetrievalRetriever, Golden resolver, Ragger, augmenter, P-ID mapping, schema, Direct templates, model wrapper หรือไฟล์ข้อมูล

CoT engineering ใช้ Golden 16k / Retrieved 32k ให้ตรงกับ Direct engineering เดิม เป้าหมาย 32k ร่วมกันใน final test ยังต้องตรวจ context budget ทุกขั้นตาม Protocol ไม่เปลี่ยนค่ารันพร้อมกับการเพิ่ม cue ในรอบนี้

## สถานะและหลักฐาน

การตรวจ offline เป็นการตรวจโครงสร้าง prompt, context, schema และ mapping ไม่ใช่ผลการสร้างคำตอบหรือคะแนนคุณภาพ ยังต้องให้ผู้ใช้รัน Qwen เพื่อยืนยันพฤติกรรมจริง

เครื่องมือตรวจ: `tools/validation/validate_zero_shot_cot_offline.py`

ตรวจ engineering 10 × 2 contexts โดยประกอบ prompt ผ่าน EvalDataset, Saved adapter/Golden resolver, augmenter และ Ragger จริง ใช้เพียง metadata ของโมเดล ไม่สร้าง LLM client และปิดการเชื่อมต่อเครือข่ายระหว่างตรวจ

รายการตรวจรวม: ต่างจาก Direct เพียง cue เดียว, system/context ตรงกัน, Top 10/ลำดับคงเดิม, Golden resolve ครบ, P-ID map และ enum ตรงกัน, ปฏิเสธ ID นอก context, ไม่ส่ง reference answer, และไม่ import live retrieval stack

ผลตรวจที่บันทึกในรอบเพิ่ม CoT: `results/current/offline_validation/zero_shot_cot_20260926.json` ตรวจเพิ่มเติมกับ PromptManager ก่อนแก้เพื่อยืนยันว่า Direct ไม่เปลี่ยนพฤติกรรม

## ตรวจ offline ซ้ำ

รันจาก `C:\NitiBench\Project_reasoning_clean` ไม่ต้อง activate venv เมื่อระบุ interpreter เต็มแบบนี้:

```powershell
.\.venv\Scripts\python.exe -B tools/validation/validate_zero_shot_cot_offline.py
```

คำสั่งนี้ไม่สร้างคำตอบจาก LLM และไม่ให้คะแนนคำตอบ

ดู final prompt ของสองเงื่อนไขโดยไม่เรียกโมเดล:

```powershell
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/golden_qwen_zero_shot_cot_v3_citation_id_enum_diagnostic_source_0008_ctx16384.yaml --dump-final-prompt
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/section_based_rag_qwen_zero_shot_cot_v3_citation_id_enum_diagnostic_source_0008_ctx32768.yaml --dump-final-prompt
```

จะได้ไฟล์ใน `results/current/debug_prompts/` ชื่อ `golden_zero_shot_cot_...` และ `section_based_zero_shot_cot_...` ตาม source/runtime index โดยต้องเห็น `llm_calls=0`

## ผู้ใช้รันโมเดล: เริ่ม Golden หนึ่งข้อ

คำสั่งในส่วนนี้เรียก Qwen จริง ใช้แยกจากคำสั่ง offline ด้านบน ให้ตรวจว่า output ของการรันนั้นยังไม่มีผลเดิมก่อน เพราะ runner ปัจจุบันอาจนำผลเดิมมาใช้ต่อ

```powershell
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/golden_qwen_zero_shot_cot_v3_citation_id_enum_diagnostic_source_0008_ctx16384.yaml
```

ไฟล์คำตอบ:

`results/current/common_interface_v3/diagnostics/golden_zero_shot_cot_v3_citation_id_enum_source_0008_ctx16384/chunk-golden-no-ref-qwen/tax_response.json`

เมื่อตรวจผลหนึ่งข้อผ่าน ค่อยรัน Saved Retrieved หนึ่งข้อ:

```powershell
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/section_based_rag_qwen_zero_shot_cot_v3_citation_id_enum_diagnostic_source_0008_ctx32768.yaml
```

ไฟล์คำตอบ:

`results/current/common_interface_v3/diagnostics/section_based_zero_shot_cot_v3_citation_id_enum_source_0008_ctx32768/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response.json`

เลือก source `0008` เดียวกันทั้งสอง context เพื่อเริ่มจากข้อที่สั้นกว่า diagnostic Retrieved `0023` เดิม ส่วนการตรวจ offline ครอบคลุม engineering ทั้งสิบข้อรวม `0023`

## หลัง diagnostic ผ่าน: engineering 10

```powershell
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/golden_qwen_zero_shot_cot_v3_citation_id_enum_engineering_10_ctx16384.yaml
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/section_based_rag_qwen_zero_shot_cot_v3_citation_id_enum_engineering_10_ctx32768.yaml
```

ผลอยู่ในโฟลเดอร์ใหม่:

- `results/current/common_interface_v3/golden_zero_shot_cot_citation_id_enum_engineering_10_ctx16384/`
- `results/current/common_interface_v3/section_based_zero_shot_cot_citation_id_enum_engineering_10_ctx32768/`

รอบนี้ยังไม่สร้าง config สำหรับ heldout ไม่รัน IRAC/Proposed และยังไม่เลือกหรือเรียก LLM ผู้ประเมิน


## การอ่านผลอัตโนมัติ

ตั้งแต่การปรับส่วนบันทึกผลวันที่ 1 ตุลาคม 2026 การรัน Tax ผ่าน `script.response_e2e` ทั้ง Direct/CoT และ Golden/Saved Retrieved จะสร้างไฟล์สองแบบในโฟลเดอร์ผลเดิมทุกครั้งที่บันทึก batch สำเร็จ:

- `tax_response.json`: ข้อมูลครบทุกฟิลด์เหมือนเดิม จัดบรรทัดและใช้ UTF-8 เพื่อแสดงภาษาไทย/จีนโดยตรง
- `tax_response_readable.md`: แยกคำถาม การวิเคราะห์ คำตอบ กฎหมายที่อ้างอิง และข้อมูลเวลารันรายข้อ จับคู่คำถามผ่าน runtime_idx

ไฟล์อ่านง่ายถูกสร้างระหว่างรันด้วย หากข้อถัดไปล้มเหลว ไฟล์ของข้อที่บันทึกก่อนหน้ายังคงอยู่ รายงานแสดงจำนวนคำตอบที่บันทึกจริง ไม่เติมข้อที่ล้มเหลวให้ดูเหมือนตอบสำเร็จ

การจัดรูปแบบนี้ไม่ใช้ LLM ไม่แปลภาษาหรือแก้คำตอบ ไม่เปลี่ยน prompt, schema, citation mapping, จำนวน attempts หรือการเลือกข้อในการ resume การอ่าน JSON เมื่อ resume ระบุ UTF-8 ให้ตรงกับการเขียน

ผล Golden CoT engineering 9 ข้อที่มีอยู่แล้วถูกจัดรูปแบบโดยไม่รันโมเดลใหม่ และเก็บไฟล์ดิบก่อนจัดรูปแบบไว้ข้างกันชื่อ `tax_response.original.json` ส่วน failure ของ source 0046 คงเดิม การจัดรูปแบบไม่ทำให้จำนวนคำตอบเพิ่มเป็น 10

ตรวจส่วนบันทึกและ resume แบบออฟไลน์ได้ด้วย:

```powershell
.\.venv\Scripts\python.exe -B tools/validation/validate_response_output_offline.py
```

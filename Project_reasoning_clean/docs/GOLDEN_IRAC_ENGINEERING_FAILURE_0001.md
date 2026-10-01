# Golden IRAC: ข้อ 0001 สร้างคำตอบไม่จบ และวิธีรันข้อที่เหลือต่อ

วันที่ตรวจ: 1 ตุลาคม 2026

## สิ่งที่พบจากไฟล์จริง

- ชุด engineering มี 10 ข้อ บันทึกคำตอบสำเร็จแล้ว 1 ข้อ: source/runtime `0000`
- source/runtime `0001` ล้มเหลวใน attempt 1; อีก 8 ข้อยังไม่ได้รัน
- โมเดลสร้าง `analysis` ได้ แล้ววนประโยคใน `answer` ว่า “ทั้งนี้ รายได้จากการลงทุนต้องคำนวณตามมาตรา 91/5” รวม 122 ครั้ง
- `finish_reason: length`, prompt = 6,431 tokens, completion = 4,096 tokens, total = 10,527 tokens
- ข้อความถูกตัดก่อนปิด JSON และยังไม่มีฟิลด์ `citation_ids`
- SDK ส่ง `LengthFinishReasonError`; wrapper เก็บรายละเอียดเป็น `RawCompletionFailure` และ Ragger ส่ง error ต่อหลังครบหนึ่ง attempt ตามกติกาเดิม

หลักฐานชี้ว่า output ชน `max_tokens: 4096` ไม่ได้ชี้ว่าการเพิ่ม context window จะหยุดการวนข้อความ จึงคง prompt, model, context window, token budget, temperature, seed และจำนวน attempts เดิม

ไฟล์หลักฐาน:

- [ผลข้อที่บันทึกสำเร็จ](../results/current/common_interface_v3/golden_irac_citation_id_enum_engineering_10_ctx16384/chunk-golden-no-ref-qwen/tax_response.json)
- [ผลฉบับอ่านง่าย](../results/current/common_interface_v3/golden_irac_citation_id_enum_engineering_10_ctx16384/chunk-golden-no-ref-qwen/tax_response_readable.md)
- [รายละเอียด failure](../results/current/common_interface_v3/diagnostics/golden_irac_engineering_10_ctx16384_failures/runtime_0001_source_0001_attempt_1.json)
- [ข้อความดิบ](../results/current/common_interface_v3/diagnostics/golden_irac_engineering_10_ctx16384_failures/runtime_0001_source_0001_attempt_1_raw.txt)

## การแก้ส่วนควบคุมการรัน

เพิ่มตัวเลือก `--continue-on-length-failure` ใน `script/response_e2e.py` ให้ใช้ร่วมกับ config เดิม โดยจำกัดที่ Golden หรือ Saved Retrieved แบบรันทั้งชุด, `batch_size: 1`, `max_retries: 1` และเปิดบันทึก diagnostic

เมื่อเปิดตัวเลือกนี้:

1. ตรวจ runtime/source ID ของคำตอบเดิมและหลักฐาน failure; ปฏิเสธ ID ซ้ำ ไม่ตรงชุด หรือมีทั้ง success และ failure ของข้อเดียวกัน
2. รับเฉพาะหลักฐาน `LengthFinishReasonError` ที่มี `finish_reason: length`, attempt 1, ข้อความดิบ และ model settings ตรงกัน
3. ข้ามทั้งคำตอบที่บันทึกแล้วและ length failure ที่ยืนยันแล้ว โดยเลือกข้อค้างตาม ID ไม่ใช้จำนวนคำตอบเป็นจุดเริ่ม
4. หากข้อถัดไปเกิด length failure ให้รักษา diagnostic แล้วไปข้อต่อไป ไม่เรียกข้อเดิมซ้ำและไม่สร้างคำตอบว่างแทน
5. Error ประเภทอื่น เช่น ปัญหาการเชื่อมต่อ โปรแกรมผิด หรือหลักฐานไม่ครบ ยังคงหยุดเพื่อให้ตรวจ

เพิ่มไฟล์สถานะ `tax_run_status.json` และ `tax_run_status.md` ในโฟลเดอร์คำตอบ แสดงจำนวน success, generation failure และ pending พร้อม source/runtime ของทุกข้อ ส่วน `tax_response.json` และ `tax_response_readable.md` ยังคงมีเฉพาะคำตอบที่บันทึกสำเร็จ ตาม schema เดิม

เมื่อเคยเปิดตัวเลือกนี้และมีไฟล์สถานะแล้ว ต้องใช้ตัวเลือกเดิมในการรันต่อ โค้ดจะปฏิเสธการกลับไป resume ตามจำนวนรายการ เพื่อป้องกันการเรียกข้อเดิมซ้ำหลังมีช่องว่างจาก failure

ตัวเลือกนี้แก้การหยุดทั้งชุดและการรันต่อ ไม่ได้แก้พฤติกรรมวนข้อความของโมเดลหรือทำให้ข้อ 0001 เป็นคำตอบสำเร็จ ไม่เปลี่ยนไฟล์ config หรือ prompt และไม่เรียก LLM ระหว่างแก้โค้ด

ใช้กับ config/prompt และชุดข้อมูลรุ่นเดิมเท่านั้น การตรวจ model settings กับ ID ยังไม่ใช่ fingerprint ของ prompt/config/corpus ครบชุด การตรึงและตรวจ fingerprint ก่อน final test ยังเป็นงานตาม [Protocol](RESEARCH_PROTOCOL.md)

## คำสั่งรันต่อโดยผู้ใช้

รันจาก `C:\NitiBench\Project_reasoning_clean`:

```powershell
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/golden_qwen_irac_v3_citation_id_enum_engineering_10_ctx16384.yaml --continue-on-length-failure
```

จากสถานะที่ตรวจในรายงานนี้ ต้องเห็น `run_status success=1 generation_failure=1 pending=8` ก่อนเริ่มเรียกข้อ runtime/source `0002` ไม่ต้องลบไฟล์หรือเริ่ม 10 ข้อใหม่

หากอีก 8 ข้อสำเร็จทั้งหมด ผลสุดท้ายคือ 9 คำตอบสำเร็จ + 1 generation failure ไม่ใช่ 10 คำตอบสำเร็จ หากมี failure เพิ่ม ไฟล์สถานะจะแสดงตามจริง การประเมินคะแนนและการสรุปคุณภาพยังทำภายหลัง

## การตรวจ offline

เครื่องมือตรวจใหม่: `tools/validation/validate_length_continuation_offline.py`

ใช้คำตอบจำลองเพื่อตรวจกรณีคำตอบสำเร็จที่ ID ไม่ต่อกัน, failure เดิม, failure ใหม่แล้วไปต่อได้, การรันซ้ำเมื่อไม่มีข้อค้าง, การเก็บหลักฐานเดิม, การปฏิเสธ checkpoint ขัดแย้ง และการส่งต่อ error ประเภทอื่น พร้อมตรวจเส้นทางเริ่มต้นที่ยังหยุดเมื่อไม่ได้เปิดตัวเลือก

```powershell
.\.venv\Scripts\python.exe -B tools/validation/validate_length_continuation_offline.py
.\.venv\Scripts\python.exe -B tools/validation/validate_response_output_offline.py
.\.venv\Scripts\python.exe -B tools/validation/validate_ragger_failure_offline.py
```

รายงานการตรวจรอบแก้ไขเก็บที่ `results/current/offline_validation/length_continuation_20261001.txt` ไม่มีการเรียก LLM หรือ live retrieval จริง

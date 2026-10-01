# ข้อผิดพลาด Golden CoT engineering: source 0046

วันที่ตรวจ: 1 ตุลาคม 2026

## ผลของการรัน

รอบนี้มีหลักฐานครบ 10 ข้อที่พยายามรัน: คำตอบบันทึกสำเร็จ 9 ข้อ และ generation failure 1 ข้อ ไม่ใช่ผลสำเร็จครบ 10 ข้อ

- สำเร็จ: source `0000, 0001, 0002, 0003, 0008, 0023, 0026, 0036, 0041` โดย runtime `0000` ถึง `0008` แต่ละข้อมี tries = 1
- ข้อที่ล้มเหลว: source `0046` / runtime `0009` / attempt 1
- 9 คำตอบแรกยังอยู่ในไฟล์เดิม ไม่มีคำตอบว่าง และไม่มี citation validation errors ในรายการที่บันทึก
- เวลารวม llm_time ของ 9 คำตอบสำเร็จประมาณ 753 วินาที ตัว failure ไม่มี llm_time จึงไม่นับ 753 วินาทีเป็นต้นทุนรวมทั้งรอบ

## สาเหตุจากหลักฐาน

1. โมเดลสร้าง analysis ภาษาจีนและวนข้อความซ้ำ วลีเปิดประโยคเดิมปรากฏ 150 ครั้งใน raw response
2. output ใช้ครบ `4096` tokens ตาม `max_tokens` และจบด้วย `finish_reason: length`; prompt tokens = `8964`, total tokens = `13060`
3. raw response ยังไม่มีฟิลด์ answer หรือ citation_ids และ JSON ยังไม่สมบูรณ์ SDK จึงรายงาน `LengthFinishReasonError` ซึ่ง wrapper เก็บเป็น `RawCompletionFailure`
4. โค้ด Ragger เดิมจับ error นี้ไว้ เมื่อครบหนึ่ง attempt แล้วออกจากลูปโดย response ยังเป็น None จากนั้นเขียน retrieved_ids ลงไป จึงเกิด TypeError ที่บดบังสาเหตุแรก

หลักฐานยืนยันการชนงบ output ไม่ได้ยืนยันสถานะการตัด input จากฝั่งเซิร์ฟเวอร์ การเพิ่ม context window หรือ max_tokens ยังไม่มีหลักฐานว่าจะทำให้การวนข้อความหยุด จึงคงค่ารันเดิมในรอบนี้

## การแก้โค้ด

แก้ใน `lrg/e2e/ragger.py`: เมื่อ attempt ล้มเหลวเป็นครั้งสุดท้าย ให้ส่งต่อ exception เดิมหลังบันทึก diagnostic แล้ว ป้องกันทั้ง response=None และกรณีมี response ที่ไม่ผ่าน schema หลุดออกไปเป็นผลสำเร็จ

ใช้เส้นทางร่วมของ rag/rag_multi จึงครอบคลุมทั้ง Golden และ Retrieved โดยไม่เพิ่มจำนวน attempts ไม่เปลี่ยนเส้นทางที่ได้คำตอบสำเร็จ และไม่สร้างคำตอบว่างแทน failure

คง prompt, model, max_tokens, context, resolver, P-ID mapping, output schema และผลทดลองเดิมทั้งหมด การแก้นี้ทำให้รายงานสาเหตุ failure ได้ถูกต้อง ไม่ได้แก้พฤติกรรมวนข้อความของ Qwen และไม่ได้ทำให้ข้อ 0046 กลายเป็นคำตอบสำเร็จ

## ผลตรวจออฟไลน์

เครื่องมือตรวจ: `tools/validation/validate_ragger_failure_offline.py`

ตรวจด้วยคำตอบจำลอง 5 กรณี: ล้มเหลวหนึ่ง attempt, ล้มเหลวครบสอง attempts, สำเร็จทันที, สำเร็จหลัง failure และ response ผิด schema ต้องไม่หลุดเป็น success ตรวจจำนวน attempts, การส่งต่อ error เดิม, การเก็บ raw diagnostic และ mapping ของกรณีสำเร็จ

โค้ดก่อนแก้ตรวจไม่ผ่านเพราะได้ TypeError แทน RawCompletionFailure; หลังแก้ผ่านทั้ง 5 กรณี ไม่มีการเรียก Qwen, API หรือ retrieval จริง และตรวจ hash ยืนยันว่าผล 9 ข้อกับไฟล์ failure เดิมไม่เปลี่ยน

รันตรวจซ้ำจากโฟลเดอร์ Clean:

```powershell
.\.venv\Scripts\python.exe -B tools/validation/validate_ragger_failure_offline.py
```

## การดำเนินงานต่อ

- เก็บชุดนี้เป็น 9 คำตอบสำเร็จ + 1 failure ตามกติกาหนึ่ง attempt ของ Protocol ไม่รันซ้ำเพื่อเลือกเฉพาะคำตอบที่สำเร็จ
- ยังไม่ควรรันคำสั่ง Golden เดิมซ้ำ: runner จะใช้จำนวนรายการเป็นจุด resume แล้วเรียกข้อ 0046 ใหม่ และชื่อ diagnostic เดิมอาจถูกเขียนทับ
- ขั้นต่อไปตามแผนคือเก็บ Saved Retrieved CoT engineering 10 ข้อ แล้วตรวจผลและ failure ให้ครบ
- หากจะทดลองแก้การวนข้อความบน engineering ให้แยกเป็น diagnostic หรือรุ่นทดลองใหม่พร้อมบันทึกสิ่งที่เปลี่ยน ไม่เขียนทับหลักฐานรอบนี้ และไม่เปลี่ยน prompt เฉพาะข้อแล้วนับเป็นผลชุดเดียวกัน
- ยังไม่รัน evaluator และไม่แตะ heldout

## หลักฐานเดิม

- [คำตอบ 9 ข้อ](../results/current/common_interface_v3/golden_zero_shot_cot_citation_id_enum_engineering_10_ctx16384/chunk-golden-no-ref-qwen/tax_response.json)
- [รายละเอียด failure](../results/current/common_interface_v3/diagnostics/golden_zero_shot_cot_engineering_10_ctx16384_failures/runtime_0009_source_0046_attempt_1.json)
- [ข้อความดิบที่สร้างไม่จบ](../results/current/common_interface_v3/diagnostics/golden_zero_shot_cot_engineering_10_ctx16384_failures/runtime_0009_source_0046_attempt_1_raw.txt)

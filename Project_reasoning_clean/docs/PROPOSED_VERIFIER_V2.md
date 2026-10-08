# การปรับ verifier รุ่น 2

## เหตุผล

pilot Golden source `0000` ของรุ่น 1 ให้ PASS ทั้ง I/R/A/C โดยเหตุผล R/A/C กว้างและไม่มีหลักฐานเฉพาะข้อความ ประกอบกับคำตอบร่างมีประเด็นไม่ตรงเฉลย engineering จึงเป็นสัญญาณให้ตรวจ false PASS เพิ่ม ยังไม่ใช่ข้อสรุปคะแนนหรือประสิทธิภาพของ Proposed ทั้งชุด

รุ่น 2 ขยายกติกาอ้างหลักฐานของ rubric เดิมให้ครอบคลุม PASS และ UNCERTAIN ด้วย เป็นการปรับของโครงการจากปัญหา engineering ไม่อ้างว่าเป็น prompt ต้นฉบับจาก LegalReasoner และไม่ใส่เฉลย ประเทศ มาตรา หรือคำตอบของข้อ `0000` ลงใน prompt ไม่ใช้ heldout ในการปรับครั้งนี้

## สิ่งที่เปลี่ยน

ทุก check ต้องมี `evidence` ระบุ `source` และ `quote` ที่คัดตรง โปรแกรมตรวจว่า quote อยู่ในข้อความต้นทางจริง สำหรับ PASS กำหนดแหล่งขั้นต่ำดังนี้:

| แกน | แหล่งหลักฐาน |
|---|---|
| I | คำถาม + ร่าง |
| R | กฎหมาย P-ID + ร่าง |
| A | คำถาม + กฎหมาย P-ID + ร่าง |
| C | analysis + answer |

prompt กำหนดให้เหตุผลอธิบายความสัมพันธ์ของข้อความที่อ้าง ตรวจสิทธิ/หน้าที่ที่คำตอบเพิ่มเอง เงื่อนไขและข้อยกเว้นที่มีสาระสำคัญ และความสอดคล้องของ analysis กับ answer แม้คนละภาษา ข้อความที่คล้ายกันทางภาษาต้องไม่ถูกเหมาว่ามีผลทางกฎหมายเดียวกัน หากหลักฐานไม่พอให้ UNCERTAIN ไม่บังคับ FAIL

การตรวจ quote และแหล่งอ้างอิงเป็นการตรวจรูปแบบกับที่มาเท่านั้น โมเดลยังอาจตีความหลักฐานผิดหรือให้ false PASS ได้ ไม่ใช้กฎค้นคำในภาษาอังกฤษเพื่อตัดสินความหมายทางกฎหมาย

เพิ่ม config รุ่น 2 และโฟลเดอร์ผลใหม่ รักษา v1 เป็นค่าเริ่มต้นของ config เก่า corrector prompt และ schema คำตอบเดิมยังใช้ร่วมกัน; corrector รับ feedback รุ่น 2 ที่ผ่าน validator ของรุ่นนั้น งบ verifier 2,048 และ corrector 4,096 ยังเดิม ตัวรันพิมพ์สถานะและที่เก็บผลเมื่อจบเพื่อไม่ให้กรณี PASS จบเงียบ

## การตรวจและการรันจริง

ตรวจ offline ด้วย `tools/validation/validate_proposed_v2_offline.py`: ประกอบ prompt จากร่าง engineering 19 รายการ ตรวจ quote ที่ผิด/หลักฐานหาย/แหล่งไม่ครบ ตรวจความเข้ากันได้กับ v1 และใช้โมเดลจำลองทดสอบ PASS, UNCERTAIN, FAIL→corrector, feedback ผิดรูปแบบ และ resume ผล offline ไม่รับรองว่า Qwen จะจับความผิดพลาดจริงได้

ตรวจงบ corrector offline ด้วย feedback สมมติสั้นเท่านั้น เมื่อตรวจจริงจะนับใหม่จาก feedback ที่โมเดลส่งกลับ งบ output 2,048 อาจไม่พอเมื่อหลักฐานยาว ต้องเก็บ failure และตรวจจาก pilot ไม่เพิ่มงบเฉพาะข้อเพื่อเลือกผลสำเร็จมาปนกัน

เริ่มจาก `C:\NitiBench\Project_reasoning_clean`:

```powershell
.\.venv\Scripts\python.exe -B -m script.response_proposed --config-path config/local/response/proposed_golden_v2_engineering_10.yaml --source-idx 0000
```

ผลอยู่ใน `results/current/common_interface_v3/golden_proposed_v2_engineering_10_ctx16384/diagnostics/source_0000/` แยกจาก pilot รุ่น 1 อ่าน `tax_proposed_trace.md` เพื่อดู verdict/หลักฐานและก่อน–หลัง; `tax_response_readable.md` เป็นคำตอบสุดท้าย

หลังตรวจ pilot นี้ ให้ลอง Saved Retrieved และกรณี engineering ที่ร่างมีหลักฐานรองรับด้วย เพื่อดูว่ารุ่นใหม่มีแนวโน้มสั่งแก้เกินจำเป็นหรือไม่ ไม่ปรับจนข้อ `0000` ได้ FAIL เพียงอย่างเดียวแล้วถือว่าผ่าน ร่าง IRAC เดิมใช้ต่อได้ ไม่ต้องสร้างใหม่ เก็บผลรุ่น 1 ไว้เทียบ หากเกิดการเปลี่ยน prompt/งบอีกให้แยกรุ่นผลและบันทึกเหตุผลก่อน final test

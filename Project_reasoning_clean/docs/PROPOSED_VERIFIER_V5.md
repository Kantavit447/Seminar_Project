# Proposed v5: แยกช่องหลักฐานตามประเภท

## ปัญหาที่แก้

ผล v4 ข้อ 0000 สร้าง JSON ครบ แต่ให้ PASS โดยไม่มีหลักฐานจากร่างคำตอบใน I/R/A จึงถูกปฏิเสธ การเพิ่ม token ไม่แก้สาเหตุนี้

v5 เปลี่ยนเฉพาะรูปแบบ feedback และคำอธิบายรูปแบบใน prompt ให้ PASS มีช่องบังคับตามด้าน:

| ด้าน | ช่องใน evidence_ids |
| --- | --- |
| I | question, draft |
| R | law, draft |
| A | question, law, draft |
| C | analysis, answer |

แต่ละช่องมี enum ของ ID จากประเภทนั้นโดยเฉพาะ เช่น question เลือกได้เฉพาะ Q-S... และ draft เลือก DA-S... หรือ DR-S... ไม่มีการเติมหลักฐานแทนโมเดลหลังรับผล

FAIL/UNCERTAIN ใช้ช่องเดียวกันแต่อนุญาต null และมี supporting_ids สำหรับเลือกหลักฐานอื่นที่แสดงปัญหาหรือข้อมูลที่ขาด ยังคงต้องมี 1–3 ID ที่ไม่ซ้ำรวมทั้งด้าน และ FAIL ต้องมีคำแนะนำแก้ ส่วน PASS/UNCERTAIN ต้อง revision=null เช่นเดิม

## สิ่งที่คงเดิม

ใช้ร่าง IRAC เดิมและข้อความคำถาม/กฎหมายครบเหมือน v4 ไม่เปลี่ยนเกณฑ์ I/R/A/C, Golden resolver, Saved Retrieved Top 10, P-ID mapping, baseline prompt, answer schema หรือเงื่อนไขเรียก Corrector ไม่มีการใช้เฉลยเป็น input และไม่แตะ heldout

model, temperature, seed, context window และ output token limit เท่าเดิม ผล v5 แยก output_path จาก v1–v4 ไม่ต้องรัน baseline ใหม่

## ไฟล์ที่เปลี่ยน

- lrg/prompting/proposed_v5.py: schema แยกตามด้านและ verdict พร้อมตัวอ่าน ID ที่เลือก
- lrg/prompting/proposed.py: รองรับ v5 และใช้ตัวตรวจหลักฐานเดิม
- script/response_proposed.py: รองรับ v5 ใน provenance, trace และการขยาย ID เป็นข้อความต้นฉบับในรายงาน
- lrg/prompting/templates/proposed-tax-v5/verifier.md: อธิบายช่องหลักฐานใหม่
- lrg/prompting/templates/proposed-tax-v5/corrector.md: อ่าน feedback รูปแบบใหม่ เกณฑ์แก้คำตอบคงเดิม
- config/local/response/proposed_golden_v5_engineering_10.yaml และ proposed_retrieved_v5_engineering_10.yaml: config แยกเวอร์ชัน
- tools/validation/validate_proposed_v5_offline.py: ทดสอบโดยบล็อก network และใช้โมเดลจำลอง

## การตรวจ offline

ตรวจข้อมูลที่มีร่างครบ 19 รายการ: Golden 9 + Saved Retrieved 10; Golden 0001 ยังคง draft_failed จาก baseline เดิม ไม่สร้างร่างใหม่

- ข้อความต้นฉบับและตำแหน่งหลักฐานครบทั้ง verifier/corrector
- ปฏิเสธ feedback ผิดเงื่อนไข 133 กรณี และตรวจเพิ่มเติมว่า schema ปฏิเสธ PASS ที่ขาดช่องหลักฐาน
- FAIL/UNCERTAIN ยังส่งได้เมื่อมีเพียงหลักฐานที่แสดงข้อจำกัด
- เส้นทาง PASS, UNCERTAIN, FAIL → Corrector, invalid feedback → fallback และ resume ผ่านทั้งสอง context (8 เส้นทาง)
- เรียก LLM จริง 0 ครั้ง; ผลจำลองเก็บในโฟลเดอร์ชั่วคราว

งบประเมินรวม schema + output limit + margin 512: verifier สูงสุด Golden 16,279/16,384 และ Retrieved 31,136/32,768 tokens ส่วน corrector ที่ใช้ feedback จำลองสั้นสูงสุด 15,343 และ 28,219 ตามลำดับ ตัว runner จะตรวจงบใหม่กับ feedback จริงก่อนเรียก corrector

Golden บางข้ออยู่ใกล้เพดาน จึงยังไม่ควรสรุปจาก offline ว่ารันจริงได้ทุกข้อ หรือเพิ่ม token โดยอัตโนมัติ

## ข้อจำกัดและการเก็บผลเดิม

schema บังคับประเภทหลักฐานได้ แต่ไม่รับรองว่าหลักฐานสนับสนุน verdict จริง ยังต้องตรวจคุณภาพการตัดสินและวัดผลตามแผน งานนี้ไม่ได้พิสูจน์ว่า v5 ดีกว่า v4 ด้านความถูกต้อง

ยังไม่ได้ทดสอบกับ Ollama จริง โดยเฉพาะ schema ที่ใช้ anyOf แยกตามด้านและ verdict จึงเริ่ม pilot หนึ่งข้อก่อน

ไม่ได้แก้ไฟล์ผลเดิมหรือ template v1–v4 แต่ v4 fingerprint รวมไฟล์ proposed.py ซึ่งเปลี่ยนเพื่อรองรับ v5 จึงอาจปฏิเสธการ resume checkpoint v4 เดิมด้วย fingerprint mismatch ตามกลไกป้องกันการปนเวอร์ชัน อย่าลบ checkpoint หรือแก้ fingerprint เพื่อฝืนผ่าน ให้ใช้ config/output v5 สำหรับงานใหม่

## คำสั่ง pilot

รันจาก C:\NitiBench\Project_reasoning_clean:

```powershell
.\.venv\Scripts\python.exe -B -m script.response_proposed --config-path config/local/response/proposed_golden_v5_engineering_10.yaml --source-idx 0000
```

ผลอยู่ใน results/current/common_interface_v3/golden_proposed_v5_engineering_10_ctx16384/diagnostics/source_0000 และมี tax_proposed_trace.md กับ tax_response_readable.md อัตโนมัติ

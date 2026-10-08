# Proposed v6: ตรวจข้อกล่าวอ้างและเงื่อนไขก่อนตัดสิน

วันที่: 3 ตุลาคม 2026

## เหตุผลของการเปลี่ยน

[รายงานตรวจ v5](PROPOSED_V5_OFFLINE_REVIEW.md) พบว่า Verifier กรอกชนิดหลักฐานครบ แต่เลือกหัวมาตราหรือส่วนแนะนำประเด็นมารองรับการตัดสินด้าน Application/Conclusion โดยไม่แสดงว่าข้อกล่าวอ้างตามมาจากเงื่อนไขจริงอย่างไร

v6 เพิ่ม assessment เป็นบันทึกตรวจสั้นที่อ่านและตรวจย้อนหลังได้ ไม่ใช่การฝึกโมเดล ไม่รับประกันว่าคำตัดสินจะถูก และไม่ใช่การจำลองงานวิจัยต้นฉบับแบบตรงตัว ข้อเสนอนี้มาจากปัญหาใน implementation และผลทดลองของเรา

## รูปแบบใหม่

แต่ละด้าน I/R/A/C มี assessment เพิ่มสามช่อง:

| ช่อง | ความหมาย | เพดานอักขระ |
| --- | --- | --- |
| claim | ข้อกล่าวอ้างของร่างที่กำลังตรวจ | 120 |
| criterion | เงื่อนไขที่ต้องใช้ตรวจข้อกล่าวอ้างนั้น | 160 |
| comparison | ข้อเท็จจริง/กฎหมายสนับสนุน ขัดแย้ง หรือยังไม่พออย่างไร | 240 |

schema v6 เรียง axis → assessment → evidence_ids → reason → verdict → revision เพื่อเสนอให้รายงานการตรวจและหลักฐานก่อนคำตัดสิน แต่ลำดับฟิลด์ไม่ใช่หลักฐานว่าการคิดภายในโมเดลเกิดตามลำดับนั้น

ยังคง evidence_ids แบบแยกแหล่งของ v5 และเงื่อนไข PASS/FAIL/UNCERTAIN เดิม PASS ต้องมีหลักฐานครบประเภท ส่วน FAIL/UNCERTAIN อาจเลือกบางช่องเป็น null และใช้ supporting_ids ได้ ต้องมี 1–3 ID ไม่ซ้ำในแต่ละด้านเช่นเดิม

claim/criterion/comparison ต้องไม่ว่าง ไม่ใช่ช่องสำหรับคัดคำตอบจากเฉลย ไม่มีการเพิ่ม source-specific hint หรือคำตอบของ 0036/0041/0008 ลง prompt

prompt ให้ตรวจข้อกล่าวอ้างสำคัญภายในแต่ละด้าน แล้วรายงานปัญหาที่มีผลสำคัญที่สุด หรือข้อกล่าวอ้างหลักเมื่อไม่พบปัญหา จึงมีเพียงหนึ่ง assessment ต่อด้านเพื่อควบคุมความยาว ไม่ใช่การแจกแจงทุกข้อกล่าวอ้างอย่างครบถ้วน

## การทำงานที่คงเดิม

- ร่าง IRAC, Golden resolver, Saved Retrieved Top 10, P-ID, คำถามและกฎหมายทั้งชุดเดิม
- เรียก Verifier หนึ่งครั้ง และ Corrector ไม่เกินหนึ่งครั้งเมื่อ feedback ที่ใช้ได้มี FAIL
- หาก PASS/UNCERTAIN โดยไม่มี FAIL เก็บร่างเดิมตามสถานะที่เกี่ยวข้อง
- หาก feedback ใช้ไม่ได้ เก็บร่างเดิมพร้อมสถานะล้มเหลว ไม่เปลี่ยนเป็น PASS
- โมเดล, temperature, seed, เพดาน context, verifier 2048 tokens, corrector 4096 tokens เท่าเดิม
- รูปแบบคำตอบสุดท้าย analysis/answer/citation_ids คงเดิม
- ไม่มีการเรียก retrieval ใหม่ ไม่มีเฉลยใน prompt และไม่แตะ heldout

Corrector รับ assessment พร้อม feedback แต่คำสั่งระบุให้ตรวจสอบกับต้นฉบับก่อนแก้ ไม่เชื่อ assessment เป็นข้อเท็จจริงใหม่

## ไฟล์

ไฟล์ใหม่:

- [verifier.md](../lrg/prompting/templates/proposed-tax-v6/verifier.md)
- [corrector.md](../lrg/prompting/templates/proposed-tax-v6/corrector.md)
- [Golden config](../config/local/response/proposed_golden_v6_engineering_10.yaml)
- [Saved Retrieved config](../config/local/response/proposed_retrieved_v6_engineering_10.yaml)
- [offline validation](../tools/validation/validate_proposed_v6_offline.py)

ไฟล์ร่วมที่เพิ่มทางเลือก v6:

- lrg/prompting/proposed_v5.py: ใช้ตัวสร้างเดิม เพิ่ม assess=True เฉพาะ v6; v5 ใช้ค่าเริ่มต้น False
- lrg/prompting/proposed.py: รองรับ v6 และตรวจ assessment ว่าไม่เป็นช่องว่าง
- script/response_proposed.py: provenance/trace ของ v6 และแสดง assessment ใน tax_proposed_trace.md

ไม่ได้แก้ template v1–v5 หรือผลเดิม แต่ไฟล์ร่วมที่ checkpoint v4/v5 เคยเก็บ hash เปลี่ยนแล้ว การ resume ผลเก่าอาจถูกปฏิเสธด้วย fingerprint mismatch ตามการป้องกันที่มีอยู่ อย่าแก้ fingerprint ฝืนผ่าน ให้ใช้ config v6 กับ output ใหม่

## ผล offline

ใช้ข้อมูล engineering ที่มีร่างครบ 19 รายการ (Golden 9, Saved Retrieved 10) โดยบล็อก network และ real LLM constructors ผลจำลองอยู่ในโฟลเดอร์ชั่วคราว ไม่ใช่ผลทดลองจริง

- ตรวจการคงข้อความทั้งหมดใน verifier/corrector และการแปลง ID กลับเป็นข้อความเดิม
- ทดสอบ PASS, FAIL และ UNCERTAIN ที่มี assessment
- ปฏิเสธข้อมูลผิดเงื่อนไข 190 กรณี รวม assessment หาย ว่าง หรือยาวเกิน
- ตรวจ schema ว่า PASS ที่ไม่มีหลักฐานตามประเภทไม่ผ่าน
- ทดสอบ 8 เส้นทางรวมสอง context: kept_pass, kept_uncertain, corrected และ verifier_failed พร้อม resume โดยไม่เรียกซ้ำ
- ตรวจว่า Markdown แสดง assessment ที่ได้รับจริง
- mock Corrector ใช้ร่างเดิมเป็นคำตอบเพื่อทดสอบการเชื่อมต่อ ไม่ได้พิสูจน์ความสามารถแก้ข้อผิด
- จำนวนการเรียกโมเดลจริง: 0

การตรวจนี้รับรองโครงสร้างและการทำงานของโปรแกรม ไม่รับรองการตรวจความหมายของโมเดลหรือการรองรับ schema ของ Ollama จนกว่าจะทดลองจริง

## งบ context

ตัวเลขรวมข้อความ + schema + เพดาน output + margin 512:

| context | verifier สูงสุด | ขอบเขต context | corrector สูงสุดเมื่อใช้ feedback จำลองสั้น |
| --- | ---: | ---: | ---: |
| Golden | 16,354 (0023) | 16,384 | 15,545 |
| Saved Retrieved | 31,211 (0023) | 32,768 | 28,421 |

Golden 0023 เหลือเพียง 30 tokens เหนือยอดที่รวม margin แล้ว จึงถือว่าใกล้เพดานมาก ตัวเลขเป็นการประมาณก่อนเรียกและไม่ใช่ actual usage ของ backend ไม่เพิ่มเพดานหรือตัด context อัตโนมัติ

Corrector ยังต้องตรวจงบใหม่กับ feedback จริงที่มี assessment; หากยาวเกินจะเป็น input_blocked ไม่ควรถือว่าค่าจาก feedback จำลองรับประกันทุกรอบ ความยาว output ของ verifier อาจเพิ่มจาก v5 จึงยังมีโอกาส length failure ภายใต้เพดานเดิม ต้องเก็บเป็นผลล้มเหลวจริง

## ทดลองจริงโดยผู้ใช้

เริ่มสามข้อที่ตรวจไว้ โดยใช้ config v6 เดียวกันทั้งหมดและไม่ปรับระหว่างข้อ:

```powershell
foreach ($id in @("0036","0041","0008")) {
    .\.venv\Scripts\python.exe -B -m script.response_proposed --config-path config/local/response/proposed_golden_v6_engineering_10.yaml --source-idx $id
    if ($LASTEXITCODE -ne 0) { break }
}
```

รันจาก C:\NitiBench\Project_reasoning_clean ผลแยกใน results/current/common_interface_v3/golden_proposed_v6_engineering_10_ctx16384/diagnostics/source_XXXX และสร้างไฟล์อ่านง่ายอัตโนมัติ ไม่ต้องรัน IRAC ใหม่

สามข้อนี้เป็น pilot ตรวจการทำงาน ไม่ใช้ตัดสินว่า v6 ดีกว่าทั้งชุด หากทำงานได้ให้คงเวอร์ชันแล้วตรวจ engineering ข้อที่เหลือทั้งหมดด้วย ไม่แก้จนได้ FAIL ตามที่ต้องการ

ให้ตรวจว่า assessment ระบุข้อกล่าวอ้างจริงไหม เงื่อนไขมาจากกฎหมายส่วนที่เกี่ยวข้องไหม เปรียบเทียบกับข้อเท็จจริงได้ไหม และ verdict สอดคล้องกับ assessment หรือไม่ หากมีการแก้ให้ตรวจคำตอบก่อน/หลังพร้อมต้นทุน หาก 0008 เดิมข้อสรุปหลักถูก ต้องไม่ถือว่าการเปลี่ยนคำตอบเองเป็นความสำเร็จ

ยังไม่เพิ่มการประเมินด้วย LLM ภายนอก ไม่ใช้ heldout และยังไม่มีข้อสรุปด้านคะแนน benchmark

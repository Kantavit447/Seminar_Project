# Prompt ของ Proposed และผลตรวจ offline

วันที่: 1 ตุลาคม 2026 — รุ่น prompt `proposed-tax-v1`

สถานะ: สร้าง prompt ของ verifier/corrector, ตัวประกอบข้อความ, schema ผลตรวจ และตัวตรวจ feedback แล้ว ตรวจ offline ผ่าน ยังไม่มี runner ที่เรียกโมเดลครบขั้นตอนหรือผลคำตอบ Proposed จริง

ข้อกำหนดและที่มางานวิจัยอยู่ใน [PROPOSED_DESIGN.md](PROPOSED_DESIGN.md) ส่วนคะแนนและขอบเขตการทดลองอยู่ใน [RESEARCH_PROTOCOL.md](RESEARCH_PROTOCOL.md)

## ไฟล์ที่ใช้

| ไฟล์ | หน้าที่ |
|---|---|
| [verifier.md](../lrg/prompting/templates/proposed-tax-v1/verifier.md) | คำสั่งตรวจ I/R/A/C แบบเป็นกลาง ขอ PASS/FAIL/UNCERTAIN และหลักฐานที่คัดตรงจากแหล่ง |
| [corrector.md](../lrg/prompting/templates/proposed-tax-v1/corrector.md) | คำสั่งแก้หนึ่งครั้ง ตรวจ feedback เทียบหลักฐาน และรักษาเนื้อหาที่รองรับได้ |
| [proposed.py](../lrg/prompting/proposed.py) | ประกอบข้อความด้วย context เดิม สร้าง schema และตรวจ feedback ก่อนสร้าง prompt ของ corrector |
| [ตัวตรวจ offline](../tools/validation/validate_proposed_prompts_offline.py) | ตรวจกับร่าง IRAC engineering ที่มีจริง รวมกรณีข้อมูลผิด โดยปิดกั้น network, generation และ live retrieval |
| [รายงานตรวจ JSON](../results/current/offline_validation/proposed_prompts_v1_20261001.json) | รายการรายข้อ จำนวน prompt ผลตรวจกรณีผิด และ hash ของไฟล์ที่ตรวจ |

ไฟล์ prompt เป็นภาษาอังกฤษตามแนวทางการทดลองเดิม เอกสารอธิบายเป็นภาษาไทย ไม่มี few-shot example จากเอกสารออกแบบหรือเฉลยถูกเพิ่มเข้า prompt

## การประกอบข้อความ

ทั้งสองบทบาทมีสองข้อความ: system instruction และ user data ไม่มีประวัติสนทนาหรือคำตอบตัวอย่างเพิ่มเติม

User data เริ่มด้วย LEGAL_CONTEXT, ALLOWED_CITATION_IDS และ QUESTION ในรูปแบบเดิมจาก `NitiLinkAugmenter.serialize_common_v3` แล้วต่อด้วย DRAFT_JSON เฉพาะ corrector จึงมี FEEDBACK_JSON เพิ่มท้าย ไม่ส่งทั้งแถว dataset หรือทั้ง response record ให้โมเดล

Corrector ใช้ [system prompt คำตอบเดิม](../lrg/prompting/templates/system_prompt_tax_v3_citation_id_enum.md) เป็นส่วนต้น แล้วเพิ่มคำสั่งแก้ รักษา `analysis`, `answer`, `citation_ids` และสร้าง citation enum ด้วย `PromptManager.build_citation_id_enum_structure` เดิม จึงไม่มี schema คำตอบใหม่สำหรับ Proposed

Verifier มี schema แยกชื่อ `IRACVerification` สำหรับ `checks` เท่านั้น `source` ของหลักฐานจำกัดที่ QUESTION, DRAFT_ANALYSIS, DRAFT_ANSWER และ P-ID ที่มีในข้อนั้น หลักฐานจาก P-ID เทียบกับ LAW_TEXT ของมาตรานั้น ไม่รวมชื่อกฎหมายหรือหัวข้อ block

## ตัวตรวจ feedback ทำอะไรได้

- บังคับสี่แกน I/R/A/C อย่างละหนึ่งและลำดับเดิม พร้อม verdict ที่อนุญาต
- FAIL ต้องมี issue ส่วน PASS/UNCERTAIN ต้องไม่มี issue
- reason, problem, revision และ quote ต้องไม่ว่างตามหน้าที่ของแต่ละ field
- ตรวจว่า draft_quote อยู่ใน draft_field ที่ระบุ และ evidence quote อยู่ใน source ที่ระบุจริง ไม่มี fuzzy matching หรือการแก้ quote ให้อัตโนมัติ
- อนุญาต `draft_quote: null` สำหรับรูปแบบปัญหาละประเด็นตามข้อกำหนด แต่การยืนยันว่าเป็นการละประเด็นจริงยังเป็นเรื่องความหมาย ไม่ใช่สิ่งที่ validator พิสูจน์ได้
- หาก feedback ผิดจะยก `ValueError` รวมถึง schema error ไม่ดึงเฉพาะส่วนที่ดูถูกต้องมาใช้
- การสร้าง prompt ของ corrector ต้องผ่านการตรวจ feedback และมี FAIL อย่างน้อยหนึ่งแกน ถ้า PASS ทั้งหมด หรือมีเพียง UNCERTAIN จะถูกปฏิเสธ

การตรวจเหล่านี้ยืนยันรูปแบบและการมีอยู่ของข้อความอ้างอิง ไม่ยืนยันว่า verdict หรือการตีความกฎหมายของ verifier ถูกต้อง ตัวอย่างที่อ้างข้อความจริงก็ยังให้เหตุผลผิดได้

## ผลตรวจ offline รอบนี้

| รายการ | ผล |
|---|---:|
| รายการ engineering ที่ตรวจสถานะ | 20: Golden 10 + Saved Retrieved 10 |
| ร่าง IRAC ที่สำเร็จและใช้ประกอบ prompt | 19: Golden 9 + Retrieved 10 |
| ร่างที่ไม่มีคำตอบสมบูรณ์ | 1: Golden source 0001 คง `draft_failed` |
| Prompt ที่ประกอบและตรวจ | 38: verifier 19 + corrector 19 |
| กรณีข้อมูลผิดเงื่อนไขที่ปฏิเสธได้ | 27 |
| การเรียก LLM | 0 |
| การพยายามใช้ network หรือ generation/live retrieval ที่ถูก guard จับ | 0 |
| การยืนยันว่า input พอดี context window ด้วย tokenizer ของโมเดล | ยังไม่ได้ทำ |

ใช้ feedback สมมติที่ระบุว่าเป็นการทดสอบ interface เพื่อประกอบ corrector ทั้ง 19 ร่าง ไม่ได้ให้โมเดลตัดสิน FAIL และไม่ได้กล่าวว่าร่างเหล่านั้นมีข้อผิดพลาดตาม feedback สมมติ

หลักฐานที่ตรวจแล้ว:

1. จับคู่ source/runtime ID และสถานะสำเร็จตรงกับไฟล์ร่าง ไม่มีการข้ามตามตำแหน่งแถวหรือสร้างร่างใหม่ให้ข้อที่ล้มเหลว
2. Context ของ Proposed ตรงกับข้อความที่ baseline สร้างจาก corpus ปัจจุบันทุกตัวอักษร รวมลำดับกฎหมาย และ P-ID map ตรงกับที่บันทึกในผล IRAC ทั้ง 19 ร่าง; Saved Retrieved ยังคง Top 10 และ Golden ใช้ resolver เดิม
3. เปลี่ยนคอลัมน์เฉลยและ metadata ต้องห้ามในหน่วยความจำเป็นข้อความทดสอบ แล้วตรวจว่าไม่หลุดเข้า prompt ฝั่ง Retrieved ยังทดสอบปิดบัง `relevant_laws` หลังเตรียม saved adapter ด้วย
4. Schema คำตอบ corrector ตรงกับ enum schema เดิม และใช้ mapper เดิมแล้วได้ citations เดิม รวมการเก็บ ID ซ้ำครั้งแรกพร้อม warning ตามนโยบายเดิม
5. ตัวประกอบ prompt ไม่แก้ draft/feedback ที่ส่งเข้า ไม่มีตัวอย่างเพิ่ม ไม่มี field คะแนนหรือ metadata แอบเพิ่มในข้อความ
6. ทดสอบ feedback ขาด/ซ้ำ/สลับแกน, verdict ไม่ถูก, FAIL ไม่มี issue, PASS มี issue, quote ไม่มีจริง/ผิด source, P-ID นอก context, ช่องว่าง, field เกิน, JSON ถูกตัด, ร่างหาย และการส่ง PASS/UNCERTAIN เข้า corrector
7. ตรวจ hash ของไฟล์เดิม 98 ไฟล์ รวมโค้ด prompt/config เดิม corpus, saved retrieval และผลตอบเดิมก่อน–หลัง พบว่าคงเดิม

การตรวจข้อความ context เทียบกับ corpus ปัจจุบันไม่สามารถรับรอง digest โมเดลหรือข้อความ input ในอดีตที่ไม่ได้บันทึก hash ไว้ ข้อจำกัด provenance เดิมยังคงตามเอกสารออกแบบ

## ตัวอย่าง prompt ที่อ่านได้

เก็บตัวอย่าง source `0000` ไว้สี่ไฟล์เพื่อเปิดดูข้อความที่ประกอบจริง:

- [Golden verifier](../results/current/debug_prompts/proposed_v1_offline/golden_source_0000_verifier_offline.txt)
- [Golden corrector — feedback สมมติ](../results/current/debug_prompts/proposed_v1_offline/golden_source_0000_corrector_offline.txt)
- [Saved Retrieved verifier](../results/current/debug_prompts/proposed_v1_offline/retrieved_source_0000_verifier_offline.txt)
- [Saved Retrieved corrector — feedback สมมติ](../results/current/debug_prompts/proposed_v1_offline/retrieved_source_0000_corrector_offline.txt)

หัวไฟล์อธิบายสถานะ offline และท้ายไฟล์แสดง schema สำหรับอ่าน ทั้งสองส่วนเป็นข้อมูลประกอบไฟล์ dump ไม่ใช่ข้อความเพิ่มเติมที่ส่งให้โมเดล ส่วน feedback สมมติแสดงเฉพาะวิธีประกอบ input ห้ามนำไปอ้างเป็นผลตรวจคุณภาพจริง

## ตรวจซ้ำด้วยตนเอง

รันจาก `C:\NitiBench\Project_reasoning_clean` คำสั่งนี้ไม่เรียกโมเดล:

```powershell
.\.venv\Scripts\python.exe -B tools/validation/validate_proposed_prompts_offline.py
```

เมื่อระบุ `--output <ไฟล์ใหม่.json>` จะบันทึกรายงาน และ `--dump-dir <โฟลเดอร์ใหม่>` จะบันทึก prompt ที่ประกอบครบ 38 ชุด ควรเลือกปลายทางใหม่เพื่อเก็บรายงานเดิมไว้ ส่วน `--candidate-root` กับ `--project-root` ใช้สำหรับตรวจไฟล์ที่เตรียมใน staging ก่อนบันทึกเข้าโปรเจกต์

## งานที่ยังต้องทำก่อนให้ผู้ใช้รันจริง

1. เพิ่ม runner ของ Proposed เพื่ออ่านร่าง ตรวจ provenance เลือก PASS/FAIL/UNCERTAIN เรียกแต่ละขั้นไม่เกินหนึ่ง attempt และเก็บสถานะ/fallback/resume ตามข้อกำหนด
2. ตรวจงบ input ด้วยวิธีนับ tokens ที่ตรงกับ Qwen และตรวจทรัพยากรจริง ค่า character count ในรายงานไม่ใช่จำนวน tokens การตรวจนี้ยังไม่รับรองว่า 16k/32k เพียงพอหรือ endpoint รองรับ structured output ชุดใหม่ครบ
3. เพิ่ม config ของ Proposed และการบันทึกคำตอบ/trace ที่อ่านได้ จากนั้นให้ผู้ใช้รัน pilot ตรวจพฤติกรรมจริงก่อน engineering ครบชุด

ขั้นตอนข้างต้นยังไม่ได้ทำในรอบสร้าง prompt นี้ โดยเฉพาะการ fallback/การ resume ยังไม่ได้เชื่อมกับการเรียกโมเดลจริง ผลผ่าน offline ไม่ใช่คะแนนคุณภาพของ Proposed และไม่ทำให้ต้องรัน Direct/CoT/IRAC เดิมใหม่

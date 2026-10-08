# ตัวรัน Proposed สำหรับ engineering 10 ข้อ

ตัวรันอยู่ที่ `script/response_proposed.py` ใช้ร่าง IRAC ที่บันทึกไว้ แล้วส่งเฉพาะคำถาม บริบทกฎหมายเดิม ร่าง และ feedback ที่ผ่านการตรวจเข้าสู่ verifier/corrector ไม่ส่งเฉลยหรือคะแนนให้โมเดล ไม่สร้าง embedding และไม่เรียก live retrieval

ขั้นตอนต่อข้อคืออ่านร่าง → ตรวจ I/R/A/C → ถ้ามี FAIL ที่ผ่านการตรวจหลักฐานจึงแก้หนึ่งครั้ง ถ้า PASS ทั้งหมดหรือมี UNCERTAIN โดยไม่มี FAIL จะเก็บร่างเดิม ข้อที่ไม่มีร่างสมบูรณ์เป็น `draft_failed` และยังนับอยู่ใน 10 ข้อ Golden มีกรณีนี้ที่ source `0001` อยู่แล้ว

ตัวรันแยกผลจาก IRAC เดิมและบันทึก `tax_response.json`, `tax_response_readable.md`, `tax_proposed_trace.json`, `tax_proposed_trace.md`, `tax_run_status.json` อัตโนมัติหลังแต่ละข้อ `tax_response.json` รักษารูปแบบคำตอบหลักเดิม ส่วน trace มีร่าง ผลตรวจ คำตอบหลังแก้ สถานะ การใช้ tokens และที่มาของข้อมูล การกลับมารันด้วยคำสั่งเดิมจะข้ามข้อที่จบแล้ว หากโปรแกรมหยุดระหว่างคำขอซึ่งไม่ทราบผล จะหยุดและให้ตรวจ checkpoint ก่อน ไม่ส่งคำขอนั้นซ้ำอัตโนมัติ

## ตรวจแบบไม่เรียกโมเดล

เริ่มจากโฟลเดอร์ `C:\NitiBench\Project_reasoning_clean` โดยใช้ Python ใน `.venv`:

```powershell
.\.venv\Scripts\python.exe -B -m script.response_proposed --config-path config/local/response/proposed_golden_engineering_10.yaml --dry-run
.\.venv\Scripts\python.exe -B -m script.response_proposed --config-path config/local/response/proposed_retrieved_engineering_10.yaml --dry-run
```

`--dry-run` ตรวจการจับคู่ source/runtime, P-ID, context และงบ verifier โดยไม่สร้างไฟล์ผลและไม่เรียก Ollama ข้อ `draft_failed` จะไม่อยู่ในรายการงบเพราะไม่มี prompt ให้ส่ง หากเครื่องไม่มี tokenizer ที่ cache ไว้ ให้ระบุ `--tokenizer-path` ไปยัง `tokenizer.json` ของ `Qwen/Qwen2.5-7B-Instruct` ต้องติดตั้ง standalone `tokenizers==0.21.4` ใน `.venv`; ไม่ต้องติดตั้ง `transformers` หรือ embedding stack

## Pilot จริงโดยผู้ใช้

เมื่อ Ollama พร้อม ให้ลองหนึ่งข้อในแต่ละ context ก่อน:

```powershell
.\.venv\Scripts\python.exe -B -m script.response_proposed --config-path config/local/response/proposed_golden_engineering_10.yaml --source-idx 0000
.\.venv\Scripts\python.exe -B -m script.response_proposed --config-path config/local/response/proposed_retrieved_engineering_10.yaml --source-idx 0000
```

ผล pilot อยู่ใต้ `output_path/diagnostics/source_0000/` ของแต่ละ config จึงไม่ปนกับผล engineering เต็ม หลังตรวจคุณภาพ feedback, ผลลัพธ์, เวลาและ `usage.prompt_tokens` จริงแล้ว จึงรัน 10 ข้อด้วยคำสั่งเดิมโดยตัด `--source-idx 0000` ออก การรัน pilot เป็นการเรียกโมเดลจริง ผู้ใช้เป็นผู้เริ่มเท่านั้น

## งบและข้อจำกัด

งบเริ่มต้นคือ verifier output 2,048 tokens และ corrector output 4,096 tokens; Golden ใช้หน้าต่าง 16,384 และ Saved Retrieved 32,768 ตาม alias ของ IRAC เดิม โปรแกรมนับข้อความด้วย Qwen2.5 tokenizer ในเครื่อง รวม chat markers, JSON schema, output limit และเผื่ออีก 512 tokens ก่อนส่งแต่ละขั้น ถ้าเกินให้ `input_blocked` โดยไม่ย่อบริบทหรือส่งคำขอนั้น

การนับนี้เป็น **การประมาณก่อนเรียก** เพราะ Ollama อาจเพิ่มรูปแบบของ structured output ในระดับ backend หลังเรียกแล้วต้องเทียบกับ `usage.prompt_tokens` จริง รายงาน offline ใช้ feedback สมมติหนึ่งประเด็นเพื่อทดสอบงบ corrector ไม่ได้รับประกันว่า feedback จริงทุกข้อจะมีขนาดเท่ากัน งบ corrector จึงถูกตรวจอีกครั้งหลังได้ feedback จริงก่อนเรียกโมเดลแก้

ผลตรวจ offline ณ วันที่ 2 ตุลาคม 2026: verifier ผ่านงบทั้ง 19 ร่าง; corrector ผ่านทั้ง 19 ร่างเมื่อใช้ feedback สมมติสั้น โดยสูงสุด Golden 14,938/16,384 และ Saved Retrieved 27,411/32,768 tokens ตามวิธีประมาณข้างต้น ตัวทดสอบโมเดลจำลองผ่าน PASS, UNCERTAIN, feedback ผิดรูปแบบ, FAIL→corrector, corrector ล้มเหลว และ resume ในทั้งสอง context โดยไม่มี network call ผลนี้ตรวจการเดินสายและรูปแบบเท่านั้น ยังไม่ใช่ผลคุณภาพจริงของวิธี Proposed

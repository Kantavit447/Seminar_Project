# งานปรับปรุงที่เลื่อนไปทำภายหลัง

> อัปเดต 18 กันยายน 2026: แก้ startup เป็น lazy import แล้ว และนำ dependencies ของ Live Retrieval ออกจาก requirements สำหรับ generation-only ตรวจ imports กับ Saved/Golden แบบ offline ผ่านแล้ว รายละเอียดอยู่ใน [รายงานการแก้ไข](LAZY_IMPORT_FIX_REPORT.md) ข้อความเรื่อง eager imports และข้อจำกัดการตรวจ imports ด้านล่างเป็นสถานะก่อนแก้ ไม่ใช่สถานะล่าสุด


รายการนี้เป็นบันทึกสิ่งที่ควรตรวจหรือปรับปรุง ยังไม่ได้แก้ logic ระหว่างทำ clean project

1. `PromptManager` ไล่โฟลเดอร์ Tax/Wangchan และ response/evaluation/long/pure/o1 ทันทีเมื่อสร้าง object จึงต้องเก็บ compatibility templates เพื่อรักษาพฤติกรรมเดิม ไม่ได้หมายความว่าโปรเจกต์รองรับการทดลองเหล่านั้น
2. `response_e2e` import `retrieval_init` ทันที ทำให้ต้องมี HuggingFace/BM25/Cohere/BGE แม้ใช้ saved retrieval หรือ Golden การเปลี่ยนเป็น lazy import ต้องทำเป็นงานแยกและตรวจพฤติกรรมเทียบเดิม
3. `EvalDataset` โหลด law catalogs ทั้ง 36 ไฟล์, `section_idx` และสร้าง QA corpus แม้เส้นทางปัจจุบันใช้ nodes โดยตรง
4. `llama-index-core` ของ source เป็น editable package ที่มีการแก้ไข เก็บ overlays ที่ทราบ 3 ไฟล์ไว้แล้ว แต่ยังไม่พิสูจน์ความเทียบเท่าของ dependencies และ environment ทั้งหมด
5. Source requirements ต่างจาก metadata ใน environment สำรอง เช่น pandas `2.2.2` กับ `3.0.3`, OpenAI `1.61.1` กับ `2.48.0`, Pydantic `2.8.2` กับ `2.13.4` และ Jinja2 `3.1.4` กับ `3.1.6` จึงรักษา application pins ที่ประกาศไว้ โดยไม่อ้างว่าเป็น historical lock ที่แน่นอน
6. ต้องติดตั้งและตรวจ environment ใหม่ก่อน inference การย้ายโปรเจกต์ไม่ได้ติดตั้ง dependencies
7. Default paths แบบ Linux ยังอยู่ ให้ใช้เฉพาะ configs ที่คัดลอกมา เรียกจากรากโปรเจกต์ และกำหนด `PYTHONUTF8=1`
8. Wrapper โหลด `/app/setting.env` ส่วน `.env.example` เป็นเอกสารตัวอย่าง ไม่ได้ถูกโหลดอัตโนมัติ
9. ต้องทบทวนกรณี retry ครบแล้วยังล้มเหลว และการนับต้นทุนทุก attempt เพราะ usage ของผลสำเร็จไม่ได้รวมต้นทุนทั้งหมด
10. Resume ใช้จำนวนผลเดิมแทนการตรวจ source ID/config fingerprint จึงแยก reference results ออกจากตำแหน่งผลที่รันจริง
11. Audit ปัจจุบันเชื่อ stored invalid/duplicate fields, ไม่รวม context mismatch เป็น summary error และไม่ resolve Golden labels ใหม่อย่างอิสระ ระหว่าง migration ได้ตรวจ engineering references เพิ่มแบบ offline แล้ว
12. Direct ขอ reasoning points แบบสั้นเป็นภาษาอังกฤษอยู่แล้ว ต้องนิยามความต่างของ CoT ในอนาคตให้ชัด โดยไม่เปลี่ยน Direct เงียบ ๆ
13. ไม่คัดลอก legacy evaluator: `metric_e2e` สลับ FP/FN ของ citation และมี paths/model routing ที่ไม่ตรงกับ pipeline ปัจจุบัน
14. ไม่คัดลอก `custom_retriever` ดังนั้น lazy branches `nvembed`, `jinnav2`, `jinnav3` ไม่อยู่ในขอบเขตที่ clean project รองรับ
15. ยังไม่มีการเพิ่ม reasoning method, เรียกโมเดล, rerun retrieval หรือวิเคราะห์ held-out

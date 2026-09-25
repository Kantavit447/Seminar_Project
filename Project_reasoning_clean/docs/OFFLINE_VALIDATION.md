# ผลการตรวจแบบ offline

> อัปเดต 18 กันยายน 2026: แก้ startup เป็น lazy import แล้ว และนำ dependencies ของ Live Retrieval ออกจาก requirements สำหรับ generation-only ตรวจ imports กับ Saved/Golden แบบ offline ผ่านแล้ว รายละเอียดอยู่ใน [รายงานการแก้ไข](LAZY_IMPORT_FIX_REPORT.md) ข้อความเรื่อง eager imports และข้อจำกัดการตรวจ imports ด้านล่างเป็นสถานะก่อนแก้ ไม่ใช่สถานะล่าสุด


ผลนี้เป็นบันทึกการตรวจระหว่างสร้าง clean project ไม่ได้รันการตรวจใหม่หรือเรียกโมเดลระหว่างแปลเอกสาร

ไม่ได้เรียก LLM, API หรือ retriever ไม่ติดตั้ง environment และไม่วิเคราะห์คำตอบ held-out

| รายการตรวจ | สถานะ | รายละเอียด |
|---|---|---|
| ตรวจไวยากรณ์และ compile Python | ผ่าน | Compile 24 ไฟล์ในหน่วยความจำ ไม่เขียนไฟล์ pyc |
| section_based_rag_qwen_direct_v3_citation_id_enum_engineering_10.yaml: law_dir | ผ่าน | test_data/laws |
| section_based_rag_qwen_direct_v3_citation_id_enum_engineering_10.yaml: node_path | ผ่าน | chunking/golden/nodes.json |
| section_based_rag_qwen_direct_v3_citation_id_enum_engineering_10.yaml: tax_data_path | ผ่าน | data_splits/tax_engineering_10.csv |
| section_based_rag_qwen_direct_v3_citation_id_enum_engineering_10.yaml: section_idx_path | ผ่าน | dump/section_idx.json |
| section_based_rag_qwen_direct_v3_citation_id_enum_engineering_10.yaml: ข้อมูล retrieval ที่บันทึกไว้ | ผ่าน | results/current/retrieval_evaluation/section_based_no_ref/retrieval_results.json |
| section_based_rag_qwen_direct_v3_citation_id_enum_engineering_10.yaml: ค่าควบคุม | ผ่าน | YAML ตรงกับ source ไม่สร้าง output directories ก่อนรันครั้งแรกโดยตั้งใจ |
| golden_qwen_direct_v3_citation_id_enum_engineering_10.yaml: law_dir | ผ่าน | test_data/laws |
| golden_qwen_direct_v3_citation_id_enum_engineering_10.yaml: node_path | ผ่าน | chunking/golden/nodes.json |
| golden_qwen_direct_v3_citation_id_enum_engineering_10.yaml: tax_data_path | ผ่าน | data_splits/tax_engineering_10.csv |
| golden_qwen_direct_v3_citation_id_enum_engineering_10.yaml: section_idx_path | ผ่าน | dump/section_idx.json |
| golden_qwen_direct_v3_citation_id_enum_engineering_10.yaml: ค่าควบคุม | ผ่าน | YAML ตรงกับ source ไม่สร้าง output directories ก่อนรันครั้งแรกโดยตั้งใจ |
| section_based_rag_qwen_direct_v3_citation_id_enum_diagnostic_source_0023.yaml: law_dir | ผ่าน | test_data/laws |
| section_based_rag_qwen_direct_v3_citation_id_enum_diagnostic_source_0023.yaml: node_path | ผ่าน | chunking/golden/nodes.json |
| section_based_rag_qwen_direct_v3_citation_id_enum_diagnostic_source_0023.yaml: tax_data_path | ผ่าน | data_splits/tax_engineering_10.csv |
| section_based_rag_qwen_direct_v3_citation_id_enum_diagnostic_source_0023.yaml: section_idx_path | ผ่าน | dump/section_idx.json |
| section_based_rag_qwen_direct_v3_citation_id_enum_diagnostic_source_0023.yaml: ข้อมูล retrieval ที่บันทึกไว้ | ผ่าน | results/current/retrieval_evaluation/section_based_no_ref/retrieval_results.json |
| section_based_rag_qwen_direct_v3_citation_id_enum_diagnostic_source_0023.yaml: ค่าควบคุม | ผ่าน | YAML ตรงกับ source ไม่สร้าง output directories ก่อนรันครั้งแรกโดยตั้งใจ |
| golden_qwen_direct_v3_citation_id_enum_diagnostic_source_0008.yaml: law_dir | ผ่าน | test_data/laws |
| golden_qwen_direct_v3_citation_id_enum_diagnostic_source_0008.yaml: node_path | ผ่าน | chunking/golden/nodes.json |
| golden_qwen_direct_v3_citation_id_enum_diagnostic_source_0008.yaml: tax_data_path | ผ่าน | data_splits/tax_engineering_10.csv |
| golden_qwen_direct_v3_citation_id_enum_diagnostic_source_0008.yaml: section_idx_path | ผ่าน | dump/section_idx.json |
| golden_qwen_direct_v3_citation_id_enum_diagnostic_source_0008.yaml: ค่าควบคุม | ผ่าน | YAML ตรงกับ source ไม่สร้าง output directories ก่อนรันครั้งแรกโดยตั้งใจ |
| ตรวจ engineering split | ผ่าน | 0000,0001,0002,0003,0008,0023,0026,0036,0041,0046 |
| นับแถว held-out | ผ่าน | มี 40 แถว ไม่ตรวจคำตอบหรือผลทดลอง |
| ตรวจ golden nodes | ผ่าน | มี 5,127 nodes ที่ ID ไม่ซ้ำกัน |
| ตรวจโครงสร้าง saved artifact | ผ่าน | ใช้ artifact เดิมเท่านั้น ไม่รัน retrieval หรือคำนวณ held-out metrics |
| ตรวจ saved nodes ของ engineering | ผ่าน | แต่ละข้อมี 10 nodes ไม่ซ้ำ รักษาลำดับ และอยู่ใน corpus |
| ตรวจ exact resolution ของ Golden engineering | ผ่าน | พบ node IDs ตรงตัว 27/27 รายการ ไม่อ่านคำตอบ |
| ตรวจ interface ของผลอ้างอิง Retrieved | ผ่าน | ผล engineering อ้างอิงเดิมตรงกับ context ลำดับ map และ final citations ไม่ทำ inference |
| ตรวจ interface ของผลอ้างอิง Golden | ผ่าน | ผล engineering อ้างอิงเดิมตรงกับ context ลำดับ map และ final citations ไม่ทำ inference |
| ตรวจรายการที่ PromptManager โหลดตอนเริ่มต้น | ผ่าน | โหลด schema/template folders ที่ constructor ต้องใช้ได้ด้วย Jinja/Pydantic ที่มี ไม่ใช่การยืนยัน environment ทั้งชุด |
| ตรวจ enum ['P1', 'P2'] | ผ่าน | ยอมรับ IDs ที่อนุญาตและกรณีรายการว่าง ปฏิเสธ P999 |
| ตรวจ enum [] | ผ่าน | ยอมรับ IDs ที่อนุญาตและกรณีรายการว่าง ปฏิเสธ P999 |
| ตรวจ imports ของ entry point ทั้งชุด | ยังไม่ได้รัน | ยังไม่สร้าง clean environment ตามขอบเขตงาน Interpreter ที่ใช้ตรวจไม่มี torch/openai และไม่ได้มี package stack ตาม pins ที่ต้องการ ไม่ใช้ mock imports |
| ตรวจไฟล์ที่คัดลอกตรงต้นฉบับทุก byte | ผ่าน | ไฟล์ที่คัดลอก 117 ไฟล์มี SHA-256 ตรงกับ source |
| ตรวจสถานะ source ไม่เปลี่ยน | ผ่าน | ผล git status --short ก่อนและหลังตรงกันทุกตัวอักษร |
| ตรวจ filesystem ของ source ไม่เปลี่ยน | ผ่าน | เปรียบเทียบขนาดและ mtime_ns ของทุกไฟล์ใน source นอก .git พร้อมตรวจ SHA-256 ของไฟล์ที่คัดลอก |

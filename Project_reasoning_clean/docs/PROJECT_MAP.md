# แผนผังโปรเจกต์

> อัปเดต 18 กันยายน 2026: แก้ startup เป็น lazy import แล้ว และนำ dependencies ของ Live Retrieval ออกจาก requirements สำหรับ generation-only ตรวจ imports กับ Saved/Golden แบบ offline ผ่านแล้ว รายละเอียดอยู่ใน [รายงานการแก้ไข](LAZY_IMPORT_FIX_REPORT.md) ข้อความเรื่อง eager imports และข้อจำกัดการตรวจ imports ด้านล่างเป็นสถานะก่อนแก้ ไม่ใช่สถานะล่าสุด


รองรับเฉพาะ Direct YAML ทั้งสี่ไฟล์ที่คัดลอกมา แผนวิจัยมี 8 conditions แต่ reasoning methods อื่นยังไม่ได้ implement

| โฟลเดอร์หรือไฟล์ | ผู้เรียกใช้ | สิ่งที่เรียกหรืออ่านต่อ | Context ที่เกี่ยวข้อง | ประเภท |
|---|---|---|---|---|
| config/local/response | CLI ผ่าน --config_path | Paths และค่าของ PromptManager/โมเดล | ทั้งสองแบบ | Config |
| script/response_e2e.py | python -m script.response_e2e | EvalDataset, context adapter, init_llm, Ragger | ทั้งสองแบบ | โค้ดทำงาน |
| lrg/data/data_init.py | Entry point | CSV, law JSON ทุกไฟล์, nodes, section_idx | ทั้งสองแบบ | โค้ดทำงาน |
| lrg/retrieval/retrieval_init.py | Entry point/package import ทันที | HF/BM25/Cohere/BGE; ไม่เรียกค้นหาในเส้นทาง saved/Golden ที่เลือก | Dependency ตอนเริ่มต้นทั้งสองแบบ | โค้ดทำงาน |
| lrg/augmenter/augmenter.py | Ragger | บล็อกกฎหมายและ QUESTION | ทั้งสองแบบ | โค้ดทำงาน |
| lrg/prompting/prompt_manager.py | Entry point / Ragger | รายการ templates, schemas, Jinja และ enum model | ทั้งสองแบบ | โค้ดทำงาน |
| lrg/e2e/ragger.py | evaluate_ragger | Context, prompt, model, mapping และ metadata | ทั้งสองแบบ | โค้ดทำงาน |
| lrg/llm/collections/openai | init_llm / Ragger | Local OpenAI-compatible endpoint เมื่อสั่งรันภายหลัง | ทั้งสองแบบ | โค้ดทำงาน |
| chunking/golden/nodes.json | EvalDataset | TextNodes ของกฎหมาย | ทั้งสองแบบ | ข้อมูล |
| test_data/laws/*.json และ dump/section_idx.json | EvalDataset constructor | Law catalog และโครงสร้าง QA | ทั้งสองแบบ | ข้อมูล |
| data_splits/tax_engineering_10.csv | Configs ทั้งสองแบบ | question/relevant_laws/source_idx | ทั้งสองแบบ | ข้อมูล |
| data_splits/tax_heldout_40.csv | ไม่มี config ปัจจุบันเรียก | สงวนไว้สำหรับ final test ห้าม tuning | งานอนาคต | ข้อมูล |
| test_data/hf_tax.csv | ไม่มี config ปัจจุบันเรียก | หลักฐานแหล่งข้อมูลต้นฉบับ | ทั้งสองแบบ | ข้อมูลอ้างอิง |
| results/.../retrieval_results.json | init_saved_retriever | IDs และคะแนนตามลำดับที่เลือก | Retrieved | ข้อมูลนำเข้าที่บันทึกไว้ |
| reference_results | เปรียบเทียบด้วยตนเอง | Engineering outputs/audits จาก source | ทั้งสองแบบ | ผลอ้างอิง |
| tools/evaluation/audit_common_interface_v3_citation_id.py | CLI เมื่อต้องการตรวจ | Output/context interface | ทั้งสองแบบ | เครื่องมือ |
| vendor/llama-index-indices-managed-bge-m3 | pip แบบ editable แล้ว retrieval_init | BGE integration เฉพาะส่วนจาก source | Import ตอนเริ่มต้น | Dependency |
| vendor/core_overrides | tools/apply_core_overrides.py ระหว่างเตรียม environment ใหม่ | ไฟล์ core ใน environment ที่ติดตั้ง | ความเข้ากันได้ทั้งสองแบบ | Dependency |
| docs/DEPENDENCY_MANIFEST.md | ผู้อ่านเอกสาร | รายการ source/destination/เหตุผลและดัชนี hash รายไฟล์ | ทั้งสองแบบ | เอกสาร |

รายละเอียดของไฟล์ที่คัดลอกแต่ละไฟล์ รวม compatibility prompts อยู่ใน `DEPENDENCY_MANIFEST.md`

คง relative paths เดิมไว้โดยตั้งใจ เพื่อไม่เปลี่ยนชื่อโฟลเดอร์ `golden` ซึ่งมีผลต่อ `strat_name`, ข้อมูลนำเข้าของ saved adapter หรือความหมายของ config

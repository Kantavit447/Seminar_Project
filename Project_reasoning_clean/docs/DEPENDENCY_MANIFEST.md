# รายการไฟล์และ dependencies

> อัปเดต 18 กันยายน 2026: แก้ startup เป็น lazy import แล้ว และนำ dependencies ของ Live Retrieval ออกจาก requirements สำหรับ generation-only ตรวจ imports กับ Saved/Golden แบบ offline ผ่านแล้ว รายละเอียดอยู่ใน [รายงานการแก้ไข](LAZY_IMPORT_FIX_REPORT.md) ข้อความเรื่อง eager imports และข้อจำกัดการตรวจ imports ด้านล่างเป็นสถานะก่อนแก้ ไม่ใช่สถานะล่าสุด


ต้นทาง: `C:/NitiBench/Project_meandyou` อ่านอย่างเดียว ปลายทาง: `C:/NitiBench/Project_reasoning_clean`

ตารางนี้ระบุไฟล์ที่คัดลอกทุกไฟล์ โดยมี hash ใน `COPY_MANIFEST.json` ไม่มีการแก้ application code, config หรือ prompt การแปลครั้งนี้เปลี่ยนเฉพาะเอกสารอธิบาย

## โค้ดและทรัพยากรที่จำเป็นตอนทำงาน

| Path เดิมจาก source | Path ในปลายทาง | ผู้เรียกหรือจุดอ้างอิง | เหตุผล |
|---|---|---|---|
| lrg/__init__.py | lrg/__init__.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | ตัวเริ่มต้น Python package |
| script/response_e2e.py | script/response_e2e.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | จุดเริ่มต้นการเรียกผ่าน CLI |
| lrg/data/__init__.py | lrg/data/__init__.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | response_e2e import EvalDataset |
| lrg/data/data_init.py | lrg/data/data_init.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | EvalDataset โหลดกฎหมาย nodes และข้อมูล Tax |
| lrg/e2e/__init__.py | lrg/e2e/__init__.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | response_e2e import Ragger |
| lrg/e2e/ragger.py | lrg/e2e/ragger.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | Ragger จัดการ context การเรียกโมเดล mapping และ metadata |
| lrg/augmenter/__init__.py | lrg/augmenter/__init__.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | response_e2e import augmenter |
| lrg/augmenter/augmenter.py | lrg/augmenter/augmenter.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | จัดรูปแบบ context ตาม Common Interface v3 |
| lrg/prompting/__init__.py | lrg/prompting/__init__.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | response_e2e import PromptManager |
| lrg/prompting/prompt_manager.py | lrg/prompting/prompt_manager.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | โหลด prompt/schema สร้าง enum และประกอบ prompt |
| lrg/llm/__init__.py | lrg/llm/__init__.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | init_llm เลือก wrapper สำหรับ Qwen |
| lrg/llm/collections/openai/__init__.py | lrg/llm/collections/openai/__init__.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | ส่งออก OpenAIModel และ OpenAIConfig ให้โมดูลอื่นใช้ |
| lrg/llm/collections/openai/config.py | lrg/llm/collections/openai/config.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | กำหนดค่า API ด้วย Pydantic |
| lrg/llm/collections/openai/model.py | lrg/llm/collections/openai/model.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | ส่งคำขอและแปลงผลแบบ OpenAI-compatible |
| lrg/retrieval/__init__.py | lrg/retrieval/__init__.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | ตัวเริ่มต้น package import retrieval_init ทันที |
| lrg/retrieval/retrieval_init.py | lrg/retrieval/retrieval_init.py | ลำดับ dependencies ที่ import จาก script/response_e2e.py | Entry point import init_retriever ทันที แม้ใช้ saved/Golden |
| lrg/prompting/templates/response-tax-v3-citation-id-enum/turn0.md | lrg/prompting/templates/response-tax-v3-citation-id-enum/turn0.md | PromptManager._init_template() | Template ของ Direct ที่ใช้งานจริง |
| lrg/prompting/templates/response-wangchan/turn0.md | lrg/prompting/templates/response-wangchan/turn0.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-wangchan/turn1.md | lrg/prompting/templates/response-wangchan/turn1.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-wangchan/turn2.md | lrg/prompting/templates/response-wangchan/turn2.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-wangchan/turn3.md | lrg/prompting/templates/response-wangchan/turn3.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/coverage-contradiction-tax/turn0.md | lrg/prompting/templates/coverage-contradiction-tax/turn0.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/coverage-contradiction-tax/turn1.md | lrg/prompting/templates/coverage-contradiction-tax/turn1.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/coverage-contradiction-tax/turn2.md | lrg/prompting/templates/coverage-contradiction-tax/turn2.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/coverage-contradiction-tax/turn3.md | lrg/prompting/templates/coverage-contradiction-tax/turn3.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/coverage-contradiction-tax/turn4.md | lrg/prompting/templates/coverage-contradiction-tax/turn4.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/coverage-contradiction-wangchan/turn0.md | lrg/prompting/templates/coverage-contradiction-wangchan/turn0.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/coverage-contradiction-wangchan/turn1.md | lrg/prompting/templates/coverage-contradiction-wangchan/turn1.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/coverage-contradiction-wangchan/turn2.md | lrg/prompting/templates/coverage-contradiction-wangchan/turn2.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/coverage-contradiction-wangchan/turn3.md | lrg/prompting/templates/coverage-contradiction-wangchan/turn3.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/coverage-contradiction-wangchan/turn4.md | lrg/prompting/templates/coverage-contradiction-wangchan/turn4.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-long-tax/turn0.md | lrg/prompting/templates/response-long-tax/turn0.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-long-tax/turn1.md | lrg/prompting/templates/response-long-tax/turn1.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-long-tax/turn2.md | lrg/prompting/templates/response-long-tax/turn2.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-long-tax/turn3.md | lrg/prompting/templates/response-long-tax/turn3.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-long-wangchan/turn0.md | lrg/prompting/templates/response-long-wangchan/turn0.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-long-wangchan/turn1.md | lrg/prompting/templates/response-long-wangchan/turn1.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-long-wangchan/turn2.md | lrg/prompting/templates/response-long-wangchan/turn2.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-long-wangchan/turn3.md | lrg/prompting/templates/response-long-wangchan/turn3.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-pure-tax/turn0.md | lrg/prompting/templates/response-pure-tax/turn0.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-pure-tax/turn1.md | lrg/prompting/templates/response-pure-tax/turn1.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-pure-tax/turn2.md | lrg/prompting/templates/response-pure-tax/turn2.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-pure-tax/turn3.md | lrg/prompting/templates/response-pure-tax/turn3.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-pure-wangchan/turn0.md | lrg/prompting/templates/response-pure-wangchan/turn0.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-pure-wangchan/turn1.md | lrg/prompting/templates/response-pure-wangchan/turn1.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-pure-wangchan/turn2.md | lrg/prompting/templates/response-pure-wangchan/turn2.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-pure-wangchan/turn3.md | lrg/prompting/templates/response-pure-wangchan/turn3.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-o1-tax/turn0.md | lrg/prompting/templates/response-o1-tax/turn0.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/response-o1-wangchan/turn0.md | lrg/prompting/templates/response-o1-wangchan/turn0.md | PromptManager._init_template() | Dependency ของรายการ templates ที่โหลดตอนเริ่มต้น ไม่ใช่การทดลองที่ clean project รองรับ |
| lrg/prompting/templates/default_query.md | lrg/prompting/templates/default_query.md | PromptManager/Jinja | Template ที่ constructor โหลด หรือ system prompt ของ Direct ที่ใช้งานจริง |
| lrg/prompting/templates/o1_query.md | lrg/prompting/templates/o1_query.md | PromptManager/Jinja | Template ที่ constructor โหลด หรือ system prompt ของ Direct ที่ใช้งานจริง |
| lrg/prompting/templates/system_prompt_tax_v3_citation_id_enum.md | lrg/prompting/templates/system_prompt_tax_v3_citation_id_enum.md | PromptManager/Jinja | Template ที่ constructor โหลด หรือ system prompt ของ Direct ที่ใช้งานจริง |
| lrg/prompting/structured_outputs/system_response_v3_citation_id.json | lrg/prompting/structured_outputs/system_response_v3_citation_id.json | PromptManager._init_template() | Response schema ที่ใช้จริง หรือ evaluation schema ที่โหลดทันทีตอนสร้าง object |
| lrg/prompting/structured_outputs/system_eval.json | lrg/prompting/structured_outputs/system_eval.json | PromptManager._init_template() | Response schema ที่ใช้จริง หรือ evaluation schema ที่โหลดทันทีตอนสร้าง object |
| llama_index/llama-index-integrations/indices/llama-index-indices-managed-bge-m3/pyproject.toml | vendor/llama-index-indices-managed-bge-m3/pyproject.toml | retrieval_init -> BGEM3Index | Local editable integration ที่พบใน metadata ของ source package ไม่ได้สร้าง index |
| llama_index/llama-index-integrations/indices/llama-index-indices-managed-bge-m3/README.md | vendor/llama-index-indices-managed-bge-m3/README.md | retrieval_init -> BGEM3Index | Local editable integration ที่พบใน metadata ของ source package ไม่ได้สร้าง index |
| llama_index/llama-index-integrations/indices/llama-index-indices-managed-bge-m3/llama_index/indices/managed/bge_m3/__init__.py | vendor/llama-index-indices-managed-bge-m3/llama_index/indices/managed/bge_m3/__init__.py | retrieval_init -> BGEM3Index | Local editable integration ที่พบใน metadata ของ source package ไม่ได้สร้าง index |
| llama_index/llama-index-integrations/indices/llama-index-indices-managed-bge-m3/llama_index/indices/managed/bge_m3/base.py | vendor/llama-index-indices-managed-bge-m3/llama_index/indices/managed/bge_m3/base.py | retrieval_init -> BGEM3Index | Local editable integration ที่พบใน metadata ของ source package ไม่ได้สร้าง index |
| llama_index/llama-index-integrations/indices/llama-index-indices-managed-bge-m3/llama_index/indices/managed/bge_m3/retriever.py | vendor/llama-index-indices-managed-bge-m3/llama_index/indices/managed/bge_m3/retriever.py | retrieval_init -> BGEM3Index | Local editable integration ที่พบใน metadata ของ source package ไม่ได้สร้าง index |
| llama_index/LICENSE | vendor/llama-index-indices-managed-bge-m3/LICENSE | ใบอนุญาตของโค้ดภายนอก | เก็บใบอนุญาตของต้นทาง |
| llama_index/llama-index-core/llama_index/core/base/base_retriever.py | vendor/core_overrides/llama_index/core/base/base_retriever.py | Editable core ของ source / รูปแบบ overlay ใน Docker | การแก้ core ของ source ที่ทราบ ใช้เฉพาะใน environment ใหม่ |
| llama_index/llama-index-core/llama_index/core/evaluation/retrieval/base.py | vendor/core_overrides/llama_index/core/evaluation/retrieval/base.py | Editable core ของ source / รูปแบบ overlay ใน Docker | การแก้ core ของ source ที่ทราบ ใช้เฉพาะใน environment ใหม่ |
| llama_index/llama-index-core/llama_index/core/evaluation/retrieval/metrics.py | vendor/core_overrides/llama_index/core/evaluation/retrieval/metrics.py | Editable core ของ source / รูปแบบ overlay ใน Docker | การแก้ core ของ source ที่ทราบ ใช้เฉพาะใน environment ใหม่ |
| llama_index/llama-index-core/LICENSE | vendor/core_overrides/LICENSE | ใบอนุญาตของโค้ดภายนอก | เก็บใบอนุญาตของต้นทาง |

## Config ที่ต้องเก็บ

| Path เดิมจาก source | Path ในปลายทาง | ผู้เรียกหรือจุดอ้างอิง | เหตุผล |
|---|---|---|---|
| config/local/response/section_based_rag_qwen_direct_v3_citation_id_enum_engineering_10.yaml | config/local/response/section_based_rag_qwen_direct_v3_citation_id_enum_engineering_10.yaml | response_e2e.main() | Config Direct engineering ปัจจุบันหรือ diagnostic หนึ่งข้อเดิม โดยไม่แก้ค่า |
| config/local/response/golden_qwen_direct_v3_citation_id_enum_engineering_10.yaml | config/local/response/golden_qwen_direct_v3_citation_id_enum_engineering_10.yaml | response_e2e.main() | Config Direct engineering ปัจจุบันหรือ diagnostic หนึ่งข้อเดิม โดยไม่แก้ค่า |
| config/local/response/section_based_rag_qwen_direct_v3_citation_id_enum_diagnostic_source_0023.yaml | config/local/response/section_based_rag_qwen_direct_v3_citation_id_enum_diagnostic_source_0023.yaml | response_e2e.main() | Config Direct engineering ปัจจุบันหรือ diagnostic หนึ่งข้อเดิม โดยไม่แก้ค่า |
| config/local/response/golden_qwen_direct_v3_citation_id_enum_diagnostic_source_0008.yaml | config/local/response/golden_qwen_direct_v3_citation_id_enum_diagnostic_source_0008.yaml | response_e2e.main() | Config Direct engineering ปัจจุบันหรือ diagnostic หนึ่งข้อเดิม โดยไม่แก้ค่า |

## ข้อมูลที่ต้องเก็บ

| Path เดิมจาก source | Path ในปลายทาง | ผู้เรียกหรือจุดอ้างอิง | เหตุผล |
|---|---|---|---|
| chunking/golden/nodes.json | chunking/golden/nodes.json | EvalDataset/config และหลักฐานการแบ่งชุดข้อมูล | ทั้งสองแบบ: TextNodes และการค้น provision แบบตรงตัว |
| dump/section_idx.json | dump/section_idx.json | EvalDataset/config และหลักฐานการแบ่งชุดข้อมูล | ทั้งสองแบบ: EvalDataset constructor อ่านเสมอ |
| data_splits/tax_engineering_10.csv | data_splits/tax_engineering_10.csv | EvalDataset/config และหลักฐานการแบ่งชุดข้อมูล | ทั้งสองแบบ: ชุด engineering ที่เลือกใช้จริง |
| data_splits/tax_heldout_40.csv | data_splits/tax_heldout_40.csv | EvalDataset/config และหลักฐานการแบ่งชุดข้อมูล | สงวนสำหรับ final test ตรวจเฉพาะจำนวน ไม่ตรวจคำตอบ |
| test_data/hf_tax.csv | test_data/hf_tax.csv | EvalDataset/config และหลักฐานการแบ่งชุดข้อมูล | หลักฐาน dataset ต้นฉบับ configs ที่เลือกไม่ได้โหลดไฟล์นี้ |
| test_data/laws/ก0028-1B-0001.json | test_data/laws/ก0028-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ก0039-1B-0002.json | test_data/laws/ก0039-1B-0002.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ก0070-1B-0003.json | test_data/laws/ก0070-1B-0003.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ก0102-1B-0001.json | test_data/laws/ก0102-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ก0104-1B-0001.json | test_data/laws/ก0104-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ก0106-1B-0001.json | test_data/laws/ก0106-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ก0123-1B-0001.json | test_data/laws/ก0123-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ก0164-1B-0001.json | test_data/laws/ก0164-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ก0173-1C-0001.json | test_data/laws/ก0173-1C-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ก0178-1B-0001.json | test_data/laws/ก0178-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ก0185-1B-0001.json | test_data/laws/ก0185-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ค0031-1B-0001.json | test_data/laws/ค0031-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ท0002-1B-0001.json | test_data/laws/ท0002-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ท0009-1B-0001.json | test_data/laws/ท0009-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ท0010-1B-0001.json | test_data/laws/ท0010-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ธ0012-1B-0001.json | test_data/laws/ธ0012-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/น0002-1C-0001.json | test_data/laws/น0002-1C-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/บ0011-1B-0001.json | test_data/laws/บ0011-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ป0003-1D-0002.json | test_data/laws/ป0003-1D-0002.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ป0008-1D-0001.json | test_data/laws/ป0008-1D-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ป0043-1A-0001.json | test_data/laws/ป0043-1A-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ภ0002-1B-0001.json | test_data/laws/ภ0002-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ย0022-1B-0001.json | test_data/laws/ย0022-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ร0043-1B-0001.json | test_data/laws/ร0043-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ว0008-1B-0001.json | test_data/laws/ว0008-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ว0016-1B-0001.json | test_data/laws/ว0016-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ว0029-1B-0001.json | test_data/laws/ว0029-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ว0033-1B-0001.json | test_data/laws/ว0033-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ว0067-1B-0001.json | test_data/laws/ว0067-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ว0083-1B-0001.json | test_data/laws/ว0083-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ส0022-1B-0001.json | test_data/laws/ส0022-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ส0065-1B-0001.json | test_data/laws/ส0065-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ส0095-1B-0001.json | test_data/laws/ส0095-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ห0002-1B-0001.json | test_data/laws/ห0002-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ห0015-1B-0002.json | test_data/laws/ห0015-1B-0002.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |
| test_data/laws/ห0060-1B-0001.json | test_data/laws/ห0060-1B-0001.json | EvalDataset.set_law()/convert_to_qa() | ทั้งสองแบบ: โหลด law catalog ทั้งชุดเสมอ |

## ข้อมูลนำเข้าที่บันทึกไว้และจำเป็น

| Path เดิมจาก source | Path ในปลายทาง | ผู้เรียกหรือจุดอ้างอิง | เหตุผล |
|---|---|---|---|
| results/current/retrieval_evaluation/section_based_no_ref/retrieval_results.json | results/current/retrieval_evaluation/section_based_no_ref/retrieval_results.json | init_saved_retriever() | Retrieved: ผล top-10 เดิมที่บันทึกไว้เป็นข้อมูลนำเข้า คง path เดิม |

## เครื่องมือและผลอ้างอิงเสริม

| Path เดิมจาก source | Path ในปลายทาง | ผู้เรียกหรือจุดอ้างอิง | เหตุผล |
|---|---|---|---|
| tools/evaluation/audit_common_interface_v3_citation_id.py | tools/evaluation/audit_common_interface_v3_citation_id.py | การสั่งตรวจแบบ offline ด้วยตนเอง | เครื่องมือตรวจ interface ปัจจุบัน โดยไม่แก้โค้ด |
| results/current/common_interface_v3/section_based_direct_citation_id_enum_engineering_10/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response.json | reference_results/section_based_direct_citation_id_enum_engineering_10/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response.json | การเปรียบเทียบผล reproduce ของ clean project ภายหลัง | ผล engineering สำหรับอ้างอิงเท่านั้น ห้ามใช้เป็นข้อมูลเริ่ม resume |
| results/current/common_interface_v3/section_based_direct_citation_id_enum_engineering_10/audit/response_quality.json | reference_results/section_based_direct_citation_id_enum_engineering_10/audit/response_quality.json | การเปรียบเทียบผล reproduce ของ clean project ภายหลัง | ผล engineering สำหรับอ้างอิงเท่านั้น ห้ามใช้เป็นข้อมูลเริ่ม resume |
| results/current/common_interface_v3/section_based_direct_citation_id_enum_engineering_10/audit/response_quality.md | reference_results/section_based_direct_citation_id_enum_engineering_10/audit/response_quality.md | การเปรียบเทียบผล reproduce ของ clean project ภายหลัง | ผล engineering สำหรับอ้างอิงเท่านั้น ห้ามใช้เป็นข้อมูลเริ่ม resume |
| results/current/common_interface_v3/golden_direct_citation_id_enum_engineering_10/chunk-golden-no-ref-qwen/tax_response.json | reference_results/golden_direct_citation_id_enum_engineering_10/chunk-golden-no-ref-qwen/tax_response.json | การเปรียบเทียบผล reproduce ของ clean project ภายหลัง | ผล engineering สำหรับอ้างอิงเท่านั้น ห้ามใช้เป็นข้อมูลเริ่ม resume |
| results/current/common_interface_v3/golden_direct_citation_id_enum_engineering_10/audit/response_quality.json | reference_results/golden_direct_citation_id_enum_engineering_10/audit/response_quality.json | การเปรียบเทียบผล reproduce ของ clean project ภายหลัง | ผล engineering สำหรับอ้างอิงเท่านั้น ห้ามใช้เป็นข้อมูลเริ่ม resume |
| results/current/common_interface_v3/golden_direct_citation_id_enum_engineering_10/audit/response_quality.md | reference_results/golden_direct_citation_id_enum_engineering_10/audit/response_quality.md | การเปรียบเทียบผล reproduce ของ clean project ภายหลัง | ผล engineering สำหรับอ้างอิงเท่านั้น ห้ามใช้เป็นข้อมูลเริ่ม resume |

## ของเก่าหรือไฟล์ที่ไม่คัดลอก

| ต้นทาง | การจัดการ | เหตุผล |
|---|---|---|
| baseline_runner.py | ไม่คัดลอก | Entry point ปัจจุบันไม่ได้ import |
| script/metric_e2e.py และ metric configs เดิม | ไม่คัดลอก | ไม่ถูก import มีปัญหาสูตรและการเลือกโมเดล เลื่อนการปรับ evaluator ไว้ภายหลัง |
| results/legacy และผล No-RAG/Vanilla/v2/non-enum เดิม | ไม่คัดลอก | ไม่ใช่ข้อมูลนำเข้าของ configs ปัจจุบัน |
| Prompts/configs v2, inline-v3, non-enum-v3 เดิม | ไม่คัดลอก | PromptManager ปัจจุบันไม่ได้เลือกใช้ ยกเว้น compatibility task folders ที่จำเป็นและแจกแจงไว้ข้างต้น |
| backups, .venv, .venv_broken_backup, __pycache__, .git | ไม่คัดลอก | ไม่ใช่ runtime dependency อ่าน metadata ของ environment เก่าเพื่อดู versions เท่านั้น |
| lrg/retrieval/custom_retriever.py | ไม่คัดลอก | อ้างอิงเฉพาะ lazy branches NVEmbed/ColBERT/Jina ที่ไม่รองรับ จึงไม่ใส่ ragatouille |
| lrg/llm/collections/claude และ gemini | ไม่คัดลอก | init_llm ปัจจุบัน import เฉพาะ OpenAI-compatible wrapper |
| config/local/retrieval/proposed_tax_retrieval.yaml และเครื่องมือ rerun retrieval | ไม่คัดลอก | เป็นหลักฐานต้นทางเท่านั้น saved adapter ไม่อ้างอิง และ clean scope ไม่รัน retrieval ใหม่ |
| test_data/hf_wcx.csv และ naive chunking | ไม่คัดลอก | load_wangchan=false และ configs ที่คัดลอกใช้ golden nodes ทั้งหมด |
| llama_index checkout ส่วนใหญ่ รวม tests/examples/caches | ไม่คัดลอก | ประกาศ external packages และเก็บเฉพาะ integration/core overlays ที่จำเป็น |
| Handoff เดิม | ไม่คัดลอก | ใช้เอกสารเฉพาะ clean project แทน ไม่ใช่ runtime dependency |

## สิ่งที่ยังยืนยันไม่ได้

- Package stack ที่ใช้จริงในอดีต: source requirements ต่างจาก metadata ในข้อมูลสำรอง และไม่มี source venv ที่ทำงานได้เพื่อยืนยัน
- การแก้ไขอื่นใน external editable core/dependency tree: เก็บ overlays ที่ทราบแล้ว แต่ยังไม่พิสูจน์ความเทียบเท่าของ dependencies ทั้งหมด
- Ollama server/model digest และค่าของ server ในอดีต: ไม่ได้ติดต่อหรือแก้ไข

## ไฟล์ที่สร้างใหม่แทนการคัดลอก

`README.md`, `requirements.txt`, `.env.example`, `.gitignore`, `tools/apply_core_overrides.py`,
`PROJECT_MAP.md`, `PIPELINE.md`, `CLEANUP_TODO.md`, เอกสารฉบับนี้, `COPY_MANIFEST.json`,
`OFFLINE_VALIDATION.md`, `OFFLINE_VALIDATION.json`, `SOURCE_STATUS_BEFORE.txt` และ `SOURCE_STATUS_AFTER.txt`

Application pins ใน requirements มาจาก source `requirements.txt`; torch มาจาก Dockerfile;
LlamaIndex versions มาจาก editable pyproject/package metadata; YAML/tqdm/typing versions มาจาก metadata ในข้อมูลสำรอง

ไม่ได้คัดลอก secrets จริงหรือเนื้อหาของ environment เดิม

ภายหลังเพิ่ม `AGENTS.md` ที่ราก clean project เพื่อบันทึกความต้องการของผู้ใช้ให้เอกสารอธิบาย `.md` เขียนเป็นภาษาไทย

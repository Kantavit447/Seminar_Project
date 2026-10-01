# IRAC สำหรับชุด engineering

วันที่เพิ่ม: 1 ตุลาคม 2026

แผนหลักอยู่ใน [RESEARCH_PROTOCOL.md](RESEARCH_PROTOCOL.md) เอกสารนี้อธิบายการเพิ่ม IRAC และขั้นตอนทดลองกับ engineering 10 ข้อ การสร้างคำตอบจริงให้ผู้ใช้เป็นผู้รัน ส่วนการตรวจของผู้ช่วยใช้เฉพาะ offline

## ที่มาของวิธีและส่วนที่เราดัดแปลง

ชื่อวิธีในรายงาน: **Zero-shot IRAC prompting adapted from Yu et al. (2022)**

อ้างอิง [Legal Prompting: Teaching a Language Model to Think Like a Lawyer — หัวข้อ 4.5 และ Figure 5](https://arxiv.org/html/2212.01326#S4.SS5) งานต้นฉบับทดลอง legal reasoning prompt แบบ zero-shot กับ COLIEE และ GPT-3 โดยให้ตัดสิน True/False ตาม premise และ hypothesis

เราใช้แนวคิด Issue → Rule → Application → Conclusion กับ Thai Tax QA บน Qwen โดยกำหนดสี่หัวข้อไว้ในสตริง `analysis` เพื่ออ่านและตรวจโครงสร้างได้ง่าย การเขียนคำสั่งสี่หัวข้ออย่างชัดเจนและการคืน JSON/P-ID เป็นการดัดแปลงของโปรเจกต์นี้ ไม่ได้คัดลอก prompt ต้นฉบับทุกคำ

IRAC เป็น baseline เพื่อทดสอบโครงสร้างทางกฎหมาย ไม่ถือว่าเหนือกว่า Direct หรือ CoT ล่วงหน้า และ Table 4 ของงานต้นฉบับก็ไม่ได้รายงานว่า IRAC ได้คะแนนดีที่สุดในทุกเงื่อนไข

## Prompt อยู่ตรงไหน

- [template IRAC](../lrg/prompting/templates/response-tax-v3-citation-id-enum-irac/turn0.md): คำชี้นำ I/R/A/C ที่เพิ่มใหม่
- [PromptManager](../lrg/prompting/prompt_manager.py): เลือก template เมื่อ config ระบุ `reasoning_method: irac`
- [system prompt ร่วม](../lrg/prompting/templates/system_prompt_tax_v3_citation_id_enum.md): ข้อกำหนดหลักฐาน ภาษา ความกระชับ และ JSON เดิม
- [runner](../script/response_e2e.py): บังคับให้ Retrieved ของ IRAC ใช้ saved artifact และแยกชื่อไฟล์ dump prompt

Prompt มี system message, user instruction และคำถามพร้อม context ไม่มีตัวอย่างคำตอบ และเรียกโมเดลหนึ่งรอบเพื่อคืน `analysis`, `answer`, `citation_ids` พร้อมกัน

`analysis` ยังคงเป็นสตริงเดียว ภายในให้แบ่ง I — Issue, R — Rule, A — Application และ C — Conclusion เป็นสี่ส่วนสั้น ๆ ตามข้อจำกัดความกระชับเดิม ส่วน `answer` เป็นคำตอบภาษาไทย และ `citation_ids` ใช้ P-ID จากรายการที่อนุญาต

คงคำสั่ง `analysis` ภาษาอังกฤษตาม Direct/CoT เดิม หากโมเดลตอบผิดภาษาหรือไม่แบ่งหัวข้อ ให้บันทึกเป็นข้อสังเกตของผลทดลอง ไม่แปลผลที่บันทึกไว้ และไม่เพิ่มการเรียกซ้ำอัตโนมัติจากเหตุนี้

## เงื่อนไขการทดลอง

| รายการ | Golden | Saved Retrieved |
|---|---|---|
| แหล่ง context | exact resolve จาก `relevant_laws` และ `nodes.json` | `retrieval_results.json` เดิม |
| โมเดลใน config | `qwen2.5-16k:7b` | `qwen2.5-32k:7b` |
| context window ที่ตั้งไว้ | 16,384 | 32,768 |
| จำนวน context | ตามกฎหมายอ้างอิงของข้อ | Top 10 เดิมและลำดับเดิม |
| ชุดข้อมูล | engineering 10 | engineering 10 |

ทั้งสองใช้ `max_tokens: 4096`, `temperature: 0.0`, `seed: 42`, `batch_size: 1` และ `diagnostic.max_retries: 1` เทียบ Direct/CoT ใน context เดียวกันด้วยค่ารันเดิม เป้าหมาย 32k ร่วมกันก่อน final test ยังต้องตรวจตาม Protocol

มี config ใหม่สี่ไฟล์ใน `config/local/response/`:

| เงื่อนไข | ชื่อไฟล์ |
|---|---|
| Golden หนึ่งข้อ | `golden_qwen_irac_v3_citation_id_enum_diagnostic_source_0008_ctx16384.yaml` |
| Saved Retrieved หนึ่งข้อ | `section_based_rag_qwen_irac_v3_citation_id_enum_diagnostic_source_0008_ctx32768.yaml` |
| Golden 10 ข้อ | `golden_qwen_irac_v3_citation_id_enum_engineering_10_ctx16384.yaml` |
| Saved Retrieved 10 ข้อ | `section_based_rag_qwen_irac_v3_citation_id_enum_engineering_10_ctx32768.yaml` |

แบบหนึ่งข้อใช้ source `0008` ซึ่งตรงกับ runtime `0004` ส่วน engineering 10 ใช้ source IDs `0000, 0001, 0002, 0003, 0008, 0023, 0026, 0036, 0041, 0046`

## สิ่งที่คงเดิม

System prompt, Direct/CoT templates, JSON schema, citation enum, P-ID mapping, Golden resolver, SavedRetrievalRetriever, augmenter, model wrapper, การบันทึกผลให้อ่านได้ และกติกาความล้มเหลวใช้ implementation เดิม Config ใหม่เปลี่ยนจาก CoT เฉพาะชื่อวิธีและเส้นทางผลลัพธ์/diagnostic เท่านั้น

ไม่มีการทำ embedding, live BGE-M3, rerank หรือค้นกฎหมายเพิ่ม และไม่มี verifier/correction ใน IRAC baseline นี้ ผลเดิมของ Direct และ CoT จึงไม่ต้องรันใหม่เพราะการเพิ่ม IRAC

## ตรวจ offline

ใช้เครื่องมือตรวจเดิมร่วมกัน โดยเพิ่ม `--method irac` คำสั่งเดิมที่ไม่ระบุ method ยังตรวจ CoT เหมือนเดิม รันจาก `C:\NitiBench\Project_reasoning_clean`:

```powershell
.\.venv\Scripts\python.exe -B tools/validation/validate_zero_shot_cot_offline.py --method irac
```

ตรวจ engineering 10 × 2 contexts ผ่าน dataset, augmenter และ Ragger จริง โดยใช้เพียงข้อมูลชื่อโมเดลและปิดกั้น LLM client, network และ live retrieval imports ตรวจว่าต่างจาก Direct เฉพาะ user instruction, context/ลำดับ/P-ID/schema คงเดิม, Golden resolve ครบ, enum ปฏิเสธ ID นอก context และไม่มีเฉลยหลุดเข้า prompt

การตรวจเทียบ PromptManager ก่อนเพิ่ม IRAC ใช้ `--baseline-prompt-manager` เพื่อยืนยัน Direct และ CoT เดิม และ `--dump-prompts` เพื่อตรวจเส้นทาง dump prompt ของ IRAC ทั้งสอง context รายงานรอบเพิ่ม IRAC เก็บใน `results/current/offline_validation/irac_20261001.json` และรายงานตรวจ CoT ซ้ำอยู่ใน `results/current/offline_validation/zero_shot_cot_after_irac_20261001.json`

ผล offline ไม่ใช่คะแนนคุณภาพหรือการยืนยันว่า Qwen จะทำตาม IRAC ได้ ต้องตรวจคำตอบจากการรันจริงต่อไป

## ผู้ใช้รัน: เริ่ม Golden หนึ่งข้อ

คำสั่งต่อไปนี้เรียกโมเดลจริง ระบุ interpreter ของ venv โดยตรงจึงไม่ต้อง activate ก่อน:

```powershell
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/golden_qwen_irac_v3_citation_id_enum_diagnostic_source_0008_ctx16384.yaml
```

จะได้ `tax_response.json` และ `tax_response_readable.md` ใน:

`results/current/common_interface_v3/diagnostics/golden_irac_v3_citation_id_enum_source_0008_ctx16384/chunk-golden-no-ref-qwen/`

ตรวจว่าอ่าน JSON ได้ มีคำตอบและ citation, source/runtime ถูกข้อ รวมถึงดูว่ามี I/R/A/C และใช้หลักฐานตาม context หรือไม่ การมีหัวข้อครบไม่ใช่หลักฐานว่าคำตอบถูกกฎหมาย หากเกิด failure ให้ตรวจไฟล์ diagnostic ก่อนตัดสินใจรันซ้ำ

เมื่อตรวจ Golden หนึ่งข้อแล้วจึงทดลอง Saved Retrieved หนึ่งข้อ:

```powershell
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/section_based_rag_qwen_irac_v3_citation_id_enum_diagnostic_source_0008_ctx32768.yaml
```

จากนั้นจึงรัน engineering 10 ทีละเงื่อนไข:

```powershell
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/golden_qwen_irac_v3_citation_id_enum_engineering_10_ctx16384.yaml
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/section_based_rag_qwen_irac_v3_citation_id_enum_engineering_10_ctx32768.yaml
```

ผล engineering แยกที่ `results/current/common_interface_v3/golden_irac_citation_id_enum_engineering_10_ctx16384/` และ `results/current/common_interface_v3/section_based_irac_citation_id_enum_engineering_10_ctx32768/` ใต้ชื่อกลยุทธ์ของแต่ละ context จะมี JSON ที่จัดย่อหน้าและ Markdown สำหรับอ่านโดยอัตโนมัติ

หากต้องการดู prompt ก่อนเรียกโมเดล ให้เติม `--dump-final-prompt` ท้ายคำสั่ง diagnostic จะได้ `llm_calls=0` และไฟล์ `golden_irac_...` หรือ `section_based_irac_...` ใน `results/current/debug_prompts/`

รอบนี้ยังไม่สร้าง config หรือรัน heldout และยังไม่ประเมินคะแนนด้วย LLM ภายนอก


## เมื่อ engineering หยุดเพราะคำตอบเต็มงบ output

หากเกิด `LengthFinishReasonError` ใช้ตัวเลือก `--continue-on-length-failure` กับคำสั่ง engineering เดิม เพื่อคงข้อที่ล้มเหลวเป็น generation failure และทำเฉพาะข้อค้างโดยไม่เรียกข้อเดิมซ้ำ รายละเอียดสาเหตุและคำสั่งรันต่ออยู่ใน [รายงาน Golden IRAC ข้อ 0001](GOLDEN_IRAC_ENGINEERING_FAILURE_0001.md)

ตัวเลือกนี้เพิ่มไฟล์ `tax_run_status.json` และ `tax_run_status.md` แยกจากคำตอบสำเร็จ ไม่เปลี่ยน prompt หรือค่าการสร้างคำตอบ ไม่ใช้กับ diagnostic หนึ่งข้อ และไม่ได้แก้การวนข้อความของโมเดล

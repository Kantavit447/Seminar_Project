# รายงานแก้ปัญหา startup import ของ generation-only pipeline

วันที่ 18 กันยายน 2026

## ผลลัพธ์

ตรวจด้วย Python ใน `.venv` ของ clean project แล้วได้ `IMPORT OK` โดยนำเข้า `lrg` และ `script.response_e2e` ได้สำเร็จ ไม่มีการ upgrade/downgrade ติดตั้ง หรือถอน packages

สคริปต์ตรวจบล็อกการเชื่อมต่อ network และปฏิเสธ imports ของ live stack หากมีการพยายามโหลด จึงไม่ได้แก้ด้วย mock ของ dependencies ที่ขาดหรือข้าม import error

## สาเหตุและสิ่งที่แก้

เดิม entry point import `lrg.retrieval.retrieval_init` โดยตรง และ package initializer import โมดูลเดียวกันทันที จึงโหลด HuggingFace → sentence-transformers → transformers ก่อนอ่าน config แม้ต้องการเพียง Saved Retrieved หรือ Golden

แก้โค้ดสองไฟล์:

1. `script/response_e2e.py`: เปลี่ยน import เป็น `from lrg.retrieval import init_retriever`
2. `lrg/retrieval/__init__.py`: ใช้ฟังก์ชันตัวส่งต่อชื่อและ arguments เดิม โดย import live implementation ภายในฟังก์ชันเมื่อถูกเรียกจริงเท่านั้น

Saved Retrieved ยังเรียก `init_saved_retriever()` ส่วน Golden ยังใช้ `retriever=None` และ exact resolver ตามเดิม ทั้งสองเส้นทางไม่เรียกตัวส่งต่อไป live retrieval

## การลด requirements

นำรายการที่เป็น live retrieval ออกจาก `requirements.txt`:

- `llama-index-embeddings-huggingface==0.5.1`
- `llama-index-embeddings-cohere==0.4.0`
- `llama-index-retrievers-bm25==0.5.2`
- `FlagEmbedding==1.2.11`
- `-e ./vendor/llama-index-indices-managed-bge-m3`

ลบ comments ที่อธิบาย eager dependency เดิมด้วย ไม่ได้เปลี่ยน versions ของรายการที่เหลือ และไม่ได้ถอน packages ที่ติดตั้งอยู่แล้ว

ยังเก็บ Torch เพราะ entry point import และเรียก `torch.cuda.empty_cache()` ยังเก็บ llama-index-core เพราะใช้ TextNode, NodeWithScore, EmbeddingQAFinetuneDataset และ BaseRetriever ส่วน vendor/live implementation เดิมยังอยู่บนดิสก์ ไม่ได้ลบหรือ refactor

## ผลตรวจ offline

| รายการ | ผล |
|---|---|
| Import `lrg` และ `script.response_e2e` ใน clean venv | ผ่าน: IMPORT OK |
| บล็อกและตรวจว่าไม่โหลด transformers, sentence_transformers, FlagEmbedding | ผ่าน |
| บล็อกและตรวจว่าไม่โหลด HuggingFace/Cohere/BM25/BGE integration และ lrg.retrieval.retrieval_init | ผ่าน |
| Saved Retrieved engineering 10: nodes และลำดับตรง reference | ผ่าน 10/10 |
| Golden engineering 10: exact resolve ไม่มี unresolved และ nodes ตรง reference | ผ่าน 10/10 |
| ประกอบ prompts ด้วย PromptManager จริง | ผ่านทั้งสอง contexts |
| Provision map และ dynamic enum validate model_content อ้างอิง | ผ่านทั้งสอง contexts |
| แปลง citation IDs จากผลอ้างอิงเป็น final content และ validate citations | ตรง reference ทั้ง 20 รายการ |
| Hash ของโค้ด/config/prompt/schema ที่ไม่อยู่ในขอบเขตแก้ | ไม่เปลี่ยน |
| git status ของ source Project_meandyou เทียบก่อนทำ | ไม่เปลี่ยน |

การตรวจ 10+10 ข้อข้างต้นเป็นการอ่านข้อมูล engineering และประมวลผล context/prompt/interface ในหน่วยความจำ ไม่ใช่การรัน generation experiment หรือประเมินคุณภาพคำตอบใหม่ ใช้ `PromptDumpLLM` เป็น metadata แทนการสร้าง API client และปิด model/live-retriever initialization ระหว่างตรวจ

## ขอบเขตที่คงเดิม

ไม่แก้ SavedRetrievalRetriever, Golden resolver, Ragger, EvalDataset, Augmenter, PromptManager, prompts, citation enum, output schema, P-ID mapping หรือ experiment configs และไม่ได้แก้ source project

## ข้อจำกัดและสิ่งที่ยังไม่ได้รัน

- ไม่เรียก Ollama/Qwen, ไม่สร้าง embeddings/index, ไม่รัน live retrieval และไม่รัน held-out
- ไม่อ้างว่าผล generation ใหม่จะเหมือนเดิมทุกตัวอักษร เพราะยังไม่มี model call
- ไม่ทดสอบ live retrieval ซึ่งยังต้องมี environment ของ backend ที่เข้ากันได้เมื่อเรียกใช้งาน
- ไม่ติดตั้ง environment ใหม่จาก requirements ที่ลดแล้ว การตรวจ import ใช้ clean venv ที่ผู้ใช้มี โดยบล็อกโมดูล live stack แบบ fail-fast
- ครั้งแรกเปิด Python ใน sandbox ไม่สำเร็จ จึงตรวจซ้ำโดยได้รับสิทธิ์ใช้งานนอก sandbox แล้วผ่าน

## เอกสารที่ปรับ

เพิ่มรายงานนี้ และเพิ่มหมายเหตุใน README กับเอกสาร .md เดิมใน docs เพื่อแยกสถานะตอนสร้าง clean project ออกจากสถานะหลังแก้ lazy import บันทึก validation และ copy manifests เดิมยังคงเป็นหลักฐานของการย้ายครั้งแรก ไม่แก้ผลใน JSON ย้อนหลัง

## คำสั่งตรวจ import ด้วยตนเอง

เรียกจากราก clean project:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -B -c "import lrg; import script.response_e2e; print('IMPORT OK')"
```

## Diff ของโค้ดและ requirements

```diff
--- ก่อน/script\response_e2e.py
+++ หลัง/script\response_e2e.py
@@ -12,7 +12,7 @@
     sys.path.append("/app/LRG")
 
 from lrg.data import EvalDataset
-from lrg.retrieval.retrieval_init import init_retriever
+from lrg.retrieval import init_retriever
 from lrg.prompting import PromptManager
 from lrg.llm import init_llm
 from lrg.augmenter import NitiLinkAugmenterConfig, NitiLinkAugmenter

```

```diff
--- ก่อน/lrg\retrieval\__init__.py
+++ หลัง/lrg\retrieval\__init__.py
@@ -1,3 +1,12 @@
-# from .retrieval_evaluation import evaluate_retrieval
+"""Load live retrieval dependencies only when a live retriever is requested."""
 
-from .retrieval_init import init_retriever+
+def init_retriever(model_name, dataset, k, strat_name):
+    from .retrieval_init import init_retriever as init_live_retriever
+
+    return init_live_retriever(
+        model_name=model_name,
+        dataset=dataset,
+        k=k,
+        strat_name=strat_name,
+    )

```

```diff
--- ก่อน/requirements.txt
+++ หลัง/requirements.txt
@@ -12,10 +12,3 @@
 typing_extensions==4.16.0
 torch==2.2.0
 llama-index-core==0.12.19
-llama-index-embeddings-huggingface==0.5.1
-llama-index-embeddings-cohere==0.4.0
-llama-index-retrievers-bm25==0.5.2
-# Eager retriever import requires this local integration package.
-# Its unchanged package metadata declares FlagEmbedding/peft dependencies.
-FlagEmbedding==1.2.11
--e ./vendor/llama-index-indices-managed-bge-m3

```


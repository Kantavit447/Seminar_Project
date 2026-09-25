# NitiBench / Thai Legal QA - clean Direct project

> อัปเดต 18 กันยายน 2026: แก้ startup เป็น lazy import แล้ว และนำ dependencies ของ Live Retrieval ออกจาก requirements สำหรับ generation-only ตรวจ imports กับ Saved/Golden แบบ offline ผ่านแล้ว รายละเอียดอยู่ใน [รายงานการแก้ไข](docs/LAZY_IMPORT_FIX_REPORT.md) ข้อความเรื่อง eager imports และข้อจำกัดการตรวจ imports ด้านล่างเป็นสถานะก่อนแก้ ไม่ใช่สถานะล่าสุด


Minimal source-preserving extraction for Thai legal QA generation. Planned design: Qwen2.5:7b x
Retrieved/Golden contexts x Direct/Zero-shot CoT/IRAC/Proposed (8 conditions).
Currently supported: Direct Retrieved and Direct Golden only, with citation-ID enum interface.

## Structure
- config/local/response/: two engineering configs and two existing one-item diagnostic configs
- lrg/, script/response_e2e.py: unchanged generation implementation
- chunking/golden/, test_data/laws/, dump/: constructor-required legal corpus/catalog
- data_splits/: engineering 10 and reserved held-out 40; test_data/hf_tax.csv: raw provenance
- results/current/retrieval_evaluation/section_based_no_ref/retrieval_results.json: saved INPUT
- reference_results/: two engineering results plus interface audits, never resume targets
- tools/evaluation/: current interface audit; tools/apply_core_overrides.py: new-env setup only
- vendor/: minimal local BGE integration and three known source core overrides
- docs/: project map, dependency manifest, pipeline, validation and deferred cleanup

Original relative paths are retained deliberately, including the saved retrieval input under results/.
No source git history, venv, caches, old experiment trees or evaluator runner are copied.

## Environment (run later; not installed or validated as a complete environment yet)
Use Python 3.11 and run PowerShell from this clean project's root:
```powershell
py -3.11 -m venv .venv
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/apply_core_overrides.py
.\.venv\Scripts\python.exe -B -c "from script.response_e2e import main; from lrg.data import EvalDataset; print('imports OK')"
```
Requirements preserve declared source application pins; additional import dependencies use source metadata.
This is not a resolved lock or a claim of historical environment equivalence. See docs/CLEANUP_TODO.md.
Do not copy the source venv. Apply overlays only inside this project's new venv.

## Ollama/Qwen (later, explicitly authorized)
Make qwen2.5:7b available to local Ollama. YAML points to http://localhost:11434/v1 and
uses the non-secret placeholder api_key: ollama. Model= qwen2.5:7b, temperature=0,
seed=42, max_tokens=4096, batch_size=1 are unchanged. .env.example contains no secrets;
current wrapper does not auto-load it. The server/model was not contacted during migration.

## Offline inspect (after dependency installation)
```powershell
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/section_based_rag_qwen_direct_v3_citation_id_enum_diagnostic_source_0023.yaml --dump-final-prompt
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/golden_qwen_direct_v3_citation_id_enum_diagnostic_source_0008.yaml --dump-final-prompt
```
These write prompt dumps but do not create an LLM client or run retrieval. Full imports still must resolve.

## One-item smoke reproduction (MANUAL ONLY; these commands call Qwen)
Use empty diagnostic output folders for first run; do not repeat against existing diagnostic results.
Retrieved uses existing source 0023 diagnostic (runtime 0005); Golden uses source 0008 (runtime 0004).
```powershell
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/section_based_rag_qwen_direct_v3_citation_id_enum_diagnostic_source_0023.yaml
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/golden_qwen_direct_v3_citation_id_enum_diagnostic_source_0008.yaml
```
Compare source_idx, context IDs/order, provision map, schema and selected-to-final mapping with reference_results/.
Exact output equality is not established by this migration (server/model/environment provenance is not locked).

## Engineering 10 (MANUAL ONLY; not run during cleanup)
```powershell
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/section_based_rag_qwen_direct_v3_citation_id_enum_engineering_10.yaml
.\.venv\Scripts\python.exe -B -m script.response_e2e --config_path config/local/response/golden_qwen_direct_v3_citation_id_enum_engineering_10.yaml
```
Audit later with tools/evaluation/audit_common_interface_v3_citation_id.py --responses <generated JSON>
--engineering-data data_splits/tax_engineering_10.csv --saved-retrieval
results/current/retrieval_evaluation/section_based_no_ref/retrieval_results.json --output-dir <new audit folder>.
The audit is an interface check, not answer-quality evaluation.

Engineering sources: 0000,0001,0002,0003,0008,0023,0026,0036,0041,0046.
Held-out 40 is reserved for final evaluation AFTER all prompts/methods freeze. Never use it for tuning.
Roadmap after Direct reproduction: CoT -> IRAC -> Proposed. No later methods or evaluator redesign today.

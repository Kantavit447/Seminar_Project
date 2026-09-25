# Project file map — NitiBench / Project_meandyou

> Scope: inventory only, prepared 2026-07-28. No source, configuration, prompt,
> data, or result file was changed. No model, API, or metric command was run.

## 1. Project overview

This is a working copy of the NitiBench Thai legal-QA benchmark.  Its normal
pipeline is:

`config/*.yaml` → `script/response_e2e.py` → `lrg/` → `test_data/`,
`chunking/`, `dump/` → `results/`; evaluation uses
`script/metric_e2e.py` and its metric configuration.

The working tree has 12 tracked files modified and 10 untracked paths reported
by Git. `results/` is ignored by `.gitignore`, so result artifacts do not appear
in `git status --short` or `git ls-files`; they were classified by location and
producer instead. The classifications below use:

- `git ls-files` for original tracked content;
- `git diff --name-only` / `git status --short` for altered tracked content;
- `git ls-files --others --exclude-standard` for custom untracked content;
- path and direct source/configuration references for movement safety.

## 2. Original NitiBench files

These paths are tracked by Git and are not listed by `git diff --name-only`.
They are repository content, not generated working artifacts.

| Path / glob | Purpose | Category | Referenced by | Safe to move |
|---|---|---|---|---|
| `README.md`, `CHANGELOG.md`, `Dockerfile`, `.gitignore`, `setting.env.example` | Repository documentation, container, and environment definition | ORIGINAL | User/documentation and Docker workflow | No — repository root conventions |
| `setup_data.py`, `test.py` | Dataset setup and repository test entry points | ORIGINAL | Manual/Docker workflow | No — root entry-point convention |
| `config/all_e2e_config/{README.md,*.yaml}` except Qwen Windows YAMLs | Original response-run configurations | ORIGINAL | Passed to `script/response_e2e.py` | No — configs contain input/output paths |
| `config/all_e2e_metric_config/**` except `main_table/parametric_qwen_windows.yaml` | Original E2E metric configurations | ORIGINAL | Passed to `script/metric_e2e.py` | No — configs contain node/result paths |
| `config/retriever_config/**` | Retriever configurations | ORIGINAL | Retrieval workflow | No — configuration convention |
| `lrg/**` except entries in section 3 and section 4 | Benchmark implementation: data, augmentation, retrieval, LLM adapters, prompting templates | ORIGINAL | Imported by `script/*.py` and package imports | No — Python package/import paths |
| `script/eval_retrieval.py` | Retrieval evaluation entry point | ORIGINAL | Manual invocation; imports `lrg` | No — script entry point |
| `test_data/hf_tax.csv`, `test_data/hf_wcx.csv`, `test_data/laws/*.json` | Tax/WCX test sets and source laws | ORIGINAL | Dataset configuration → `lrg.data.EvalDataset` | No — configs reference `test_data/...` |
| `chunking/553_50_line/{nodes.json,chunk_to_gold_mapping.json,gold_to_chunk_mapping.json}` | Standard chunk nodes and mappings | ORIGINAL | Response/metric configs and `EvalDataset` | No — direct config/path dependency |
| `chunking/golden/nodes.json`, `chunking/reduced_golden/nodes.json` | Golden/reduced-golden node sets | ORIGINAL | Response/metric configs | No — direct config/path dependency |
| `chunking/{553_50_line,golden}/jinnav2_colbert_index/**` | Prebuilt ColBERT retrieval indexes | ORIGINAL | `lrg.retrieval.retrieval_init.init_colbert` when selected | No — index directory is constructed from `chunking/<strategy>` |
| `dump/docs.json`, `dump/lc_law.txt`, `dump/section_idx.json` | Preprocessed legal documents and section index | ORIGINAL | Data/configuration paths | No — `section_idx_path` is configured |
| `llama_index_extra/**` | Tracked supplemental LlamaIndex implementation files | ORIGINAL | Repository support/vendor content | Do not move without dependency review |

## 3. Original files modified by us

All entries below are tracked by Git and appear in both `git status --short` as
`M` and `git diff --name-only`.

| Path | Purpose of current file | Category | Referenced by | Safe to move |
|---|---|---|---|---|
| `baseline_runner.py` | Baseline runner; current diff removes commented manual test block | MODIFIED_ORIGINAL | Manual entry point | No — root entry point |
| `lrg/data/data_init.py` | Loads datasets, law nodes, mappings, and section index | MODIFIED_ORIGINAL | Imported by `lrg`; response/evaluation scripts | No |
| `lrg/e2e/ragger.py` | Response generation orchestration | MODIFIED_ORIGINAL | `script/response_e2e.py` | No |
| `lrg/llm/__init__.py` | Selects and initializes model adapter | MODIFIED_ORIGINAL | `script/response_e2e.py` through `lrg` | No |
| `lrg/prompting/prompt_manager.py` | Locates templates/structured-output schemas and formats prompts | MODIFIED_ORIGINAL | `Ragger` and judge/test code | No — derives paths from its package directory |
| `lrg/prompting/structured_outputs/system_response.json` | Response JSON schema | MODIFIED_ORIGINAL | `PromptManager.TASK_NAMES` | No — direct constructed path |
| `lrg/prompting/templates/response-tax/turn0.md` | First Tax response prompt template | MODIFIED_ORIGINAL | `PromptManager` loads `response-tax/*.md` | No |
| `lrg/retrieval/__init__.py` | Retrieval package exports | MODIFIED_ORIGINAL | `lrg` imports | No |
| `lrg/retrieval/retrieval_init.py` | Retriever initialization | MODIFIED_ORIGINAL | `script/response_e2e.py` / retrieval workflow | No |
| `requirements.txt` | Python dependencies | MODIFIED_ORIGINAL | Environment setup | No — root dependency manifest |
| `script/metric_e2e.py` | E2E metric entry point | MODIFIED_ORIGINAL | Manual invocation / metric configs | No |
| `script/response_e2e.py` | E2E response entry point | MODIFIED_ORIGINAL | Manual invocation / response configs | No |

## 4. Custom files created by us

These paths are untracked in `git status --short`; they are not present in
`git ls-files`.

| Path | Purpose | Category | Referenced by | Safe to move |
|---|---|---|---|---|
| `config/local/response/parametric_qwen_windows.yaml` | Local Windows/Ollama Qwen parametric run configuration | CUSTOM | Manual argument to `script/response_e2e.py`; names its controlled output path | No — path-bearing config |
| `config/local/response/vanilla_rag_qwen_windows.yaml` | Local Windows/Ollama Qwen RAG run configuration | CUSTOM | Manual argument to `script/response_e2e.py`; references `test_data/`, `chunking/`, `dump/` | No — path-bearing config |
| `config/local/metric/parametric_qwen_windows.yaml` | Qwen parametric metric configuration | CUSTOM | Manual argument to `script/metric_e2e.py`; references nodes and a result directory | No — path-bearing config |
| `tools/evaluation/citation_metric_tax.py` | Custom Tax citation scorer and JSON artifact writer | CUSTOM | Manual invocation; all paths are CLI arguments with project-relative defaults | Yes |
| `tools/evaluation/audit_citation_formats.py` | Custom citation-format audit script | CUSTOM | Manual invocation; all paths are CLI arguments with project-relative defaults | Yes |
| `docs/PROJECT_FILE_MAP.md` | This inventory and proposed reorganization map | CUSTOM | Human reference only | Yes |

## 5. Current controlled results

`results/` is Git-ignored (`.gitignore` rule `results/`). These are generated
artifacts, not source/configuration. “Current controlled” is inferred solely
from the `_controlled` directory names and matching custom Qwen Windows configs;
this is a location classification, not an experiment assessment.

| Path / glob | Purpose | Category | Referenced by | Safe to move |
|---|---|---|---|---|
| `results/current/parametric_qwen_controlled/parametric-qwen/tax_response.json` | Controlled parametric response output | GENERATED_RESULT | `parametric_qwen_windows.yaml` sets parent output path; custom scorer may be retargeted | No until run/config provenance is relocated together |
| `results/current/parametric_qwen_controlled/parametric-qwen/tax_response_readable.json` | Readable derivative of controlled response output | GENERATED_RESULT | No repository reference found | Yes, as an artifact with its response JSON |
| `results/current/parametric_qwen_controlled/parametric-qwen/tax_citation_metrics*.json` | Generated citation artifacts | GENERATED_RESULT | No active config reference; custom scorer output convention when retargeted | Yes, with its source response output |
| `results/current/vanilla_rag_qwen_controlled/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response.json` | Controlled RAG response output | GENERATED_RESULT | `vanilla_rag_qwen_windows.yaml` sets parent output path | No until run/config provenance is relocated together |
| `results/current/vanilla_rag_qwen_controlled/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response_readable.json` | Readable derivative of controlled RAG output | GENERATED_RESULT | No repository reference found | Yes, with its response JSON |
| `results/current/vanilla_rag_qwen_controlled/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_citation_metrics*.json` | Generated citation artifacts | GENERATED_RESULT | No active config reference | Yes, with its source response output |

## 6. Old / legacy results

| Path / glob | Purpose / evidence | Category | Referenced by | Safe to move |
|---|---|---|---|---|
| `results/legacy/parametric_qwen/**` | Earlier Qwen parametric run; lacks `_controlled` name | TEMP_OR_LEGACY | May be supplied explicitly to `tests/manual/test_nitibench_judge_0000.py` | Yes, after archiving with its provenance |
| `results/legacy/vanilla_rag_qwen/**` | Earlier Qwen RAG run; includes citation audit/derivatives | TEMP_OR_LEGACY | May be supplied explicitly to `tools/evaluation/*` and `tests/manual/test_nitibench_judge_0000.py` | Yes, after archiving with its provenance |
| `results/legacy/baseline/baseline_qwen_tax_json.csv` | Standalone baseline output | TEMP_OR_LEGACY | `baseline_runner.py` | No — active script reference |

## 7. Temporary / test files

| Path / glob | Purpose / evidence | Category | Referenced by | Safe to move |
|---|---|---|---|---|
| `backups/prompting/system_response_original.json` | Untracked backup of original schema | TEMP_OR_LEGACY | No repository reference found; `PromptManager` selects `system_response.json` | Yes |
| `backups/prompting/turn0_original.md` | Untracked backup of original prompt | TEMP_OR_LEGACY | No repository reference found; template loader uses `turn0.md` | Yes |
| `tests/manual/test_kku_judge.py` | One-off KKU judge connectivity/JSON test | TEMP_OR_LEGACY | Manual invocation only | Yes |
| `tests/manual/test_nitibench_judge_0000.py` | One-index (`0000`) judge test; accepts response paths as CLI arguments | TEMP_OR_LEGACY | Manual invocation only | Yes |
| `results/tests/judge/judge_test_0000.json` | Output from one-index judge test | TEMP_OR_LEGACY | Produced by `test_nitibench_judge_0000.py` | No — manual-test default |
| `llama_index/**` | Untracked nested LlamaIndex source checkout (contains its own `.git`) | TEMP_OR_LEGACY | No direct project source/config path reference found | Conditional: first verify Python environment has no editable install pointing here |
| `**/__pycache__/**`, `.venv/**` | Python bytecode and local virtual environment | TEMP_OR_LEGACY | Python runtime only | Do not move manually; recreate/clean through environment workflow if approved |

## 8. Cross-cutting path reference table

| Path | Purpose | Category | Referenced by | Safe to move |
|---|---|---|---|---|
| `test_data/` | Raw benchmark CSVs and laws | ORIGINAL | Response YAMLs → `EvalDataset` | No |
| `chunking/` | Node stores, mappings, and retrieval indexes | ORIGINAL | Response/metric YAMLs; `EvalDataset`; `init_colbert` | No |
| `dump/section_idx.json` | Legal section index | ORIGINAL | Response YAMLs → `EvalDataset` | No |
| `lrg/prompting/templates/` | Prompt assets | ORIGINAL / MODIFIED_ORIGINAL | `PromptManager` scans template subdirectories | No |
| `lrg/prompting/structured_outputs/` | Output schemas | ORIGINAL / MODIFIED_ORIGINAL | `PromptManager` constructs paths from package directory | No |
| `results/e2e/*_controlled/` | Current generated artifacts | GENERATED_RESULT | Custom Qwen YAML `output_path` values | No until configs and artifacts are migrated as a set |
| `results/e2e/{parametric_qwen,vanilla_rag_qwen}/` | Legacy artifacts | TEMP_OR_LEGACY | Optional CLI inputs to evaluation/manual-test scripts | Yes, after archiving with provenance |

## 9. Proposed folder structure for the next step (not applied)

The following is a proposal only; it intentionally does **not** imply that any
file is approved to move.

```text
Project_meandyou/
├── config/
│   ├── all_e2e_config/                 # original configs
│   └── local/                          # local/Qwen configs
├── docs/
│   └── PROJECT_FILE_MAP.md
├── lrg/                                # pipeline package and active prompt assets
├── script/                             # active pipeline entry points
├── tools/                              # approved reusable custom utilities
├── tests/manual/                       # approved retained one-off tests
├── artifacts/
│   ├── current/<run-id>/               # generated controlled artifacts
│   └── archive/<run-id>/               # legacy artifacts and their metadata
├── test_data/                          # fixed benchmark input
├── chunking/                           # fixed node/index input
└── dump/                               # fixed preprocessing input
```

Before any relocation, configs and scripts must be made path-independent (for
example via CLI arguments or a run manifest), then results should move with the
exact config and input-version metadata that produced them.

## 10. Files/directories that must not move now

The following have active pipeline references or are package/entry-point
locations. Do not move them without a coordinated code/configuration change:

- `test_data/`, especially `hf_tax.csv`, `hf_wcx.csv`, and `laws/`;
- `chunking/553_50_line/`, `chunking/golden/`, and `chunking/reduced_golden/`;
- `dump/section_idx.json` (and retain the `dump/` directory layout);
- `lrg/`, including `prompting/templates/` and `prompting/structured_outputs/`;
- all original `config/all_e2e_config/` and `config/all_e2e_metric_config/`
  files, plus the three custom Qwen YAMLs while they remain usable;
- `script/response_e2e.py`, `script/metric_e2e.py`, and `script/eval_retrieval.py`;
- `results/current/parametric_qwen_controlled/` and
  `results/current/vanilla_rag_qwen_controlled/` until their custom configs are
  migrated in the same approved change;
- no legacy result directory is path-locked by the custom scripts; preserve its
  provenance before any later approved archive/move.

## Classification caveats

- “Original” means tracked and clean in this checkout; it does not claim every
  tracked file was authored upstream at the same time.
- “Custom” means untracked in the current parent repository. It does not infer
  authorship beyond that Git evidence.
- `results/` is classified from its ignored path and producer naming, not Git
  ownership. No quality, correctness, or metric interpretation is included.
- `llama_index/` is a nested, untracked repository. It is not referenced by the
  parent project source/configuration search, but a local editable Python install
  is outside that search and must be checked before any later move.

## Configuration relocation record

Before moving the three custom Qwen YAML files, the only old-path references
were the three entries in this document itself. No source code, script, or
other configuration referenced the old locations. The references were updated
to the current locations below; YAML content was not changed.

| Old directory | File name | Current path |
|---|---|---|
| `config/all_e2e_config/` | `parametric_qwen_windows.yaml` | `config/local/response/parametric_qwen_windows.yaml` |
| `config/all_e2e_config/` | `vanilla_rag_qwen_windows.yaml` | `config/local/response/vanilla_rag_qwen_windows.yaml` |
| `config/all_e2e_metric_config/main_table/` | `parametric_qwen_windows.yaml` | `config/local/metric/parametric_qwen_windows.yaml` |

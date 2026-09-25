# Results file map

> Scope: read-only inventory, prepared 2026-07-28. No result, config, source,
> dataset, model, API, or metric computation was changed or run.

## Classification rule

- **CURRENT_CONTROLLED**: directories named `_controlled`, matching the current
  local response configurations.
- **LEGACY**: earlier `parametric_qwen` and `vanilla_rag_qwen` run directories,
  plus the standalone baseline CSV.
- **TEST_OR_TEMP**: one-item judge output.

`tax_response.json` is the raw structured E2E response output (its entries
contain `content`, `usage`, timing, retrieval IDs, index, and retry fields).
`*_readable.json` and `*_readable.html` are readable copies. Citation metric
files are generated metric outputs; `citation_format_audit.json` is a generated
audit output; `judge_test_0000.json` is a judge-test output.

## 1. Current controlled results

### Parametric / No-RAG

Directory: `results/current/parametric_qwen_controlled/parametric-qwen/`

| Path | Type / purpose | Size (bytes) | Modified | Referenced by | Safe to move |
|---|---|---:|---|---|---|
| `tax_response.json` | Raw output | 139,339 | 2026-07-25 00:29:36 | `config/local/response/parametric_qwen_windows.yaml` output path; default input in `tests/manual/test_nitibench_judge_0000.py`; documentation examples | No — active config/script references |
| `tax_response_readable.json` | Readable copy | 101,333 | 2026-07-25 10:38:24 | No direct runtime reference found | Conditional — retain with raw output |
| `tax_citation_metrics.json` | Metric output (global) | 999 | 2026-07-25 10:58:37 | No direct runtime reference found | Conditional — retain with raw output |
| `tax_citation_metrics_per_question.json` | Metric output (per question) | 76,149 | 2026-07-25 10:58:37 | No direct runtime reference found | Conditional — retain with raw output |

### Vanilla RAG

Directory: `results/current/vanilla_rag_qwen_controlled/chunk-human-finetuned-bge-m3-no-ref-qwen/`

| Path | Type / purpose | Size (bytes) | Modified | Referenced by | Safe to move |
|---|---|---:|---|---|---|
| `tax_response.json` | Raw output | 373,195 | 2026-07-25 03:18:31 | `config/local/response/vanilla_rag_qwen_windows.yaml` output path; defaults in both `tools/evaluation/` scripts and manual judge; documentation examples | No — active config/script references |
| `tax_response_readable.json` | Readable copy | 215,688 | 2026-07-25 10:38:30 | No direct runtime reference found | Conditional — retain with raw output |
| `tax_citation_metrics.json` | Metric output (global) | 972 | 2026-07-25 11:00:13 | No direct runtime reference found | Conditional — retain with raw output |
| `tax_citation_metrics_per_question.json` | Metric output (per question) | 107,752 | 2026-07-25 11:00:13 | No direct runtime reference found | Conditional — retain with raw output |

## 2. Legacy results

### Parametric / No-RAG

Directory: `results/legacy/parametric_qwen/parametric-qwen/`

| Path | Type / purpose | Size (bytes) | Modified | Referenced by | Safe to move |
|---|---|---:|---|---|---|
| `tax_response.json` | Raw output | 139,342 | 2026-07-23 22:27:12 | `config/local/metric/parametric_qwen_windows.yaml` points to this run directory; documentation examples | No — active metric config reference |
| `wangchan_response.json` | Raw output (Wangchan) | 8,161 | 2026-07-23 22:29:56 | Same legacy run directory is referenced by local metric config | No — preserve with referenced run directory |
| `tax_response_readable.json` | Readable copy | 101,336 | 2026-07-24 21:34:05 | No direct runtime reference found | Conditional — retain with raw output |
| `tax_response_readable.html` | Readable HTML copy | 113,580 | 2026-07-24 21:35:57 | No direct runtime reference found | Conditional — retain with raw output |
| `tax_citation_metrics.json` | Metric output (global) | 988 | 2026-07-25 10:53:57 | No direct runtime reference found | Conditional — retain with raw output |
| `tax_citation_metrics_per_question.json` | Metric output (per question) | 76,149 | 2026-07-25 10:53:57 | No direct runtime reference found | Conditional — retain with raw output |

### Vanilla RAG

Directory: `results/legacy/vanilla_rag_qwen/chunk-human-finetuned-bge-m3-no-ref-qwen/`

| Path | Type / purpose | Size (bytes) | Modified | Referenced by | Safe to move |
|---|---|---:|---|---|---|
| `tax_response.json` | Raw output | 373,211 | 2026-07-24 15:14:39 | Documentation examples only; can be supplied by CLI to evaluation/judge tools | Conditional — no hard-coded code/config reference |
| `tax_response_readable.json` | Readable copy | 215,704 | 2026-07-24 21:34:09 | No direct runtime reference found | Conditional — retain with raw output |
| `tax_response_readable.html` | Readable HTML copy | 234,196 | 2026-07-24 21:40:17 | No direct runtime reference found | Conditional — retain with raw output |
| `tax_citation_metrics.json` | Metric output (global) | 961 | 2026-07-24 21:24:45 | No direct runtime reference found | Conditional — retain with raw output |
| `tax_citation_metrics_per_question.json` | Metric output (per question) | 107,752 | 2026-07-24 21:24:45 | No direct runtime reference found | Conditional — retain with raw output |
| `citation_format_audit.json` | Audit output | 16,288 | 2026-07-24 15:36:41 | No direct runtime reference found | Conditional — retain with raw output |

### Standalone baseline

| Path | Type / purpose | Size (bytes) | Modified | Referenced by | Safe to move |
|---|---|---:|---|---|---|
| `results/legacy/baseline/baseline_qwen_tax_json.csv` | Raw baseline CSV output | 315,813 | 2026-07-23 17:07:54 | `baseline_runner.py` (`OUTPUT_PATH`) | No — active script reference |

## 3. Test / temporary results

| Path | Type / purpose | Size (bytes) | Modified | Referenced by | Safe to move |
|---|---|---:|---|---|---|
| `results/tests/judge/judge_test_0000.json` | Judge test output for one item | 20,732 | 2026-07-24 23:04:48 | Default output in `tests/manual/test_nitibench_judge_0000.py` | No — active manual-test default |

## 4. Reference inventory

The project was searched for both the full result paths and their directory/file
names. The following are the active references that affect relocation safety:

| Result location | Active reference | Effect |
|---|---|---|
| `parametric_qwen_controlled/` | `config/local/response/parametric_qwen_windows.yaml`; `tests/manual/test_nitibench_judge_0000.py` defaults | Do not move without updating config and manual-test defaults |
| `vanilla_rag_qwen_controlled/` | `config/local/response/vanilla_rag_qwen_windows.yaml`; defaults in `tools/evaluation/citation_metric_tax.py`, `tools/evaluation/audit_citation_formats.py`, and manual judge | Do not move without updating config and tool defaults |
| `parametric_qwen/` | `config/local/metric/parametric_qwen_windows.yaml` | Do not move without updating the metric configuration |
| `vanilla_rag_qwen/` | No hard-coded source/config reference; listed in `docs/CUSTOM_SCRIPT_PATH_USAGE.md` as an optional CLI example | Documentation-only reference; archive only with updated docs/provenance |
| `judge_test_0000.json` | Default output in `tests/manual/test_nitibench_judge_0000.py` | Do not move without updating the manual-test default |
| `baseline_qwen_tax_json.csv` | `baseline_runner.py` | Do not move without updating that script |

`docs/PROJECT_FILE_MAP.md` and `docs/CUSTOM_SCRIPT_PATH_USAGE.md` also mention
some of these result locations. Those are documentation references, not runtime
dependencies, but must be updated when a future approved move occurs.

## 5. Files that must not move now

- The complete `results/current/parametric_qwen_controlled/` directory.
- The complete `results/current/vanilla_rag_qwen_controlled/` directory.
- The complete `results/legacy/parametric_qwen/` directory.
- `results/tests/judge/judge_test_0000.json`.
- `results/legacy/baseline/baseline_qwen_tax_json.csv`.

The remaining legacy Vanilla RAG directory has no runtime path lock, but no
result should move until a future provenance/archive plan is approved.

## 6. Proposed next-step structure (not applied)

```text
results/
├── current/
│   ├── parametric_qwen_controlled/
│   └── vanilla_rag_qwen_controlled/
├── legacy/
│   ├── parametric_qwen/
│   ├── vanilla_rag_qwen/
│   └── baseline/
└── tests/
    └── judge/
```

Any future move must preserve each raw response with its readable copies,
metric/audit derivatives, producing configuration, and a run manifest. The
path-bearing config/script references in section 4 must be changed together in
that approved step.

## Post-move metadata note

The four `tax_citation_metrics.json` files retain their original absolute
`result_file` string from the pre-move layout. This is historical metadata
inside generated JSON, not an active runtime reference. It was intentionally
not rewritten because this move must not change result content.

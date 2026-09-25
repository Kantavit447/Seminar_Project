# Custom script path usage

The custom scripts now accept input and output paths at the command line. Their
defaults use `PROJECT_DIR` (the repository root), but every path below can be
overridden. Each script prints the resolved input/output path before it reads or
writes a file, and stops with a clear `FileNotFoundError` if an input file is
missing.

Run the commands from the repository root (`Project_meandyou`). The examples
write derived artifacts beside each selected response file unless `--output` is
provided. They do not move or delete any files.

## Arguments

| Script | Required/primary arguments |
|---|---|
| `tools/evaluation/citation_metric_tax.py` | `--input RESPONSE.json`, optional `--dataset TAX.csv`, `--output GLOBAL.json`, and `--per-question-output LOCAL.json` |
| `tools/evaluation/audit_citation_formats.py` | `--input RESPONSE.json`, optional `--output AUDIT.json` |
| `tests/manual/test_nitibench_judge_0000.py` | `--dataset TAX.csv`, `--no-rag-input RESPONSE.json`, `--rag-input RESPONSE.json`, `--output JUDGE.json`, and optional `--idx 0000` |

The judge script calls the configured KKU service only after all input files
have been printed and validated, and only when `KKU_API_KEY` is set. The
citation and audit scripts do not call a model or external API.

## No-RAG controlled

```powershell
python tools/evaluation/citation_metric_tax.py `
  --input results/current/parametric_qwen_controlled/parametric-qwen/tax_response.json

python tools/evaluation/audit_citation_formats.py `
  --input results/current/parametric_qwen_controlled/parametric-qwen/tax_response.json
```

## Vanilla RAG controlled

```powershell
python tools/evaluation/citation_metric_tax.py `
  --input results/current/vanilla_rag_qwen_controlled/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response.json

python tools/evaluation/audit_citation_formats.py `
  --input results/current/vanilla_rag_qwen_controlled/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response.json
```

## Legacy No-RAG

```powershell
python tools/evaluation/citation_metric_tax.py `
  --input results/legacy/parametric_qwen/parametric-qwen/tax_response.json

python tools/evaluation/audit_citation_formats.py `
  --input results/legacy/parametric_qwen/parametric-qwen/tax_response.json
```

## Legacy Vanilla RAG

```powershell
python tools/evaluation/citation_metric_tax.py `
  --input results/legacy/vanilla_rag_qwen/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response.json

python tools/evaluation/audit_citation_formats.py `
  --input results/legacy/vanilla_rag_qwen/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response.json
```

## Compare No-RAG with Vanilla RAG using the judge

Choose one matched pair of result paths. The following two commands show the
controlled and legacy pairs; they require `KKU_API_KEY` and make an external
judge API call when executed.

```powershell
# Controlled pair
python tests/manual/test_nitibench_judge_0000.py `
  --no-rag-input results/current/parametric_qwen_controlled/parametric-qwen/tax_response.json `
  --rag-input results/current/vanilla_rag_qwen_controlled/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response.json `
  --output results/tests/judge/judge_controlled_0000.json `
  --idx 0000

# Legacy pair
python tests/manual/test_nitibench_judge_0000.py `
  --no-rag-input results/legacy/parametric_qwen/parametric-qwen/tax_response.json `
  --rag-input results/legacy/vanilla_rag_qwen/chunk-human-finetuned-bge-m3-no-ref-qwen/tax_response.json `
  --output results/tests/judge/judge_legacy_0000.json `
  --idx 0000
```

## Explicit output locations

Use the output arguments when artifacts should be written outside the response
directory:

```powershell
python tools/evaluation/citation_metric_tax.py `
  --input results/current/parametric_qwen_controlled/parametric-qwen/tax_response.json `
  --output artifacts/current/parametric_qwen/tax_citation_metrics.json `
  --per-question-output artifacts/current/parametric_qwen/tax_citation_metrics_per_question.json

python tools/evaluation/audit_citation_formats.py `
  --input results/current/parametric_qwen_controlled/parametric-qwen/tax_response.json `
  --output artifacts/current/parametric_qwen/citation_format_audit.json
```

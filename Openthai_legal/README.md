# OpenThai 2.0 Legal — NitiBench-Tax

Project scaffold for running selected NitiBench-Tax questions with OpenThai 2.0 Legal. The inference dataset contains only `source_index` and `question`; it intentionally excludes answers, laws, and gold context.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Then edit `.env` and set `IAPP_API_KEY` yourself. Do not commit that file.

Create the inference dataset:

```powershell
python scripts/import_tax.py
```

Later, run a deliberately selected subset:

```powershell
python run_benchmark.py --run-name smoke_test --limit 1
python run_benchmark.py --run-name engineering_10 --indices 0000,0001,0002,0003,0008,0023,0026,0036,0041,0046
```

Full-dataset execution is opt-in only:

```powershell
python run_benchmark.py --run-name full_run --all
```

Each run writes UTF-8 JSON/JSONL files to `results/<run_name>/`: `responses.jsonl`, `errors.jsonl`, `run_config.json`, and `summary.json`.

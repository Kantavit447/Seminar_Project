"""Install source core overlays into the CURRENT NEW venv only; never run inference."""
from pathlib import Path
import sys, shutil, importlib.metadata, importlib.util
ROOT = Path(__file__).resolve().parents[1]
if sys.prefix == sys.base_prefix:
    raise SystemExit("Activate the new clean-project venv first.")
venv = (ROOT / ".venv").resolve()
if Path(sys.prefix).resolve() != venv:
    raise SystemExit("Only this clean project's .venv may be modified.")
if importlib.metadata.version("llama-index-core") != "0.12.19":
    raise SystemExit("Expected llama-index-core 0.12.19.")
spec = importlib.util.find_spec("llama_index.core")
core = Path(spec.origin).resolve().parent
if not core.is_relative_to(venv):
    raise SystemExit("Core package is outside this clean project's venv.")
for source in (ROOT / "vendor/core_overrides/llama_index/core").rglob("*.py"):
    target = core / source.relative_to(ROOT / "vendor/core_overrides/llama_index/core")
    if not target.is_file():
        raise SystemExit(f"Expected installed file missing: {target}")
    shutil.copyfile(source, target)
    print(target)

"""Offline integration tests for Proposed; no LLM or network."""

import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "config/local/response"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("proposed_candidate", ROOT / "script/response_proposed.py")
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def forbidden(*args, **kwargs):
    raise AssertionError("Network call during offline runner validation")

socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden
socket.create_connection = forbidden

import lrg.llm
calls = []
mode = "pass"

class FakeLLM:
    def __init__(self, config):
        self.config = config

    async def complete(self, *, messages, structure, diagnostic):
        assert "reference_answer" not in str(messages) and "relevant_laws" not in str(messages)
        calls.append(structure.__name__)
        if structure.__name__ == "IRACVerification":
            if mode == "invalid":
                return {"content": {"checks": []}, "usage": {"total_tokens": 1}, "llm_time": 0.01}
            checks = [dict(axis=axis, verdict="PASS", reason="Offline fixture.", issues=[])
                      for axis in "IRAC"]
            if mode in ("fail", "correction_error"):
                checks[2]["verdict"] = "FAIL"
                checks[2]["issues"] = [dict(draft_field="analysis", draft_quote=None,
                    problem="A material point in the question was omitted.",
                    evidence=[dict(source="QUESTION", quote=messages[1]["content"].split("[QUESTION]\n", 1)[1][:10])],
                    revision="Address the omitted point.")]
            if mode == "uncertain":
                checks[2]["verdict"] = "UNCERTAIN"
            return {"content": {"checks": checks}, "usage": {"total_tokens": 1}, "llm_time": 0.01}
        if mode == "correction_error":
            raise RuntimeError("Synthetic correction failure")
        raw = messages[1]["content"].split("[DRAFT_JSON]\n", 1)[1].split("\n[/DRAFT_JSON]", 1)[0]
        return {"content": json.loads(raw), "usage": {"total_tokens": 2}, "llm_time": 0.02}

lrg.llm.init_llm = lambda config: FakeLLM(config)

async def run():
    global mode
    with tempfile.TemporaryDirectory(prefix="proposed_offline_") as temp:
        for context, fixture in (("golden", "proposed_golden_engineering_10.yaml"),
                                 ("retrieved", "proposed_retrieved_engineering_10.yaml")):
            settings = yaml.safe_load((STAGE / fixture).read_text(encoding="utf-8"))
            for variant, expected, expected_calls in (("pass", "kept_pass", 1),
                                                      ("uncertain", "kept_uncertain", 1),
                                                      ("invalid", "verifier_failed", 1),
                                                      ("fail", "corrected", 2),
                                                      ("correction_error", "correction_failed", 2)):
                mode = variant
                local = deepcopy(settings)
                local["output_path"] = str(Path(temp) / context / variant)
                calls.clear()
                trace = await candidate.execute(local, source_idx="0000")
                item = trace["items"][0]
                assert item["status"] == expected, (context, variant, item)
                assert len(calls) == expected_calls, (context, variant, calls)
                output = Path(local["output_path"]) / "diagnostics/source_0000"
                saved = json.loads((output / "tax_response.json").read_text(encoding="utf-8"))
                assert len(saved) == 1 and saved[0]["source_idx"] == "0000"
                assert (output / "tax_proposed_trace.md").is_file()
                calls.clear()
                await candidate.execute(local, source_idx="0000")
                assert not calls, "A completed stage was called again on resume"
                if variant == "fail":
                    checkpoint = output / "tax_proposed_trace.json"
                    saved_trace = json.loads(checkpoint.read_text(encoding="utf-8"))
                    saved_trace["items"][0]["status"] = "verified_fail_pending_correction"
                    checkpoint.write_text(json.dumps(saved_trace, ensure_ascii=False), encoding="utf-8")
                    calls.clear()
                    resumed = await candidate.execute(local, source_idx="0000")
                    assert len(calls) == 1 and calls[0] != "IRACVerification"
                    assert resumed["items"][0]["status"] == "corrected"
                if variant == "invalid":
                    checkpoint = output / "tax_proposed_trace.json"
                    saved_trace = json.loads(checkpoint.read_text(encoding="utf-8"))
                    saved_trace["items"][0]["status"] = "in_flight"
                    checkpoint.write_text(json.dumps(saved_trace, ensure_ascii=False), encoding="utf-8")
                    calls.clear()
                    try:
                        await candidate.execute(local, source_idx="0000")
                    except ValueError as error:
                        assert "outcome unknown" in str(error)
                    else:
                        raise AssertionError("An unknown in-flight request must not be retried")
                    assert not calls
                if context == "golden":
                    assert next(i for i in trace["items"] if i["source_idx"] == "0001")["status"] == "draft_failed"
            mode = "pass"
            full = deepcopy(settings)
            full["output_path"] = str(Path(temp) / context / "pilot_then_full")
            await candidate.execute(full, source_idx="0000")
            calls.clear()
            complete = await candidate.execute(full)
            assert len(calls) == (9 if context == "golden" else 10)
            assert sum(item["status"] == "draft_failed" for item in complete["items"]) == (1 if context == "golden" else 0)
            assert len(json.loads((Path(full["output_path"]) / "tax_response.json").read_text(encoding="utf-8"))) == len(calls)
            print(f"offline {context}: pass/uncertain/invalid/fail/correction_error/resume OK")
    print("network_calls=0")

try:
    loop.run_until_complete(run())
finally:
    loop.close()

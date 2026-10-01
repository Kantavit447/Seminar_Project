"""ตรวจการไปต่อหลัง length failure ด้วยคำตอบจำลอง ไม่มี LLM/network/retrieval จริง."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path.cwd()))
import pandas as pd
import script.response_e2e as entry
from lrg.e2e.ragger import Ragger
from lrg.llm.collections.openai.model import OpenAIModel, RawCompletionFailure


async def main():
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
         patch.object(socket.socket, "connect_ex", side_effect=AssertionError("Network forbidden")), \
         patch.object(socket, "create_connection", side_effect=AssertionError("Network forbidden")), \
         patch.object(OpenAIModel, "_create_client", side_effect=AssertionError("LLM client forbidden")), \
         patch.object(entry, "init_retriever", side_effect=AssertionError("Live retrieval forbidden")), \
         patch.object(entry.time, "sleep"), tempfile.TemporaryDirectory(prefix="length-continuation-test-") as temporary:
        folder = Path(temporary)
        failures = folder / "failures"
        settings = dict(model="qwen2.5-16k:7b", max_tokens=4096, n=1, temperature=0.0, seed=42)
        diagnostic = dict(continue_on_length_failure=True, max_retries=1,
                          save_raw_on_parse_failure=True, failure_output_dir=str(failures))
        sources = ["0000", "0001", "0008", "0023", "0046"]
        frame = pd.DataFrame([dict(idx=f"{i:04d}", source_idx=source, question=f"คำถาม {i}", relevant_laws=[])
                              for i, source in enumerate(sources)])
        records = [dict(idx=f"{i:04d}", source_idx=source, tries=1,
                        content=dict(analysis="I/R/A/C จำลอง", answer=f"คำตอบ {i}", citations=[]),
                        usage=dict(total_tokens=100), llm_time=1.0, custom_metadata=[None, "ไทย"])
                   for i, source in enumerate(sources)]
        raw = dict(raw_response_content='{"analysis":"จำลอง","answer":"วนซ้ำ',
                   finish_reason="length", exception_type="LengthFinishReasonError",
                   completion_tokens=4096, model_settings=settings)
        length_error = RawCompletionFailure(RuntimeError("length"), raw)
        ragger = SimpleNamespace(dataset=SimpleNamespace(tax_df=frame, wangchan_df=None),
                                 diagnostic=diagnostic, max_retries=1, llm=SimpleNamespace(config=settings))
        output = folder / "tax_response.json"
        # ผลสำเร็จมีช่องว่างของ runtime ID ต้องไม่ resume ด้วยจำนวนรายการ
        initial = [records[0], records[2]]
        output.write_text(json.dumps(initial, ensure_ascii=False, indent=2), encoding="utf-8")
        Ragger.save_diagnostic_failure(ragger, "0001", 1, length_error)
        old_failure_path = failures / "runtime_0001_source_0001_attempt_1.json"
        old_failure = old_failure_path.read_bytes()
        old_raw_path = old_failure_path.with_name(old_failure_path.stem + "_raw.txt")
        old_raw = old_raw_path.read_bytes()

        async def generate(**kwargs):
            idx = kwargs["indices"][0]
            if idx == "0003":
                Ragger.save_diagnostic_failure(ragger, idx, 1, length_error)
                raise length_error
            assert idx == "0004", "A completed question was called again."
            return [deepcopy(records[4])]

        ragger.rag_multi = AsyncMock(side_effect=generate)
        await entry.evaluate_ragger(ragger, setting_name=str(folder), diagnostic=diagnostic)
        assert [call.kwargs["indices"] for call in ragger.rag_multi.await_args_list] == [["0003"], ["0004"]]
        assert json.loads(output.read_text(encoding="utf-8")) == initial + [records[4]]
        assert old_failure_path.read_bytes() == old_failure and old_raw_path.read_bytes() == old_raw
        state = json.loads((folder / "tax_run_status.json").read_text(encoding="utf-8"))
        assert (state["success"], state["generation_failure"], state["pending"]) == (3, 2, 0)
        assert [row["source_idx"] for row in state["items"] if row["status"] == "generation_failure"] == ["0001", "0023"]
        assert "generation failure 2" in (folder / "tax_run_status.md").read_text(encoding="utf-8")
        assert "คำตอบ 4" in (folder / "tax_response_readable.md").read_text(encoding="utf-8")
        ragger.rag_multi.reset_mock()
        await entry.evaluate_ragger(ragger, setting_name=str(folder), diagnostic=diagnostic)
        ragger.rag_multi.assert_not_awaited()
        print("PASS: noncontiguous success + saved/new length failures + remaining success + no-op resume.")

        async def rejects(action, expected):
            try:
                await action()
            except expected:
                return
            raise AssertionError(f"Expected {expected.__name__}.")

        await rejects(lambda: entry.evaluate_ragger(ragger, setting_name=str(folder)), ValueError)
        for overrides in (dict(max_retries=2), dict(runtime_idx="0004"), dict(save_raw_on_parse_failure=False)):
            await rejects(lambda: entry.evaluate_ragger(ragger, setting_name=str(folder), diagnostic=dict(diagnostic, **overrides)), ValueError)
        await rejects(lambda: entry.evaluate_ragger(ragger, batch_size=2, setting_name=str(folder), diagnostic=diagnostic), ValueError)
        for corrupt in (dict(source_idx="9999"), dict(exception_type="APIConnectionError"),
                        dict(model_settings=dict(settings, seed=99))):
            modified = dict(json.loads(old_failure), **corrupt)
            old_failure_path.write_text(json.dumps(modified), encoding="utf-8")
            await rejects(lambda: entry.evaluate_ragger(ragger, setting_name=str(folder), diagnostic=diagnostic), ValueError)
            old_failure_path.write_bytes(old_failure)
        for invalid in (initial + [initial[0]], [dict(initial[0], source_idx="9999")], initial + [records[1]]):
            output.write_text(json.dumps(invalid), encoding="utf-8")
            await rejects(lambda: entry.evaluate_ragger(ragger, setting_name=str(folder), diagnostic=diagnostic), ValueError)
        ragger.rag_multi.assert_not_awaited()
        print("PASS: mismatched/duplicate/ambiguous checkpoints and unsafe options stop before generation.")

        # API/program errors และ length ที่ไม่มีหลักฐานต้องไม่ถูกข้ามเงียบ ๆ
        for name, error, expected in [
            ("connection", RawCompletionFailure(RuntimeError("offline"), dict(finish_reason=None, exception_type="APIConnectionError")), RawCompletionFailure),
            ("program", TypeError("program bug"), TypeError),
            ("missing_evidence", length_error, RuntimeError),
            ("default_stop", length_error, RawCompletionFailure),
        ]:
            destination = folder / name
            diag = dict(diagnostic, failure_output_dir=str(destination / "failures"))
            if name == "default_stop":
                diag.pop("continue_on_length_failure")
            ragger.rag_multi = AsyncMock(side_effect=error)
            await rejects(lambda: entry.evaluate_ragger(ragger, setting_name=str(destination), diagnostic=diag), expected)
            ragger.rag_multi.assert_awaited_once()
            assert not (destination / "tax_response.json").exists()
        print("PASS: unrelated errors propagate; missing length evidence cannot be skipped; default remains stop-on-error.")
        print("PASS: real LLM/API/live retrieval calls = 0")


if __name__ == "__main__":
    asyncio.run(main())

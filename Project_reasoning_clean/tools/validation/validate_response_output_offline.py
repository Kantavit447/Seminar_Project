"""ตรวจการบันทึกภาษาไทย/จีนและ resume หลัง failure โดยใช้ผลจำลอง ไม่เรียกโมเดล."""

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


async def check_output():
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
         patch.object(socket, "create_connection", side_effect=AssertionError("Network forbidden")), \
         patch.object(entry, "init_llm", side_effect=AssertionError("LLM forbidden")), \
         patch.object(entry, "init_retriever", side_effect=AssertionError("Retrieval forbidden")), \
         patch.object(entry.time, "sleep"), tempfile.TemporaryDirectory(prefix="response-output-test-") as temporary:
        folder = Path(temporary)
        path = folder / "tax_response.json"
        questions = ["คำถามเก่า", "คำถามข้อสอง", "คำถามข้อสาม"]
        sources = ["0000", "0008", "0046"]
        frame = pd.DataFrame([{"idx": f"{i:04d}", "source_idx": source,
            "question": questions[i], "relevant_laws": []} for i, source in enumerate(sources)])
        records = [{"idx": f"{i:04d}", "source_idx": source, "tries": 1,
            "content": {"analysis": f"分析 {i}\nบรรทัดถัดไป", "answer": f'คำตอบที่ {i} "ข้อความ"',
                        "citations": [{"law": "กฎหมายทดสอบ", "section": "1"}]},
            "usage": {"total_tokens": 100 + i}, "llm_time": 1.125,
            "metadata_to_preserve": {"nullable": None, "nested": [True, "ไทย", "中文"]}}
            for i, source in enumerate(sources)]
        original = deepcopy(records)
        path.write_text(json.dumps(records[:1]), encoding="utf-8")
        failure = RuntimeError("simulated generation failure")
        ragger = SimpleNamespace(dataset=SimpleNamespace(tax_df=frame, wangchan_df=None),
            rag_multi=AsyncMock(side_effect=[[records[1]], failure]))
        try:
            await entry.evaluate_ragger(ragger, setting_name=str(folder))
        except RuntimeError as error:
            assert error is failure
        else:
            raise AssertionError("Generation failure was unexpectedly swallowed.")
        assert json.loads(path.read_text(encoding="utf-8")) == original[:2]
        text = path.read_text(encoding="utf-8")
        assert "\\u" not in text and "คำตอบที่" in text and "分析" in text and len(text.splitlines()) > 1
        readable = path.with_name("tax_response_readable.md")
        md = readable.read_text(encoding="utf-8")
        assert "จำนวนคำตอบที่บันทึก: 2 รายการ" in md
        assert "คำถามข้อสอง" in md and "คำถามข้อสาม" not in md
        assert "source 0008" in md and "source 0046" not in md
        assert [call.kwargs["indices"] for call in ragger.rag_multi.await_args_list] == [["0001"], ["0002"]]
        print("PASS: legacy checkpoint + partial success + failure preserve readable results.")

        ragger.rag_multi = AsyncMock(return_value=[records[2]])
        await entry.evaluate_ragger(ragger, setting_name=str(folder))
        assert json.loads(path.read_text(encoding="utf-8")) == original
        ragger.rag_multi.assert_awaited_once()
        assert ragger.rag_multi.await_args.kwargs["indices"] == ["0002"]
        md = readable.read_text(encoding="utf-8")
        assert "จำนวนคำตอบที่บันทึก: 3 รายการ" in md and "คำถามข้อสาม" in md
        assert md.count("## รายการ ") == 3
        assert records == original, "Formatting changed the input records."
        print("PASS: UTF-8 resume preserves all fields, avoids duplicate successful rows, and refreshes Markdown.")
        print("PASS: real LLM/API/retrieval calls = 0")


if __name__ == "__main__":
    asyncio.run(check_output())

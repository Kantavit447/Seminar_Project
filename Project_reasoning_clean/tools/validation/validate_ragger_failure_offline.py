"""ตรวจว่า Ragger ส่งต่อ error เมื่อครบ attempts โดยใช้คำตอบจำลองและไม่เรียก API.

รันจากโฟลเดอร์รากของ Clean Project
"""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path.cwd()))

import pandas as pd
from pydantic import ValidationError
from lrg.e2e.ragger import Ragger
from lrg.llm.collections.openai.model import OpenAIModel, RawCompletionFailure
from lrg.prompting import PromptManager


async def check_failure_handling():
    # event loop ถูกสร้างแล้วก่อนปิดกั้น network เพื่อรองรับ socketpair ภายใน Windows
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")), \
         patch.object(socket.socket, "connect_ex", side_effect=AssertionError("Network forbidden")), \
         patch.object(socket, "create_connection", side_effect=AssertionError("Network forbidden")), \
         patch.object(OpenAIModel, "_create_client", side_effect=AssertionError("LLM client forbidden")), \
         tempfile.TemporaryDirectory(prefix="ragger-failure-test-") as temporary:
        node = SimpleNamespace(id_="กฎหมายทดสอบ-1")
        dataset = SimpleNamespace(text_nodes=[node], strat_name="golden",
            tax_df=pd.DataFrame([{"idx": "0009", "source_idx": "0046"}]))
        pm = PromptManager(prompt_version="v3", reasoning_method="zero_shot_cot",
            citation_mode="provision_id", citation_constraint_mode="enum")
        failure = RawCompletionFailure(RuntimeError("output limit reached"), {
            "finish_reason": "length", "raw_response_content": '{"analysis":"unfinished',
            "completion_tokens": 4096})
        valid = {"content": {"analysis": "Offline check.", "answer": "คำตอบจำลอง",
            "citation_ids": ["P1"]}, "usage": {}, "llm_time": 0.0}
        cases = [
            ("failure_one_attempt", 1, [failure], RawCompletionFailure),
            ("failure_two_attempts", 2, [failure, failure], RawCompletionFailure),
            ("success_first_attempt", 2, [deepcopy(valid)], None),
            ("success_after_failure", 2, [failure, deepcopy(valid)], None),
            ("invalid_response_must_not_escape", 1, [{"content": {}}], ValidationError),
        ]
        for name, limit, outcomes, expected_error in cases:
            diagnostic = {"save_raw_on_parse_failure": True,
                "failure_output_dir": str(Path(temporary) / name)}
            llm = SimpleNamespace(model_name="qwen2.5-16k:7b", complete=AsyncMock(side_effect=outcomes))
            ragger = Ragger(dataset=dataset, prompt_manager=pm, llm=llm,
                max_retries=limit, context_source="golden", citation_validation=True,
                diagnostic=diagnostic)
            ragger.get_prompt_structure = Mock(return_value=({"messages": []}, None, [node], 0))
            try:
                results = await ragger.rag_multi(indices=["0009"], queries=["คำถามจำลอง"],
                    dataset_names=["tax"], relevant_laws=[[{"law": "กฎหมายทดสอบ", "sections": "1"}]])
            except Exception as error:
                assert expected_error and isinstance(error, expected_error), (
                    f"{name}: expected {expected_error}, got {type(error).__name__}: {error}")
                if expected_error is RawCompletionFailure:
                    assert error is failure, "Original exception was replaced."
            else:
                assert expected_error is None, "Failed response was returned as success."
                response = results[0]
                assert response["content"] == {"analysis": "Offline check.", "answer": "คำตอบจำลอง",
                    "citations": [{"law": "กฎหมายทดสอบ", "section": "1"}]}
                assert response["tries"] == len(outcomes)
                assert response["idx"] == "0009" and response["source_idx"] == "0046"
                assert response["gold_node_ids"] == [node.id_]
                assert not response["citation_validation_errors"]
            assert llm.complete.await_count == len(outcomes), "Attempt count changed."
            for attempt, outcome in enumerate(outcomes, 1):
                if outcome is failure:
                    path = Path(diagnostic["failure_output_dir"]) / f"runtime_0009_source_0046_attempt_{attempt}.json"
                    saved = json.loads(path.read_text(encoding="utf-8"))
                    assert saved["finish_reason"] == "length" and saved["completion_tokens"] == 4096
                    assert saved["runtime_idx"] == "0009" and saved["source_idx"] == "0046"
                    assert saved["retry_attempt"] == attempt
                    assert path.with_name(path.stem + "_raw.txt").read_text(encoding="utf-8") == failure.diagnostic_record["raw_response_content"]
            print(f"PASS {name}")
        print("PASS: 5 offline scenarios; real LLM/API/retrieval calls = 0")


if __name__ == "__main__":
    asyncio.run(check_failure_handling())

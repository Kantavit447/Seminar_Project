import argparse
import sys
import asyncio
import os
import yaml
import json
import pandas as pd
from pathlib import Path
from llama_index.core.schema import NodeWithScore

if "/app/LRG" not in sys.path:
    sys.path.append("/app/LRG")

from lrg.data import EvalDataset
from lrg.retrieval import init_retriever
from lrg.prompting import PromptManager
from lrg.llm import init_llm
from lrg.llm.collections.openai.model import RawCompletionFailure
from lrg.augmenter import NitiLinkAugmenterConfig, NitiLinkAugmenter
from lrg.e2e import Ragger

from tqdm import tqdm
import torch

import time

import asyncio
import gc

tqdm.pandas()


def canonical_idx(value):
    """Return a dataset/source index in the retrieval-result format (e.g. 0008)."""
    try:
        return f"{int(str(value).strip()):04d}"
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid source_idx: {value!r}") from error


class SavedRetrievalRetriever:
    """Retriever-compatible adapter that returns saved, rank-preserving nodes."""

    def __init__(self, nodes_by_question):
        self.nodes_by_question = nodes_by_question

    def retrieve(self, query):
        try:
            return self.nodes_by_question[query]
        except KeyError as error:
            raise KeyError("No saved retrieval entry for the current query.") from error


class PromptDumpLLM:
    """Minimal Ragger-compatible model metadata; it never creates an LLM client."""

    def __init__(self, model_name):
        self.model_name = model_name


def write_final_prompt_dump(path, messages, response_format=None, provision_map=None):
    """Write the exact OpenAI-compatible message sequence in a readable UTF-8 transcript."""
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for number, message in enumerate(messages, start=1):
            handle.write(f"===== MESSAGE {number}: {message['role']} =====\n")
            handle.write(message["content"])
            handle.write("\n\n")
        if response_format is not None:
            handle.write("===== RESPONSE_FORMAT (not a chat message) =====\n")
            json.dump(response_format, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        if provision_map is not None:
            handle.write("\n===== PROVISION_MAP (runtime deterministic mapping) =====\n")
            json.dump(provision_map, handle, ensure_ascii=False, indent=2)
            handle.write("\n")


def init_saved_retriever(dataset, saved_retrieval_path):
    """Validate saved top-10 retrievals and expose them without building an index."""
    path = Path(saved_retrieval_path)
    if not path.is_file():
        raise FileNotFoundError(f"saved_retrieval_path does not exist: {path}")

    with path.open("r", encoding="utf-8") as handle:
        raw_results = json.load(handle)
    if not isinstance(raw_results, list) or len(raw_results) != 50:
        raise ValueError("saved_retrieval_path must contain exactly 50 retrieval result entries.")

    expected_indices = {f"{number:04d}" for number in range(50)}
    results_by_idx = {}
    for result in raw_results:
        if not isinstance(result, dict):
            raise ValueError("Every saved retrieval result must be an object.")
        idx = canonical_idx(result.get("idx"))
        if idx in results_by_idx:
            raise ValueError(f"Duplicate saved retrieval idx: {idx}")
        retrieved_ids = result.get("retrieved_ids")
        if not isinstance(retrieved_ids, list) or len(retrieved_ids) != 10:
            raise ValueError(f"Saved retrieval {idx} must have exactly 10 retrieved_ids.")
        if len(set(retrieved_ids)) != 10:
            raise ValueError(f"Saved retrieval {idx} has duplicate retrieved_ids.")
        scores = result.get("scores")
        if scores is not None and (not isinstance(scores, list) or len(scores) != 10):
            raise ValueError(f"Saved retrieval {idx} has invalid scores.")
        results_by_idx[idx] = result
    if set(results_by_idx) != expected_indices:
        raise ValueError("Saved retrieval indices must be exactly 0000 through 0049.")

    nodes_by_id = {node.id_: node for node in dataset.text_nodes}
    if len(nodes_by_id) != len(dataset.text_nodes):
        raise ValueError("Corpus contains duplicate node IDs.")

    nodes_by_question = {}
    source_mapping = []
    for runtime_idx, row in dataset.tax_df.iterrows():
        if "source_idx" not in row:
            raise ValueError("Tax test dataset requires a source_idx column for saved retrieval.")
        source_idx = canonical_idx(row["source_idx"])
        result = results_by_idx.get(source_idx)
        if result is None:
            raise ValueError(f"No saved retrieval result for source_idx {source_idx}.")
        retrieved_ids = result["retrieved_ids"]
        missing_ids = [node_id for node_id in retrieved_ids if node_id not in nodes_by_id]
        if missing_ids:
            raise ValueError(f"Saved retrieval {source_idx} contains IDs absent from the corpus: {missing_ids}")
        question = row["question"]
        if question in nodes_by_question:
            raise ValueError("Duplicate test question cannot be mapped safely to saved retrieval.")
        scores = result.get("scores") or [None] * 10
        nodes_by_question[question] = [
            NodeWithScore(node=nodes_by_id[node_id], score=score)
            for node_id, score in zip(retrieved_ids, scores)
        ]
        source_mapping.append({"runtime_idx": canonical_idx(runtime_idx), "source_idx": source_idx})

    print("using_saved_retrieval=true")
    print("index_build_skipped=true")
    print(f"saved_retrieval_path={path}")
    print(f"saved_retrieval_runtime_to_source_idx={source_mapping}")
    return SavedRetrievalRetriever(nodes_by_question)

def write_response_results(path, results, questions):
    """บันทึกข้อมูลเดิมเป็น JSON ภาษา UTF-8 และสร้างฉบับอ่านง่ายโดยไม่เรียกโมเดล."""
    path = Path(path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    lines = ["# ผลการสร้างคำตอบ", "", f"จำนวนคำตอบที่บันทึก: {len(results)} รายการ", "",
             f"จัดรูปแบบจาก `{path.name}` โดยคงข้อความและภาษาที่โมเดลส่งกลับ ไม่แปลหรือแก้คำตอบ", "",
             "รายงานนี้แสดงเฉพาะคำตอบที่บันทึกสำเร็จ ข้อที่ล้มเหลวให้ตรวจจากไฟล์ diagnostic แยกต่างหาก", ""]
    for number, result in enumerate(results, start=1):
        runtime_idx = canonical_idx(result["idx"])
        source_idx = result.get("source_idx", "ไม่ระบุ")
        content = result["content"]
        elapsed = result.get("llm_time")
        elapsed_text = f"{elapsed:.2f}" if isinstance(elapsed, (int, float)) else "ไม่ระบุ"
        lines.extend([f"## รายการ {number} — source {source_idx}", "",
                      f"runtime_idx: `{runtime_idx}` | source_idx: `{source_idx}`", "",
                      f"ครั้งที่ลอง: {result.get('tries', 'ไม่ระบุ')} | เวลา LLM: {elapsed_text} วินาที | "
                      f"token รวม: {result.get('usage', {}).get('total_tokens', 'ไม่ระบุ')}", ""])
        for title, text in (
            ("คำถาม", questions.get(runtime_idx, "ไม่พบคำถามที่ตรงกับ runtime_idx")),
            ("การวิเคราะห์จากโมเดล", content.get("analysis", "ไม่มีฟิลด์ analysis")),
            ("คำตอบจากโมเดล", content.get("answer", "ไม่มีฟิลด์ answer")),
        ):
            lines.extend([f"### {title}", "", "> " + text.replace("\r\n", "\n").replace("\n", "\n> "), ""])
        lines.extend(["### กฎหมายที่อ้างอิง", ""])
        lines.extend([f"- {item['law']} มาตรา {item['section']}" for item in content.get("citations", [])]
                     or ["ไม่มีรายการอ้างอิง"])
        lines.append("")
    path.with_name(f"{path.stem}_readable.md").write_text("\n".join(lines), encoding="utf-8")


def get_tax_run_status(tax_df, results, failure_dir, model_settings):
    """ตรวจ checkpoint ราย ID และนับ length failure เป็น attempt ที่สิ้นสุดแล้ว."""
    sources = {canonical_idx(row["idx"]): canonical_idx(row["source_idx"])
               for _, row in tax_df.iterrows()}
    if len(sources) != len(tax_df) or len(set(sources.values())) != len(sources):
        raise ValueError("Continuation requires unique runtime/source IDs.")
    successes = set()
    for result in results:
        idx = canonical_idx(result["idx"])
        if idx in successes or sources.get(idx) != canonical_idx(result.get("source_idx")):
            raise ValueError("Duplicate or mismatched IDs in saved responses; inspect before resuming.")
        successes.add(idx)
    rows = []
    for idx, source in sources.items():
        row = {"runtime_idx": idx, "source_idx": source,
               "status": "success" if idx in successes else "pending"}
        path = Path(failure_dir) / f"runtime_{idx}_source_{source}_attempt_1.json"
        artifacts = list(Path(failure_dir).glob(f"runtime_{idx}_source_*_attempt_*.json"))
        if artifacts and (len(artifacts) != 1 or artifacts[0] != path):
            raise ValueError(f"Unexpected failure attempts/source for runtime {idx}; inspect before resuming.")
        if path.is_file():
            record = json.loads(path.read_text(encoding="utf-8"))
            if (record.get("finish_reason") != "length"
                    or record.get("exception_type") != "LengthFinishReasonError"
                    or canonical_idx(record.get("runtime_idx")) != idx
                    or canonical_idx(record.get("source_idx")) != source
                    or record.get("retry_attempt") != 1
                    or record.get("model_settings") != model_settings
                    or not isinstance(record.get("raw_response_content"), str)):
                raise ValueError(f"Failure evidence does not match this one-attempt run: {path}")
            if idx in successes:
                raise ValueError(f"Runtime {idx} has both success and failure; inspect before resuming.")
            row.update(status="generation_failure", finish_reason="length", diagnostic_file=str(path))
        rows.append(row)
    return {"total": len(rows),
            **{status: sum(row["status"] == status for row in rows)
               for status in ("success", "generation_failure", "pending")},
            "items": rows}


def write_tax_run_status(folder, status):
    """บันทึกสถานะครบทุกข้อแยกจาก schema คำตอบสำเร็จ."""
    path = Path(folder) / "tax_run_status.json"
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    labels = {"success": "บันทึกคำตอบสำเร็จ", "generation_failure": "สร้างคำตอบไม่จบ: เต็มงบ output",
              "pending": "ยังไม่ได้คำตอบหรือหลักฐาน failure ที่ยืนยันได้"}
    lines = ["# สถานะการรัน", "",
             f"ทั้งหมด {status['total']} ข้อ | บันทึกคำตอบสำเร็จ {status['success']} | "
             f"generation failure {status['generation_failure']} | ค้าง {status['pending']}", "",
             "สถานะสำเร็จหมายถึงบันทึกคำตอบได้ ไม่ใช่คะแนนความถูกต้องของคำตอบ", "",
             "ข้อที่มี length failure นับเป็น attempt ที่สิ้นสุดแล้ว ไม่มีคำตอบว่างแทนและไม่เรียกซ้ำอัตโนมัติ", "",
             "| runtime | source | สถานะ | หลักฐาน failure |", "|---|---|---|---|"]
    lines.extend(f"| {row['runtime_idx']} | {row['source_idx']} | {labels[row['status']]} | "
                 f"{row.get('diagnostic_file', '')} |" for row in status["items"])
    path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"run_status success={status['success']} generation_failure={status['generation_failure']} pending={status['pending']}")


async def evaluate_ragger(
    ragger: Ragger,
    golden_retriever: bool = False,
    batch_size: int = 1,
    setting_name: str = "",
    diagnostic: dict | None = None,
):
    
    os.makedirs(setting_name, exist_ok=True)
    
    tax_df = ragger.dataset.tax_df
    wangchan_df = ragger.dataset.wangchan_df
    questions = {canonical_idx(idx): question for idx, question in zip(tax_df["idx"], tax_df["question"])}
    
    #First, do tax
    tax_results = []
    if os.path.exists(os.path.join(setting_name, "tax_response.json")):
        with open(os.path.join(setting_name, "tax_response.json"), "r", encoding="utf-8") as f:
            tax_results = json.load(f)
    diagnostic = diagnostic or {}
    target_runtime_idx = diagnostic.get("runtime_idx")
    continue_on_length = diagnostic.get("continue_on_length_failure", False)
    if not continue_on_length and (Path(setting_name) / "tax_run_status.json").is_file():
        raise ValueError("This run has per-question status; resume with --continue-on-length-failure.")
    if continue_on_length:
        if (batch_size != 1 or diagnostic.get("max_retries") != 1 or ragger.max_retries != 1
                or not diagnostic.get("save_raw_on_parse_failure")
                or not diagnostic.get("failure_output_dir") or target_runtime_idx is not None):
            raise ValueError("Length-failure continuation requires a full run, batch_size=1, max_retries=1, and saved diagnostics.")
        status = get_tax_run_status(tax_df, tax_results, diagnostic["failure_output_dir"], ragger.llm.config)
        write_tax_run_status(setting_name, status)
        positions = [i for i, row in enumerate(status["items"]) if row["status"] == "pending"]
    elif target_runtime_idx is not None:
        target_runtime_idx = canonical_idx(target_runtime_idx)
        matches = [
            position for position, value in enumerate(tax_df["idx"].tolist())
            if canonical_idx(value) == target_runtime_idx
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Diagnostic runtime_idx {target_runtime_idx} must match exactly one Tax row; found {len(matches)}."
            )
        positions = matches
        print(f"diagnostic_runtime_idx={target_runtime_idx}")
    else:
        positions = range(len(tax_results), tax_df.shape[0], batch_size)

    for i in tqdm(positions):
        
        job_params = tax_df.iloc[i: i+batch_size][["idx", "question", "relevant_laws"]].to_dict(orient="records")

        if isinstance(job_params, dict):
            job_params = [job_params]

        indices = [p["idx"] for p in job_params]
        queries = [p["question"] for p in job_params]
        
        if golden_retriever:
            relevant_laws = [p["relevant_laws"] for p in job_params]
            
        else:
            relevant_laws = [None] * len(indices)
            
        dataset_names = ["tax"] * len(indices)
               
        start = time.time()
        jobs = ragger.rag_multi(indices=indices, queries=queries, relevant_laws=relevant_laws, dataset_names=dataset_names)
            
        try:
            results = await jobs
        except RawCompletionFailure as error:
            if (not continue_on_length or error.diagnostic_record.get("finish_reason") != "length"
                    or error.diagnostic_record.get("exception_type") != "LengthFinishReasonError"):
                raise
            status = get_tax_run_status(tax_df, tax_results, diagnostic["failure_output_dir"], ragger.llm.config)
            if status["items"][i]["status"] != "generation_failure":
                raise RuntimeError("Length failure was not saved; refusing to skip the question.") from error
            write_tax_run_status(setting_name, status)
            print(f"length_failure_recorded idx={indices[0]}; continuing without retry")
            time.sleep(max(0, 30 - (time.time() - start)))
            continue

        tax_results.extend(results)
        write_response_results(
            Path(setting_name) / "tax_response.json", tax_results, questions
        )
        if continue_on_length:
            status = get_tax_run_status(tax_df, tax_results, diagnostic["failure_output_dir"], ragger.llm.config)
            write_tax_run_status(setting_name, status)
        
        time.sleep(max(0, 30 - (time.time() - start)))
    return    

    
    #Next, do wangchan
    wangchan_results = []
    if os.path.exists(os.path.join(setting_name, "wangchan_response.json")):
        with open(os.path.join(setting_name, "wangchan_response.json"), "r") as f:
            wangchan_results = json.load(f)
    
    print(len(wangchan_results))
    for i in tqdm(range(len(wangchan_results), wangchan_df.shape[0], batch_size)):
        
        job_params = wangchan_df.iloc[i: i+batch_size][["idx", "question", "relevant_laws"]].to_dict(orient="records")
        if isinstance(job_params, dict):
            job_params = [job_params]
                
        indices = [p["idx"] for p in job_params]
        queries = [p["question"] for p in job_params]
        
        if golden_retriever:
            relevant_laws = [p["relevant_laws"] for p in job_params]
            
        else:
            relevant_laws = [None] * len(indices)
                   
        dataset_names = ["wangchan"] * len(indices)
            
        jobs = ragger.rag_multi(indices=indices, queries=queries, relevant_laws=relevant_laws, dataset_names=dataset_names)
        
        start = time.time()
        results = await jobs
        
        wangchan_results.extend(results)
        
        with open(os.path.join(setting_name, "wangchan_response.json"), "w") as f:
            json.dump(wangchan_results, f)
        
        time.sleep(max(0, 60 - (time.time() - start)))
        

        
    torch.cuda.empty_cache()
    
    
    
    

async def main(args):
    
    #Read config
    with open(args.config_path, "r") as f:
        config = yaml.safe_load(f)
        
    #Iterate through each config
    data_config = config["data_config"]
    retriever_config = config["retriever_config"]
    augmenter_config = config["augmenter_config"]
    llm_config = config["llm_config"]
    
    batch_size = config.get("batch_size", 1)
    output_path = config["output_path"]
    saved_retrieval_path = config.get("saved_retrieval_path")
    diagnostic = config.get("diagnostic") or {}
    context_source = config.get("context_source", "retrieved")
    if context_source not in ("retrieved", "golden"):
        raise ValueError("context_source must be 'retrieved' or 'golden'.")
    if getattr(args, "continue_on_length_failure", False):
        if context_source == "retrieved" and not saved_retrieval_path:
            raise ValueError("Length-failure continuation supports only Golden or Saved Retrieved.")
        diagnostic = dict(diagnostic, continue_on_length_failure=True)
    if config.get("reasoning_method") in ("zero_shot_cot", "irac") and context_source == "retrieved" and not saved_retrieval_path:
        raise ValueError(f"{config['reasoning_method']} with retrieved context requires saved_retrieval_path; live retrieval is disabled.")

    os.environ["CUDA_VISIBLE_DEVICES"] = str(config.get("device", "0"))
    print(os.environ["CUDA_VISIBLE_DEVICES"])

    if args.saved_retrieval_smoke_test:
        if not saved_retrieval_path:
            raise ValueError("--saved-retrieval-smoke-test requires saved_retrieval_path in the config.")
        if len(data_config) != 1:
            raise ValueError("--saved-retrieval-smoke-test requires exactly one data_config entry.")
        dataset = EvalDataset(**next(iter(data_config.values())))
        retriever = init_saved_retriever(dataset, saved_retrieval_path)
        first_question = dataset.tax_df.iloc[0]["question"]
        if len(retriever.retrieve(first_question)) != 10:
            raise RuntimeError("Saved retrieval smoke test expected exactly 10 nodes.")
        print("saved_retrieval_smoke_test=true")
        print("saved_retrieval_smoke_test_passed=true")
        return

    if args.dump_final_prompt:
        if context_source == "retrieved" and not saved_retrieval_path:
            raise ValueError("--dump-final-prompt requires saved_retrieval_path in the config.")
        if len(data_config) != 1 or len(augmenter_config) != 1 or len(llm_config) != 1:
            raise ValueError("--dump-final-prompt requires exactly one data, augmenter, and LLM configuration.")
        dataset = EvalDataset(**next(iter(data_config.values())))
        retriever = init_saved_retriever(dataset, saved_retrieval_path) if context_source == "retrieved" else None
        if context_source == "golden":
            print("context_source=golden")
            print("retriever_disabled=true")
            print("index_build_skipped=true")
        debug_runtime_idx = canonical_idx(diagnostic.get("runtime_idx", "0000"))
        expected_source_idx = canonical_idx(diagnostic.get("source_idx", debug_runtime_idx))
        row = dataset.tax_df.loc[
            dataset.tax_df["idx"].map(canonical_idx) == debug_runtime_idx
        ]
        if len(row) != 1:
            raise ValueError(f"Expected exactly one runtime idx {debug_runtime_idx} in the Tax test dataset.")
        row = row.iloc[0]
        source_idx = canonical_idx(row["source_idx"])
        if source_idx != expected_source_idx:
            raise ValueError(
                f"Runtime idx {debug_runtime_idx} must map to source_idx {expected_source_idx}, found {source_idx}."
            )
        augmenter = NitiLinkAugmenter(
            dataset=dataset,
            config=NitiLinkAugmenterConfig(
                **next(iter(augmenter_config.values())), strat_name=dataset.strat_name
            ),
        )
        llm = PromptDumpLLM(next(iter(llm_config.values()))["model"])
        ragger = Ragger(
            dataset=dataset,
            prompt_manager=PromptManager(
                prompt_version=config.get("prompt_version"),
                reasoning_method=config.get("reasoning_method"),
                citation_mode=config.get("citation_mode", "inline"),
                citation_constraint_mode=config.get("citation_constraint_mode", "none"),
            ),
            llm=llm,
            augmenter=augmenter,
            retriever=retriever,
            context_source=context_source,
        )
        formatted_prompt, structure, retrieved_nodes, _ = ragger.get_prompt_structure(
            query=row["question"],
            relevant_laws=row["relevant_laws"] if context_source == "golden" else None,
            dataset_name="tax",
        )
        retrieved_ids = [node.node.id_ if hasattr(node, "node") else node.id_ for node in retrieved_nodes]
        if context_source == "retrieved" and (len(retrieved_ids) != 10 or len(set(retrieved_ids)) != 10):
            raise RuntimeError("Final-prompt dump requires exactly 10 unique saved retrieved nodes.")
        debug_dir = Path("results/current/debug_prompts")
        debug_dir.mkdir(parents=True, exist_ok=True)
        if config.get("prompt_version") == "v3" and config.get("reasoning_method") == "direct":
            if diagnostic.get("runtime_idx") is not None or diagnostic.get("source_idx") is not None:
                if context_source == "golden" and config.get("citation_constraint_mode") == "enum":
                    dump_name = f"golden_direct_v3_citation_id_enum_runtime_{debug_runtime_idx}_source_{source_idx}_final_prompt.txt"
                elif config.get("citation_constraint_mode") == "enum":
                    dump_name = f"section_based_direct_v3_citation_id_enum_runtime_{debug_runtime_idx}_source_{source_idx}_final_prompt.txt"
                elif config.get("citation_mode") == "provision_id":
                    dump_name = f"section_based_direct_v3_citation_id_runtime_{debug_runtime_idx}_source_{source_idx}_final_prompt.txt"
                else:
                    dump_name = f"section_based_direct_v3_runtime_{debug_runtime_idx}_source_{source_idx}_final_prompt.txt"
            else:
                dump_name = f"section_based_direct_v3_runtime_{debug_runtime_idx}_final_prompt.txt"
        elif config.get("prompt_version") == "v3" and config.get("reasoning_method") in ("zero_shot_cot", "irac"):
            context_label = "golden" if context_source == "golden" else "section_based"
            dump_name = f"{context_label}_{config['reasoning_method']}_v3_citation_id_enum_runtime_{debug_runtime_idx}_source_{source_idx}_final_prompt.txt"
        else:
            dump_name = f"section_based_v2_runtime_{debug_runtime_idx}_final_prompt.txt"
        dump_path = debug_dir / dump_name
        provision_map = Ragger.build_provision_map(retrieved_nodes) if config.get("citation_mode") == "provision_id" else None
        if config.get("citation_constraint_mode") == "enum":
            structure = ragger.prompt_manager.build_citation_id_enum_structure(
                [entry["provision_id"] for entry in provision_map]
            )
        response_format = {
            "sdk_method": "client.beta.chat.completions.parse",
            "response_format_argument": "Pydantic model class",
            "pydantic_model": getattr(structure, "__name__", None),
            "json_schema": structure.model_json_schema() if hasattr(structure, "model_json_schema") else structure,
        }
        write_final_prompt_dump(
            dump_path,
            formatted_prompt["messages"],
            response_format=response_format,
            provision_map=provision_map,
        )
        print(f"debug_runtime_idx={debug_runtime_idx}")
        print(f"debug_source_idx={source_idx}")
        if context_source == "golden":
            _, unresolved_gold = ragger.resolve_gold_provisions(row["relevant_laws"])
            print(f"debug_gold_node_ids={retrieved_ids}")
            print(f"debug_unresolved_gold_provisions={unresolved_gold}")
        else:
            print(f"debug_retrieved_ids={retrieved_ids}")
        print("debug_response_format_included=true")
        print("llm_calls=0")
        print(f"final_prompt_dump_path={dump_path}")
        return
    
    #Makedirs
    os.makedirs(output_path, exist_ok=True)

    if diagnostic.get("runtime_idx") is not None:
        if batch_size != 1:
            raise ValueError("Diagnostic single-question mode requires batch_size=1.")
        if context_source == "retrieved" and not saved_retrieval_path:
            raise ValueError("Diagnostic single-question mode requires saved_retrieval_path.")
        retries = diagnostic.get("max_retries")
        if not isinstance(retries, int) or retries < 1:
            raise ValueError("Diagnostic max_retries must be a positive integer.")
    
    pm = PromptManager(
        prompt_version=config.get("prompt_version"),
        reasoning_method=config.get("reasoning_method"),
        citation_mode=config.get("citation_mode", "inline"),
        citation_constraint_mode=config.get("citation_constraint_mode", "none"),
    )

    if context_source == "golden":
        print("context_source=golden")
        print("retriever_disabled=true")
        print("index_build_skipped=true")
        for dc in data_config:
            dataset = EvalDataset(**data_config[dc])
            for ac in augmenter_config:
                augmenter = NitiLinkAugmenter(
                    dataset=dataset,
                    config=NitiLinkAugmenterConfig(**augmenter_config[ac], strat_name=dataset.strat_name),
                )
                for lc in llm_config:
                    llm = init_llm(llm_config[lc])
                    setting_name = f"{dc}-golden-{ac}-{lc}"
                    print(f"Doing {setting_name}...")
                    ragger = Ragger(
                        dataset=dataset,
                        prompt_manager=pm,
                        llm=llm,
                        augmenter=augmenter,
                        retriever=None,
                        context_source="golden",
                        max_retries=diagnostic.get("max_retries", 5),
                        citation_validation=config.get("citation_validation", False),
                        diagnostic=diagnostic,
                    )
                    await evaluate_ragger(
                        ragger,
                        batch_size=batch_size,
                        golden_retriever=True,
                        setting_name=os.path.join(output_path, setting_name),
                        diagnostic=diagnostic,
                    )
                    del ragger
                    gc.collect()
                    torch.cuda.empty_cache()
        return
    
    #Some concern, if the setting is golden retriever -> Ignore data config. if the setting is lclm -> ignore retriever, augmenter, data. if the augmenter have reference -> do only golden and if chunk is not golden, ignore augmenter that uses referencer
    
    #1. LCLM
    lclm_keys = [k for k in llm_config if "-lc" in k]
    # print(llm_config)
    
    if len(lclm_keys) > 0:
        
        #Dataset dont matter
        dataset = EvalDataset(**list(data_config.values())[0])
        #No need to parse retriever or augmenter
        for k in lclm_keys:
            print("Doing {}...".format(k))
            llm = init_llm(config = llm_config[k])
            
            ragger = Ragger(dataset = dataset,
                            prompt_manager = pm,
                            llm = llm)
            
            await evaluate_ragger(ragger, batch_size = batch_size, setting_name = os.path.join(output_path, k))
            
            del llm_config[k]
            del ragger
            gc.collect()
            torch.cuda.empty_cache()
            
    #1.5 Parametric Knowledge
    pr_keys = [k for k in retriever_config if "no-retriever" in k]
    
    if len(pr_keys) > 0:
        #Dataset dont matter
        dataset = EvalDataset(**list(data_config.values())[0])
            
        for lc in llm_config:
            llm = init_llm(llm_config[lc])

            setting_name = f"parametric-{lc}"

            print("Doing {}...".format(setting_name))

            ragger = Ragger(dataset = dataset,
                        prompt_manager = pm,
                        llm = llm)

            await evaluate_ragger(ragger, batch_size = batch_size, setting_name = os.path.join(output_path, setting_name))

            del ragger
            gc.collect()
            torch.cuda.empty_cache()
            
        del retriever_config["no-retriever"]
            
            
    #2 Golden Retriever
    gr_keys = [k for k in retriever_config if "golden-retriever" in k]
    
    if len(gr_keys) > 0:
        #Dataset dont matter
        dataset = EvalDataset(**list(data_config.values())[0])
        
        for ac in augmenter_config:
            augmenter = NitiLinkAugmenter(dataset = dataset, config = NitiLinkAugmenterConfig(**augmenter_config[ac], strat_name=dataset.strat_name))
            
            for lc in llm_config:
                llm = init_llm(llm_config[lc])
                
                setting_name = f"{ac}-golden-retriever-{lc}"
                
                print("Doing {}...".format(setting_name))
                
                ragger = Ragger(dataset = dataset,
                            prompt_manager = pm,
                            llm = llm,
                            augmenter=augmenter)
                
                await evaluate_ragger(ragger, batch_size = batch_size, golden_retriever=True, setting_name = os.path.join(output_path, setting_name))
                
                del ragger
                gc.collect()
                torch.cuda.empty_cache()
            
        del retriever_config["golden-retriever"]
        
    #3. Augment with referencer
    ref_keys = [k for k in augmenter_config if "ref-depth" in k]
    
    if len(ref_keys) > 0:
        #Dataset is golden only
        dataset = EvalDataset(**data_config["golden"])
        
        for key in ref_keys:
            augmenter = NitiLinkAugmenter(dataset = dataset, config = NitiLinkAugmenterConfig(**augmenter_config[key], strat_name=dataset.strat_name))
            
            #Init the retriever as well
            for rc in retriever_config:
                retriever = init_retriever(dataset=dataset, strat_name = dataset.strat_name, **retriever_config[rc])
                
                for lc in llm_config:
                    print(llm_config[lc])
                    llm = init_llm(llm_config[lc])
                    
                    setting_name = f"golden-{rc}-{key}-{lc}"
                    
                    print("Doing {}...".format(setting_name))
                    
                    ragger = Ragger(dataset = dataset,
                                prompt_manager = pm,
                                llm = llm,
                                augmenter=augmenter,
                                retriever=retriever,
                                citation_validation=config.get("citation_validation", False))

                    await evaluate_ragger(ragger, batch_size = batch_size, golden_retriever=False, setting_name = os.path.join(output_path, setting_name))
                    del ragger
                    gc.collect()
                    torch.cuda.empty_cache()
                    
            del augmenter_config[key]
            
    #4. Everything else. Just loop inside loop normally
    for dc in data_config:
        dataset = EvalDataset(**data_config[dc])
        
        for rc in retriever_config:
            if saved_retrieval_path:
                retriever = init_saved_retriever(dataset, saved_retrieval_path)
            else:
                retriever = init_retriever(dataset=dataset, strat_name=dataset.strat_name, **retriever_config[rc])
            
            for ac in augmenter_config:
                augmenter = NitiLinkAugmenter(dataset = dataset, config = NitiLinkAugmenterConfig(**augmenter_config[ac], strat_name=dataset.strat_name))
                
                for lc in llm_config:
                    llm = init_llm(llm_config[lc])
                    
                    setting_name = f"{dc}-{rc}-{ac}-{lc}"
                    
                    print("Doing {}...".format(setting_name))
                    
                    ragger = Ragger(dataset = dataset,
                                prompt_manager = pm,
                                llm = llm,
                                augmenter=augmenter,
                                retriever=retriever,
                                max_retries=diagnostic.get("max_retries", 5),
                                citation_validation=config.get("citation_validation", False),
                                diagnostic=diagnostic)
                    
                    

                    await evaluate_ragger(
                        ragger,
                        batch_size=batch_size,
                        golden_retriever=False,
                        setting_name=os.path.join(output_path, setting_name),
                        diagnostic=diagnostic,
                    )
                    
                    del ragger
                    gc.collect()
                    torch.cuda.empty_cache()
                    
                    
    
    
                
                
        
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_path", type=str, default="/app/LRG/config/all_e2e.yaml")
    parser.add_argument("--saved-retrieval-smoke-test", action="store_true")
    parser.add_argument("--dump-final-prompt", action="store_true")
    parser.add_argument("--continue-on-length-failure", action="store_true",
                        help="Record saved output-length failures and continue pending questions without retrying them.")
    args = parser.parse_args()
    if args.saved_retrieval_smoke_test and args.dump_final_prompt:
        parser.error("--saved-retrieval-smoke-test and --dump-final-prompt cannot be used together.")
    asyncio.run(main(args))

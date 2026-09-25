from llama_index.core.base.base_retriever import BaseRetriever
from typing import List, Dict, Any, Optional, Union

# from ..llm import GeminiModel, OpenAIModel, ClaudeModel
# งานนี้ใช้ Qwen ผ่าน OpenAI-compatible API ของ Ollama
from ..llm import OpenAIModel


from ..data import EvalDataset
from ..prompting import PromptManager
from ..augmenter import NitiLinkAugmenter

from pydantic import ValidationError
import time
import re
import json
from datetime import datetime, timezone
from pathlib import Path

import asyncio

class Ragger(object):
    """
    This class needs to handle 3 things:
    1. Normal RAG pipeline: Take in only query and go through the whole RAG process
    2. Long Context Pipeline: Take in only query and skip through retrieval and augmentation process straight to prompt formatting
    3. Golden Context Pipeline (Only work if strat is golden) : Take in query and nodes. Input to the process during augmenter (change retrieved nodes to input nodes)
    """
    
    def __init__(self,
                 dataset: EvalDataset,
                 prompt_manager: PromptManager,
                 llm: OpenAIModel,
                 retriever: Optional[BaseRetriever] = None,
                 augmenter: Optional[NitiLinkAugmenter] = None,
                 max_retries: int = 5,
                 citation_validation: bool = False,
                 diagnostic: Optional[Dict[str, Any]] = None,
                 context_source: str = "retrieved",
                ):
    
        #Set attributes
        self.dataset = dataset
        self.prompt_manager = prompt_manager
        self.llm = llm
        self.retriever = retriever
        self.augmenter = augmenter
        self.citation_validation = citation_validation
        self.diagnostic = diagnostic or {}
        if context_source not in ("retrieved", "golden"):
            raise ValueError("context_source must be 'retrieved' or 'golden'.")
        self.context_source = context_source
        self.pure = False
        self.o1 = False
        
        
        #Create node map for easy access
        self.id_to_node = {n.id_: n for n in self.dataset.text_nodes}
        # self.model_name = self.llm.model_name.split("-")[0]
        # assert self.model_name in ["gemini", "claude", "gpt", "o1", "typhoon"], "Unrecognized model name: {}".format(self.model_name)
        raw_model_name = self.llm.model_name.lower()

        if raw_model_name.startswith("qwen"):
            self.model_name = "qwen"
        else:
            self.model_name = raw_model_name.split("-")[0]

        assert self.model_name in ["qwen"], (
            f"Unrecognized model name: {self.llm.model_name}"
        )


        self.strat_name = self.dataset.strat_name
        self.max_retries = max_retries
        print("Max Retries: {}".format(self.max_retries))
        
        if hasattr(self.llm, "long_context"):
            self.long_context = self.llm.long_context
            
        else:
            self.long_context = False
        
        if (self.retriever is None) and (self.augmenter is None):
            self.pure = True
            
        if "o1" in self.llm.model_name:
            self.o1 = True
            
        # if long_context:
        #     assert isinstance(self.llm, GeminiModel), "Long context is activated but the model provided is not Gemini"
            
        
    def get_prompt_structure(self,
            query: str,
            relevant_laws: List[Dict] = None,
            dataset_name: str = "tax"):
    
        """
        For dealing with both normal RAG pipeline and Golden Context Pipeline. If relevant laws are parsed use nodes from it. If not, go through normal RAG pipeline
        """
        
        retrieve_query = query
        
        
            
        common_v3_context = bool(
            self.augmenter
            and self.augmenter.config.get("context_format") in ("common_v3", "common_v3_citation_id", "common_v3_citation_id_enum")
        )
        if dataset_name == "tax" and common_v3_context:
            query = retrieve_query
        elif dataset_name == "tax":
            query = f"<ข้อหารือ> {retrieve_query} </ข้อหารือ>"
        else:
            query = f"<question> {retrieve_query} </question>"
        
        
        retriever_time = 0
        if self.context_source == "golden":
            if relevant_laws is None:
                raise ValueError("Golden context requires dataset relevant_laws; retriever fallback is disabled.")
            retrieved_nodes, _ = self.resolve_gold_provisions(relevant_laws)
            augmented_query = self.augmenter(query, retrieved_nodes)
        elif self.long_context or self.pure:
            retrieved_nodes = []
            augmented_query = query
            
        elif (relevant_laws is not None):
            # Exact dataset law/section resolution only; no fuzzy matching or retrieval.
            retrieved_nodes, _ = self.resolve_gold_provisions(relevant_laws)
            augmented_query = self.augmenter(query, retrieved_nodes)
            
            
        else:
            #Otherwise, retrieve node normally with the retriever
            assert self.retriever is not None, "Please provide a retriever in case of normal rag pipeline"
            start_time = time.time()
            retrieved_nodes = self.retriever.retrieve(retrieve_query)
            retriever_time = time.time() - start_time
            #Then, augment the query
            augmented_query = self.augmenter(query, retrieved_nodes)
            
        
        name = self.model_name.split("-")[0]
        
        task = "response"
        if self.long_context:
            task = "response-long"
        elif self.pure:
            task = "response-pure"
        elif self.o1:
            task = "response-o1"
            
        formatted_prompt = self.prompt_manager.get_formatted_prompt(query=augmented_query, task=task, dataset=dataset_name, model=self.model_name)
        if name == "qwen":
            structure = self.prompt_manager.response_structure["response"][1]
    
        # if name == "gemini":
        #     structure = self.prompt_manager.response_structure["response"][2]
        # elif name == "gpt" or name == "o1":
        #     structure = self.prompt_manager.response_structure["response"][1]
        # elif name == "typhoon":
        #     structure = None
        # else:
        #     structure = self.prompt_manager.response_structure["response"][0]
            
        
        
        
        return formatted_prompt, structure, retrieved_nodes, retriever_time

    def resolve_gold_provisions(self, relevant_laws: List[Dict]) -> tuple[List, List[Dict[str, Any]]]:
        """Resolve dataset gold provisions against golden node IDs without guessing."""
        resolved = []
        unresolved = []
        for position, item in enumerate(relevant_laws or [], start=1):
            if not isinstance(item, dict):
                unresolved.append({"dataset_value": item, "position": position, "status": "invalid_gold_entry"})
                continue
            law = item.get("law")
            section = item.get("sections")
            if law is None or section is None:
                unresolved.append({"dataset_value": item, "position": position, "status": "missing_law_or_sections"})
                continue
            node_id = f"{str(law).strip()}-{str(section).strip()}"
            node = self.id_to_node.get(node_id)
            if node is None:
                unresolved.append({
                    "dataset_value": item,
                    "position": position,
                    "candidate_node_id": node_id,
                    "status": "exact_node_id_not_found",
                })
                continue
            resolved.append(node)
        return resolved, unresolved

    @staticmethod
    def build_provision_map(retrieved_nodes: List) -> List[Dict[str, str]]:
        """Create rank-stable model-facing IDs without changing retrieval order."""
        provision_map = []
        for rank, node in enumerate(retrieved_nodes, start=1):
            raw_node = node.node if hasattr(node, "node") else node
            law_name, section_id = raw_node.id_.rsplit("-", 1)
            provision_map.append({
                "provision_id": f"P{rank}",
                "law": law_name,
                "section": section_id,
                "retrieved_node_id": raw_node.id_,
            })
        return provision_map

    @staticmethod
    def map_citation_ids(model_content: Any, provision_map: List[Dict[str, str]]) -> tuple[Dict[str, Any], List[str], List[str], List[str]]:
        """Convert only model-selected provision IDs; no matching or semantic repair."""
        if not isinstance(model_content, dict):
            raise ValueError("model_content must be a JSON object before citation-ID mapping.")
        expected_keys = {"analysis", "answer", "citation_ids"}
        if set(model_content) != expected_keys:
            raise ValueError(f"model-facing top-level keys must be exactly {sorted(expected_keys)}.")
        citation_ids = model_content.get("citation_ids")
        if not isinstance(citation_ids, list) or not all(isinstance(item, str) for item in citation_ids):
            raise ValueError("citation_ids must be an array of strings.")

        by_id = {item["provision_id"]: item for item in provision_map}
        invalid_ids = []
        duplicate_ids = []
        selected = []
        seen = set()
        for provision_id in citation_ids:
            if provision_id in seen:
                duplicate_ids.append(provision_id)
                continue  # documented policy: preserve the first model-selected occurrence
            seen.add(provision_id)
            entry = by_id.get(provision_id)
            if entry is None:
                invalid_ids.append(provision_id)
                continue
            selected.append({"law": entry["law"], "section": entry["section"]})

        validation_errors = []
        if invalid_ids:
            validation_errors.append("invalid_provision_ids")
        if duplicate_ids:
            validation_errors.append("duplicate_provision_ids_preserve_first")
        final_content = {
            "analysis": model_content["analysis"],
            "answer": model_content["answer"],
            "citations": selected,
        }
        return final_content, invalid_ids, duplicate_ids, validation_errors

    def save_diagnostic_failure(self, index: str, attempt: int, error: Exception) -> None:
        """Persist diagnostic evidence only when explicitly enabled; never alter the response."""
        if not self.diagnostic.get("save_raw_on_parse_failure"):
            return
        output_dir = Path(self.diagnostic["failure_output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        source_idx = index
        if "source_idx" in self.dataset.tax_df.columns:
            matching = self.dataset.tax_df.loc[self.dataset.tax_df["idx"] == index, "source_idx"]
            if len(matching) == 1:
                source_idx = f"{int(str(matching.iloc[0])):04d}"
        record = dict(getattr(error, "diagnostic_record", {}))
        record.update({
            "runtime_idx": index,
            "source_idx": source_idx,
            "retry_attempt": attempt,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        stem = f"runtime_{index}_source_{source_idx}_attempt_{attempt}"
        raw_content = record.get("raw_response_content")
        if isinstance(raw_content, str):
            (output_dir / f"{stem}_raw.txt").write_text(raw_content, encoding="utf-8")
        (output_dir / f"{stem}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"diagnostic_failure_saved={output_dir / f'{stem}.json'}")

    @staticmethod
    def validate_citations(content: Any, retrieved_nodes: List) -> List[str]:
        """Validate common-interface citations without mutating model output."""
        errors = []
        expected_keys = {"analysis", "answer", "citations"}
        if not isinstance(content, dict):
            return ["response_content_not_json_object"]
        if set(content) != expected_keys:
            errors.append(f"top_level_keys={sorted(content)}")
        if not isinstance(content.get("answer"), str) or not content["answer"].strip():
            errors.append("empty_or_invalid_answer")
        citations = content.get("citations")
        if not isinstance(citations, list):
            return errors + ["citations_not_list"]
        allowed_pairs = {tuple(node.id_.rsplit("-", 1)) for node in retrieved_nodes}
        seen = set()
        for number, citation in enumerate(citations, start=1):
            prefix = f"citation_{number}"
            if not isinstance(citation, dict) or set(citation) != {"law", "section"}:
                errors.append(f"{prefix}_invalid_keys")
                continue
            law, section = citation["law"], citation["section"]
            if not isinstance(law, str) or not isinstance(section, str):
                errors.append(f"{prefix}_non_string")
                continue
            if re.search(r"มาตรา|<[^>]+>|\n", law):
                errors.append(f"{prefix}_law_format")
            if re.search(r"มาตรา|<[^>]+>|\n", section) or len(section.strip()) > 64 or len(section.split()) > 3:
                errors.append(f"{prefix}_section_format")
            pair = (law, section)
            if pair not in allowed_pairs:
                errors.append(f"{prefix}_not_in_context")
            if pair in seen:
                errors.append(f"{prefix}_duplicate")
            seen.add(pair)
        return errors
    
    async def rag(self, 
                  index: str, 
                  query: str,
                  relevant_laws: List[Dict] = None,
                  dataset_name: str = "tax"):
        
        formatted_prompt, structure, retrieved_nodes, retriever_time = self.get_prompt_structure(query=query, relevant_laws=relevant_laws, dataset_name=dataset_name)
        
        main_structure = self.prompt_manager.response_structure["response"][1]
        if self.prompt_manager.citation_constraint_mode == "enum":
            provision_map = self.build_provision_map(retrieved_nodes)
            structure = self.prompt_manager.build_citation_id_enum_structure(
                [entry["provision_id"] for entry in provision_map]
            )
            main_structure = structure
        
        counter = 0
        
        
        if self.o1:
            structure = None
        
        if self.long_context:
            response = await self.llm.complete_lc(**formatted_prompt, structure=structure)
            
            
        else:
            
            response = None
            while counter < self.max_retries:
                
                try:
                    response = await self.llm.complete(
                        **formatted_prompt, structure=structure, diagnostic=self.diagnostic
                    )
                    tmp = main_structure(**response["content"])
                    if self.prompt_manager.citation_mode == "provision_id":
                        model_content = response["content"]
                        provision_map = self.build_provision_map(retrieved_nodes)
                        final_content, invalid_ids, duplicate_ids, mapping_errors = self.map_citation_ids(
                            model_content, provision_map
                        )
                        response["model_content"] = model_content
                        response["model_citation_ids"] = model_content["citation_ids"]
                        response["provision_map"] = provision_map
                        response["invalid_provision_ids"] = invalid_ids
                        response["duplicate_provision_ids"] = duplicate_ids
                        response["content"] = final_content
                        response["citation_validation_errors"] = mapping_errors
                        if mapping_errors:
                            print(f"citation_id_mapping_errors idx={index}: {mapping_errors}")
                    if self.citation_validation:
                        validation_errors = self.validate_citations(response["content"], retrieved_nodes)
                        response.setdefault("citation_validation_errors", []).extend(validation_errors)
                        if validation_errors:
                            print(f"citation_validation_errors idx={index}: {validation_errors}")
                    break

                except Exception as e:
                    counter += 1
                    self.save_diagnostic_failure(index, counter, e)
                    if self.diagnostic.get("save_raw_on_parse_failure"):
                        print(f"response_attempt_failed idx={index} attempt={counter} error_type={type(e).__name__}")
                    else:
                        print(e)
                    continue
            # if (counter == self.max_retries) and (response is None):
            #     response = {"content": {}, "usage": {}}
                   
        
        #Save retrieve ids as well
        response["retrieved_ids"] = [n.id_ for n in retrieved_nodes]
        if self.context_source == "golden":
            gold_nodes, unresolved_gold = self.resolve_gold_provisions(relevant_laws)
            response["context_source"] = "golden"
            response["gold_provision_ids"] = [node.id_ for node in gold_nodes]
            response["gold_node_ids"] = [node.id_ for node in gold_nodes]
            response["unresolved_gold_provisions"] = unresolved_gold
        
        response["idx"] = index
        if self.prompt_manager.citation_mode == "provision_id" and "source_idx" in self.dataset.tax_df.columns:
            matching = self.dataset.tax_df.loc[self.dataset.tax_df["idx"] == index, "source_idx"]
            if len(matching) == 1:
                response["source_idx"] = f"{int(str(matching.iloc[0])):04d}"
        response["tries"] = counter + 1
        response["retriever_time"] = retriever_time
               
        return response
    
    async def rag_multi(self,
                        indices: List[str],
                        queries: List[str],
                        dataset_names: List[str],
                        relevant_laws: List[List[Dict]]):
        
        #If the model name is not claude, just return the job of rag
        # if self.model_name != "claude":
        return await asyncio.gather(*(self.rag(i, q, r, d) for i, q, r, d in zip(indices, queries, relevant_laws, dataset_names)))
                                    
                                    
        
        
        
        
        
        
            
        
        
            
            
            
                 
                 
                 

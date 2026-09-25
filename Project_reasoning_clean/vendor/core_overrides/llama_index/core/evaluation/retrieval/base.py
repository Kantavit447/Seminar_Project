"""Base retrieval abstractions."""

import asyncio
from abc import abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from llama_index.core.async_utils import asyncio_run
from llama_index.core.bridge.pydantic import BaseModel, Field, ConfigDict
from llama_index.core.evaluation.retrieval.metrics import resolve_metrics
from llama_index.core.evaluation.retrieval.metrics_base import (
    BaseRetrievalMetric,
    RetrievalMetricResult,
)
from llama_index.core.llama_dataset.legacy.embedding import (
    EmbeddingQAFinetuneDataset,
)

from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

import concurrent.futures


class RetrievalEvalMode(str, Enum):
    """Evaluation of retrieval modality."""

    TEXT = "text"
    IMAGE = "image"

    @classmethod
    def from_str(cls, label: str) -> "RetrievalEvalMode":
        if label == "text":
            return RetrievalEvalMode.TEXT
        elif label == "image":
            return RetrievalEvalMode.IMAGE
        else:
            raise NotImplementedError


class RetrievalEvalResult(BaseModel):
    """Retrieval eval result.

    NOTE: this abstraction might change in the future.

    Attributes:
        query (str): Query string
        expected_ids (List[str]): Expected ids
        retrieved_ids (List[str]): Retrieved ids
        metric_dict (Dict[str, BaseRetrievalMetric]): \
            Metric dictionary for the evaluation

    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    query: str = Field(..., description="Query string")
    expected_ids: List[str] = Field(..., description="Expected ids")
    expected_texts: Optional[List[str]] = Field(
        default=None,
        description="Expected texts associated with nodes provided in `expected_ids`",
    )
    retrieved_ids: List[str] = Field(..., description="Retrieved ids")
    retrieved_texts: List[str] = Field(..., description="Retrieved texts")
    mode: "RetrievalEvalMode" = Field(
        default=RetrievalEvalMode.TEXT, description="text or image"
    )
    metric_dict: Dict[str, RetrievalMetricResult] = Field(
        ..., description="Metric dictionary for the evaluation"
    )

    @property
    def metric_vals_dict(self) -> Dict[str, float]:
        """Dictionary of metric values."""
        return {k: v.score for k, v in self.metric_dict.items()}

    def __str__(self) -> str:
        """String representation."""
        return f"Query: {self.query}\n" f"Metrics: {self.metric_vals_dict!s}\n"


class BaseRetrievalEvaluator(BaseModel):
    """Base Retrieval Evaluator class."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    metrics: List[BaseRetrievalMetric] = Field(
        ..., description="List of metrics to evaluate"
    )

    @classmethod
    def from_metric_names(
        cls, metric_names: List[str], **kwargs: Any
    ) -> "BaseRetrievalEvaluator":
        """Create evaluator from metric names.

        Args:
            metric_names (List[str]): List of metric names
            **kwargs: Additional arguments for the evaluator

        """
        metric_types = resolve_metrics(metric_names)
        return cls(metrics=[metric() for metric in metric_types], **kwargs)

    @abstractmethod
    async def _aget_retrieved_ids_and_texts(
        self, query: str, mode: RetrievalEvalMode = RetrievalEvalMode.TEXT
    ) -> Tuple[List[str], List[str]]:
        """Get retrieved ids and texts."""
        raise NotImplementedError

    def evaluate(
        self,
        query: str,
        expected_ids: List[str],
        expected_texts: Optional[List[str]] = None,
        mode: RetrievalEvalMode = RetrievalEvalMode.TEXT,
        **kwargs: Any,
    ) -> RetrievalEvalResult:
        """Run evaluation results with query string and expected ids.

        Args:
            query (str): Query string
            expected_ids (List[str]): Expected ids

        Returns:
            RetrievalEvalResult: Evaluation result

        """
        return asyncio_run(
            self.aevaluate(
                query=query,
                expected_ids=expected_ids,
                expected_texts=expected_texts,
                mode=mode,
                **kwargs,
            )
        )

    # @abstractmethod
    async def aevaluate(
        self,
        query: str,
        expected_ids: List[str],
        expected_texts: Optional[List[str]] = None,
        mode: RetrievalEvalMode = RetrievalEvalMode.TEXT,
        **kwargs: Any,
    ) -> RetrievalEvalResult:
        """Run evaluation with query string, retrieved contexts,
        and generated response string.

        Subclasses can override this method to provide custom evaluation logic and
        take in additional arguments.
        """
        retrieved_ids, retrieved_texts = await self._aget_retrieved_ids_and_texts(
            query, mode
        )
        metric_dict = {}
        for metric in self.metrics:
            eval_result = metric.compute(
                query, expected_ids, retrieved_ids, expected_texts, retrieved_texts
            )
            metric_dict[metric.metric_name] = eval_result

        return RetrievalEvalResult(
            query=query,
            expected_ids=expected_ids,
            expected_texts=expected_texts,
            retrieved_ids=retrieved_ids,
            retrieved_texts=retrieved_texts,
            mode=mode,
            metric_dict=metric_dict,
        )
    
    # @abstractmethod
    async def aevaluate_multik(
        self,
        query: str,
        expected_ids: List[str],
        expected_texts: Optional[List[str]] = None,
        mode: RetrievalEvalMode = RetrievalEvalMode.TEXT,
        k: List[int] = [1],
        mapping: Dict[str, List[str]] = None,
        **kwargs: Any,
    ) -> RetrievalEvalResult:
        """Run evaluation with query string, retrieved contexts,
        and generated response string.

        Subclasses can override this method to provide custom evaluation logic and
        take in additional arguments. Take in multiple k. Return dict of retrievalEvalResults
        """
        retrieved_ids, retrieved_texts = await self._aget_retrieved_ids_and_texts(
            query, mode
        )
        
        assert len(retrieved_ids) >= max(k), "Please set the top k of the retriever to be at least the same as maximum k"
        
        k_dict = {}
        
        for _k in k:
            metric_dict = {}
            for metric in self.metrics:
                eval_result = metric.compute(
                    query, expected_ids, retrieved_ids[:_k], expected_texts, retrieved_texts[:_k], mapping=mapping
                )
                metric_dict[metric.metric_name] = eval_result
            
            k_dict[_k] = RetrievalEvalResult(
                            query=query,
                            expected_ids=expected_ids,
                            expected_texts=expected_texts,
                            retrieved_ids=retrieved_ids[:_k],
                            retrieved_texts=retrieved_texts[:_k],
                            mode=mode,
                            metric_dict=metric_dict,
                        )

        return k_dict
    
    def evaluate_multik(
        self,
        query: str,
        expected_ids: List[str],
        expected_texts: Optional[List[str]] = None,
        mode: RetrievalEvalMode = RetrievalEvalMode.TEXT,
        k: List[int] = [1],
        mapping: Dict[str, List[str]] = None,
        **kwargs: Any,
    ) -> RetrievalEvalResult:
        
        return asyncio.run(aevaluate_multik(query=query, expected_ids=expected_ids, expected_texts=expected_texts, mode=mode, k=k, mapping=mapping, **kwargs))
    
    
    async def evaluate_dataset_multik(
        self,
        dataset: EmbeddingQAFinetuneDataset,
        k: List[int] = [1],
        mapping: Dict[str, List[str]] = None,
        **kwargs: Any,
    ) -> List[RetrievalEvalResult]:
        """Run evaluation with dataset. Handle multiple k as well. Return dictionary of multiple results"""
        
        mode = RetrievalEvalMode.from_str(dataset.mode)
        
        eval_results = {_k: [] for _k in k}
        # eval_results = []
        # eval_jobs = []
        
        # Then, just get the retrieved id and text first for every query        
        for query_id, query in tqdm(dataset.queries.items()):
            
            expected_ids = dataset.relevant_docs[query_id]
            
            tmp = await self.aevaluate_multik(query, expected_ids=expected_ids, mode=mode, k = k, mapping=mapping)
            
            for _k in tmp:
                eval_results[_k].append(tmp[_k])
        
        #Creating jobs
#         for query_id, query in tqdm(dataset.queries.items()):
       
#             expected_ids = dataset.relevant_docs[query_id]
#             eval_jobs.append({"query": query, "expected_ids": expected_ids, "mode": mode, "k": k, "mapping": mapping})
            
#        #Running jobs
#         # Use ProcessPoolExecutor for parallel processing
#         with concurrent.futures.ProcessPoolExecutor(max_workers = 12) as executor:
#             # Use tqdm to show progress
#             futures = {executor.submit(self.evaluate_multik, **item): item for item in eval_jobs}

#             # Collect results with progress display
#             for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing Items"):
#                 result = future.result()  # Get the result of each processed item
#                 eval_results.append(result)


        return eval_results
        

    async def aevaluate_dataset(
        self,
        dataset: EmbeddingQAFinetuneDataset,
        workers: int = 2,
        show_progress: bool = False,
        **kwargs: Any,
    ) -> List[RetrievalEvalResult]:
        """Run evaluation with dataset."""
        semaphore = asyncio.Semaphore(workers)

        async def eval_worker(
            query: str, expected_ids: List[str], mode: RetrievalEvalMode
        ) -> RetrievalEvalResult:
            async with semaphore:
                return await self.aevaluate(query, expected_ids=expected_ids, mode=mode)

        response_jobs = []
        mode = RetrievalEvalMode.from_str(dataset.mode)
        for query_id, query in dataset.queries.items():
            expected_ids = dataset.relevant_docs[query_id]
            response_jobs.append(eval_worker(query, expected_ids, mode))
        
        if show_progress:

            eval_results = await tqdm_asyncio.gather(*response_jobs)
        else:
            eval_results = await asyncio.gather(*response_jobs)

        return eval_results

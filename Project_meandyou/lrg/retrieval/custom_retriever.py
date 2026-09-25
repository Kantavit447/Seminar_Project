from typing import Any, List

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.embeddings import BaseEmbedding
from transformers import AutoTokenizer, AutoModel

from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core.schema import NodeWithScore

from ragatouille import RAGPretrainedModel


class NVEmbeddings(BaseEmbedding):
    
    _query_prefix: str = PrivateAttr()
    _passage_prefix: str = PrivateAttr()
    _max_length: str = PrivateAttr()
    
    def __init__(
        self,
        query_prefix: str = "Instruction: Given a question, retrieve passages that answer the question\nQuery: ",
        passage_prefix: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._model = AutoModel.from_pretrained('nvidia/NV-Embed-v1', trust_remote_code=True, cache_dir="/app/cache", device_map="auto")
        self._query_prefix = query_prefix
        self._passage_prefix = passage_prefix
        self._max_length = 4096

    @classmethod
    def class_name(cls) -> str:
        return "nvembed"

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)

    def _get_query_embedding(self, query: str) -> List[float]:
        embeddings = self._model.encode([query], instruction=self._query_prefix, max_length=self._max_length)
        return embeddings[0].cpu().detach().numpy()

    def _get_text_embedding(self, text: str) -> List[float]:
        embeddings = self._model.encode([text], instruction=self._passage_prefix, max_length=self._max_length)
        return embeddings[0].cpu().detach().numpy()

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(
            texts, instruction = self._passage_prefix, max_length = self._max_length
        )
        return embeddings.cpu().detach().numpy()

#Jinna V3 need to have its own class since it has different <task> token for query and passages
class JinnaV3Embeddings(BaseEmbedding):
    
    _query_task: str = PrivateAttr()
    _passage_task: str = PrivateAttr()
    _max_length: str = PrivateAttr()
    
    def __init__(
        self,
        query_task: str = "retrieval.query",
        passage_task: str = "retrieval.passage",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._model = AutoModel.from_pretrained("jinaai/jina-embeddings-v3", trust_remote_code=True, cache_dir = "/app/cache", device_map="cuda")
        self._query_task = query_task
        self._passage_task = passage_task
        self._max_length = 4096

    @classmethod
    def class_name(cls) -> str:
        return "jinnav3"

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)

    def _get_query_embedding(self, query: str) -> List[float]:
        embeddings = self._model.encode([query], task=self._query_task, max_length=self._max_length)
        return embeddings[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        embeddings = self._model.encode([text], task=self._passage_task, max_length=self._max_length)
        return embeddings[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(
            texts, task=self._passage_task, max_length = self._max_length
        )
        
        return embeddings
    
## Another retriever for JinnaAI colbert. Use RAGatouille for indexing and searching
class ColbertRetriever(BaseRetriever):
    
    #What it needs is index_path, dataset and k
    def __init__(
        self,
        index_path: str,
        dataset,
        k: int) -> None:
        
        #What needs to be done??: 1. Load the index and checkpoint 2. Get idx to docid and docid to idx 3. set k
        super().__init__()
        
        self.RAG = RAGPretrainedModel.from_index(index_path)
        self.RAG.model.config.query_maxlen = 4096
        
        #Create mapping
        self.docid_to_idx = dict()
        self.idx_to_docid = dict()
        for i, n in enumerate(dataset.text_nodes):
            self.docid_to_idx[n.id_] = i
            self.idx_to_docid[i] = n.id_
        
        self.k = k
        self.nodes = dataset.text_nodes
        
        #Warmup
        print("Warming up ColBERT...")
        tmp = self._retrieve(query = "เจ้าของโรงงาน")
        
    #Then function for retrieval
    def _retrieve(self, query: str) -> List[NodeWithScore]:
        #Call search function
        results = self.RAG.search(query, k=self.k)
        
        # return results
        
        node_results = [NodeWithScore(node = self.nodes[self.docid_to_idx[r["document_id"]]], score = r["score"]) for r in results]
        
        return node_results
    
    async def aretrieve(self, query: str):
        
        return self._retrieve(query)
    
    
        
        
       
    
#Places for initialization of each type of embeddings
#Everything should return VectorIndexRetriever object
#Have one main method that maps the model name and call other method accordingly
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import (
    VectorStoreIndex,
)

from llama_index.core import (
    VectorStoreIndex,
)

from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.indices.managed.bge_m3 import BGEM3Index
from llama_index.embeddings.cohere import CohereEmbedding

import os

#เนื่องจากตัวโปรเจคของเราจะไม่ได้ใช้ colbert เลยจะไม่เรียกตัวนี้จะได้ไม่ error
# from .custom_retriever import NVEmbeddings, ColbertRetriever, JinnaV3Embeddings

from ..data import EvalDataset

def init_retriever(model_name: str, dataset: EvalDataset, k:int, strat_name: str):
    
    assert model_name in MODEL_NAME, f"{model_name} not legit. The available choices are {MODEL_NAME.keys()}"
    
    #Call accordingly
    retriever = MODEL_NAME[model_name][0](model_name, MODEL_NAME[model_name][1], dataset, k, strat_name)
    
    return retriever

def init_bm25(model_name: str, batch_size: int, dataset, k: int, strat_name: str):
    
    retriever = BM25Retriever.from_defaults(nodes=dataset.text_nodes, similarity_top_k=k)
    
    return retriever

def init_huggingface(model_name: str, batch_size: int, dataset, k: int, strat_name: str):
    
    if model_name == "wangchan-rerank":
        model_path = "VISAI-AI/nitibench-ccl-human-finetuned-bge-m3"
        
    elif model_name == "wangchan-auto-rerank":
        model_path = "VISAI-AI/nitibench-ccl-auto-finetuned-bge-m3"
        
    elif model_name == "bge-m3":
        model_path = "BAAI/bge-m3"
        
    
    print("Loading retriever...")
    embed_model = HuggingFaceEmbedding(
                model_name=model_path,
                embed_batch_size=batch_size,
                cache_folder = "/app/cache", device="cuda")
    
    index = VectorStoreIndex(dataset.text_nodes,
                                    embed_model=embed_model,
                                    show_progress=True,
                                    )
    
    retriever = index.as_retriever(similarity_top_k = k)
    
    return retriever 

def init_nvembed(model_name: str, batch_size: int, dataset, k: int, strat_name: str):
    from .custom_retriever import NVEmbeddings
    embed_model = NVEmbeddings()
    index = VectorStoreIndex(dataset.text_nodes,
                        embed_model=embed_model,
                        show_progress=True,
                        )
    
    return index.as_retriever(similarity_top_k=k)

def init_colbert(model_name:str, batch_size: int, dataset, k: int, strat_name: str):
    from .custom_retriever import ColbertRetriever
    
    index_path = os.path.join("/app/LRG/chunking", strat_name, f"{model_name}_colbert_index")
    # print(index_path)
    
    retriever = ColbertRetriever(index_path, dataset, k)
    
    return retriever

def init_jinnav3(model_name:str, batch_size: int, dataset, k: int, strat_name: str):

    from .custom_retriever import JinnaV3Embeddings
    
    embed_model = JinnaV3Embeddings()
    index = VectorStoreIndex(dataset.text_nodes,
                    embed_model=embed_model,
                    show_progress=True,
                    )
    
    return index.as_retriever(similarity_top_k=k)

def init_bge(model_name:str, batch_size: int, dataset, k: int, strat_name: str):
    
    if model_name == "bge-m3-multi":
        model_path = "BAAI/bge-m3"
    elif model_name == "wangchan-rerank-multi":
        model_path = "VISAI-AI/nitibench-ccl-human-finetuned-bge-m3"
    elif model_name == "wangchan-auto-rerank-multi":
        model_path = "VISAI-AI/nitibench-ccl-auto-finetuned-bge-m3"
        
    index = BGEM3Index(
                        nodes = dataset.text_nodes,
                        model_name = model_path,
                        show_progress = True,

                        weights_for_different_modes=[
                            0.4,
                            0.2,
                            0.4,
                        ],  # [dense_weight, sparse_weight, multi_vector_weight]
                    )
    
    return index.as_retriever(similarity_top_k = k)


def init_cohere(model_name:str, batch_size: int, dataset, k: int, strat_name: str):
    
    embed_model = CohereEmbedding(
                        api_key=os.environ["COHERE_API_KEY"],
                        model_name="embed-multilingual-v3.0",
                    )
    
    index = VectorStoreIndex(dataset.text_nodes,
                        embed_model=embed_model,
                        show_progress=True,
                        )
    
    return index.as_retriever(similarity_top_k = k)
    
     
MODEL_NAME = {"bm25": (init_bm25, 32), 
              "wangchan-rerank": (init_huggingface, 32),
              "bge-m3": (init_huggingface, 32),
              "nvembed": (init_nvembed, 32),
              "jinnav2": (init_colbert, 32),
              "jinnav3": (init_jinnav3, 32),
              "wangchan-rerank-multi": (init_bge, 32),
              "bge-m3-multi": (init_bge, 32),
              "wangchan-auto-rerank-multi": (init_bge, 32),
              "wangchan-auto-rerank": (init_huggingface, 32),
              "cohere": (init_cohere, 32)}
    


    
    
    
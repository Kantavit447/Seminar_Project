import yaml
from typing import List
import pandas as pd
import os
import json

from llama_index.retrievers.bm25 import BM25Retriever

from llama_index.core import (
    VectorStoreIndex,
)
from ..data import EvalDataset
from .retrieval_init import init_retriever
from llama_index.core.evaluation import (
    RetrieverEvaluator,
)

from dotenv import load_dotenv

load_dotenv("/app/setting.env")

def convert_result_to_df(results: dict, k: List[int], indices: List[str]):
    #What we need to do is just create a dictionary
    result_dict = []
    for i in range(len(indices)):
        tmp = dict()
        tmp["idx"] = indices[i]
        tmp["expected_ids"] = results[k[0]][i].expected_ids
        for _k in k:
            metric = results[_k][i].metric_dict 
            for key in metric:
                   tmp[f"{key}@{_k}"] = metric[key].score
                   
            if _k == max(k):
                   tmp["retrieved_ids"] = results[_k][i].retrieved_ids
                   
        result_dict.append(tmp)
        
    return pd.DataFrame(result_dict)
        
    
                
        

async def evaluate_retrieval(config_path: str):
    
    #Load config with yaml
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    #Read config
    metrics = config.get("metrics", ["multimrr", "mrr", "hit_rate", "precision", "recall"])
    
    k = config.get("k", [1, 5, 10, 20])
    max_k = max(k)
    
    model_names = config.get("model_names", ["bm25", "wangchan", "bge-m3"])
    
    law_dir = config.get("law_dir", "/app/test_data/laws")
    tax_data_path = config.get("tax_data_path", "/app/test_data/usable_tax_case.csv")
    wangchan_data_path = config.get("wangchan_data_path", "/app/test_data/full_data.csv")
    
    output_path = config.get("output_path", "/app/LRG/results/retriever/")
    
    chunking_strategies = config.get("chunking_strategy", [{"type": "golden"}])
    
    print("Loading Dataset...")
    
    for strat in chunking_strategies:
        print(f"Doing {strat}...")
        if strat["type"] == "golden":
            node_path = "/app/LRG/chunking/golden/nodes.json"
            mapping = None
            strat_dir = os.path.join(output_path, "golden")
            strat_name = "golden"
        else:
            chunk_dir = f"/app/LRG/chunking/{strat['chunk_size']}_{strat['chunk_overlap']}_{strat['type']}"
            with open(os.path.join(chunk_dir, "chunk_to_gold_mapping.json"), "r") as f:
                mapping = json.load(f)
            node_path = os.path.join(chunk_dir, "nodes.json")
            strat_dir = os.path.join(output_path, f"{strat['chunk_size']}_{strat['chunk_overlap']}_{strat['type']}")
            strat_name = f"{strat['chunk_size']}_{strat['chunk_overlap']}_{strat['type']}"
        
        print("Loading Dataset...")
        dataset = EvalDataset(law_dir = law_dir,
                              tax_data_path = tax_data_path,
                              wangchan_data_path = wangchan_data_path,
                              node_path = node_path)

        tax_indices = list(dataset.qa_tax.queries.keys())
        wangchan_indices = list(dataset.qa_wangchan.queries.keys())
                      
        #Then, create output directory
        os.makedirs(os.path.join(strat_dir, "tax"), exist_ok=True)
        os.makedirs(os.path.join(strat_dir, "wangchan"), exist_ok=True)
                      
        
            
        #Then, iterate through model
        for m in model_names:

            print("Doing {}".format(m))
            print("Creating Retriever...")
            #Create VectorStore Index for other indexing than the BM25
            retriever = init_retriever(m, dataset, max_k, strat_name)


            print("Evaluating...")
            evaluator = RetrieverEvaluator.from_metric_names(
                        metrics, retriever=retriever
                    )

            tax_results = await evaluator.evaluate_dataset_multik(
                                    dataset.qa_tax, k, mapping = mapping
                                )

            wangchan_results = await evaluator.evaluate_dataset_multik(
                                    dataset.qa_wangchan, k, mapping = mapping
                                )


            print("Dumping Results...")
            tax_result_df = convert_result_to_df(tax_results, k, tax_indices)
            tax_result_df.to_csv(os.path.join(strat_dir, "tax", f"{m}.csv"), index=False)

            wangchan_result_df = convert_result_to_df(wangchan_results, k, wangchan_indices)
            wangchan_result_df.to_csv(os.path.join(strat_dir, "wangchan", f"{m}.csv"), index=False)       
            
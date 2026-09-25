from typing import List
import json
import os
import glob
# from IPython.display import display

import pandas as pd
import numpy as np

from llama_index.core.evaluation import (
    EmbeddingQAFinetuneDataset)
from llama_index.core.schema import TextNode

from pathlib import Path
from ast import literal_eval


class EvalDataset(object):
    """
    Class for dealing with all data processing method including cross reference method, getting text node and converting to QAFinetuning Dataset
    """
    def __init__(self, 
                 law_dir: str = "/app/test_data/laws",
                 node_path: str = "/app/LRG/chunking/golden/gold_nodes.json",
                 tax_data_path: str = "/app/test_data/hf_tax.csv",
                 wangchan_data_path: str = "/app/test_data/hf_wcx.csv",
                 section_idx_path: str = "/app/LRG/dump/section_idx.json",
                 tax_columns: List[str] = ["question", "relevant_laws"],
                 wangchan_columns: List[str] = ["question", "relevant_laws"],
                 load_wangchan: bool = True,
                 ):
        
        
        self.law_dir = law_dir
        self.tax_data_path = tax_data_path
        self.wangchan_data_path = wangchan_data_path
        
        self.wangchan_columns = wangchan_columns
        self.tax_columns = tax_columns
        self.load_wangchan = load_wangchan
        
        #First, load the sections data
        self.set_law(self.law_dir)
        
        #Load tax and wangchan data
        if self.load_wangchan:
            self.wangchan_df = pd.read_csv(
                self.wangchan_data_path,
                encoding="utf-8-sig",
                converters={wangchan_columns[1]: literal_eval},
            )
        else:
            self.wangchan_df = pd.DataFrame(columns=wangchan_columns)

        self.tax_df = pd.read_csv(
            self.tax_data_path,
            encoding="utf-8-sig",
            converters={tax_columns[1]: literal_eval},
        )
        # display(self.tax_df)
        #Get text nodes
        self.node_path = node_path
        self.text_nodes = self.get_nodes()
        
        self.tax_df["idx"] = [f"{i:04d}" for i in range(self.tax_df.shape[0])]
        self.qa_tax = self.convert_to_qa(self.tax_df, self.tax_columns[0], self.tax_columns[1], "idx")
        
        if self.load_wangchan:
            self.wangchan_df["idx"] = [f"{i:04d}" for i in range(self.wangchan_df.shape[0])]
            self.qa_wangchan = self.convert_to_qa(self.wangchan_df, self.wangchan_columns[0], self.wangchan_columns[1], "idx")
        else:
            self.qa_wangchan = None
        
        with open(section_idx_path, "r") as f:
            section_idx = json.load(f)
            
        for k in section_idx:
            section_idx[k] = pd.Series(section_idx[k])
        
        self.section_idx = section_idx
        node_path_obj = Path(node_path)
        self.strat_name = node_path_obj.parent.name
        
        if "golden" in self.strat_name:
            self.mapper = None
        else:
            mapping_path = node_path_obj.parent / "chunk_to_gold_mapping.json"

            with open(mapping_path, "r",    encoding="utf-8") as f:
                self.mapper = json.load(f)
                
        print("There are {} nodes".format(len(self.text_nodes)))
        
        
        
    def set_law(self, law_dir):
        """
        Function for reading chunked sections of laws.
        """
        json_files = glob.glob(os.path.join(law_dir, "*.json"))
        sections = {}
        law_name_dict = {}
        name_law_dict = {}

        for json_file in json_files:
            filename = os.path.basename(json_file).split(".")[0]
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                data = pd.DataFrame(data).set_index("section_num")

                assert len(data["law_name"].unique()) == 1
                law_name = data["law_name"].unique()[0]
                law_name_dict[law_name] = filename
                name_law_dict[filename] = law_name
                sections[filename] = data
                
        self.sections = sections
        self.law_name_dict = law_name_dict
        self.name_law_dict = name_law_dict
        
        
    def get_nodes(self):
        """
        Function for converting each sections into llam_index TextNodes. With index being {law_code}-{section_num"
        """
        
        with open(self.node_path, "r") as f:
            raw_text_nodes = json.load(f)
            
        text_nodes = [TextNode(**r) for r in raw_text_nodes]
                
        return text_nodes
    
    def convert_to_qa(self, df, q_column, r_column, idx_column): 
        """
        Convert to llama index QAFinetuning dataset
        """
        #Just append to list ready for dumping to json. Use idx column as index for each queries
        assert df[idx_column].nunique() == df.shape[0]
        #Create corpus
        corpus = dict()
        for k, v in self.sections.items():
            for idx, row in v.iterrows():
                text = row["section_content"]
                id_ = f"{self.name_law_dict[k]}-{row.name}"
                corpus[id_] = text

        queries = dict()
        relevant_docs = dict()

        for idx, row in df.iterrows():
            q = row[q_column]
            r = [f"{l['law']}-{l['sections']}" for l in row[r_column]]
            idx = str(row[idx_column]).strip()
            queries[idx] = q
            relevant_docs[idx] = r

        tmp = {"queries": queries, "corpus": corpus, "relevant_docs": relevant_docs, "mode": "text"}
        
        return EmbeddingQAFinetuneDataset(**tmp)
    
        
    
        
        
    

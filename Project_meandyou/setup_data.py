import pandas as pd
from sklearn.model_selection import train_test_split
import json
import os
# This script is run when creating image.
# The purpose is to load the data from huggingface and do some preprocessing to prepare for evaluation

def filter_reduced_law(relevant_laws, possible_chunks):
    
    return [s for s in relevant_laws if f"{s['law']}-{s['sections']}" in possible_chunks]


def main():

    splits = {'ccl': 'data/nitibench-ccl.parquet', 'tax': 'data/nitibench-tax.parquet'}

    wcx_df = pd.read_parquet("hf://datasets/VISAI-AI/nitibench/" + splits["ccl"])
    tax_df = pd.read_parquet("hf://datasets/VISAI-AI/nitibench/" + splits["tax"])

    os.makedirs("/app/test_data", exist_ok=True)
    
    tax_df = tax_df.rename(columns = {"question": "ข้อหารือ", "relevant_laws": "actual_relevant_laws"})
    tax_df["actual_relevant_laws"] = tax_df["actual_relevant_laws"].apply(lambda x: [{'law': _x['law_name'],
                                                                                      'sections': _x['section_num']} for _x in x])
    
    wcx_df["relevant_laws"] = wcx_df["relevant_laws"].apply(lambda x: [{'law': _x['law_name'],
                                                                        'sections': _x['section_num']} for _x in x])
    
    #Then, select the ratio
    ratio = 0.2
    n_samples = round(ratio*wcx_df.shape[0])

    #Then, get the stats
    relevant_law_codes = wcx_df["relevant_laws"].apply(lambda x: x[0]["law"])
    
    train, test = train_test_split(wcx_df, test_size=n_samples, random_state=42, shuffle=True, stratify=relevant_law_codes)
    
    wcx_df.to_csv("/app/test_data/hf_wcx.csv", encoding="utf-8-sig", index=False)
    tax_df.to_csv("/app/test_data/hf_tax.csv", encoding="utf-8-sig", index=False)
    test.to_csv("/app/test_data/lclm_sample.csv", encoding="utf-8-sig", index=False)
    
    # Another thing we should do in setup is that we should remove some labels for evaluating chunking vary
    with open("/app/LRG/chunking/reduced_golden/nodes.json", "r") as f:
        chunks = json.load(f)
        
    chunks = [c["id_"] for c in chunks]
    
    wcx_df["relevant_laws"] = wcx_df["relevant_laws"].apply(lambda x: filter_reduced_law(x, chunks))
    tax_df["actual_relevant_laws"] = tax_df["actual_relevant_laws"].apply(lambda x: filter_reduced_law(x, chunks))
    
    wcx_df = wcx_df[wcx_df["relevant_laws"].apply(len) > 0].reset_index(drop = True)
    tax_df = tax_df[tax_df["actual_relevant_laws"].apply(len) > 0].reset_index(drop = True)
    
    wcx_df.to_csv("/app/test_data/hf_wcx_reduced_sections.csv", index = False)
    tax_df.to_csv("/app/test_data/hf_tax_reduced_sections.csv", index = False)
    
    


if __name__ == "__main__":
    main()

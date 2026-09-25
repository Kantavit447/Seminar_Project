# Retrieval Evaluation Config  

This folder contains all configuration files for **retrieval evaluation**. You can modify the following **seven key components**:  

---

1. **`tax_data_path`** & **`wangchan_data_path`**  
   - Paths to the **Tax Case** dataset and **CCL dataset**, respectively.  

2. **`output_path`**  
   - Directory where retrieval results and evaluations will be stored.  

3. **`metrics`**  
   - Specifies the **evaluation metrics** for retrieval performance.  
   - You can choose from **six available metrics** in our work:  
     - **Multi-MRR**  
     - **MRR (Mean Reciprocal Rank)**  
     - **Hit-Rate**  
     - **Multi-Hit-Rate**  
     - **Precision**  
     - **Recall**  

4. **`k`**  
   - Specifies the **top-k document settings** for evaluation.  

5. **`chunking_strategy`**  
   - Defines the **chunking method** used in retrieval evaluation.  
   - Options:  
     - **Golden chunking** → Use `type: golden` in the config.  
     - **Naive chunking** → Specify `chunk_size`, `chunk_overlap`, and `type`.  

6. **`model_name`**  
   - Name of the **retrieval model**.  
   - Available models can be found in:  
     ```
     lrg/retrieval/retrieval_init.py
     ```  

---

Modify these settings in the configuration file to tailor retrieval evaluation to your needs. 🚀  
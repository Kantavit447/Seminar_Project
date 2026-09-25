# E2E Evaluation Config

This folder contains all configuration files for E2E evaluation. There are **six key components** you can modify:  

1. **`chunk_node_path`**  
   - Path to the **naive chunks**.  
   - Modify this if you use a different chunking method for nodes.  

2. **`golden_node_path`**  
   - Path to the **section-based chunks**.  
   - **Should not be changed** as it serves as a reference.  

3. **`result_dir`**  
   - Directory containing results from running `script/response_e2e.py`.  

4. **`llm_config`**  
   - Configuration for the **Judge LLM**.  
   - Can be configured similarly to the LLM settings in the response config.  

5. **`eval_retrieval`**  
   - Boolean flag (`True/False`).  
   - Set to `True` if you want to **evaluate the retrieval** alongside **end-to-end (E2E) metrics**.  

6. **`batch_size`**  
   - Batch size for LLM response generation.  

---

Modify these parameters in the configuration file to customize the evaluation process according to your needs. 🚀 
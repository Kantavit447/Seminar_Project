# System Response Config

This folder contains all configuration files for system-generated responses in our experiments. You can modify the config file for your own experiments.  

The response config file consists of **four main components**:  

1. **Data Config**  
2. **Retriever Config**  
3. **Augmenter Config**  
4. **LLM Config**  

When executing `response_e2e.py`, the script iterates through all possible combinations within the config file. This means a single config file can include **multiple versions** of data, retrievers, augmenters, and LLMs. Below, we describe each component in detail:  

---

## 1. Data Config  

- Defined under the `data_config` key in the YAML file.  
- Each data setting is stored as a key-value pair, where the **key** is the folder name for the resulting data, and the **value** is the parameter configuration.  
- Important parameters:  

    - `node_path`: Path to the chunked data used in the experiment.  
    - `tax_data_path`: Path to the **Tax Case** dataset (modifiable if using a different version of the original **NitiBench-Tax** dataset).  
    - `wangchan_data_path`: Path to the **CCL dataset** (modifiable if using a different version of the original **NitiBench-CCL** dataset).  

---

## 2. Retriever Config  

- Defined under the `retriever_config` key in the YAML file.  
- Each retriever setting is stored as a key-value pair, where the **key** is the folder name for the resulting retriever and the **value** is the parameter configuration.  
- Important parameters:  

    - `model_name`: Name of the retriever model.  
      - You can find available retriever models in `lrg/retrieval/retrieval_init.py`.  
      - To add a custom model, modify this file accordingly. 
      If you want to use golden context in the system, just specify the key as **golden-retriever**
    - `k`: Number of chunks to retrieve.  

---

## 3. Augmenter Config  

- Defined under the `augmenter_config` key in the YAML file.  
- Each augmenter setting is stored as a key-value pair, where the **key** is the folder name for the resulting augmenter and the **value** is the parameter configuration.  
- Important parameters:  

    - `reference`: Boolean flag indicating whether to perform **cross-referencing** on the retrieved context.  
    - `max_depth`: Maximum depth for cross-referencing.  
      - **Default in our experiments:** `max_depth = 1`.  

---

## 4. LLM Config  

- Defined under the `llm_config` key in the YAML file.  
- Each LLM setting is stored as a key-value pair, where the **key** is the folder name for the resulting LLM and the **value** is the parameter configuration.  
- **LLM parameters vary** based on the model.  
  - To see available parameters for each model, check the source code in `lrg/llm`. 
  - You can specify the use of Long Context LLM (LCLM) here as well under the boolean parameter `lclm` in the Gemini Config.

---

## Additional Parameters  

Aside from these four components, there are **three additional parameters** to configure:  

- **`output_path`**: Path to the output folder where generated responses will be saved.  
- **`device`**: GPU device ID to run the retriever or LLM model on (**default: `0`**).  
- **`batch_size`**: Batch size for the LLM during response generation.  

---

By modifying the YAML configuration, you can customize the system’s response generation process for your experiments. 🚀  

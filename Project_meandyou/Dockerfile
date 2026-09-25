FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install gcc git python3-dev -y

RUN git clone https://github.com/run-llama/llama_index.git /app/llama_index 

COPY . /app/LRG 

RUN apt-get update && apt-get install -y rsync && \
    rsync -a /app/LRG/llama_index_extra/ /app/llama_index/

RUN pip install --upgrade pip
RUN pip install torch==2.2.0 --index-url https://download.pytorch.org/whl/cu121
RUN pip install --no-cache-dir -r /app/LRG/requirements.txt  

# Install LlamaIndex
RUN pip install -e /app/llama_index/llama-index-core  
RUN pip install -e /app/llama_index/llama-index-integrations/embeddings/llama-index-embeddings-cohere
RUN pip install -e /app/llama_index/llama-index-integrations/embeddings/llama-index-embeddings-huggingface
RUN pip install -e /app/llama_index/llama-index-integrations/indices/llama-index-indices-managed-bge-m3
RUN pip install -e /app/llama_index/llama-index-integrations/indices/llama-index-indices-managed-colbert
RUN pip install -e /app/llama_index/llama-index-integrations/retrievers/llama-index-retrievers-bm25

# Run the Python script to download and preprocess data
RUN mv /app/LRG/test_data /app
RUN python /app/LRG/setup_data.py 

# Set the entrypoint to /app/LRG
# ENTRYPOINT ["/app"]

CMD ["bash"]
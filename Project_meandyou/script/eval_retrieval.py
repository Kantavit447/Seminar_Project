import argparse
import sys
import asyncio
import os

os.environ["CUDA_VISIBLE_DEVICES"] = "3"

sys.path.append("/app/LRG")

from lrg.retrieval import evaluate_retrieval

async def main(args):
    
    await evaluate_retrieval(args.config_path)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_path", type=str, default="/app/LRG/config/all.yaml")
    args = parser.parse_args()
    asyncio.run(main(args))
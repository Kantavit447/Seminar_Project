from dotenv import load_dotenv
from typing import List, Dict
from typing_extensions import TypedDict
import os
import datetime


import google.generativeai as genai
from google.generativeai import caching, GenerativeModel, GenerationConfig

import time

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

from .config import GeminiConfig
import time

load_dotenv("/app/setting.env")

with open("/app/LRG/dump/lc_law.txt", encoding="utf-8", mode =  "r") as f:
    full_ns = f.read()
    
contents=[{"role": "user", "parts": "Here's every law available: {}".format(full_ns)},
          {"role": "model", "parts": "Got it! I will refer to this given knowledge for any future task"}] 


class GeminiModel(object):
    
    def __init__(self, config: GeminiConfig = GeminiConfig()) -> None:
        """
        Just initialize everything including set attributes and start client
        """
        config = config.model_dump()
        
        #Split to model name, config and GenerationConfig
        self.generation_config = GenerationConfig(**config.pop("generation_config"))
        self.model_name = config.pop("model")
        self.long_context = config.pop("long_context")
        
        
        self.gemini_config = config
        
        self.client = None
        
        if not self.long_context:
            self._create_client()
            
        self.full_ns = full_ns
        
            
    def _create_lc_client(self, system: str, messages: List[Dict]) -> None:
        
        contents=[{"role": "user", "parts": [{"text": "Here's every law available: {}".format(full_ns)}]},
                  {"role": "model", "parts": [{"text": "Got it! I will refer to this given knowledge for any future task"}]}] 
        
        contents += messages[:-1]

        
        cache = caching.CachedContent.create(
                                                model="models/gemini-1.5-pro-002",
                                                display_name='law_context', # used to identify the cache
                                                system_instruction=system,
                                                contents=contents,
                                                ttl=datetime.timedelta(hours=2),
                                            )
        
        print("Create new cached!")
        
        
        self.client = GenerativeModel.from_cached_content(cached_content=cache)
        
        time.sleep(120)
        
        
        
    def _create_client(self) -> None:
        """
        Create the client
        """
        client = GenerativeModel(f"models/{self.model_name}", system_instruction="You are a helpful assistant")
       
        self.client = client
        
        
    async def complete_lc(self, system: str, messages: List[Dict], structure:TypedDict = None) -> Dict:
        #First, check if cache exists or not
        caches = caching.CachedContent.list()
        law_cache = [c for c in caches if c.display_name == "law_context"] #c.display_n
        
        if len(law_cache) == 0:
            self._create_lc_client(system, messages)
        elif self.client is None:
            self.client = GenerativeModel.from_cached_content(law_cache[0])
        
        
        if structure is not None:
            self.generation_config.response_schema = structure
           
        else:
            self.generation_config.response_schema = None
        # self.client._system_instruction.parts[0].text = system
        start_time = time.time()
        response = await self.client.generate_content_async(contents = [messages[-1]],
                                                 generation_config = self.generation_config,
                                                 **self.gemini_config)
        time_taken = time.time() - start_time
        
        try:
            content = eval(response.candidates[0].content.parts[0].text)
        
        except (SyntaxError, NameError):
            content = response.candidates[0].content.parts[0].text
            
        usage = response.usage_metadata
        
        usage = {"prompt_token_count": usage.prompt_token_count,
                 "candidates_token_count": usage.candidates_token_count,
                 "total_token_count": usage.total_token_count,
                 "llm_time": time_taken}
        
        return {"content": content, "usage": usage}

    async def complete(self, system: str, messages: List[Dict], structure: TypedDict) -> Dict:
        """
        Complete chat message. For gemini api, must provide system, messages, structure to use. This is in the form of TypedDict
        """
        
        #Before calling, need to set structure 
        self.generation_config.response_schema = structure
        self.client._system_instruction.parts[0].text = system
        
        start_time = time.time()
        response = await self.client.generate_content_async(contents = messages,
                                                            generation_config = self.generation_config,
                                                            **self.gemini_config)
        
        time_taken = time.time() - start_time
        
        
        if len(response.candidates[0].content.parts) > 0:
            try:
                content = eval(response.candidates[0].content.parts[0].text)
            except SyntaxError:
                content = response.candidates[0].content.parts[0].text
                
        else:
            content = {"analysis": "", "answer": "", "citations": []}
        
            
        usage = response.usage_metadata
        
        usage = {"prompt_token_count": usage.prompt_token_count,
                 "candidates_token_count": usage.candidates_token_count,
                 "total_token_count": usage.total_token_count,
                 "llm_time": time_taken}
        
        return {"content": content, "usage": usage}
    
    async def multi_complete(self, systems: List[str], messages: List[List[Dict]], structures: List[TypedDict]) -> List[Dict]:
        """
        For calling async function
        """
        
        jobs = [self.complete(system, message, structure) for system, message, structure in zip(systems, messages, structures)]
        
        return await asyncio.gather(*jobs)
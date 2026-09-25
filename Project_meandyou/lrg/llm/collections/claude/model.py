from dotenv import load_dotenv
from typing import List, Dict
import os

from anthropic import AsyncAnthropic, Anthropic

import time

from .config import ClaudeConfig

from anthropic.types.beta.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.beta.messages.batch_create_params import Request



load_dotenv("/app/setting.env")

def convert_from_str(content):

    pattern = r'\{(.*)\}'
    if not isinstance(content, str):
        return content

    try:
        x = re.search(pattern, content, re.DOTALL).group().strip()
        return eval(x) 
    
    except SyntaxError:
        try:
            content = content.replace(bias, "").replace("```", "").replace("json", "").strip()
            if content[-1] != "}":
                content += "}"
                
            x = re.search(pattern, content, re.DOTALL).group().strip()
            return eval(x) 
        except:
            
            return content

class ClaudeModel(object):
    
    def __init__(self, config: ClaudeConfig = ClaudeConfig()) -> None:
        """
        Just initialize everything including set attributes and start client
        """
        
        self.config = config.model_dump()
        
        self.model_name = self.config["model"]
        
        self._create_client()
        
    def _create_client(self) -> None:
        """
        Create the client
        """
        client = AsyncAnthropic(
                    # This is the default and can be omitted
                    api_key=os.environ.get("ANTHROPIC_API_KEY"),
                )
        
        batch_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
       
        self.client = client
        self.batch_client = batch_client
    
    #Need to take in same parameters
    async def complete(self, system: List[Dict], messages: List[Dict], structure: Dict) -> Dict:
        """
        Complete chat message. For claude api, must provide system, messages, tools (structure to use)
        """
        start_time = time.time()
        response = await self.client.messages.create(**self.config,
                                                system=system,
                                                messages=messages,
                                                tools=[structure],
                                                tool_choice = {"type": "any"}
                                                )
        time_taken = time.time() - start_time
        
        content = response.content[0].input
        
        
        usage = response.usage.model_dump()
        
        return {"content": content, "usage": {**usage, "llm_time": time_taken}}
    
    async def batch_complete(self, systems: List[List[Dict]], messages: List[List[Dict]], structures: List[Dict], indices: List[str]) -> List[Dict]:
        """
        This is done to call batch API of claude, send everything at once. Then retrieve in notebook later (24 hr)
        """
        
        requests=[
            Request(
                custom_id=indices[i],
                params=MessageCreateParamsNonStreaming(
                    **config,
                    system = systems[i],
                    messages = messages[i],
                    tools=[structures[i]],
                    tool_choice = {"type": "any"}
                )
            ) for i in range(len(structures))
        ]
        
        
        message_batch = client.beta.messages.batches.create(requests=requests)
        
        return message_batch.model_dump()
            
            
        
        
        
    
    

        
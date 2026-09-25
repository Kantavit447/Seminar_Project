## Contain function to parse schema(json file) to actual pydantic class (need to do this for openai)
from typing import List, Dict, Any, Tuple, Literal

import json
import os
import re
from pydantic import ConfigDict, Field, create_model

from typing_extensions import TypedDict
from types import new_class

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, meta
#Structuring Prompt Manager
class PromptManager(object):
    
    def __init__(
    self,
    template_dir: str | None = None,
    main_template: str = "default_query.md",
    prompt_version: str | None = None,
    reasoning_method: str | None = None,
    citation_mode: str = "inline",
    citation_constraint_mode: str = "none",
    ) -> None:
        """
        Initialise templates and structured-output definitions.
        """

        base_dir = Path(__file__).resolve().parent

        if template_dir is None:
            template_path = base_dir / "templates"
        else:
            template_path = Path(template_dir)

        self.template_dir = str(template_path)
        self.prompt_version = prompt_version
        self.reasoning_method = reasoning_method
        self.citation_mode = citation_mode
        self.citation_constraint_mode = citation_constraint_mode

        if self.prompt_version not in (None, "v2", "v3"):
            raise ValueError(
                "Unsupported prompt_version: "
                f"{self.prompt_version}. Supported values are None, 'v2', and 'v3'."
            )
        if self.prompt_version == "v3" and self.reasoning_method != "direct":
            raise ValueError("Prompt v3 currently implements only reasoning_method: direct.")
        if self.citation_mode not in ("inline", "provision_id"):
            raise ValueError("Unsupported citation_mode. Supported values are 'inline' and 'provision_id'.")
        if self.citation_mode == "provision_id" and self.prompt_version != "v3":
            raise ValueError("citation_mode 'provision_id' requires prompt_version 'v3'.")
        if self.citation_constraint_mode not in ("none", "enum"):
            raise ValueError("Unsupported citation_constraint_mode. Supported values are 'none' and 'enum'.")
        if self.citation_constraint_mode == "enum" and self.citation_mode != "provision_id":
            raise ValueError("citation_constraint_mode 'enum' requires citation_mode 'provision_id'.")

        env = Environment(
            loader=FileSystemLoader(self.template_dir)
        )

        self.template = env.get_template(main_template)
        self.o1_template = env.get_template("o1_query.md")

        self.DATASET_NAMES = ["tax", "wangchan"]

        structured_output_dir = base_dir / "structured_outputs"
        if self.prompt_version == "v3" and self.citation_mode == "provision_id":
            response_schema_name = "system_response_v3_citation_id.json"
        elif self.prompt_version == "v3":
            response_schema_name = "system_response_v3.json"
        else:
            response_schema_name = "system_response.json"
        system_response_path = str(structured_output_dir / response_schema_name)
        system_eval_path = str(
            structured_output_dir / "system_eval.json"
        )

        self.TASK_NAMES = {
            "response": system_response_path,
            "coverage-contradiction": system_eval_path,
            "response-long": system_response_path,
            "response-pure": system_response_path,
            "response-o1": system_response_path,
        }

        self._init_template()

    def _get_template_folder(self, task: str, dataset: str) -> str:
        """Select an opt-in versioned Tax response prompt without changing defaults."""
        if (
            self.prompt_version == "v2"
            and dataset == "tax"
            and task.startswith("response")
        ):
            return "response-tax-v2"

        if (
            self.prompt_version == "v3"
            and self.citation_constraint_mode == "enum"
            and dataset == "tax"
            and task == "response"
        ):
            return "response-tax-v3-citation-id-enum"

        if (
            self.prompt_version == "v3"
            and self.citation_mode == "provision_id"
            and dataset == "tax"
            and task == "response"
        ):
            return "response-tax-v3-citation-id"

        if (
            self.prompt_version == "v3"
            and dataset == "tax"
            and task == "response"
        ):
            return "response-tax-v3"

        return f"{task}-{dataset}"
        
    def _init_template(self) -> None:
        '''
        Initialise all required templates necessary for all model and all task
        '''
        response_structure = dict()
        turn_prompts = dict()
        number_pattern = re.compile(r'\d+')
        
        for task in self.TASK_NAMES:
            #Read structure
            if os.path.exists(self.TASK_NAMES[task]):
                with open(self.TASK_NAMES[task], "r") as f:
                    json_schema = json.load(f)
                    pydantic_schema = PromptManager.parse_schema_to_pydantic(
                        json_schema["input_schema"],
                        task.replace("-", "").capitalize(),
                        extra_forbid=self.citation_mode == "provision_id",
                    )
                    typing_schema = PromptManager.parse_schema_to_typed_dict(json_schema["input_schema"], task.replace("-", "").capitalize())
                    response_structure[task] = (json_schema, pydantic_schema, typing_schema)
                
            
            for dataset in self.DATASET_NAMES:      
                folder_name = self._get_template_folder(task, dataset)
                template_folder = os.path.join(self.template_dir, folder_name)

                turn_prompts[f"{task}-{dataset}"] = [f"{folder_name}/{file}"for file in os.listdir(template_folder)if file.endswith(".md")]
                turn_prompts[f"{task}-{dataset}"] = sorted(turn_prompts[f"{task}-{dataset}"], key = lambda x: int(re.search(number_pattern, x).group()))
                
        self.response_structure = response_structure
        self.turn_files = turn_prompts
            
        
    @staticmethod
    def parse_schema_to_pydantic(schema: Dict[str, Any], model_name: str, extra_forbid: bool = False):
        """Converts JSON schema to Pydantic model."""
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        fields = {}
        # Use $defs instead of definitions
        definitions = schema.get("$defs", {})

        # Process each property in the schema
        for prop_name, prop_info in properties.items():
            field_type = prop_info.get("type")

            # Handle string fields
            if field_type == "string":
                fields[prop_name] = (str, ...)

            # Handle integer fields
            elif field_type == "integer":
                fields[prop_name] = (int, ...)

            # Handle boolean fields
            elif field_type == "boolean":
                fields[prop_name] = (bool, ...)

            # Handle array (list) fields
            elif field_type == "array":
                items = prop_info.get("items")
                if "$ref" in items:
                    ref = items["$ref"].split("/")[-1]  # Get the model name from $ref
                    ref_model = PromptManager.parse_schema_to_pydantic(definitions[ref], ref, extra_forbid=extra_forbid)
                    fields[prop_name] = (List[ref_model], ...)
                else:
                    # Handle simple item types if needed
                    item_type = items.get("type")
                    if item_type == "string":
                        fields[prop_name] = (List[str], ...)
                    elif item_type == "integer":
                        fields[prop_name] = (List[int], ...)

            # Handle nested objects via references
            elif "$ref" in prop_info:
                ref = prop_info["$ref"].split("/")[-1]
                ref_model = PromptManager.parse_schema_to_pydantic(definitions[ref], ref, extra_forbid=extra_forbid)
                fields[prop_name] = (ref_model, ...)

        # Include required fields
        for req in required:
            if req in fields:
                fields[req] = (fields[req][0], ...)

        # Dynamically create the Pydantic model
        if extra_forbid:
            return create_model(model_name, __config__=ConfigDict(extra="forbid"), **fields)
        return create_model(model_name, **fields)

    @staticmethod
    def build_citation_id_enum_structure(allowed_ids: List[str]):
        """Build a per-request response model whose citation IDs are context-only."""
        if len(allowed_ids) != len(set(allowed_ids)):
            raise ValueError("Allowed provision IDs must be unique.")
        if allowed_ids:
            citation_id_type = Literal.__getitem__(tuple(allowed_ids))
            citation_ids_field = (List[citation_id_type], ...)
        else:
            # With no supplied context, only [] can satisfy the citation field.
            citation_ids_field = (List[str], Field(default_factory=list, max_length=0))
        return create_model(
            "ResponseCitationIdEnum",
            __config__=ConfigDict(extra="forbid"),
            analysis=(str, ...),
            answer=(str, ...),
            citation_ids=citation_ids_field,
        )
    
    @staticmethod
    def parse_schema_to_typed_dict(schema: Dict[str, Any], model_name: str) -> TypedDict:
        """Converts JSON schema to TypedDict."""
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        fields = {}
        definitions = schema.get("$defs", {})

        # Process each property in the schema
        for prop_name, prop_info in properties.items():
            field_type = prop_info.get("type")
            is_required = prop_name in required
            
            # Handle string fields
            if field_type == "string":
                fields[prop_name] = str

            # Handle integer fields
            elif field_type == "integer":
                fields[prop_name] = int
            
            # Handle boolean fields
            elif field_type == "boolean":
                fields[prop_name] = bool

            # Handle array fields
            elif field_type == "array":
                items = prop_info.get("items")
                if "$ref" in items:
                    ref = items["$ref"].split("/")[-1]  # Get the model name from $ref
                    fields[prop_name] = List[PromptManager.parse_schema_to_typed_dict(definitions[ref], ref)]
                else:
                    item_type = items.get("type", "string")
                    if item_type == "string":
                        fields[prop_name] = List[str]
                    elif item_type == "integer":
                        fields[prop_name] = List[int]
                    # Add more types as necessary

            # Handle nested objects via references
            elif "$ref" in prop_info:
                ref = prop_info["$ref"].split("/")[-1]
                fields[prop_name] = PromptManager.parse_schema_to_typed_dict(definitions[ref], ref)

        # Create the TypedDict dynamically
        TypedDictModel = TypedDict(model_name, {k: (v, NotRequired) if not is_required else v for k, v in fields.items()})
        
        return TypedDictModel
    
    

    def get_prompt_rendered(self, task: str, dataset: str, query: str):
        
        assert task in self.TASK_NAMES, "{} not found in TASK_NAMES".format(task)
        assert dataset in self.DATASET_NAMES, "{} not found in DATASET_NAMES".format(dataset)
        
        extra_task = task.split("-")[1] if len(task.split("-")) > 1 else ""
        
        system_path = ""
        if extra_task in ["long", "pure"]:
            system_path = f"system_prompt_{dataset}_{extra_task}.md"
        elif extra_task != "o1":
            if self.prompt_version == "v3" and self.citation_constraint_mode == "enum" and dataset == "tax":
                system_path = f"system_prompt_{dataset}_v3_citation_id_enum.md"
            elif self.prompt_version == "v3" and self.citation_mode == "provision_id" and dataset == "tax":
                system_path = f"system_prompt_{dataset}_v3_citation_id.md"
            else:
                system_path = f"system_prompt_{dataset}_v3.md" if self.prompt_version == "v3" and dataset == "tax" else f"system_prompt_{dataset}.md"
        
        if system_path == "":
            data = {"turn_files": self.turn_files[f"{task}-{dataset}"],
                "query": query}
            
            return self.o1_template.render(data)
        else:
            data = {"system_prompt": system_path,
                "turn_files": self.turn_files[f"{task}-{dataset}"],
                "query": query}
            

            return self.template.render(data)

    def get_prompt(self, prompt_str):
        prompts = []
        for line in prompt_str.split("\n"):
            if re.search(r"^<system>", line.strip()):
                prompts.append({"role": "system", "content": [line.replace("<system>", "").strip()]})
            elif re.search(r"^<user>", line.strip()):
                prompts.append({"role": "user", "content": [line.replace("<user>", "").strip()]})
            elif re.search(r"^<assistant>", line.strip()):
                prompts.append({"role": "assistant", "content": [line.replace("<assistant>", "").strip()]})
            else:
                prompts[-1]["content"].append(line)

        for prompt in prompts:
            prompt["content"] = "\n".join(prompt["content"]).strip()

        return prompts

    def format_gemini_prompt(self, prompts: List[Dict[str, str]], task: str) -> Tuple[str, List[Dict[str, str]]]:
        pattern = r'```json(.*?)```'

        #Normally, the first thing in the list is system prompt
        #Next two are considered instruction prompt and should be put in the message as is
        #The last one is the actual query
        new_prompts = prompts[1:]
        system_prompt = prompts[0]["content"]

        for prompt in new_prompts:
            if prompt["role"] == "assistant":
                prompt["role"] = "model"

            prompt["parts"] = [{"text": prompt["content"]}]
            del prompt["content"]


        return {"system": system_prompt, "messages": new_prompts}
    
    def format_claude_prompt(self, prompts: List[Dict[str, str]], task: str) -> Tuple[str, List[Dict[str, str]]]:
        pattern = r'```json(.*?)```'

        #Normally, the first thing in the list is system prompt
        #Next two are considered instruction prompt and should be put in the message as is
        #The last one is the actual query
        new_prompts = prompts[1:3]
        system_prompt = [{"type": "text", "text": prompts[0]["content"], "cache_control": {"type": "ephemeral"}}]
        counter = 0

        for i, prompt in enumerate(prompts[3:len(prompts)-1]):

            if prompt["role"] == "assistant":
                tmp = prompt["content"]
                match = re.search(pattern, tmp, re.DOTALL)
                #Prepare tool use 
                if match:
                    tool_input = eval(match.group(1).strip())
                else:
                    #If not match, append as is
                    new_prompts.append([{"role": prompt["role"], "content": [{"type": "text", "text": prompt["content"]}]}])
                    continue

                tool_id = "toolu_{:04d}".format(counter)
                content = [{"type": "tool_use", "id": tool_id, "name": task, "input": tool_input}]
                prompt["content"] = content

                new_prompts.append(prompt)
                new_prompts.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": "success"}]})
                new_prompts.append({"role": "assistant", "content": [{"type": "text", "text": "Great Success"}]})
                counter += 1

            else:
                new_prompts.append({"role": prompt["role"], "content": [{"type": "text", "text": prompt["content"]}]})
                

        #The last one should be cached
        new_prompts[-1]["content"][0]["cache_control"] = {"type": "ephemeral"}

        new_prompts.append(prompts[-1])


        return {"system": system_prompt, "messages": new_prompts}
    
    def format_gpt_prompt(self, prompts: List[Dict[str, str]], task: str) -> Tuple[str, List[Dict[str, str]]]:
        #For gpt, no need to do anything
        return {"messages": prompts}

    #Then, need to have a set of functions to format the prompt for each model
    #Get everything and return prompt ready for parsing
    def get_formatted_prompt(self, query: str, task: str, model: str, dataset: str):
       
        assert task in self.TASK_NAMES, "{} not found in TASK_NAMES".format(task)
        assert dataset in self.DATASET_NAMES, "{} not found in DATASET_NAMES".format(dataset)
        
        prompt_str = self.get_prompt_rendered(task=task, dataset=dataset, query=query).strip()

        prompts = self.get_prompt(prompt_str=prompt_str)
        
        type_name = model.split("-")[0].lower()

        if type_name in [
            "qwen",
            "o1",
            "aisingapore/gemma2",
            "typhoon",
        ]:
            type_name = "gpt"

        return getattr(self,f"format_{type_name}_prompt",)(prompts, task=task)
            

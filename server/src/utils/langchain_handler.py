import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler
from datetime import datetime

class VerboseFileCallbackHandler(BaseCallbackHandler):
    def __init__(self, graph_name: str):
        chats_dir = "/output/chats"
        os.makedirs(chats_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.logfile_path = f"{chats_dir}/{graph_name}-{timestamp}.log"
        self.graph_name = graph_name
        #self.chain_depth = 0  # Track nested chains

    def _write_log(self, message: str):
        with open(self.logfile_path, "a", encoding="utf-8") as f:
            f.write(message + "\n")

    def on_chain_start(
        self, 
        serialized: Optional[Dict[str, Any]], 
        inputs: Dict[str, Any], 
        **kwargs: Any
    ) -> None:
        # Just log the inputs in a clean format
        if inputs:
            # Extract the most relevant input for logging
            if isinstance(inputs, dict):
                # Look for common input keys
                for key in ["input", "query", "question", "text", "prompt"]:
                    if key in inputs and isinstance(inputs[key], str):
                        self._write_log(f"[Input] {inputs[key]}")
                        return
                
                # If we get here, no common keys were found, log a simplified representation
                simplified = {k: v for k, v in inputs.items() 
                              if isinstance(v, (str, int, float, bool)) and len(str(v)) < 500}
                if simplified:
                    self._write_log(f"[Input] {simplified}")

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        # Extract only the text content from outputs
        if outputs:
            # For string outputs
            if isinstance(outputs, str):
                self._write_log(f"[Output] {outputs}")
                return
                
            # For dict outputs, extract the most relevant text
            if isinstance(outputs, dict):
                # Check for common output keys
                for key in ["output", "result", "text", "response", "content"]:
                    if key in outputs and isinstance(outputs[key], str):
                        self._write_log(f"[Output] {outputs[key]}")
                        return
                
                # Try message content for chat models
                if "message" in outputs and hasattr(outputs["message"], "content"):
                    self._write_log(f"[Output] {outputs['message'].content}")
                    return
                
                # If no obvious text content, show a simplified representation
                simplified = {k: v for k, v in outputs.items() 
                             if isinstance(v, (str, int, float, bool)) and len(str(v)) < 500}
                if simplified:
                    self._write_log(f"[Output] {simplified}")

    def on_llm_start(self, serialized: Optional[Dict[str, Any]], prompts: List[str], **kwargs: Any) -> None:
        if prompts and len(prompts) > 0:
            self._write_log(f"[User] {prompts[0]}")

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        import json
        response_text = ""
        tool_json_logged = False
        # Handle different response formats
        if hasattr(response, "generations"):
            for gen in response.generations:
                if gen and len(gen) > 0:
                    # Check for tool_calls in message
                    if hasattr(gen[0], "message") and hasattr(gen[0].message, "tool_calls"):
                        tool_calls = gen[0].message.tool_calls
                        if tool_calls and isinstance(tool_calls, list):
                            for tool_call in tool_calls:
                                if "args" in tool_call:
                                    try:
                                        tool_args = tool_call["args"]
                                        tool_json = json.dumps(tool_args, ensure_ascii=False)
                                        self._write_log(f"[AI TOOL] {tool_json}")
                                        tool_json_logged = True
                                    except Exception as e:
                                        self._write_log(f"[AI TOOL] (error extracting tool_call args: {e})")
                    # Standard text or message content
                    if hasattr(gen[0], "text") and gen[0].text:
                        response_text = gen[0].text
                        break
                    elif hasattr(gen[0], "message") and hasattr(gen[0].message, "content") and gen[0].message.content:
                        response_text = gen[0].message.content
                        break
        # If we couldn't extract the text with the above methods, try a more generic approach
        if not response_text and hasattr(response, "content"):
            response_text = response.content
        # Last resort - convert to string
        if not response_text:
            try:
                response_text = str(response)
            except:
                response_text = "Unable to extract response text"
        if response_text:
            self._write_log(f"[AI] {response_text}")
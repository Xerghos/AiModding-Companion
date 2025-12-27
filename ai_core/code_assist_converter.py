"""
Convertisseur entre les formats Gemini API et CodeAssist.
Base sur packages/core/src/code_assist/converter.ts de gemini-cli.

CORRECTION: Aligne sur le vrai code gemini-cli-core/converter.js:
- contents: contient les messages user/assistant (pas vide!)
- systemInstruction: UNIQUEMENT l instruction systeme
- generationConfig: seulement temperature par defaut (pas maxOutputTokens)
"""

from typing import Dict, List, Any, Optional, Union
import uuid


def to_generate_content_request(
    model: str,
    messages: List[Dict[str, str]],
    user_prompt_id: Optional[str] = None,
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    tools: Optional[List[Dict]] = None,
    system_instruction: Optional[str] = None,
    safety_settings: Optional[List[Dict]] = None,
    labels: Optional[Dict[str, str]] = None,
    cached_content: Optional[Dict] = None,
    **kwargs
) -> Dict[str, Any]:
    if user_prompt_id is None:
        user_prompt_id = str(uuid.uuid4())
    
    # 1. CONTENTS: Messages user/assistant (NON VIDE!)
    contents = _to_contents(messages)
    
    # 2. SYSTEM INSTRUCTION
    system_parts = []
    if system_instruction:
        system_parts.append(system_instruction)
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system" and content:
            system_parts.append(str(content))
    
    vertex_request: Dict[str, Any] = {"contents": contents}
    
    if system_parts:
        full_system_instruction = "\n\n".join(system_parts)
        vertex_request["systemInstruction"] = {
            "role": "user",
            "parts": [{"text": full_system_instruction}]
        }
    
    generation_config: Dict[str, Any] = {"temperature": temperature}
    if max_tokens is not None and max_tokens > 0:
        generation_config["maxOutputTokens"] = min(max_tokens, 8192)
    
    if generation_config:
        vertex_request["generationConfig"] = generation_config
    
    if cached_content:
        vertex_request["cachedContent"] = cached_content
    
    if tools and len(tools) > 0:
        vertex_request["tools"] = _convert_tools_to_gemini_format(tools)
        if "toolConfig" not in vertex_request:
            function_calling_mode = kwargs.get("function_calling_mode", "AUTO")
            vertex_request["toolConfig"] = {"functionCallingConfig": {"mode": function_calling_mode}}
    
    if safety_settings:
        vertex_request["safetySettings"] = safety_settings
    if labels:
        vertex_request["labels"] = labels
    
    vertex_request["session_id"] = session_id if session_id else ""
    
    ca_request: Dict[str, Any] = {"model": model, "request": vertex_request}
    if project_id:
        ca_request["project"] = project_id
    if user_prompt_id:
        ca_request["user_prompt_id"] = user_prompt_id
    
    return ca_request


def from_generate_content_response(response: Dict[str, Any]) -> Dict[str, Any]:
    inner_response = response.get("response", {})
    trace_id = response.get("traceId")
    gemini_response: Dict[str, Any] = {"candidates": inner_response.get("candidates", [])}
    if "promptFeedback" in inner_response:
        gemini_response["promptFeedback"] = inner_response["promptFeedback"]
    if "usageMetadata" in inner_response:
        gemini_response["usageMetadata"] = inner_response["usageMetadata"]
    if "modelVersion" in inner_response:
        gemini_response["modelVersion"] = inner_response["modelVersion"]
    if "automaticFunctionCallingHistory" in inner_response:
        gemini_response["automaticFunctionCallingHistory"] = inner_response["automaticFunctionCallingHistory"]
    if trace_id:
        gemini_response["responseId"] = trace_id
    return gemini_response


def _to_contents(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            continue
        if role == "assistant":
            ca_role = "model"
        else:
            ca_role = "user"
        parts = _content_to_parts(content)
        if parts:
            contents.append({"role": ca_role, "parts": parts})
    return contents


def _content_to_parts(content: Any) -> List[Dict[str, Any]]:
    parts = []
    if isinstance(content, str):
        if content.strip():
            parts.append({"text": content})
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                has_content = False
                if "text" in part and part["text"] and str(part["text"]).strip():
                    has_content = True
                elif any(key in part for key in ["functionCall", "functionResponse", "inlineData", "fileData"]):
                    has_content = True
                if has_content:
                    parts.append(part)
            elif part:
                parts.append({"text": str(part)})
    elif content:
        content_str = str(content)
        if content_str.strip():
            parts.append({"text": content_str})
    return parts


def _convert_tools_to_gemini_format(tools: List[Dict]) -> List[Dict[str, Any]]:
    if not tools:
        return []
    function_declarations = []
    for tool in tools:
        if isinstance(tool, dict):
            if "type" in tool and tool.get("type") == "function" and "function" in tool:
                func_def = tool["function"]
                function_declarations.append({"name": func_def.get("name", ""), "description": func_def.get("description", ""), "parameters": func_def.get("parameters", {})})
            elif "functionDeclarations" in tool:
                function_declarations.extend(tool["functionDeclarations"])
            elif "name" in tool and "parameters" in tool:
                function_declarations.append({"name": tool.get("name", ""), "description": tool.get("description", ""), "parameters": tool.get("parameters", {})})
    if function_declarations:
        return [{"functionDeclarations": function_declarations}]
    return []

"""
Convertisseur entre les formats Gemini API et CodeAssist.
Base sur packages/core/src/code_assist/converter.ts de gemini-cli.

CORRECTION FINALE: Aligné sur le payload gemini-cli qui FONCTIONNE:
- contents: VIDE [] (gemini-cli met tout dans systemInstruction)
- systemInstruction: contient TOUT (contexte + messages user/assistant)
- PAS de generationConfig
- PAS de toolConfig
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
    """
    Convertit les messages au format CodeAssist.
    
    IMPORTANT: Aligné sur le payload gemini-cli qui fonctionne:
    - contents: [] (VIDE)
    - systemInstruction contient TOUT le contexte + messages
    - Pas de generationConfig
    - Pas de toolConfig
    """
    if user_prompt_id is None:
        user_prompt_id = str(uuid.uuid4())
    
    # 1. CONTENTS: VIDE (gemini-cli fait ainsi)
    contents: List[Dict[str, Any]] = []
    
    # 2. SYSTEM INSTRUCTION: contient TOUT (contexte + messages user/assistant)
    all_text_parts = []
    
    # Ajouter l'instruction système si fournie
    if system_instruction:
        all_text_parts.append(system_instruction)
    
    # Ajouter les messages système des messages
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system" and content:
            all_text_parts.append(str(content))
    
    # Ajouter les messages user/assistant à la fin (comme gemini-cli le fait)
    # gemini-cli ajoute les messages de l'historique dans systemInstruction
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            continue  # Déjà traité
        if content:
            # Format: ajouter le message avec préfixe pour indiquer le rôle
            if role == "user":
                all_text_parts.append(f"\nUser:\n{content}")
            elif role in ("assistant", "model"):
                all_text_parts.append(f"\nAssistant:\n{content}")
    
    # Construire le payload request
    vertex_request: Dict[str, Any] = {"contents": contents}  # VIDE!
    
    if all_text_parts:
        full_system_instruction = "\n\n".join(all_text_parts)
        vertex_request["systemInstruction"] = {
            "role": "system",
            "parts": [{"text": full_system_instruction}]
        }
    
    # 3. PAS de generationConfig (gemini-cli ne l'inclut pas)
    # 4. PAS de toolConfig (gemini-cli ne l'inclut pas)
    
    # Outils (sans toolConfig)
    if tools and len(tools) > 0:
        vertex_request["tools"] = _convert_tools_to_gemini_format(tools)
        # NE PAS ajouter toolConfig - gemini-cli ne le fait pas
    
    # Optionnels (garder pour compatibilité mais généralement non utilisés par gemini-cli)
    if safety_settings:
        vertex_request["safetySettings"] = safety_settings
    if labels:
        vertex_request["labels"] = labels
    if cached_content:
        vertex_request["cachedContent"] = cached_content
    
    # Construire la requête CodeAssist finale
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
    """
    DEPRECATED: Cette fonction n'est plus utilisée car contents doit être vide.
    Gardée pour compatibilité.
    """
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

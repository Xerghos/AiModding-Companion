"""
Convertisseur entre les formats Gemini API et CodeAssist.
Basé sur packages/core/src/code_assist/converter.ts de gemini-cli.
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
    **kwargs
) -> Dict[str, Any]:
    """
    Convertit les paramètres Gemini API vers le format CodeAssist.
    
    Args:
        model: Nom du modèle (ex: "gemini-3-flash-preview")
        messages: Liste de messages au format OpenAI (role, content)
        user_prompt_id: ID unique pour le prompt utilisateur
        project_id: ID du projet Google Cloud (optionnel)
        session_id: ID de session pour maintenir le contexte
        temperature: Température
        max_tokens: Nombre max de tokens
        tools: Outils (tool calling)
        system_instruction: Instruction système
        **kwargs: Paramètres additionnels
        
    Returns:
        Requête au format CodeAssist (CAGenerateContentRequest)
    """
    if user_prompt_id is None:
        user_prompt_id = str(uuid.uuid4())
    
    # Extraire les instructions système des messages
    system_parts = []
    
    # 1. Ajouter l'instruction système explicite si présente
    if system_instruction:
        system_parts.append(system_instruction)
    
    # 2. Extraire les messages avec role='system' de la liste des messages
    for msg in messages:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if content:
                system_parts.append(str(content))
    
    # Convertir les messages au format CodeAssist (en excluant les system qui sont gérés ci-dessus)
    contents = _to_contents(messages)
    
    # Construire la requête Vertex (format interne CodeAssist)
    vertex_request: Dict[str, Any] = {
        "contents": contents,
    }
    
    # Ajouter l'instruction système si présente (concaténée)
    if system_parts:
        full_system_instruction = "\n\n".join(system_parts)
        vertex_request["systemInstruction"] = {
            "role": "system",
            "parts": [{"text": full_system_instruction}]
        }
    
    # Ajouter les outils si présents
    if tools and len(tools) > 0:  # Vérifier que tools n'est pas vide
        vertex_request["tools"] = _convert_tools_to_gemini_format(tools)
        # CRITIQUE: Ajouter toolConfig pour éviter erreur 500 (comme gemini-cli)
        # Le toolConfig est requis quand des outils sont présents
        if "toolConfig" not in vertex_request:
            # Mode par défaut: AUTO (comme gemini-cli)
            function_calling_mode = kwargs.get("function_calling_mode", "AUTO")
            vertex_request["toolConfig"] = {
                "functionCallingConfig": {
                    "mode": function_calling_mode  # AUTO, ANY, ou NONE
                }
            }
    
    # Construire la configuration de génération
    generation_config: Dict[str, Any] = {
        "temperature": temperature,
    }
    
    if max_tokens:
        generation_config["maxOutputTokens"] = max_tokens
    
    # Ajouter d'autres paramètres de génération depuis kwargs
    if "top_p" in kwargs:
        generation_config["topP"] = kwargs["top_p"]
    if "top_k" in kwargs:
        generation_config["topK"] = kwargs["top_k"]
    if "stop_sequences" in kwargs:
        generation_config["stopSequences"] = kwargs["stop_sequences"]
    
    if generation_config:
        vertex_request["generationConfig"] = generation_config
    
    # Ajouter session_id si présent
    if session_id:
        vertex_request["session_id"] = session_id
    
    # Construire la requête CodeAssist complète
    ca_request: Dict[str, Any] = {
        "model": model,
        "request": vertex_request,
    }
    
    if project_id:
        ca_request["project"] = project_id
    
    if user_prompt_id:
        ca_request["user_prompt_id"] = user_prompt_id
    
    return ca_request


def from_generate_content_response(
    response: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convertit la réponse CodeAssist vers le format Gemini API.
    
    Args:
        response: Réponse CodeAssist (CaGenerateContentResponse)
        
    Returns:
        Réponse au format Gemini API (GenerateContentResponse)
    """
    # Extraire la réponse interne
    inner_response = response.get("response", {})
    trace_id = response.get("traceId")
    
    # Construire la réponse Gemini API
    gemini_response: Dict[str, Any] = {
        "candidates": inner_response.get("candidates", []),
    }
    
    # Ajouter les métadonnées si présentes
    if "promptFeedback" in inner_response:
        gemini_response["promptFeedback"] = inner_response["promptFeedback"]
    
    if "usageMetadata" in inner_response:
        gemini_response["usageMetadata"] = inner_response["usageMetadata"]
    
    if "modelVersion" in inner_response:
        gemini_response["modelVersion"] = inner_response["modelVersion"]
    
    if "automaticFunctionCallingHistory" in inner_response:
        gemini_response["automaticFunctionCallingHistory"] = inner_response["automaticFunctionCallingHistory"]
    
    # Ajouter le traceId comme responseId
    if trace_id:
        gemini_response["responseId"] = trace_id
    
    return gemini_response


def _to_contents(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Convertit les messages OpenAI vers le format CodeAssist Contents.
    
    Args:
        messages: Liste de messages au format OpenAI (role, content)
        
    Returns:
        Liste de Contents au format CodeAssist
    """
    contents = []
    
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        # Mapper les rôles
        if role == "system":
            # Les messages système sont gérés séparément dans CodeAssist
            continue
        elif role == "assistant":
            ca_role = "model"
        else:
            ca_role = "user"
        
        # Convertir le contenu en parts
        parts = []
        if isinstance(content, str):
            # Filtrer les contenus vides
            if content.strip():  # Ne pas ajouter si vide ou seulement des espaces
                parts.append({"text": content})
        elif isinstance(content, list):
            # Contenu multimodal - filtrer les parts vides
            for part in content:
                if isinstance(part, dict):
                    # Vérifier si le part a un contenu non vide
                    has_content = False
                    if "text" in part and part["text"] and part["text"].strip():
                        has_content = True
                    elif any(key in part for key in ["functionCall", "functionResponse", "inlineData", "fileData"]):
                        has_content = True
                    
                    if has_content:
                        parts.append(part)
                elif part:  # Si c'est une string non vide
                    parts.append({"text": str(part)})
        else:
            content_str = str(content)
            if content_str.strip():  # Ne pas ajouter si vide
                parts.append({"text": content_str})
        
        # Ne pas ajouter de content si tous les parts sont vides
        if parts:
            contents.append({
                "role": ca_role,
                "parts": parts
            })
    
    return contents


def _convert_tools_to_gemini_format(tools: List[Dict]) -> List[Dict[str, Any]]:
    """
    Convertit les outils du format OpenAI vers le format Gemini.
    
    Format OpenAI (entrée):
    [
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": {...}
            }
        }
    ]
    
    Format Gemini (sortie):
    [
        {
            "functionDeclarations": [
                {
                    "name": "...",
                    "description": "...",
                    "parameters": {...}
                }
            ]
        }
    ]
    """
    if not tools:
        return []
    
    function_declarations = []
    
    for tool in tools:
        if isinstance(tool, dict):
            # Format OpenAI: {"type": "function", "function": {...}}
            if "type" in tool and tool.get("type") == "function" and "function" in tool:
                func_def = tool["function"]
                function_declarations.append({
                    "name": func_def.get("name", ""),
                    "description": func_def.get("description", ""),
                    "parameters": func_def.get("parameters", {})
                })
            # Format déjà Gemini: {"functionDeclarations": [...]}
            elif "functionDeclarations" in tool:
                # Si c'est déjà au format Gemini, on extrait les déclarations
                function_declarations.extend(tool["functionDeclarations"])
            # Format plat direct (format Gemini natif): {"name": "...", "description": "...", "parameters": {...}}
            elif "name" in tool and "parameters" in tool:
                function_declarations.append({
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                })
    
    # Retourner au format Gemini: [{"functionDeclarations": [...]}]
    if function_declarations:
        return [{"functionDeclarations": function_declarations}]
    return []


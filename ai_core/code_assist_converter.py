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
    safety_settings: Optional[List[Dict]] = None,
    labels: Optional[Dict[str, str]] = None,
    cached_content: Optional[Dict] = None,
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
    
    # MODE GEMINI-CLI: Tout mettre dans systemInstruction, contents reste vide
    # Cela correspond à la structure exacte observée dans les logs de gemini-cli
    # qui fonctionne avec CodeAssist
    
    # Construction du systemInstruction complet (comme gemini-cli)
    system_parts = []

    # 1. Ajouter l'instruction système explicite si présente
    if system_instruction:
        system_parts.append(system_instruction)

    # 2. Concaténer TOUS les messages (system + user + assistant) dans systemInstruction
    # C'est la structure utilisée par gemini-cli qui fonctionne avec CodeAssist
    for msg in messages:
        content = msg.get("content", "")
        if content:
            role = msg.get("role", "user")
            # Formater avec le rôle pour contexte
            if role == "user":
                system_parts.append(f"User: {content}")
            elif role == "assistant" or role == "model":
                system_parts.append(f"Assistant: {content}")
            elif role == "system":
                # Les messages system sont ajoutés directement sans préfixe
                system_parts.append(str(content))

    # 3. Laisser contents vide (comme gemini-cli)
    contents = []
    
    # Construire la requête Vertex (format interne CodeAssist - aligné sur gemini-cli)
    vertex_request: Dict[str, Any] = {
        "contents": contents,
    }
    
    # Ajouter l'instruction système si présente (tout le contexte concaténé)
    if system_parts:
        full_system_instruction = "\n\n".join(system_parts)
        vertex_request["systemInstruction"] = {
            "role": "system",
            "parts": [{"text": full_system_instruction}]
        }

    # Construire la configuration de génération (alignée sur gemini-cli converter.js)
    generation_config: Dict[str, Any] = {
        "temperature": temperature,
    }

    if max_tokens:
        generation_config["maxOutputTokens"] = max_tokens

    # Ajouter tous les paramètres de génération depuis kwargs (aligné sur Vertex AI)
    # Paramètres de base
    if "top_p" in kwargs and kwargs["top_p"] is not None:
        generation_config["topP"] = kwargs["top_p"]
    if "top_k" in kwargs and kwargs["top_k"] is not None:
        generation_config["topK"] = kwargs["top_k"]
    if "stop_sequences" in kwargs and kwargs["stop_sequences"] is not None:
        generation_config["stopSequences"] = kwargs["stop_sequences"]

    # Paramètres avancés (alignés sur gemini-cli)
    if "candidate_count" in kwargs and kwargs["candidate_count"] is not None:
        generation_config["candidateCount"] = kwargs["candidate_count"]
    if "response_logprobs" in kwargs and kwargs["response_logprobs"] is not None:
        generation_config["responseLogprobs"] = kwargs["response_logprobs"]
    if "logprobs" in kwargs and kwargs["logprobs"] is not None:
        generation_config["logprobs"] = kwargs["logprobs"]
    if "presence_penalty" in kwargs and kwargs["presence_penalty"] is not None:
        generation_config["presencePenalty"] = kwargs["presence_penalty"]
    if "frequency_penalty" in kwargs and kwargs["frequency_penalty"] is not None:
        generation_config["frequencyPenalty"] = kwargs["frequency_penalty"]
    if "seed" in kwargs and kwargs["seed"] is not None:
        generation_config["seed"] = kwargs["seed"]

    # Paramètres de réponse structurée
    if "response_mime_type" in kwargs and kwargs["response_mime_type"] is not None:
        generation_config["responseMimeType"] = kwargs["response_mime_type"]
    if "response_schema" in kwargs and kwargs["response_schema"] is not None:
        generation_config["responseSchema"] = kwargs["response_schema"]
    if "response_json_schema" in kwargs and kwargs["response_json_schema"] is not None:
        generation_config["responseJsonSchema"] = kwargs["response_json_schema"]

    # Paramètres avancés de modèle
    if "thinking_config" in kwargs and kwargs["thinking_config"] is not None:
        generation_config["thinkingConfig"] = kwargs["thinking_config"]
    if "routing_config" in kwargs and kwargs["routing_config"] is not None:
        generation_config["routingConfig"] = kwargs["routing_config"]
    if "model_selection_config" in kwargs and kwargs["model_selection_config"] is not None:
        generation_config["modelSelectionConfig"] = kwargs["model_selection_config"]

    # Paramètres multimédias et audio
    if "response_modalities" in kwargs and kwargs["response_modalities"] is not None:
        generation_config["responseModalities"] = kwargs["response_modalities"]
    if "media_resolution" in kwargs and kwargs["media_resolution"] is not None:
        generation_config["mediaResolution"] = kwargs["media_resolution"]
    if "speech_config" in kwargs and kwargs["speech_config"] is not None:
        generation_config["speechConfig"] = kwargs["speech_config"]
    if "audio_timestamp" in kwargs and kwargs["audio_timestamp"] is not None:
        generation_config["audioTimestamp"] = kwargs["audio_timestamp"]
    
    if generation_config:
        vertex_request["generationConfig"] = generation_config

    # Ajouter les champs supplémentaires (alignés sur gemini-cli converter.js)
    if cached_content:
        vertex_request["cachedContent"] = cached_content

    if tools and len(tools) > 0:
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

    if safety_settings:
        vertex_request["safetySettings"] = safety_settings

    if labels:
        vertex_request["labels"] = labels

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


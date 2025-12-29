"""
Convertisseur entre les formats Gemini API et CodeAssist.
Base sur packages/core/src/code_assist/converter.ts de gemini-cli.

CORRECTION FINALE: Aligné sur le payload gemini-cli capturé qui FONCTIONNE:
- contents: REMPLI avec les messages user/assistant (format {"role": "user", "parts": [{"text": "..."}]})
- systemInstruction: contient le contexte système avec role: "user" (pas "system")
- user_prompt_id: AVANT request (model → project → user_prompt_id → request)
- parametersJsonSchema: utilise "parametersJsonSchema" (pas "parameters") avec types en minuscules
- toolConfig: ABSENT (pas nécessaire selon le payload capturé)

BLINDAGE ERREUR 500:
- Sanitizer de schéma: types en minuscules pour parametersJsonSchema, suppression champs interdits
- Détection arrays d'objets imbriqués (bug connu Google)
"""

from typing import Dict, List, Any, Optional, Union
from collections import OrderedDict
import uuid


# =============================================================================
# SANITIZER DE SCHEMA POUR CODEASSIST (BLINDAGE ERREUR 500)
# =============================================================================

# Champs JSON qui font crasher le parseur Protobuf de l'API v1internal
FORBIDDEN_SCHEMA_FIELDS = {"title", "default", "examples", "additionalProperties", "$schema", "$id", "$ref"}


def _build_ordered_schema(schema: Dict[str, Any], use_uppercase: bool = False) -> OrderedDict:
    """
    Construit un schéma avec l'ordre exact : properties → required → type
    (comme dans le payload gemini-cli fonctionnel)
    
    Args:
        schema: Le schéma JSON à ordonner
        use_uppercase: Si True, convertit les types en MAJUSCULES (pour "parameters"), sinon garde minuscules (pour "parametersJsonSchema")
    
    Returns:
        OrderedDict avec l'ordre : properties → required → type
    """
    result = OrderedDict()
    
    # 1. properties EN PREMIER
    if "properties" in schema:
        result["properties"] = sanitize_schema_for_codeassist(schema["properties"], use_uppercase=use_uppercase)
    
    # 2. required EN DEUXIÈME
    if "required" in schema:
        result["required"] = schema["required"]
    
    # 3. type EN DERNIER
    if "type" in schema:
        type_val = schema["type"]
        if isinstance(type_val, str):
            result["type"] = type_val.upper() if use_uppercase else type_val.lower()
        elif isinstance(type_val, list):
            # Type union (ex: ["string", "null"]) - prendre le premier non-null
            non_null_types = [t for t in type_val if t != "null"]
            if non_null_types:
                result["type"] = non_null_types[0].upper() if use_uppercase else non_null_types[0].lower()
            else:
                result["type"] = "STRING" if use_uppercase else "string"  # Fallback
        else:
            result["type"] = type_val
    
    # Autres champs (items, enum, etc.) - les ajouter après type
    for key, value in schema.items():
        if key not in ("properties", "required", "type"):
            # Supprimer les champs interdits
            if key in FORBIDDEN_SCHEMA_FIELDS:
                continue
            # Traitement récursif pour les autres dicts
            if isinstance(value, dict):
                result[key] = sanitize_schema_for_codeassist(value, use_uppercase=use_uppercase)
            elif isinstance(value, list):
                result[key] = [sanitize_schema_for_codeassist(item, use_uppercase=use_uppercase) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
    
    return result


def sanitize_schema_for_codeassist(schema: Any, _depth: int = 0, use_uppercase: bool = False) -> Any:
    """
    Sanitize récursivement un schéma JSON pour le rendre compatible avec l'API v1internal.
    
    Actions:
    1. Convertir les types en MAJUSCULES si use_uppercase=True (pour "parameters"), sinon garder minuscules (pour "parametersJsonSchema")
    2. Supprimer les champs interdits (title, default, examples, additionalProperties, etc.)
    3. Détecter et logger les arrays d'objets imbriqués (bug connu Google - peut causer erreur 500)
    
    Args:
        schema: Le schéma JSON à sanitizer (dict, list, ou valeur primitive)
        _depth: Profondeur de récursion (pour logging debug)
        use_uppercase: Si True, convertit les types en MAJUSCULES (pour "parameters"), sinon garde minuscules (pour "parametersJsonSchema")
    
    Returns:
        Le schéma sanitizé compatible avec l'API CodeAssist v1internal
    """
    # Protection contre récursion infinie
    if _depth > 50:
        return schema
    
    # Cas de base: pas un dict
    if not isinstance(schema, dict):
        if isinstance(schema, list):
            return [sanitize_schema_for_codeassist(item, _depth + 1, use_uppercase) for item in schema]
        return schema
    
    result = {}
    
    for key, value in schema.items():
        # 1. Supprimer les champs interdits
        if key in FORBIDDEN_SCHEMA_FIELDS:
            continue
        
        # 2. Convertir "const" en "enum" à une valeur (const non supporté par Protobuf)
        if key == "const":
            result["enum"] = [value]
            continue
        
        # 3. Convertir les types selon use_uppercase
        if key == "type":
            if isinstance(value, str):
                # Pour parametersJsonSchema, garder minuscules (comme dans le payload capturé)
                # Pour parameters (legacy), convertir en majuscules
                result[key] = value.upper() if use_uppercase else value.lower()
            elif isinstance(value, list):
                # Type union (ex: ["string", "null"]) - prendre le premier non-null
                non_null_types = [t for t in value if t != "null"]
                if non_null_types:
                    result[key] = non_null_types[0].upper() if use_uppercase else non_null_types[0].lower()
                else:
                    result[key] = "STRING" if use_uppercase else "string"  # Fallback
            else:
                result[key] = value
            continue
        
        # 4. Traitement récursif des propriétés
        if key == "properties" and isinstance(value, dict):
            result[key] = {k: sanitize_schema_for_codeassist(v, _depth + 1, use_uppercase) for k, v in value.items()}
            continue
        
        # 5. Traitement récursif des items (pour les arrays)
        if key == "items" and isinstance(value, dict):
            sanitized_items = sanitize_schema_for_codeassist(value, _depth + 1, use_uppercase)
            # DETECTION BUG: Array d'objets imbriqués (bug connu Google)
            item_type = sanitized_items.get("type", "").upper()
            if item_type == "OBJECT":
                # Logger un warning mais continuer (le bug peut être corrigé côté Google)
                try:
                    from features.UnifiedLogger import UnifiedLogger
                    UnifiedLogger.write(
                        "AI_CORE",
                        "WARNING",
                        f"⚠️ Détection array d'objets imbriqués dans schéma (bug connu Google - peut causer erreur 500)"
                    )
                except Exception:
                    pass
            result[key] = sanitized_items
            continue
        
        # 6. Traitement récursif des autres dicts
        if isinstance(value, dict):
            result[key] = sanitize_schema_for_codeassist(value, _depth + 1, use_uppercase)
        elif isinstance(value, list):
            result[key] = [sanitize_schema_for_codeassist(item, _depth + 1, use_uppercase) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    
    return result


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
    
    IMPORTANT: Aligné sur le payload gemini-cli capturé qui fonctionne:
    - contents: REMPLI avec les messages user/assistant (format {"role": "user", "parts": [{"text": "..."}]})
    - systemInstruction: contient le contexte système avec role: "user" (pas "system")
    - user_prompt_id: AVANT request (model → project → user_prompt_id → request)
    - parametersJsonSchema: utilise "parametersJsonSchema" (pas "parameters") avec types en minuscules
    - toolConfig: ABSENT (pas nécessaire selon le payload capturé)
    """
    if user_prompt_id is None:
        # Format Gemini CLI: hex string de 14 caractères (ex: "c59ec6dbb5bc58")
        import os
        user_prompt_id = os.urandom(7).hex()
    
    # 1. CONTENTS: REMPLI avec les messages user/assistant (comme gemini-cli)
    contents: List[Dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        # Ignorer les messages système (ils vont dans systemInstruction)
        if role == "system":
            continue
        if content:
            parts = _content_to_parts(content)
            if parts:
                # Convertir le rôle: assistant/model -> "model", user -> "user"
                ca_role = "model" if role in ("assistant", "model") else "user"
                contents.append({"role": ca_role, "parts": parts})
    
    # 2. SYSTEM INSTRUCTION: contient le contexte système uniquement
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
    
    # Construire le payload request avec OrderedDict pour garantir l'ordre exact
    vertex_request = OrderedDict()
    vertex_request["contents"] = contents  # REMPLI!
    
    if all_text_parts:
        full_system_instruction = "\n\n".join(all_text_parts)
        # Utiliser OrderedDict pour garantir l'ordre exact des clés
        # IMPORTANT: role doit être "user" (pas "system") selon le payload capturé
        vertex_request["systemInstruction"] = OrderedDict([
            ("role", "user"),  # CHANGÉ: "system" -> "user"
            ("parts", [OrderedDict([("text", full_system_instruction)])])
        ])
    
    # 3. Outils (sans toolConfig - le payload capturé n'en a pas)
    if tools and len(tools) > 0:
        vertex_request["tools"] = _convert_tools_to_gemini_format(tools)
        # NOTE: toolConfig retiré car absent du payload capturé gemini-cli
    
    # 4. generationConfig EN DERNIER (REQUIS - ordre critique pour API v1internal)
    # Le payload fonctionnel gemini-cli place generationConfig après tools/toolConfig
    # Utiliser OrderedDict pour garantir l'ordre exact des clés
    
    # Détecter si le modèle est gemini-3
    is_gemini3 = "gemini-3" in model.lower()
    
    # Température : 1.0 pour gemini-3, sinon utiliser la valeur fournie
    final_temperature = float(1.0 if is_gemini3 else temperature)
    
    # Construire generationConfig avec tous les paramètres (comme gemini-cli)
    gen_config = OrderedDict([
        ("temperature", final_temperature),
        ("topP", float(kwargs.get("top_p", 0.95))),  # Toujours inclure (valeur par défaut gemini-cli)
        ("topK", int(kwargs.get("top_k", 64)))  # Toujours inclure (valeur par défaut gemini-cli)
    ])
    
    # Pour gemini-3 : toujours inclure thinkingConfig
    if is_gemini3:
        # Si thinking_config est fourni dans kwargs, l'utiliser, sinon utiliser les valeurs par défaut
        if "thinking_config" in kwargs:
            thinking_config = kwargs["thinking_config"]
            if isinstance(thinking_config, dict):
                gen_config["thinkingConfig"] = OrderedDict([
                    ("includeThoughts", thinking_config.get("includeThoughts", True)),
                    ("thinkingLevel", thinking_config.get("thinkingLevel", "HIGH"))
                ])
            else:
                gen_config["thinkingConfig"] = thinking_config
        else:
            # Valeurs par défaut pour gemini-3 (comme dans gemini-cli)
            gen_config["thinkingConfig"] = OrderedDict([
                ("includeThoughts", True),
                ("thinkingLevel", "HIGH")
            ])
    elif "thinking_config" in kwargs:
        # Pour les modèles non-gemini-3, inclure seulement si explicitement fourni
        gen_config["thinkingConfig"] = kwargs["thinking_config"]
    
    # maxOutputTokens (optionnel)
    if max_tokens is not None:
        gen_config["maxOutputTokens"] = int(max_tokens)
    
    vertex_request["generationConfig"] = gen_config
    
    # Optionnels (garder pour compatibilité mais généralement non utilisés par gemini-cli)
    if safety_settings:
        vertex_request["safetySettings"] = safety_settings
    if labels:
        vertex_request["labels"] = labels
    if cached_content:
        vertex_request["cachedContent"] = cached_content
        
    # Ajout du session_id dans la requête (comme dans gemini_cli_captured_payload.json)
    if session_id:
        vertex_request["session_id"] = session_id
    
    # Construire la requête CodeAssist finale avec OrderedDict pour garantir l'ordre exact
    # ORDRE CRITIQUE : model → project → user_prompt_id → request (comme payload capturé gemini-cli)
    ca_request = OrderedDict()
    ca_request["model"] = model
    if project_id:
        ca_request["project"] = project_id
    if user_prompt_id:
        ca_request["user_prompt_id"] = user_prompt_id  # AVANT request
    ca_request["request"] = vertex_request
    
    return ca_request


def from_generate_content_response(response: Dict[str, Any]) -> Dict[str, Any]:
    # L'API CodeAssist encapsule la réponse Gemini dans un champ "response"
    inner_response = response.get("response", {})
    trace_id = response.get("traceId")
    
    # Construire l'objet compatible Gemini API
    gemini_response: Dict[str, Any] = {
        "candidates": inner_response.get("candidates", [])
    }
    
    # Extraire les métadonnées de haut niveau
    if "promptFeedback" in inner_response:
        gemini_response["promptFeedback"] = inner_response["promptFeedback"]
    
    # METRICS: CodeAssist peut mettre usageMetadata à plusieurs endroits
    # 1. Dans response directement (niveau racine)
    if "usageMetadata" in response:
        gemini_response["usageMetadata"] = response["usageMetadata"]
    # 2. Dans inner_response
    elif "usageMetadata" in inner_response:
        gemini_response["usageMetadata"] = inner_response["usageMetadata"]
    # 3. Dans candidates[0]
    elif gemini_response["candidates"] and len(gemini_response["candidates"]) > 0:
        candidate = gemini_response["candidates"][0]
        if "usageMetadata" in candidate:
            gemini_response["usageMetadata"] = candidate["usageMetadata"]
    
    # DEBUG: Log si usageMetadata n'a pas été trouvé (pour diagnostic)
    if "usageMetadata" not in gemini_response:
        try:
            from features.UnifiedLogger import UnifiedLogger
            # Log les clés disponibles pour debug
            available_keys = list(response.keys())
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"usageMetadata non trouvé. Clés disponibles dans response: {available_keys}"
            )
            if inner_response:
                inner_keys = list(inner_response.keys())
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    f"Clés disponibles dans inner_response: {inner_keys}"
                )
        except Exception:
            pass
        
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
    """
    Convertit les outils au format Gemini FunctionDeclaration.
    Applique le sanitizer pour garantir la compatibilité avec l'API v1internal.
    """
    if not tools:
        return []
    
    function_declarations = []
    
    for tool in tools:
        if isinstance(tool, dict):
            func_decl = None
            
            # Format OpenAI: {"type": "function", "function": {...}}
            if "type" in tool and tool.get("type") == "function" and "function" in tool:
                func_def = tool["function"]
                func_decl = {
                    "name": func_def.get("name", ""),
                    "description": func_def.get("description", ""),
                    "parametersJsonSchema": func_def.get("parameters", func_def.get("parametersJsonSchema", {}))
                }
            
            # Format Gemini: {"functionDeclarations": [...]}
            elif "functionDeclarations" in tool:
                for decl in tool["functionDeclarations"]:
                    # IMPORTANT: utiliser "parametersJsonSchema" (pas "parameters") avec types en minuscules
                    # Utiliser _build_ordered_schema pour garantir l'ordre : properties → required → type
                    raw_schema = decl.get("parameters", decl.get("parametersJsonSchema", {}))
                    if isinstance(raw_schema, dict) and raw_schema.get("type") == "object":
                        # Schéma racine : utiliser _build_ordered_schema pour l'ordre correct
                        ordered_schema = _build_ordered_schema(raw_schema, use_uppercase=False)
                    else:
                        # Schéma imbriqué : utiliser sanitize_schema_for_codeassist
                        ordered_schema = sanitize_schema_for_codeassist(raw_schema, use_uppercase=False)
                    
                    sanitized_decl = {
                        "name": decl.get("name", ""),
                        "description": decl.get("description", ""),
                        "parametersJsonSchema": ordered_schema
                    }
                    function_declarations.append(sanitized_decl)
                continue
            
            # Format direct: {"name": "...", "parameters": {...}} ou {"name": "...", "parametersJsonSchema": {...}}
            elif "name" in tool and ("parameters" in tool or "parametersJsonSchema" in tool):
                func_decl = {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parametersJsonSchema": tool.get("parametersJsonSchema", tool.get("parameters", {}))
                }
            
            # Appliquer le sanitizer sur les paramètres
            if func_decl:
                # IMPORTANT: utiliser "parametersJsonSchema" avec types en minuscules
                # Utiliser _build_ordered_schema pour garantir l'ordre : properties → required → type
                raw_schema = func_decl.get("parametersJsonSchema", {})
                if isinstance(raw_schema, dict) and raw_schema.get("type") == "object":
                    # Schéma racine : utiliser _build_ordered_schema pour l'ordre correct
                    func_decl["parametersJsonSchema"] = _build_ordered_schema(raw_schema, use_uppercase=False)
                else:
                    # Schéma imbriqué : utiliser sanitize_schema_for_codeassist
                    func_decl["parametersJsonSchema"] = sanitize_schema_for_codeassist(raw_schema, use_uppercase=False)
                
                # Supprimer "parameters" si présent (on utilise seulement parametersJsonSchema)
                if "parameters" in func_decl:
                    del func_decl["parameters"]
                function_declarations.append(func_decl)
    
    if function_declarations:
        # Utiliser OrderedDict pour garantir l'ordre exact des clés
        return [OrderedDict([("functionDeclarations", function_declarations)])]
    return []

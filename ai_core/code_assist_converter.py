"""
Convertisseur entre les formats Gemini API et CodeAssist.
Base sur packages/core/src/code_assist/converter.ts de gemini-cli.

CORRECTION FINALE: Aligné sur le payload gemini-cli qui FONCTIONNE:
- contents: VIDE [] (gemini-cli met tout dans systemInstruction)
- systemInstruction: contient TOUT (contexte + messages user/assistant)
- PAS de generationConfig
- toolConfig: OPTIONNEL (peut être requis pour éviter null pointer exceptions sur v1internal)

BLINDAGE ERREUR 500:
- Sanitizer de schéma: types en MAJUSCULES, suppression champs interdits
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


def sanitize_schema_for_codeassist(schema: Any, _depth: int = 0) -> Any:
    """
    Sanitize récursivement un schéma JSON pour le rendre compatible avec l'API v1internal.
    
    Actions:
    1. Convertir tous les types en MAJUSCULES (object -> OBJECT, string -> STRING)
    2. Supprimer les champs interdits (title, default, examples, additionalProperties, etc.)
    3. Détecter et logger les arrays d'objets imbriqués (bug connu Google - peut causer erreur 500)
    
    Args:
        schema: Le schéma JSON à sanitizer (dict, list, ou valeur primitive)
        _depth: Profondeur de récursion (pour logging debug)
    
    Returns:
        Le schéma sanitizé compatible avec l'API CodeAssist v1internal
    """
    # Protection contre récursion infinie
    if _depth > 50:
        return schema
    
    # Cas de base: pas un dict
    if not isinstance(schema, dict):
        if isinstance(schema, list):
            return [sanitize_schema_for_codeassist(item, _depth + 1) for item in schema]
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
        
        # 3. Convertir les types en MAJUSCULES
        if key == "type":
            if isinstance(value, str):
                result[key] = value.upper()
            elif isinstance(value, list):
                # Type union (ex: ["string", "null"]) - prendre le premier non-null
                non_null_types = [t for t in value if t != "null"]
                if non_null_types:
                    result[key] = non_null_types[0].upper()
                else:
                    result[key] = "STRING"  # Fallback
            else:
                result[key] = value
            continue
        
        # 4. Traitement récursif des propriétés
        if key == "properties" and isinstance(value, dict):
            result[key] = {k: sanitize_schema_for_codeassist(v, _depth + 1) for k, v in value.items()}
            continue
        
        # 5. Traitement récursif des items (pour les arrays)
        if key == "items" and isinstance(value, dict):
            sanitized_items = sanitize_schema_for_codeassist(value, _depth + 1)
            # DETECTION BUG: Array d'objets imbriqués (bug connu Google)
            if sanitized_items.get("type") == "OBJECT":
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
            result[key] = sanitize_schema_for_codeassist(value, _depth + 1)
        elif isinstance(value, list):
            result[key] = [sanitize_schema_for_codeassist(item, _depth + 1) if isinstance(item, dict) else item for item in value]
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
    
    IMPORTANT: Aligné sur le payload gemini-cli qui fonctionne:
    - contents: [] (VIDE)
    - systemInstruction contient TOUT le contexte + messages
    - Ordre des clés CRITIQUE pour API v1internal:
      1. tools (si présent)
      2. toolConfig (si tools présents)
      3. generationConfig EN DERNIER (requis avec temperature)
    - Sanitizer appliqué sur les outils (types MAJUSCULES, champs interdits supprimés)
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
    
    # Construire le payload request avec OrderedDict pour garantir l'ordre exact
    vertex_request = OrderedDict()
    vertex_request["contents"] = contents  # VIDE!
    
    if all_text_parts:
        full_system_instruction = "\n\n".join(all_text_parts)
        vertex_request["systemInstruction"] = {
            "role": "system",
            "parts": [{"text": full_system_instruction}]
        }
    
    # 3. Outils avec toolConfig conditionnel (EN PREMIER - ordre critique pour API v1internal)
    # BLINDAGE ERREUR 500: toolConfig peut être requis pour éviter null pointer exceptions
    if tools and len(tools) > 0:
        vertex_request["tools"] = _convert_tools_to_gemini_format(tools)
        # Ajouter toolConfig pour lever l'ambiguïté du mode d'exécution
        # Mode AUTO: le modèle décide s'il doit appeler un outil ou générer du texte
        vertex_request["toolConfig"] = {
            "functionCallingConfig": {
                "mode": "AUTO"
            }
        }
    
    # 4. generationConfig EN DERNIER (REQUIS - ordre critique pour API v1internal)
    # Le payload fonctionnel gemini-cli place generationConfig après tools/toolConfig
    vertex_request["generationConfig"] = {
        "temperature": float(temperature)  # Forcer float explicite
    }
    
    # Optionnels (garder pour compatibilité mais généralement non utilisés par gemini-cli)
    if safety_settings:
        vertex_request["safetySettings"] = safety_settings
    if labels:
        vertex_request["labels"] = labels
    if cached_content:
        vertex_request["cachedContent"] = cached_content
    
    # Construire la requête CodeAssist finale avec OrderedDict pour garantir l'ordre exact
    ca_request = OrderedDict()
    ca_request["model"] = model
    ca_request["request"] = vertex_request
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
                    "parameters": func_def.get("parameters", {})
                }
            
            # Format Gemini: {"functionDeclarations": [...]}
            elif "functionDeclarations" in tool:
                for decl in tool["functionDeclarations"]:
                    sanitized_decl = {
                        "name": decl.get("name", ""),
                        "description": decl.get("description", ""),
                        "parameters": sanitize_schema_for_codeassist(decl.get("parameters", {}))
                    }
                    function_declarations.append(sanitized_decl)
                continue
            
            # Format direct: {"name": "...", "parameters": {...}}
            elif "name" in tool and "parameters" in tool:
                func_decl = {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                }
            
            # Appliquer le sanitizer sur les paramètres
            if func_decl:
                func_decl["parameters"] = sanitize_schema_for_codeassist(func_decl["parameters"])
                function_declarations.append(func_decl)
    
    if function_declarations:
        return [{"functionDeclarations": function_declarations}]
    return []

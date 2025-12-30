"""
Custom LiteLLM Provider pour CodeAssist.
Encapsule CodeAssistClient et retourne un format LiteLLM-compatible.
Permet à LiteLLM d'orchestrer les sessions GeminiCLI via CodeAssist.
"""

import os
from typing import Optional, Dict, List, Any, Iterator, Generator

from features.UnifiedLogger import UnifiedLogger
from ai_core.code_assist_client import CodeAssistClient


def codeassist_completion(**kwargs) -> Any:
    """
    Custom provider LiteLLM pour CodeAssist.
    Utilise CodeAssistClient mais retourne un format LiteLLM-compatible.
    
    Args:
        **kwargs: Paramètres LiteLLM standard :
            - model: Nom du modèle (ex: "gemini-3-flash-preview")
            - messages: Liste de messages au format OpenAI
            - stream: Mode streaming (bool)
            - temperature: Température
            - max_tokens: Nombre max de tokens
            - tools: Outils (tool calling)
            - system_instruction: Instruction système
            - project_id: ID du projet Google Cloud (optionnel)
            - session_id: ID de session (optionnel)
            - **kwargs: Autres paramètres
    
    Returns:
        - Non-streaming: Objet avec choices[0].message.content, usage, etc.
        - Streaming: Générateur avec choices[0].delta.content
    """
    # Extraire les paramètres depuis kwargs
    model = kwargs.get("model", "")
    messages = kwargs.get("messages", [])
    stream = kwargs.get("stream", False)
    temperature = kwargs.get("temperature", 0.7)
    max_tokens = kwargs.get("max_tokens")
    tools = kwargs.get("tools")
    system_instruction = kwargs.get("system_instruction")
    
    # MODIFICATION: Utiliser MCP si les outils ne sont pas fournis explicitement
    # Si tools est None ou vide, on laisse LiteLLM découvrir les outils MCP automatiquement
    # Si tools contient déjà des outils MCP (format {"type": "mcp", ...}), on les utilise
    # Sinon, on utilise les outils fournis normalement
    use_mcp_tools = False
    if tools is None or (isinstance(tools, list) and len(tools) == 0):
        # Aucun outil fourni, utiliser MCP si configuré
        # LiteLLM découvrira automatiquement les outils MCP depuis la config
        use_mcp_tools = True
        UnifiedLogger.write(
            "AI_CORE",
            "MCP",
            "🔧 Utilisation des outils MCP (découverte automatique)"
        )
    elif isinstance(tools, list) and len(tools) > 0:
        # Vérifier si c'est déjà un outil MCP
        first_tool = tools[0]
        if isinstance(first_tool, dict) and first_tool.get("type") == "mcp":
            use_mcp_tools = True
            UnifiedLogger.write(
                "AI_CORE",
                "MCP",
                f"🔧 Utilisation des outils MCP explicitement configurés ({len(tools)} serveurs)"
            )
    # Ne pas récupérer project_id depuis l'environnement pour utiliser le quota personnel
    # Seulement utiliser si explicitement fourni (pour utilisation projet GCP)
    project_id = kwargs.get("project_id")  # None par défaut = quota personnel
    session_id = kwargs.get("session_id")
    shadow_history = kwargs.get("shadow_history")  # Historique Shadow pour continuation après tool call
    
    UnifiedLogger.write(
        "AI_CORE",
        "PROVIDER",
        f"🔧 Custom Provider CodeAssist: {model} (stream={stream}, quota={'personnel' if not project_id else 'projet GCP'})"
    )
    
    # Créer le client CodeAssist avec use_personal_quota=True par défaut
    # Cela garantit l'utilisation du quota personnel Google AI Pro (comme gemini-cli)
    code_assist_client = CodeAssistClient(
        project_id=project_id,  # None = utilise quota personnel
        session_id=session_id,
        use_personal_quota=True  # Force l'utilisation du quota personnel
    )
    
    # Appeler CodeAssistClient
    if stream:
        # Mode streaming
        stream_generator = code_assist_client.completion(
            model=model,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            system_instruction=system_instruction,
            shadow_history=shadow_history,  # Passer shadow_history explicitement
            **{k: v for k, v in kwargs.items() if k not in [
                "model", "messages", "stream", "temperature", 
                "max_tokens", "tools", "system_instruction", 
                "project_id", "session_id", "shadow_history"
            ]}
        )
        
        # Convertir le générateur CodeAssist en format LiteLLM
        return _convert_stream_to_litellm(stream_generator)
    else:
        # Mode non-streaming
        response = code_assist_client.completion(
            model=model,
            messages=messages,
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            system_instruction=system_instruction,
            shadow_history=shadow_history,  # Passer shadow_history explicitement
            **{k: v for k, v in kwargs.items() if k not in [
                "model", "messages", "stream", "temperature", 
                "max_tokens", "tools", "system_instruction", 
                "project_id", "session_id", "shadow_history"
            ]}
        )
        
        # Convertir la réponse CodeAssist en format LiteLLM
        return _convert_response_to_litellm(response, model)


def _convert_response_to_litellm(response: Any, model: str) -> Any:
    """
    Convertit une réponse CodeAssist (non-streaming) en format LiteLLM.
    
    Args:
        response: Réponse de CodeAssistClient (UniversalResponseWrapper)
        model: Nom du modèle
    
    Returns:
        Objet compatible LiteLLM avec choices[0].message.content, usage, etc.
    """
    # Extraire le contenu depuis la réponse CodeAssist
    content = ""
    usage_metadata = {}
    
    if hasattr(response, 'data') and isinstance(response.data, dict):
        data = response.data
        # Extraire le contenu texte
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                content = "".join(
                    part.get("text", "") 
                    for part in candidate["content"]["parts"] 
                    if "text" in part
                )
            
            # Extraire les métadonnées d'usage
            if "usageMetadata" in data:
                usage_metadata = data["usageMetadata"]
            elif "usageMetadata" in candidate:
                usage_metadata = candidate["usageMetadata"]
    elif hasattr(response, 'content'):
        content = response.content
    elif hasattr(response, 'text'):
        content = response.text
    
    # Créer un objet compatible LiteLLM
    class MessageObject:
        def __init__(self, content):
            self.content = content
            self.role = "assistant"
    
    class ChoiceObject:
        def __init__(self, message):
            self.message = message
            self.finish_reason = "stop"
            self.index = 0
    
    class UsageObject:
        def __init__(self, usage_metadata):
            self.prompt_tokens = usage_metadata.get("promptTokenCount", 0)
            self.completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
            self.total_tokens = usage_metadata.get("totalTokenCount", 0)
    
    class LiteLLMResponse:
        def __init__(self, choices, usage, model):
            self.choices = choices
            self.usage = usage
            self.model = model
            self.id = f"chatcmpl-{os.urandom(16).hex()}"
    
    message = MessageObject(content)
    choice = ChoiceObject(message)
    usage = UsageObject(usage_metadata)
    
    return LiteLLMResponse([choice], usage, model)


def _convert_stream_to_litellm(stream_generator: Generator) -> Generator:
    """
    Convertit un générateur CodeAssist (streaming) en format LiteLLM.
    Préserve l'attribut is_thinking pour distinguer thinking et réponse finale.
    
    Args:
        stream_generator: Générateur de CodeAssistClient
    
    Yields:
        Objets compatibles LiteLLM avec choices[0].delta.content
    """
    class DeltaObject:
        def __init__(self, content, is_thinking=False):
            self.content = content
            self.text = content  # Compatibilité avec worker/core.py
            self.role = "assistant"
            self.is_thinking = is_thinking  # Préserver le marqueur thinking
            # Selon la doc, LiteLLM utilise reasoning_content au lieu de thought
            # On ajoute aussi reasoning_content pour compatibilité LiteLLM
            if is_thinking:
                self.reasoning_content = content  # Format LiteLLM
            else:
                self.reasoning_content = None
    
    class ChoiceObject:
        def __init__(self, delta):
            self.delta = delta
            self.index = 0
            self.finish_reason = None
    
    class StreamChunk:
        def __init__(self, choice):
            self.choices = [choice]
            self.model = None
            self.id = None
    
    import logging
    log_convert = logging.getLogger("ai_core.litellm_codeassist_provider")
    
    # Importer FunctionCallObject pour détection
    from ai_core.code_assist_client import FunctionCallObject
    
    for chunk in stream_generator:
        # Vérifier si c'est un FunctionCallObject directement yieldé
        if isinstance(chunk, FunctionCallObject):
            # Yielder le FunctionCallObject tel quel pour que le worker le détecte
            log_convert.info(f"🔄 _convert_stream: FunctionCallObject détecté: {chunk.name}, id={chunk.id}")
            yield chunk
            continue
        
        # Extraire le contenu du chunk et le marqueur is_thinking
        chunk_content = ""
        is_thinking = False
        
        if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
            choice_obj = chunk.choices[0]
            if hasattr(choice_obj, 'delta'):
                delta = choice_obj.delta
                
                # DEBUG: Log pour comprendre la structure
                delta_type = type(delta).__name__
                has_is_thinking_attr = hasattr(delta, 'is_thinking')
                is_thinking_value = getattr(delta, 'is_thinking', None) if has_is_thinking_attr else None
                log_convert.info(f"🔄 _convert_stream: delta type={delta_type}, hasattr(is_thinking)={has_is_thinking_attr}, value={is_thinking_value}")
                
                # Vérifier si c'est du thinking
                if has_is_thinking_attr:
                    is_thinking = is_thinking_value is True
                    log_convert.info(f"🔄 _convert_stream: is_thinking détecté via hasattr: {is_thinking}")
                elif hasattr(delta, '__dict__') and 'is_thinking' in delta.__dict__:
                    is_thinking = delta.__dict__['is_thinking'] is True
                    log_convert.info(f"🔄 _convert_stream: is_thinking détecté via __dict__: {is_thinking}")
                
                if hasattr(delta, 'content'):
                    chunk_content = delta.content
                elif hasattr(delta, 'text'):
                    chunk_content = delta.text
        
        if chunk_content:
            # Préserver le marqueur is_thinking lors de la création du nouveau DeltaObject
            log_convert.info(f"🔄 _convert_stream: Création DeltaObject avec is_thinking={is_thinking}, content_len={len(chunk_content)}")
            delta = DeltaObject(chunk_content, is_thinking=is_thinking)
            choice = ChoiceObject(delta)
            stream_chunk = StreamChunk(choice)
            yield stream_chunk


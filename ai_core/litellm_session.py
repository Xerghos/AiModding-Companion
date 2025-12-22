"""
LiteLLM Session - Wrapper compatible avec l'interface existante.
Phase 1.2 : Wrapper LiteLLMSession avec interface compatible.
"""

import time
import json
import logging
from typing import Optional, Dict, List, Any, Iterator

from ai_core.sessions import (
    BaseSession, UniversalResponseWrapper, FatalKeyError, GeminiCliSession
)
from ai_core.litellm_proxy import get_litellm_proxy, LiteLLMProxy, ModelProvider
from features.CacheManager import GlobalCacheManager
from features.TokenManager import TokenManager
from features.UnifiedLogger import UnifiedLogger
from features.Decorators import trace_action
from config.tools_schema import TOOLS_SCHEMA
from config.settings import APP_SETTINGS

# Helper de conversion (réutilisé depuis sessions.py)
from ai_core.sessions import _convert_schema_to_openai, _save_payload_log

log = logging.getLogger("ai_core.litellm_session")


class LiteLLMSession(BaseSession):
    """
    Session LiteLLM compatible avec l'interface BaseSession.
    
    Préservation :
    - Interface identique send_message()
    - _build_payload_messages() identique à DeepSeekSession
    - Historique conversationnel
    - Tool calling
    - Streaming
    - Context Caching (ordre messages préservé)
    """
    
    def __init__(
        self,
        key_manager,
        model_name: str = "deepseek-chat",
        system_instruction: Optional[str] = None,
        base_url: Optional[str] = None,
        agent_name: Optional[str] = None
    ):
        """
        Initialise la session LiteLLM.
        
        Args:
            key_manager: Gestionnaire de clés
            model_name: Nom du modèle
            system_instruction: Instructions système
            base_url: URL de base (optionnel, pour DeepSeek spécial)
            agent_name: Nom de l'agent (pour logging)
        """
        super().__init__(key_manager, model_name, system_instruction)
        
        # Initialiser TOUS les attributs AVANT toute logique conditionnelle
        self.key_mgr = key_manager
        self.model_name = model_name
        self.agent_name = agent_name
        self.system_instruction = system_instruction
        self.current_key = None
        self._history = []  # Historique interne (utilisé seulement si pas de CLI)
        self.base_url = base_url  # Conservé pour compatibilité
        self._cli_session = None  # Toujours initialiser à None en premier
        self.proxy = None  # Initialiser à None (sera créé si nécessaire)
        
        # Instance proxy LiteLLM (si pas CLI ou si CLI a échoué)
        try:
            self.proxy = get_litellm_proxy()
        except ImportError as e:
            raise ImportError(
                f"LiteLLM non disponible: {e}. "
                "Installez-le avec: pip install litellm"
            )
        
        UnifiedLogger.write(
            "AI_CORE",
            "INIT",
            f"LiteLLMSession créée ({model_name})",
            {"agent": agent_name, "mode": "LiteLLM"}
        )
    
    def _truncate(self, text: str, max_chars: int) -> str:
        """Tronque le texte s'il dépasse la limite."""
        if not text: return ""
        text_str = str(text)
        if len(text_str) <= max_chars: return text_str
        return text_str[:max_chars] + f"\n... [TRONQUÉ ({len(text_str)-max_chars} chars)] ..."

    def _build_payload_messages(self, rag_context: Optional[Dict] = None) -> List[Dict[str, str]]:
        """
        Construction Atomique du Payload (identique à DeepSeekSession).
        Ordre : [Instructions] -> [Arch] -> [Tree] -> [LTM] -> [Historique] -> [RAG+Query]
        
        Pour les sessions Writer (documentation), payload minimal : seulement architecture map.
        """
        messages = []
        
        # Détection session Writer (documentation)
        is_writer_session = (
            self.agent_name and "writer" in self.agent_name.lower()
        ) or (
            hasattr(self, '_is_writer') and self._is_writer
        ) or (
            hasattr(self, 'model_type') and self.model_type and "writer" in str(self.model_type).lower()
        )
        
        # --- BLOC 1 : INSTRUCTIONS AGENTS (System) ---
        if self.system_instruction:
            messages.append({
                "role": "system",
                "content": f"=== INSTRUCTIONS AGENT ({self.model_name}) ===\n{self.system_instruction}"
            })
        
        # --- BLOCS DYNAMIQUES (System) ---
        try:
            comps = GlobalCacheManager.get_components() if GlobalCacheManager else {}
            
            # Limites de taille (inspirées de prompt_builders.py)
            LIMIT_ARCH = 10000
            LIMIT_TREE = 10000
            LIMIT_LTM = 6000
            
            if is_writer_session:
                # SESSION WRITER : Payload minimal (seulement architecture map)
                if comps.get('arch'):
                    arch_content = str(comps['arch']).strip()
                    if arch_content.startswith("--- CARTOGRAPHIE TECHNIQUE ---"):
                        arch_content = arch_content.replace("--- CARTOGRAPHIE TECHNIQUE ---", "", 1).strip()
                    
                    arch_content = self._truncate(arch_content, LIMIT_ARCH)
                    messages.append({
                        "role": "system",
                        "content": f"--- CARTOGRAPHIE TECHNIQUE ---\n{arch_content}"
                    })
            else:
                # SESSION NORMALE : Tous les blocs statiques
                # BLOC 2 : REPO MAP (remplace CARTOGRAPHIE TECHNIQUE)
                if comps.get('repo_map'):
                    repo_map_content = str(comps['repo_map']).strip()
                    repo_map_content = self._truncate(repo_map_content, LIMIT_ARCH)
                    messages.append({"role": "system", "content": repo_map_content})
                elif comps.get('arch'):
                    # Fallback sur l'ancienne cartographie technique
                    arch_content = str(comps['arch']).strip()
                    if arch_content.startswith("--- CARTOGRAPHIE TECHNIQUE ---"):
                        arch_content = arch_content.replace("--- CARTOGRAPHIE TECHNIQUE ---", "", 1).strip()
                    
                    arch_content = self._truncate(arch_content, LIMIT_ARCH)
                    messages.append({
                        "role": "system",
                        "content": f"--- CARTOGRAPHIE TECHNIQUE ---\n{arch_content}"
                    })
                
                # BLOC 3 : ARBORESCENCE PROJET
                if comps.get('tree'):
                    tree_content = str(comps['tree']).strip()
                    tree_content = self._truncate(tree_content, LIMIT_TREE)
                    messages.append({"role": "system", "content": tree_content})
                
                # (Optionnel) LTM dans le système
                if comps.get('ltm'):
                    ltm_content = str(comps['ltm']).strip()
                    ltm_content = self._truncate(ltm_content, LIMIT_LTM)
                    messages.append({"role": "system", "content": ltm_content})
        
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARNING", f"Echec assemblage composants CacheManager: {e}")
        
        # --- BLOC 4 : RAG Docs retiré des messages système (pour maximiser le cache statique) ---
        # Le RAG Docs sera injecté dans le message utilisateur dans send_message()
        
        # --- BLOCS 5 à N : HISTORIQUE CONVERSATIONNEL ---
        history_len = len(self._history)
        
        for i, msg in enumerate(self._history):
            # Normalisation du contenu
            if isinstance(msg, dict):
                role = msg.get('role', 'user')
                content = msg.get('content', '')
            else:
                role = getattr(msg, 'role', 'user')
                content = ""
                if hasattr(msg, 'parts') and msg.parts:
                    content = msg.parts[0].text
                elif hasattr(msg, 'content'):
                    content = msg.content
            
            # S'assurer que content est toujours une string
            # (peut être un dict dans le cas de tool calls ou messages complexes)
            if not isinstance(content, str):
                if isinstance(content, dict):
                    # Si c'est un dict (tool calls, etc.), le convertir en JSON string
                    content = json.dumps(content, ensure_ascii=False) if content else ""
                elif isinstance(content, list):
                    # Si c'est une liste (multimodal), extraire le texte ou convertir
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and 'text' in item:
                            text_parts.append(item['text'])
                        elif isinstance(item, str):
                            text_parts.append(item)
                    content = "\n".join(text_parts) if text_parts else ""
                else:
                    content = str(content) if content else ""
            
            if role == 'system':
                continue  # On ne réinjecte pas les vieux messages système
            if role == 'model':
                role = 'assistant'
            
            # Injection Safety au dernier tour utilisateur (Bloc N)
            if i == history_len - 1 and role == 'user':
                # Petit rappel système discret juste avant le message final
                messages.append({
                    "role": "system",
                    "content": "⚠️ INSTRUCTION : Focus sur la demande ci-dessous."
                })
            
            messages.append({"role": role, "content": content})
        
        return messages
    
    @trace_action(source="litellm_session")
    def send_message(
        self,
        message: str,
        stream: bool = False,
        tool_config: Optional[Dict] = None,
        rag_context: Optional[Dict] = None
    ) -> Any:
        """
        Envoie un message via LiteLLM.
        
        Args:
            message: Message utilisateur
            stream: Mode streaming
            tool_config: Configuration outils (optionnel)
            rag_context: Contexte RAG (dict ou str)
        
        Returns:
            UniversalResponseWrapper ou générateur (stream)
        """
        # Pour Gemini, essayer d'abord l'auth OAuth (Login with Google), sinon API key
        # Cela permet de profiter des tokens gratuits Google AI Pro
        self.current_key = None
        self._use_oauth = False
        
        if "gemini" in self.model_name.lower() or "google" in self.model_name.lower():
            # Vérifier si OAuth est disponible AVANT de récupérer une API key
            if self.proxy and hasattr(self.proxy, '_try_google_oauth_auth'):
                self._use_oauth = self.proxy._try_google_oauth_auth()
            
            if not self._use_oauth:
                # OAuth non disponible, utiliser API key
                try:
                    self.current_key = self.key_mgr.get_key(self.model_name)
                except Exception:
                    # Pas de clé disponible
                    pass
        else:
            # Pour les autres providers, API key requise
            self.current_key = self.key_mgr.get_key(self.model_name)
            if not self.current_key:
                raise FatalKeyError(f"Aucune clé disponible pour {self.model_name}")
        
        # Construire le message utilisateur avec préfixe RAG si disponible
        user_message_content = message
        if rag_context:
            if isinstance(rag_context, dict):
                if rag_context.get("docs"):
                    docs_content = str(rag_context["docs"]).strip()
                    user_message_content = (
                        f"--- 📂 CONTEXTE RAG PERTINENT ---\n{docs_content}\n\n"
                        f"--- MESSAGE UTILISATEUR ---\n{message}"
                    )
            else:
                # Ancien format string (compatibilité)
                user_message_content = (
                    f"--- 📂 CONTEXTE RAG PERTINENT ---\n{rag_context}\n\n"
                    f"--- MESSAGE UTILISATEUR ---\n{message}"
                )
        
        # Ajout du message utilisateur à l'historique
        self._history.append(self._create_msg("user", user_message_content))
        
        # Outils Natifs
        native_tools = None
        try:
            native_tools = _convert_schema_to_openai(TOOLS_SCHEMA)
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARNING", f"Echec conversion outils: {e}")
        
        # Construction du Payload Structuré (SANS RAG Docs dans messages système)
        final_messages = self._build_payload_messages(rag_context=None)
        
        # Configuration température (identique à DeepSeekSession)
        temperature = 1.3 if "coder" in self.model_name.lower() else 0.7
        
        # Déterminer le provider utilisé
        provider = "codeassist" if self._use_oauth else "standard"
        
        # Construction du payload complet pour logging
        litellm_payload = {
            "model": self.model_name,
            "agent": self.agent_name or "LiteLLM Agent",
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": 8000,
            "stream": stream,
            "tools": native_tools if native_tools else None,
            "use_oauth": self._use_oauth,
            "provider": provider
        }
        
        # Sauvegarder le payload log (format spécifique LiteLLM)
        if not getattr(self, '_skip_payload_log', False):
            _save_payload_log("litellm", self.model_name, litellm_payload)
        
        UnifiedLogger.write("AI_CORE", "START", f"LiteLLM ({self.model_name}) thinking...")
        
        try:
            start_t = time.time()
            
            # Appel via proxy LiteLLM
            # Ne pas passer api_key si OAuth est disponible (LiteLLM utilisera GOOGLE_APPLICATION_CREDENTIALS)
            api_key_to_use = None if self._use_oauth else self.current_key
            
            response = self.proxy.completion(
                model=self.model_name,
                messages=final_messages,
                api_key=api_key_to_use,  # None si OAuth, sinon API key
                stream=stream,
                temperature=temperature,
                max_tokens=8000,
                tools=native_tools if native_tools else None
            )
            
            self.key_mgr.mark_success(self.current_key, self.model_name)
            
            if stream:
                # Mode streaming
                def litellm_generator():
                    nonlocal response
                    full_response_text = ""
                    usage_data = None
                    
                    try:
                        for chunk in response:
                            # Extraction contenu
                            if hasattr(chunk, 'choices') and chunk.choices:
                                delta = chunk.choices[0].delta
                                
                                # Contenu texte
                                content = getattr(delta, 'content', '') or getattr(delta, 'text', '')
                                if content:
                                    full_response_text += content
                                    yield content
                                
                                # Tool calls (si présents)
                                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                                    # Gérer tool calls en streaming
                                    pass  # TODO: Implémenter si nécessaire
                            
                            # Métriques usage
                            if hasattr(chunk, 'usage'):
                                usage_data = self.proxy.extract_usage_metadata(chunk)
                    
                    except Exception as e:
                        UnifiedLogger.write("AI_CORE", "ERROR", f"LiteLLM Stream Interrompu: {e}")
                        yield f"\n[Erreur Stream: {e}]"
                    
                    # Fin Stream : Sauvegarde et Métriques
                    self._history.append(self._create_msg("assistant", full_response_text))
                    
                    duration = time.time() - start_t
                    
                    # Extraction métriques
                    if usage_data:
                        in_tok = usage_data.get('prompt_tokens', 0)
                        out_tok = usage_data.get('completion_tokens', 0)
                        cache_hit = usage_data.get('prompt_cache_hit_tokens', 0)
                        cache_miss = usage_data.get('prompt_cache_miss_tokens', in_tok)
                        
                        try:
                            if TokenManager:
                                TokenManager.add_usage(self.model_name, self.current_key, in_tok, out_tok)
                        except Exception:
                            pass
                        
                        savings = int((cache_hit / in_tok * 100)) if in_tok > 0 else 0
                        
                        metrics_data = {
                            "model": self.model_name,
                            "agent": self.agent_name or "LiteLLM Agent",
                            "provider": "LiteLLM",
                            "in": in_tok,
                            "out": out_tok,
                            "cache_hit": cache_hit,
                            "billed": cache_miss,
                            "savings": f"{savings}%",
                            "time": f"{duration:.2f}s"
                        }
                        
                        UnifiedLogger.write("AI_CORE", "METRICS", f"LiteLLM {savings}%", metrics_data)
                    
                    UnifiedLogger.write("AI_CORE", "SUCCESS", f"LiteLLM Stream terminé")
                
                return litellm_generator()
            
            else:
                # Mode Non-Stream
                # Extraction contenu
                content = ""
                tool_calls = []
                
                if hasattr(response, 'choices') and response.choices:
                    message_obj = response.choices[0].message
                    content = getattr(message_obj, 'content', '') or getattr(message_obj, 'text', '')
                    
                    # Tool calls
                    if hasattr(message_obj, 'tool_calls') and message_obj.tool_calls:
                        tool_calls = message_obj.tool_calls
                        # Convertir en format !native_tool
                        for tc in tool_calls:
                            func = getattr(tc, 'function', {})
                            fname = getattr(func, 'name', '')
                            fargs = getattr(func, 'arguments', '')
                            try:
                                parsed_args = json.loads(fargs) if isinstance(fargs, str) else fargs
                                content += f"\n!native_tool {json.dumps({'name': fname, 'args': parsed_args}, ensure_ascii=False)}\n"
                            except Exception:
                                pass
                
                self._history.append(self._create_msg("assistant", content))
                
                # Métriques
                try:
                    if TokenManager:
                        usage_data = self.proxy.extract_usage_metadata(response)
                        in_tok = usage_data.get('prompt_tokens', 0)
                        out_tok = usage_data.get('completion_tokens', 0)
                        cache_hit = usage_data.get('prompt_cache_hit_tokens', 0)
                        cache_miss = usage_data.get('prompt_cache_miss_tokens', in_tok)
                        
                        TokenManager.add_usage(self.model_name, self.current_key, in_tok, out_tok)
                        
                        duration = time.time() - start_t
                        savings = int((cache_hit / in_tok * 100)) if in_tok > 0 else 0
                        
                        if cache_hit > 0:
                            UnifiedLogger.write(
                                "AI_CORE",
                                "CACHE_HIT",
                                f"⚡ Cache Hit: {cache_hit} | 💲 Payés: {cache_miss} (Éco: {savings}%)"
                            )
                        else:
                            UnifiedLogger.write(
                                "AI_CORE",
                                "CACHE_MISS",
                                f"💲 Payés: {cache_miss} (Full Miss)"
                            )
                        
                        metrics_data = {
                            "model": self.model_name,
                            "agent": self.agent_name or "LiteLLM Agent",
                            "in": in_tok,
                            "out": out_tok,
                            "cache_hit": cache_hit,
                            "billed": cache_miss,
                            "time": f"{duration:.2f}s",
                            "provider": "LiteLLM"
                        }
                        UnifiedLogger.write("AI_CORE", "METRICS", "Usage", metrics_data)
                        UnifiedLogger.write("AI_CORE", "SUCCESS", f"LiteLLM terminé ({duration:.2f}s)")
                except Exception as e:
                    UnifiedLogger.write("AI_CORE", "WARNING", f"Pas de métriques: {e}")
                
                return UniversalResponseWrapper(content, response, tool_calls=tool_calls)
        
        except Exception as e:
            self.key_mgr.report_error(self.current_key, exception=e, model_name=self.model_name)
            raise e
    
    @property
    def history(self):
        """Historique de la session."""
        return self._history
    
    @history.setter
    def history(self, val):
        """Setter pour l'historique."""
        self._history = val
    
    @property
    def chat(self):
        """Interface de compatibilité pour l'historique."""
        
        class ChatInterface:
            def __init__(self, session):
                self.session = session
            
            @property
            def history(self):
                return self.session.history
            
            @history.setter
            def history(self, val):
                self.session.history = val
            
            def rewind(self):
                if self.session.history:
                    self.session.history.pop()
        
        return ChatInterface(self)


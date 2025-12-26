import google.generativeai as genai
from google.generativeai import caching
import time
import json
import contextlib
import logging
import requests
import re
from enum import Enum
import datetime
from threading import Lock
import subprocess
import shutil
import os
import sys
import tempfile
import atexit

from config.settings import APP_SETTINGS
from config.logs import get_logger
from features.Decorators import trace_action
from features.UnifiedLogger import UnifiedLogger

from ai_core.prompt_builders import build_cli_system_md, build_cli_prompt

# Note : TokenManager est importé localement pour éviter les cycles.

try:
    from config.tools_schema import TOOLS_SCHEMA
except ImportError:
    TOOLS_SCHEMA = []

try:
    from features.CacheManager import GlobalCacheManager
except ImportError:
    GlobalCacheManager = None

log = get_logger("ai_core.sessions")

class AiMode(Enum):
    STANDARD = "standard"
    ROUTER_STRICT = "router_strict"
    CREATIVE = "creative"
    REASONING = "reasoning"

class QuotaExceededException(Exception): pass
class FatalKeyError(Exception): pass


# --- HELPER DE LOGGING PAYLOAD ---
def _trigger_cache_analysis(payload_path: str, session_type: str, model_name: str):
    """
    Déclenche l'analyse automatique des cassures de cache entre le payload actuel et le précédent.
    Exécuté de manière asynchrone pour ne pas bloquer l'exécution.
    """
    try:
        import subprocess
        import glob
        from pathlib import Path
        
        logs_dir = os.path.dirname(payload_path)
        safe_model = model_name.replace("/", "_").replace(":", "_")
        
        # Trouver le payload précédent du même type (session_type + model_name)
        pattern = f"payload_{session_type}_{safe_model}_*.json"
        payload_files = sorted(
            glob.glob(os.path.join(logs_dir, pattern)),
            key=lambda p: os.path.getmtime(p),
            reverse=True
        )
        
        # Exclure le payload actuel et prendre le suivant (le plus récent avant celui-ci)
        previous_payloads = [f for f in payload_files if f != payload_path]
        
        if len(previous_payloads) < 1:
            # Pas de payload précédent, on ne fait rien
            return
        
        previous_payload = previous_payloads[0]
        
        # Chemin vers le script d'analyse
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "analyze_payload_cache_breaks.py")
        
        if not os.path.exists(script_path):
            # Script non trouvé, on ne fait rien (pas d'erreur)
            return
        
        # Appeler le script de manière asynchrone (non-bloquant)
        subprocess.Popen(
            [sys.executable, script_path, previous_payload, payload_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        
    except Exception as e:
        # Ne pas bloquer l'exécution si l'analyse échoue
        UnifiedLogger.write("AI_CORE", "DEBUG", f"Echec déclenchement analyse cache: {e}")


def _save_payload_log(session_type: str, model_name: str, payload_data: dict, extra_meta: dict = None):
    """
    Sauvegarde un payload/prompt dans logs/ avec timestamp.
    Args:
        session_type: "deepseek", "gemini", "gemini_cli"
        model_name: nom du modèle utilisé
        payload_data: le payload complet (messages, prompt, etc.)
        extra_meta: métadonnées additionnelles (metrics, etc.)
    """
    try:
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%d-%b_%Hh%M_%S")
        safe_model = model_name.replace("/", "_").replace(":", "_")
        filename = f"payload_{session_type}_{safe_model}_{timestamp}.json"
        filepath = os.path.join(logs_dir, filename)
        
        log_content = {
            "timestamp": datetime.datetime.now().isoformat(),
            "session_type": session_type,
            "model": model_name,
            "payload": payload_data
        }
        if extra_meta:
            log_content["meta"] = extra_meta
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(log_content, f, indent=2, ensure_ascii=False)
        
        UnifiedLogger.write("AI_CORE", "PAYLOAD_LOG", f"📝 Payload sauvegardé: {filename}")
        
        # Déclencher l'analyse automatique de cache (asynchrone, non-bloquant)
        _trigger_cache_analysis(filepath, session_type, model_name)
        
    except Exception as e:
        # Ne pas bloquer l'exécution si le log échoue
        UnifiedLogger.write("AI_CORE", "WARN", f"Echec sauvegarde payload: {e}")


# --- HELPER DE CONVERSION D'OUTILS ---
# --- HELPER DE CONVERSION D'OUTILS ---
def _convert_schema_to_openai(gemini_tools):
    """
    Convertit le schéma Gemini (TYPES MAJUSCULES) vers OpenAI/DeepSeek (types minuscules).
    """
    openai_tools = []
    if not gemini_tools: return None

    for tool in gemini_tools:
        tool_copy = json.loads(json.dumps(tool)) # Deep copy
        
        # Fonction récursive pour passer les types en minuscules
        def lower_types(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "type" and isinstance(v, str):
                        obj[k] = v.lower()
                    else:
                        lower_types(v)
            elif isinstance(obj, list):
                for item in obj:
                    lower_types(item)
        
        if "parameters" in tool_copy:
            lower_types(tool_copy["parameters"])
            
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool_copy["name"],
                "description": tool_copy.get("description", ""),
                "parameters": tool_copy.get("parameters", {"type": "object", "properties": {}})
            }
        })
    return openai_tools

def _proto_to_dict_recursive(obj):
    if hasattr(obj, 'items'): return {k: _proto_to_dict_recursive(v) for k, v in obj.items()}
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)): return [_proto_to_dict_recursive(v) for v in obj]
    else: return obj

class UniversalResponseWrapper:
    def __init__(self, text, raw_response=None, tool_calls=None):
        self.text = text if text else ""
        self.raw = raw_response
        self.tool_calls = tool_calls or []
        self.parts = [type('obj', (object,), {'text': self.text})]

class GroqSession:
    def __init__(self, key_manager, model_name="llama3-70b-8192", system_instruction=None, agent_name=None):
        self.key_mgr = key_manager
        self.model_name = model_name
        self.agent_name = agent_name
        self.system_instruction = system_instruction
        self.history = [] 
        self.current_key = None
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        
        if self.system_instruction:
            self.history.append({"role": "system", "content": self.system_instruction})

    @trace_action(source="sessions")
    def send_message(self, message, stream=False, tool_config=None, rag_context=None):
        self.current_key = self.key_mgr.get_key(self.model_name)
        if not self.current_key:
             raise FatalKeyError(f"Aucune clé Groq disponible pour {self.model_name}")

        # [V5] Gestion du RAG Context (Injecté dans le message utilisateur pour ne pas casser le cache système)
        text_content = message
        if not isinstance(text_content, str): text_content = str(message)
        
        final_message = text_content
        if rag_context:
            # Gérer le nouveau format dict ou l'ancien format string (compatibilité)
            if isinstance(rag_context, dict):
                # Construire le RAG context à partir du dict (sans Repo Map, déjà injectée en système)
                rag_parts = []
                # Note: Repo Map est déjà injectée dans le bloc système (via system_instruction)
                if rag_context.get("docs"):
                    docs_content = str(rag_context["docs"]).strip()
                    rag_parts.append(f"--- 📂 CONTEXTE RAG PERTINENT ---\n{docs_content}")
                # Note: LTM est déjà géré dans le bloc système
                rag_str = "\n\n".join(rag_parts) if rag_parts else ""
                if rag_str:
                    final_message = f"{rag_str}\n\n--- MESSAGE UTILISATEUR ---\n{text_content}"
            else:
                final_message = f"--- 📂 CONTEXTE RAG PERTINENT ---\n{rag_context}\n\n--- MESSAGE UTILISATEUR ---\n{text_content}"

        # Ajout User Message (avec RAG préfixé si disponible)
        self.history.append({"role": "user", "content": final_message})

        headers = {
            "Authorization": f"Bearer {self.current_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "messages": self.history,
            "stream": stream,
            "temperature": 0.7
        }

        # Payload Log (logs/) - Structure alignée sur DeepSeek (complet et bien structuré)
        messages_log = []
        
        # 1. INSTRUCTIONS AGENT (System) - comme DeepSeek
        if self.system_instruction:
            sys_content = str(self.system_instruction)
            messages_log.append({
                "role": "system",
                "content": f"=== INSTRUCTIONS AGENT ({self.model_name}) ===\n{sys_content}"
            })
        
        # 2. COMPOSANTS DU CACHE (System) - Arch, Tree, LTM - comme DeepSeek
        try:
            comps = GlobalCacheManager.get_components() if GlobalCacheManager else {}
        except Exception:
            comps = {}
        
        # EXTRACTION DE LA MÉMOIRE CONSOLIDÉE depuis l'historique (si présente)
        extracted_ltm = None
        for msg in self.history[:-1]:  # Exclure le dernier message (celui qu'on vient d'ajouter)
            if msg.get('role') == 'user':
                content = msg.get('content', '')
                if content and "--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---" in str(content):
                    # Extraire le contenu (enlever le header dupliqué)
                    ltm_content = str(content).replace("--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---", "", 1).strip()
                    # Enlever aussi "(Fin du Résumé - Reprise de la session ci-dessous)" si présent
                    ltm_content = ltm_content.replace("(Fin du Résumé - Reprise de la session ci-dessous)", "").strip()
                    if ltm_content:
                        extracted_ltm = ltm_content
                    break
        
        if comps.get('arch'):
            arch_content = str(comps['arch']).strip()
            # Enlever le header dupliqué si présent
            if arch_content.startswith("--- CARTOGRAPHIE TECHNIQUE ---"):
                arch_content = arch_content.replace("--- CARTOGRAPHIE TECHNIQUE ---", "", 1).strip()
            # Architecture map non tronquée
            messages_log.append({
                "role": "system",
                "content": f"--- CARTOGRAPHIE TECHNIQUE ---\n{arch_content}"
            })
        if comps.get('tree'):
            tree_content = str(comps['tree']).strip()
            # Enlever le header dupliqué si présent
            if tree_content.startswith("--- ARBORESCENCE PROJET ---"):
                tree_content = tree_content.replace("--- ARBORESCENCE PROJET ---", "", 1).strip()
            # Arborescence non tronquée
            messages_log.append({
                "role": "system",
                "content": f"--- ARBORESCENCE PROJET ---\n{tree_content}"
            })
        
        # MÉMOIRE LONG TERME : utiliser extracted_ltm si disponible, sinon comps.get('ltm')
        ltm_to_use = extracted_ltm
        if not ltm_to_use and comps.get('ltm'):
            ltm_content = str(comps['ltm']).strip()
            if ltm_content.startswith("--- MÉMOIRE LONG TERME ---"):
                ltm_content = ltm_content.replace("--- MÉMOIRE LONG TERME ---", "", 1).strip()
            ltm_to_use = ltm_content
        if ltm_to_use:
            # Nettoyer le header "--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---" s'il est présent
            ltm_clean = str(ltm_to_use).strip()
            if "--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---" in ltm_clean:
                ltm_clean = ltm_clean.replace("--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---", "", 1).strip()
            # Enlever aussi "(Fin du Résumé - Reprise de la session ci-dessous)" si présent
            ltm_clean = ltm_clean.replace("(Fin du Résumé - Reprise de la session ci-dessous)", "").strip()
            messages_log.append({
                "role": "system",
                "content": f"--- MÉMOIRE LONG TERME ---\n{ltm_clean}"
            })
        
        # 3. RAG CONTEXT retiré des messages système (pour maximiser le cache statique)
        # Le RAG Docs sera injecté dans le message utilisateur final_message ci-dessus
        # Note: Les blocs statiques (Repo Map, Tree, LTM) restent dans les messages système pour le cache
        
        # 4. HISTORIQUE CONVERSATIONNEL (User/Assistant) - comme DeepSeek
        # IMPORTANT: Nettoyer l'historique pour enlever le RAG dupliqué ET la mémoire consolidée
        # On reconstruit l'historique en excluant le message actuel (qui sera ajouté après)
        skip_next_ack = False  # Flag pour ignorer le message "Bien reçu" qui suit la mémoire consolidée
        for msg in self.history[:-1]:  # Exclure le dernier message (celui qu'on vient d'ajouter)
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            content_str = str(content)
            
            # NETTOYAGE: Si c'est un message user qui contient du RAG mélangé ou la mémoire consolidée, on l'extrait
            if role == 'user':
                # Ignorer les messages qui contiennent la mémoire consolidée (déjà extraite plus haut)
                if "--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---" in content_str:
                    skip_next_ack = True  # Le prochain message assistant sera l'ack "Bien reçu"
                    continue  # Skip ce message, il est déjà dans le message system LTM
                
                if '--- RAG CONTEXT ---' in content_str or '--- 📂 CONTEXTE RAG PERTINENT ---' in content_str:
                    # Pattern: "--- RAG CONTEXT ---\n...\n\n--- MESSAGE ---\n<message réel>"
                    if "--- MESSAGE ---" in content_str:
                        parts = content_str.split('--- MESSAGE ---')
                        if len(parts) > 1:
                            content = parts[-1].strip()
                    # Aussi nettoyer si le message contient "--- RAG CONTEXT ---" (même sans séparateur MESSAGE)
                    elif "--- RAG CONTEXT ---" in content_str:
                        # Si pas de séparateur, on cherche le début du contenu réel après RAG
                        # Pattern possible: "--- RAG CONTEXT ---\n\n--- 📂 DOCS TECHNIQUE ---\n..."
                        lines = content_str.split("\n")
                        in_rag = False
                        cleaned_lines = []
                        for i, line in enumerate(lines):
                            if "--- RAG CONTEXT ---" in line:
                                in_rag = True
                                continue
                            # Si on est dans RAG et qu'on trouve un pattern de contenu RAG, continuer à ignorer
                            if in_rag:
                                # Si on trouve "--- 📂" ou autre pattern de contenu RAG, continuer à ignorer
                                if "--- 📂" in line or "(Dist:" in line:
                                    continue
                                # Si ligne vide après RAG, on peut commencer à garder
                                if line.strip() == "":
                                    # Vérifier la ligne suivante
                                    if i + 1 < len(lines) and "--- 📂" not in lines[i + 1] and "(Dist:" not in lines[i + 1]:
                                        in_rag = False
                                    continue
                                # Si on trouve du contenu réel (pas de pattern RAG), on sort du mode RAG
                                if "--- 📂" not in line and "(Dist:" not in line:
                                    in_rag = False
                                    cleaned_lines.append(line)
                            else:
                                cleaned_lines.append(line)
                        content = "\n".join(cleaned_lines).strip()
                        # Si le contenu nettoyé est vide ou ne contient que des patterns RAG, on skip
                        if not content or content.startswith("--- 📂") or "(Dist:" in content[:50]:
                            continue
                    else:
                        content = content_str
                else:
                    content = content_str
            else:
                content = content_str
            
            # Ignorer le message assistant "Bien reçu" qui suit la mémoire consolidée
            if skip_next_ack and role == "assistant" and "Bien reçu. Mémoire mise à jour" in str(content):
                skip_next_ack = False
                continue
            
            if content:
                messages_log.append({"role": role, "content": str(content)[:3000]})
        
        # 5. INSTRUCTION FOCUS (System) - juste avant le dernier message user
        messages_log.append({
            "role": "system",
            "content": "⚠️ INSTRUCTION : Focus sur la demande ci-dessous."
        })
        
        # 6. MESSAGE ACTUEL (User) - avec RAG préfixé si disponible (pour le log, mais RAG n'est pas dans messages système)
        user_message_clean = final_message  # Utiliser final_message qui contient déjà le RAG préfixé
        if not isinstance(user_message_clean, str):
            user_message_clean = str(user_message_clean)
        messages_log.append({"role": "user", "content": user_message_clean[:5000]})
        
        groq_payload = {
            "model": self.model_name,
            "agent": self.agent_name,
            "messages": messages_log,
            "temperature": 0.7,
            "stream": stream
        }
        _save_payload_log("groq", self.model_name, groq_payload)

        UnifiedLogger.write("AI_CORE", "START", f"Groq ({self.model_name}) generating...", {"url": self.base_url})

        # Lazy import TokenManager
        try:
            from features.TokenManager import TokenManager
        except ImportError:
            TokenManager = None

        try:
            start_t = time.time()
            resp = requests.post(self.base_url, headers=headers, json=payload, stream=stream, timeout=60)

            if resp.status_code != 200:
                self.key_mgr.report_error(self.current_key, exception=f"HTTP {resp.status_code}", model_name=self.model_name)
                raise Exception(f"Groq Error {resp.status_code}: {resp.text}")

            self.key_mgr.mark_success(self.current_key, self.model_name)
            # Estimation Entrée
            in_tok = sum(len(m['content']) for m in self.history) // 4

            full_response_text = ""

            if stream:
                def groq_generator():
                    nonlocal full_response_text
                    try:
                        for line in resp.iter_lines():
                            if line:
                                decoded = line.decode('utf-8').replace('data: ', '').strip()
                                if decoded == '[DONE]': break
                                try:
                                    json_chunk = json.loads(decoded)
                                    chunk_content = json_chunk['choices'][0]['delta'].get('content', '')
                                    if chunk_content:
                                        full_response_text += chunk_content
                                        yield chunk_content
                                except: pass
                    except Exception as e:
                        UnifiedLogger.write("AI_CORE", "ERROR", f"Groq Stream Interrompu: {e}")
                        yield f"\n[Erreur Stream: {e}]"

                    # Fin Stream : Sauvegarde et Métriques
                    self.history.append({"role": "assistant", "content": full_response_text})
                    
                    duration = time.time() - start_t
                    out_tok = len(full_response_text) // 4
                    if TokenManager: TokenManager.add_usage(self.model_name, self.current_key, in_tok, out_tok)
                    
                    metrics_data = {
                        "model": self.model_name, 
                        "agent": self.agent_name or "Groq Agent", # <--- Fallback ajouté
                        "in": in_tok, 
                        "out": out_tok, 
                        "time": f"{duration:.2f}s",
                        "provider": "Groq"
                    }
                    UnifiedLogger.write("AI_CORE", "METRICS", "Usage", metrics_data)
                    UnifiedLogger.write("AI_CORE", "SUCCESS", f"Groq Stream terminé ({duration:.2f}s)")

                return groq_generator()

            else:
                # Mode Standard
                data = resp.json()
                content = data['choices'][0]['message']['content']
                self.history.append({"role": "assistant", "content": content})
                
                usage = data.get('usage', {})
                prompt_tok = usage.get('prompt_tokens', in_tok)
                comp_tok = usage.get('completion_tokens', len(content)//4)
                duration = time.time() - start_t
                
                if TokenManager: TokenManager.add_usage(self.model_name, self.current_key, prompt_tok, comp_tok)
                
                metrics_data = {
                    "model": self.model_name, 
                    "agent": self.agent_name, # <--- AJOUT CRUCIAL
                    "in": prompt_tok, 
                    "out": comp_tok, 
                    "time": f"{duration:.2f}s",
                    "provider": "Groq"
                }
                UnifiedLogger.write("AI_CORE", "METRICS", "Usage", metrics_data)
                UnifiedLogger.write("AI_CORE", "SUCCESS", f"Groq terminé ({duration:.2f}s)")
                
                return UniversalResponseWrapper(content, data)

        except Exception as e:
            UnifiedLogger.write("AI_CORE", "ERROR", f"Groq Exception: {e}")
            self.key_mgr.report_error(self.current_key, exception=e, model_name=self.model_name)
            raise e

    @property
    def chat(self):
        # Mock pour compatibilité interface
        class MockHistory:
            def __init__(self, h): 
                self.history = []
                for x in h:
                    if x['role'] != 'system':
                        role = 'model' if x['role'] == 'assistant' else 'user'
                        self.history.append(type('o',(),{'role': role, 'parts':[type('p',(),{'text':x['content']})]}))
            def rewind(self): pass
        return MockHistory(self.history)
class BaseSession:
    """Interface commune pour toutes les sessions."""
    def __init__(self, key_manager, model_name, system_instruction):
        self.key_manager = key_manager
        self.model_name = model_name
        self.system_instruction = system_instruction
        self.history = []

    def send_message(self, message, stream=True, tool_config=None, rag_context=None):
        """
        Envoie un message à l'API.
        Args:
            rag_context: (Nouveau V5) Contenu RAG à injecter séparément ou à fusionner.
        """
        raise NotImplementedError
# --- CLASSE DEEPSEEK MISE A JOUR ---
class DeepSeekSession(BaseSession):
    def __init__(self, key_manager, model_name="deepseek-chat", system_instruction=None, base_url=None, agent_name=None):
        self.key_mgr = key_manager
        self.model_name = model_name
        self.agent_name = agent_name
        self.system_instruction = system_instruction
        self.current_key = None
        self.history = [] 

        # --- ROUTING ENDPOINT ---
        if base_url:
            raw_url = base_url
        elif "speciale" in model_name.lower():
            raw_url = "https://api.deepseek.com/v3.2_speciale_expires_on_20251215"
            UnifiedLogger.write("AI_CORE", "CONFIG", f"🚀 DeepSeek Speciale Endpoint déduit pour {model_name}")
        else:
            raw_url = "https://api.deepseek.com"

        if raw_url.endswith("/chat/completions"):
            self.base_url = raw_url
        else:
            self.base_url = f"{raw_url.rstrip('/')}/chat/completions"

    def _create_msg(self, role, text):
        return {"role": role, "content": text}

    def _build_payload_messages(self, rag_context=None):
        """
        Construction Atomique du Payload (Architecture V5).
        Ordre : [Instructions] -> [Arch] -> [Tree] -> [RAG] -> [Historique]
        
        Pour les sessions Writer (documentation), payload minimal : seulement architecture map.
        """
        messages = []
        
        # Détection session Writer (documentation) : agent_name contient "Writer" ou "writer" dans le nom
        # La factory crée les sessions avec agent_name = model_type.capitalize() si non fourni
        is_writer_session = (
            self.agent_name and "writer" in self.agent_name.lower()
        ) or (
            hasattr(self, '_is_writer') and self._is_writer
        ) or (
            hasattr(self, 'model_type') and self.model_type and "writer" in str(self.model_type).lower()
        )
        
        # --- BLOC 1 : INSTRUCTIONS AGENTS (System) ---
        if self.system_instruction:
            messages.append({"role": "system", "content": f"=== INSTRUCTIONS AGENT ({self.model_name}) ===\n{self.system_instruction}"})

        # --- BLOCS DYNAMIQUES (System) ---
        try:
            from features.CacheManager import GlobalCacheManager
            comps = GlobalCacheManager.get_components()
            
            if is_writer_session:
                # SESSION WRITER : Payload minimal (seulement architecture map)
                if comps.get('arch'):
                    arch_content = str(comps['arch']).strip()
                    # Enlever le header dupliqué si présent
                    if arch_content.startswith("--- CARTOGRAPHIE TECHNIQUE ---"):
                        arch_content = arch_content.replace("--- CARTOGRAPHIE TECHNIQUE ---", "", 1).strip()
                    messages.append({
                        "role": "system",
                        "content": f"--- CARTOGRAPHIE TECHNIQUE ---\n{arch_content}"
                    })
            else:
                # SESSION NORMALE : Tous les blocs statiques
                # BLOC 2 : REPO MAP (remplace CARTOGRAPHIE TECHNIQUE)
                # Utiliser la Repo Map du cache (composant statique), sinon fallback sur arch
                if comps.get('repo_map'):
                    repo_map_content = str(comps['repo_map']).strip()
                    messages.append({"role": "system", "content": repo_map_content})
                elif comps.get('arch'):
                    # Fallback sur l'ancienne cartographie technique si pas de Repo Map
                    arch_content = str(comps['arch']).strip()
                    if arch_content.startswith("--- CARTOGRAPHIE TECHNIQUE ---"):
                        arch_content = arch_content.replace("--- CARTOGRAPHIE TECHNIQUE ---", "", 1).strip()
                    messages.append({"role": "system", "content": f"--- CARTOGRAPHIE TECHNIQUE ---\n{arch_content}"})
                
                # BLOC 3 : ARBORESCENCE PROJET
                if comps.get('tree'):
                    messages.append({"role": "system", "content": comps['tree']})
                    
                # (Optionnel) LTM dans le système
                if comps.get('ltm'):
                    messages.append({"role": "system", "content": comps['ltm']})

        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARNING", f"Echec assemblage composants CacheManager: {e}")

        # --- BLOC 4 : RAG Docs retiré des messages système (pour maximiser le cache statique) ---
        # Le RAG Docs sera injecté dans le message utilisateur dans send_message() pour ne pas invalider le cache
        # Note: Les blocs statiques (Repo Map, Tree, LTM) restent dans les messages système pour le cache

        # --- BLOCS 5 à N : HISTORIQUE CONVERSATIONNEL ---
        history_len = len(self.history)
        
        for i, msg in enumerate(self.history):
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
            
            if role == 'system': continue # On ne réinjecte pas les vieux messages système
            if role == 'model': role = 'assistant'

            # Injection Safety au dernier tour utilisateur (Bloc N)
            if i == history_len - 1 and role == 'user':
                # Petit rappel système discret juste avant le message final
                messages.append({"role": "system", "content": "⚠️ INSTRUCTION : Focus sur la demande ci-dessous."})

            messages.append({"role": role, "content": content})
            
        return messages

    @trace_action(source="sessions")
    def send_message(self, message, stream=False, tool_config=None, rag_context=None):
        self.current_key = self.key_mgr.get_key(self.model_name)
        if not self.current_key: 
            raise FatalKeyError(f"Aucune clé DeepSeek disponible pour {self.model_name}")
        
        # Construire le message utilisateur avec préfixe RAG si disponible (pour ne pas casser le cache système)
        user_message_content = message
        if rag_context:
            # Gérer le nouveau format dict ou l'ancien format string (compatibilité)
            if isinstance(rag_context, dict):
                # Nouveau format : seulement Docs Techniques (Repo Map déjà dans messages système)
                if rag_context.get("docs"):
                    docs_content = str(rag_context["docs"]).strip()
                    user_message_content = f"--- 📂 CONTEXTE RAG PERTINENT ---\n{docs_content}\n\n--- MESSAGE UTILISATEUR ---\n{message}"
            else:
                # Ancien format string (compatibilité)
                user_message_content = f"--- 📂 CONTEXTE RAG PERTINENT ---\n{rag_context}\n\n--- MESSAGE UTILISATEUR ---\n{message}"
        
        # Ajout du message utilisateur à l'historique (Bloc N) avec RAG préfixé
        self.history.append(self._create_msg("user", user_message_content))
        
        headers = {
            "Authorization": f"Bearer {self.current_key}", 
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Outils Natifs
        try:
            from config.tools_schema import TOOLS_SCHEMA
        except ImportError:
            TOOLS_SCHEMA = []
        native_tools = _convert_schema_to_openai(TOOLS_SCHEMA)

        # Construction du Payload Structuré (SANS RAG Docs dans messages système pour maximiser le cache)
        final_messages = self._build_payload_messages(rag_context=None)
        
        api_model_name = "deepseek-reasoner" if "reasoner" in self.model_name.lower() else "deepseek-chat"
        
        payload = {
            "model": api_model_name,
            "agent": self.agent_name,
            "messages": final_messages,
            "temperature": 1.3 if "coder" in self.model_name.lower() else 0.7,
            "max_tokens": 8000,
            "stream": stream
        }
        
        if native_tools: payload["tools"] = native_tools
        if stream: payload["stream_options"] = {"include_usage": True}

        # Payload Log (logs/) - Payload complet déjà bien structuré
        _save_payload_log("deepseek", self.model_name, payload)

        UnifiedLogger.write("AI_CORE", "START", f"DeepSeek ({self.model_name}) thinking...")

        try:
            start_t = time.time()
            resp = requests.post(self.base_url, headers=headers, json=payload, stream=stream, timeout=120)
            
            if resp.status_code != 200:
                self.key_mgr.report_error(self.current_key, exception=f"HTTP {resp.status_code}", model_name=self.model_name)
                raise Exception(f"DeepSeek Error {resp.status_code}: {resp.text}")

            self.key_mgr.mark_success(self.current_key, self.model_name)
            
            full_response_text = ""
            usage_data = None 

            if stream:
                def deepseek_generator():
                    nonlocal full_response_text, usage_data
                    tool_calls_buffer = {} 

                    with contextlib.closing(resp):
                        try:
                            for line in resp.iter_lines():
                                if line:
                                    decoded = line.decode('utf-8')
                                    if decoded.startswith("data: "): decoded = decoded[6:]
                                    if decoded.strip() == '[DONE]': break
                                    
                                    try:
                                        json_chunk = json.loads(decoded)
                                        if len(json_chunk['choices']) > 0:
                                            delta = json_chunk['choices'][0]['delta']
                                            
                                            # Contenu & Raisonnement
                                            reason = delta.get('reasoning_content', '')
                                            content = delta.get('content', '')
                                            
                                            combined = ""
                                            if reason: combined += reason.replace("!native_tool", "(thought) tool")
                                            if content: combined += content
                                            
                                            if combined:
                                                full_response_text += combined
                                                yield combined
                                            
                                            # Tool Calls
                                            if 'tool_calls' in delta and delta['tool_calls']:
                                                for tc in delta['tool_calls']:
                                                    idx = tc['index']
                                                    if idx not in tool_calls_buffer:
                                                        tool_calls_buffer[idx] = {"name": "", "args": ""}
                                                    
                                                    if 'function' in tc:
                                                        fn = tc['function']
                                                        if 'name' in fn: tool_calls_buffer[idx]['name'] += fn['name']
                                                        if 'arguments' in fn: tool_calls_buffer[idx]['args'] += fn['arguments']
                                        
                                        if 'usage' in json_chunk: usage_data = json_chunk['usage']
                                    except: pass
                        except Exception as e:
                            yield f"\n[Erreur Stream: {e}]"

                    # Injection des commandes
                    for idx in sorted(tool_calls_buffer.keys()):
                        tool = tool_calls_buffer[idx]
                        try:
                            args_obj = json.loads(tool['args']) if tool['args'] else {}
                            cmd_str = f"\n!native_tool {json.dumps({'name': tool['name'], 'args': args_obj}, ensure_ascii=False)}\n"
                            full_response_text += cmd_str
                            yield cmd_str
                        except: pass

                    self.history.append(self._create_msg("assistant", full_response_text))
                    
                    # Metrics
                    in_tok = usage_data.get('prompt_tokens', 0) if usage_data else 0
                    out_tok = usage_data.get('completion_tokens', 0) if usage_data else 0
                    cache_hit = usage_data.get('prompt_cache_hit_tokens', 0) if usage_data else 0
                    cache_miss = usage_data.get('prompt_cache_miss_tokens', in_tok) if usage_data else 0
                    
                    try:
                        from features.TokenManager import TokenManager
                        if TokenManager: TokenManager.add_usage(self.model_name, self.current_key, in_tok, out_tok)
                    except: pass
                    
                    # ... (intérieur de deepseek_generator) ...
                    
                    savings = int((cache_hit / in_tok * 100)) if in_tok > 0 else 0
                    
                    # --- CORRECTION DEBUT ---
                    # On construit un objet metrics complet pour que le Logger sache qui parle
                    metrics_data = {
                        "model": self.model_name,
                        "agent": self.agent_name or "DeepSeek Agent", # Fallback si le nom est vide
                        "provider": "DeepSeek",
                        "in": in_tok, 
                        "out": out_tok, 
                        "cache_hit": cache_hit, 
                        "billed": cache_miss,
                        "savings": f"{savings}%",
                        "time": f"{time.time() - start_t:.2f}s"
                    }
                    
                    # On envoie metrics_data au lieu du dictionnaire incomplet
                    UnifiedLogger.write("AI_CORE", "METRICS", f"DeepSeek {savings}%", metrics_data)
                    UnifiedLogger.write("AI_CORE", "SUCCESS", f"DeepSeek Stream terminé")
                    # --- CORRECTION FIN ---
                
                return deepseek_generator()
            else:
                # Mode Non-Stream
                data = resp.json()
                msg = data['choices'][0]['message']
                content = msg.get('content') or ""
                
                # --- GESTION RETRO-COMPATIBLE DES OUTILS NATIFS ---
                tool_calls = msg.get('tool_calls', [])
                if tool_calls:
                    for tc in tool_calls:
                        func = tc.get('function', {})
                        fname = func.get('name')
                        fargs = func.get('arguments')
                        try:
                            # On s'assure que les arguments sont bien du JSON valide
                            parsed_args = json.loads(fargs) if isinstance(fargs, str) else fargs
                            content += f"\n!native_tool {json.dumps({'name': fname, 'args': parsed_args}, ensure_ascii=False)}\n"
                        except:
                            pass

                self.history.append(self._create_msg("assistant", content))
                
                # Metrics
                try:
                    from features.TokenManager import TokenManager
                except ImportError:
                    TokenManager = None
                usage = data.get('usage', {})
                in_tok = usage.get('prompt_tokens', 0)
                out_tok = usage.get('completion_tokens', 0)
                cache_hit = usage.get('prompt_cache_hit_tokens', 0)
                cache_miss = usage.get('prompt_cache_miss_tokens', in_tok)
                
                duration = time.time() - start_t
                if TokenManager: TokenManager.add_usage(self.model_name, self.current_key, in_tok, out_tok)
                
                savings = int((cache_hit / in_tok * 100)) if in_tok > 0 else 0
                
                if cache_hit > 0:
                    UnifiedLogger.write("AI_CORE", "CACHE_HIT", f"⚡ Cache Hit: {cache_hit} | 💲 Payés: {cache_miss} (Éco: {savings}%)")
                else:
                    UnifiedLogger.write("AI_CORE", "CACHE_MISS", f"💲 Payés: {cache_miss} (Full Miss)")

                metrics_data = {
                    "model": self.model_name,
                    "agent": self.agent_name or "DeepSeek Agent",  # <--- Fallback ajouté
                    "in": in_tok,
                    "out": out_tok,
                    "cache_hit": cache_hit,  # Valeur entière pure pour éviter le bug de conversion
                    "billed": cache_miss,
                    "time": f"{duration:.2f}s",
                    "provider": "DeepSeek"
                }
                UnifiedLogger.write("AI_CORE", "METRICS", "Usage", metrics_data)
                UnifiedLogger.write("AI_CORE", "SUCCESS", f"DeepSeek terminé ({duration:.2f}s)")
                
                return UniversalResponseWrapper(content, data)

        except Exception as e:
            self.key_mgr.report_error(self.current_key, exception=e, model_name=self.model_name)
            raise e

    @property
    def chat(self):
        class ChatInterface:
            def __init__(self, session): self.session = session
            @property
            def history(self): return self.session.history
            @history.setter
            def history(self, val): self.session.history = val
            def rewind(self): 
                if self.session.history: self.session.history.pop()
        return ChatInterface(self)
class GeminiSession:
    def __init__(self, key_manager, model_name="gemini-2.5-flash", agent_name=None, system_instruction=None, enable_tools=True, cache_name=None, safety_settings=None, fallback_models=None):
        self.key_mgr = key_manager
        self.model_name = model_name
        self.agent_name = agent_name
        self.system_instruction = system_instruction
        self.enable_tools = enable_tools
        self.cache_name = cache_name 
        self.chat = None
        self.current_key = None
        self.fallback_models = fallback_models if fallback_models else []
        
        try:
            self._init_chat()
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARNING", f"Echec init primaire ({model_name}): {e}")
            if not self._try_fallback():
                raise

    @trace_action(source="sessions")
    def _init_chat(self, key=None):
        """
        Initialise la session. 
        Args:
            key: Si fourni, force l'utilisation de cette clé (utile pour la rotation).
        """
        try:
            if not key:
                key = self.key_mgr.get_key(self.model_name)
            
            if not key: raise FatalKeyError(f"Aucune clé disponible pour {self.model_name}")
            self.current_key = key
            
            genai.configure(api_key=key)
            tools = TOOLS_SCHEMA if self.enable_tools else None
            
            target_cache = self.cache_name
            if not target_cache and GlobalCacheManager:
                try: target_cache = GlobalCacheManager.get_or_create_cache(key, self.model_name)
                except: pass
            
            model = None
            if target_cache:
                try:
                    cc = caching.CachedContent.get(name=target_cache)
                    model = genai.GenerativeModel.from_cached_content(cached_content=cc, tools=tools)
                except: pass

            if not model:
                model = genai.GenerativeModel(
                    model_name=self.model_name, 
                    system_instruction=self.system_instruction, 
                    tools=tools
                )
            
            # Préservation de l'historique lors de la rotation/ré-init
            history = []
            if self.chat and hasattr(self.chat, 'history'):
                history = self.chat.history

            self.chat = model.start_chat(history=history, enable_automatic_function_calling=False)
            
            # On loggue l'init mais on ne déduit pas de points de santé ici (seulement au succès d'une requête)
            UnifiedLogger.write("AI_CORE", "INFO", f"Session {self.model_name} initialisée avec clé ...{key[-6:]}")
            
        except FatalKeyError: raise
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "ERROR", f"Init Error ({self.model_name}): {e}")
            if self.current_key: self.key_mgr.report_error(self.current_key, exception=e, model_name=self.model_name)
            raise

    def _try_fallback(self):
        while self.fallback_models:
            next_model = self.fallback_models.pop(0)
            UnifiedLogger.write("AI_CORE", "WARNING", f"🔄 Bascule Cascade: {self.model_name} -> {next_model}")
            self.model_name = next_model
            try:
                self._init_chat()
                return True
            except Exception as e:
                continue
        return False

    @trace_action(source="sessions")
    def send_message(self, message, stream=False, tool_config=None, rag_context=None):
        # OPTIMISATION: Retry dynamique basé sur le nombre de clés disponibles.
        max_retries = max(3, self.key_mgr.num_keys + 1)
        retry_count = 0
        start_t = time.time()
        
        # --- FIX V24: AUTO-WRAPPING TOOL RESPONSE ---
        try:
            if self.chat and self.chat.history:
                last_msg = self.chat.history[-1]
                if last_msg.role == 'model' and hasattr(last_msg, 'parts'):
                    fn_call_part = None
                    for part in last_msg.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            fn_call_part = part.function_call
                            break
                    
                    if fn_call_part and isinstance(message, str):
                        UnifiedLogger.write("AI_CORE", "INFO", f"📦 Wrapping Tool Response pour : {fn_call_part.name}")
                        message = {
                            "function_response": {
                                "name": fn_call_part.name,
                                "response": {"result": message}
                            }
                        }
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARNING", f"Echec Auto-Wrap Tool: {e}")
        # ---------------------------------------------

        # [V5] Gestion du RAG Context (Injecté dans le message utilisateur pour ne pas casser le cache système)
        text_content = message  # Initialiser text_content AVANT le if
            # Gestion basique si le message est complexe (dict/objet)
        if not isinstance(text_content, str): 
            text_content = str(message)
        
        final_message = text_content
        if rag_context:
            # Gérer le nouveau format dict ou l'ancien format string (compatibilité)
            if isinstance(rag_context, dict):
                # Construire le RAG context à partir du dict (sans Repo Map, déjà injectée en système)
                rag_parts = []
                # Note: Repo Map est déjà injectée dans le bloc système (via system_instruction)
                if rag_context.get("docs"):
                    docs_content = str(rag_context["docs"]).strip()
                    rag_parts.append(f"--- 📂 CONTEXTE RAG PERTINENT ---\n{docs_content}")
                # Note: LTM est déjà géré dans le bloc système
                rag_str = "\n\n".join(rag_parts) if rag_parts else ""
                if rag_str:
                    final_message = f"{rag_str}\n\n--- MESSAGE UTILISATEUR ---\n{text_content}"
            else:
                final_message = f"--- 📂 CONTEXTE RAG PERTINENT ---\n{rag_context}\n\n--- MESSAGE UTILISATEUR ---\n{text_content}"

        # Payload Log (logs/) - Structure alignée sur DeepSeek (complet et bien structuré)
        # Skip si c'est un appel depuis le compresseur (qui a son propre log)
        if not getattr(self, '_skip_payload_log', False):
            messages_log = []
            
            # 1. INSTRUCTIONS AGENT (System) - comme DeepSeek
            if self.system_instruction:
                sys_content = str(self.system_instruction)
                messages_log.append({
                    "role": "system",
                    "content": f"=== INSTRUCTIONS AGENT ({self.model_name}) ===\n{sys_content}"
                })
            
            # 2. COMPOSANTS DU CACHE (System) - Arch, Tree, LTM - comme DeepSeek
            try:
                comps = GlobalCacheManager.get_components() if GlobalCacheManager else {}
            except Exception:
                comps = {}
            
            # EXTRACTION DE LA MÉMOIRE CONSOLIDÉE depuis l'historique (si présente)
            extracted_ltm = None
            if self.chat and self.chat.history:
                for msg in self.chat.history:
                    if getattr(msg, 'role', '') == 'user':
                        content = ""
                        if hasattr(msg, 'parts'):
                            for part in msg.parts:
                                if hasattr(part, 'text') and part.text:
                                    content += part.text
                        if content and "--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---" in content:
                            # Extraire le contenu (enlever le header dupliqué)
                            ltm_content = content.replace("--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---", "", 1).strip()
                            # Enlever aussi "(Fin du Résumé - Reprise de la session ci-dessous)" si présent
                            ltm_content = ltm_content.replace("(Fin du Résumé - Reprise de la session ci-dessous)", "").strip()
                            if ltm_content:
                                extracted_ltm = ltm_content
                            break
            
            # BLOC 2 : REPO MAP (remplace CARTOGRAPHIE TECHNIQUE)
            # Utiliser la Repo Map du cache (composant statique), sinon fallback sur arch
            if comps.get('repo_map'):
                repo_map_content = str(comps['repo_map']).strip()
                messages_log.append({
                    "role": "system",
                    "content": repo_map_content
                })
            elif comps.get('arch'):
                # Fallback sur l'ancienne cartographie technique si pas de Repo Map
                arch_content = str(comps['arch']).strip()
                # Enlever le header dupliqué si présent
                if arch_content.startswith("--- CARTOGRAPHIE TECHNIQUE ---"):
                    arch_content = arch_content.replace("--- CARTOGRAPHIE TECHNIQUE ---", "", 1).strip()
                # Architecture map non tronquée
                messages_log.append({
                    "role": "system",
                    "content": f"--- CARTOGRAPHIE TECHNIQUE ---\n{arch_content}"
                })
            if comps.get('tree'):
                tree_content = str(comps['tree']).strip()
                # Enlever le header dupliqué si présent
                if tree_content.startswith("--- ARBORESCENCE PROJET ---"):
                    tree_content = tree_content.replace("--- ARBORESCENCE PROJET ---", "", 1).strip()
                # Arborescence non tronquée
                messages_log.append({
                    "role": "system",
                    "content": f"--- ARBORESCENCE PROJET ---\n{tree_content}"
                })
            
            # MÉMOIRE LONG TERME : utiliser extracted_ltm si disponible, sinon comps.get('ltm')
            ltm_to_use = extracted_ltm
            if not ltm_to_use and comps.get('ltm'):
                ltm_content = str(comps['ltm']).strip()
                if ltm_content.startswith("--- MÉMOIRE LONG TERME ---"):
                    ltm_content = ltm_content.replace("--- MÉMOIRE LONG TERME ---", "", 1).strip()
                ltm_to_use = ltm_content
            if ltm_to_use:
                # Nettoyer le header "--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---" s'il est présent
                ltm_clean = str(ltm_to_use).strip()
                if "--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---" in ltm_clean:
                    ltm_clean = ltm_clean.replace("--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---", "", 1).strip()
                # Enlever aussi "(Fin du Résumé - Reprise de la session ci-dessous)" si présent
                ltm_clean = ltm_clean.replace("(Fin du Résumé - Reprise de la session ci-dessous)", "").strip()
                messages_log.append({
                    "role": "system",
                    "content": f"--- MÉMOIRE LONG TERME ---\n{ltm_clean}"
                })
            
            # 3. RAG CONTEXT retiré des messages système (pour maximiser le cache statique)
            # Le RAG Docs sera injecté dans le message utilisateur final_message ci-dessous
            # Note: Les blocs statiques (Repo Map, Tree, LTM) restent dans les messages système pour le cache
            
            # 4. HISTORIQUE CONVERSATIONNEL (User/Assistant) - comme DeepSeek
            # IMPORTANT: Nettoyer l'historique pour enlever le RAG dupliqué ET la mémoire consolidée
            if self.chat and self.chat.history:
                skip_next_ack = False  # Flag pour ignorer le message "Bien reçu" qui suit la mémoire consolidée
                for msg in self.chat.history:
                    role = "assistant" if getattr(msg, 'role', '') == 'model' else "user"
                    content = ""
                    if hasattr(msg, 'parts'):
                        for part in msg.parts:
                            if hasattr(part, 'text') and part.text:
                                content += part.text
                            # Gestion des tool calls dans l'historique
                            if hasattr(part, 'function_call') and part.function_call:
                                try:
                                    args = _proto_to_dict_recursive(part.function_call.args)
                                    content += f"\n!native_tool {json.dumps({'name': part.function_call.name, 'args': args}, ensure_ascii=False)}\n"
                                except:
                                    pass
                    
                    # NETTOYAGE: Si c'est un message user qui contient du RAG mélangé ou la mémoire consolidée, on l'extrait
                    if content and role == "user":
                        # Ignorer les messages qui contiennent la mémoire consolidée (déjà extraite plus haut)
                        if "--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---" in content:
                            skip_next_ack = True  # Le prochain message assistant sera l'ack "Bien reçu"
                            continue  # Skip ce message, il est déjà dans le message system LTM
                        
                        # Pattern: "--- RAG CONTEXT ---\n...\n\n--- MESSAGE ---\n<message réel>"
                        if "--- RAG CONTEXT ---" in content and "--- MESSAGE ---" in content:
                            parts = content.split("--- MESSAGE ---")
                            if len(parts) > 1:
                                content = parts[-1].strip()  # Garder seulement la partie après "--- MESSAGE ---"
                        # Aussi nettoyer si le message contient "--- RAG CONTEXT ---" (même sans séparateur MESSAGE)
                        elif "--- RAG CONTEXT ---" in content:
                            # Chercher la fin du bloc RAG
                            if "--- MESSAGE ---" in content:
                                parts = content.split("--- MESSAGE ---")
                                content = parts[-1].strip() if len(parts) > 1 else ""
                            else:
                                # Si pas de séparateur, on cherche le début du contenu réel après RAG
                                # Pattern possible: "--- RAG CONTEXT ---\n\n--- 📂 DOCS TECHNIQUE ---\n..."
                                lines = content.split("\n")
                                in_rag = False
                                cleaned_lines = []
                                for i, line in enumerate(lines):
                                    if "--- RAG CONTEXT ---" in line:
                                        in_rag = True
                                        continue
                                    # Si on est dans RAG et qu'on trouve un pattern de contenu RAG, continuer à ignorer
                                    if in_rag:
                                        # Si on trouve "--- 📂" ou autre pattern de contenu RAG, continuer à ignorer
                                        if "--- 📂" in line or "(Dist:" in line:
                                            continue
                                        # Si ligne vide après RAG, on peut commencer à garder
                                        if line.strip() == "":
                                            # Vérifier la ligne suivante
                                            if i + 1 < len(lines) and "--- 📂" not in lines[i + 1] and "(Dist:" not in lines[i + 1]:
                                                in_rag = False
                                            continue
                                        # Si on trouve du contenu réel (pas de pattern RAG), on sort du mode RAG
                                        if "--- 📂" not in line and "(Dist:" not in line:
                                            in_rag = False
                                            cleaned_lines.append(line)
                                    else:
                                        cleaned_lines.append(line)
                                content = "\n".join(cleaned_lines).strip()
                                # Si le contenu nettoyé est vide ou ne contient que des patterns RAG, on skip
                                if not content or content.startswith("--- 📂") or "(Dist:" in content[:50]:
                                    continue
                    
                    # Ignorer le message assistant "Bien reçu" qui suit la mémoire consolidée
                    if skip_next_ack and role == "assistant" and "Bien reçu. Mémoire mise à jour" in content:
                        skip_next_ack = False
                        continue
                    
                    if content:
                        messages_log.append({"role": role, "content": content[:3000]})
            
            # 5. INSTRUCTION FOCUS (System) - juste avant le dernier message user
            messages_log.append({
                "role": "system",
                "content": "⚠️ INSTRUCTION : Focus sur la demande ci-dessous."
            })
            
            # 6. MESSAGE ACTUEL (User) - avec RAG préfixé si disponible (pour le log, mais RAG n'est pas dans messages système)
            user_message_clean = final_message  # Utiliser final_message qui contient déjà le RAG préfixé
            if not isinstance(user_message_clean, str):
                user_message_clean = str(user_message_clean)
            messages_log.append({"role": "user", "content": user_message_clean[:5000]})
            
            # Reconstruction du payload complet (structure DeepSeek-like)
            gemini_payload = {
                "model": self.model_name,
                "agent": self.agent_name,
                "messages": messages_log,
                "temperature": 0.7,  # Valeur par défaut Gemini
                "stream": stream,
                "tools_enabled": self.enable_tools,
                "tool_config": str(tool_config) if tool_config else None
            }
            _save_payload_log("gemini", self.model_name, gemini_payload)

        UnifiedLogger.write("AI_CORE", "START", f"Gemini ({self.model_name}) generating...", {"prompt_preview": str(final_message)[:100]})
        
        while retry_count < max_retries:
            try:
                # Utilisation de final_message qui contient le RAG si présent
                response = self.chat.send_message(final_message, stream=stream, tool_config=tool_config)
                
                # --- SUCCES ---
                if not stream: 
                    self.key_mgr.mark_success(self.current_key, self.model_name)
                    self._log_metrics(start_t, response)
                    text = ""
                    tools = []
                    if hasattr(response, 'parts'):
                        for p in response.parts:
                            if p.function_call:
                                args = _proto_to_dict_recursive(p.function_call.args)
                                tools.append({'function': {'name': p.function_call.name, 'arguments': args}})
                                text += f"\n!native_tool {json.dumps({'name': p.function_call.name, 'args': args}, ensure_ascii=False)}\n"
                            if p.text: text += p.text
                    if not text and not tools: text = "[⚠️ Réponse vide]"
                    return UniversalResponseWrapper(text, response, tool_calls=tools)

                else: # Stream
                    def stream_wrapper():
                        full_text_acc = ""
                        has_content = False
                        try:
                            for chunk in response:
                                if hasattr(chunk, 'parts'):
                                    for part in chunk.parts:
                                        if part.function_call:
                                            try:
                                                args = _proto_to_dict_recursive(part.function_call.args)
                                                yield f"\n!native_tool {json.dumps({'name': part.function_call.name, 'args': args}, ensure_ascii=False)}\n"
                                                has_content = True
                                            except: pass
                                        
                                        if part.text:
                                            full_text_acc += part.text
                                            yield part.text
                                            has_content = True
                                
                                if hasattr(chunk, 'prompt_feedback') and chunk.prompt_feedback:
                                    if chunk.prompt_feedback.block_reason:
                                        yield f"\n[⚠️ Vrai Blocage: {chunk.prompt_feedback.block_reason}]\n"

                            if not has_content: yield "\n[⚠️ Flux vide]"
                            
                            self.key_mgr.mark_success(self.current_key, self.model_name)
                            duration = time.time() - start_t
                            
                            in_tok = 0
                            out_tok = len(full_text_acc) // 4 
                            try:
                                if hasattr(response, 'usage_metadata'):
                                    in_tok = response.usage_metadata.prompt_token_count
                                    out_tok = response.usage_metadata.candidates_token_count
                            except: pass
                            
                            try:
                                from features.TokenManager import TokenManager
                            except ImportError: TokenManager = None
                            
                            if TokenManager:
                                TokenManager.add_usage(self.model_name, self.current_key, in_tok, out_tok)
                            
                            # --- CORRECTION FINALE LOGS ---
                            # On force l'utilisation de self.agent_name s'il existe
                            final_agent_name = self.agent_name if self.agent_name else "Gemini"
                            
                            metrics_data = {
                                "model": self.model_name,
                                "agent": final_agent_name, # <--- ICI
                                "in": in_tok, 
                                "out": out_tok, 
                                "time": f"{duration:.2f}s",
                                "provider": "Gemini"
                            }
                            UnifiedLogger.write("AI_CORE", "METRICS", "Usage", metrics_data)
                            UnifiedLogger.write("AI_CORE", "SUCCESS", f"Gemini Stream terminé ({duration:.2f}s)")
                        
                        except Exception as e:
                            UnifiedLogger.write("AI_CORE", "ERROR", f"Stream Broken: {e}")
                            yield f"\n[Erreur Flux: {str(e)}]"
                            
                    return stream_wrapper()

            except Exception as e:
                # --- ROTATION INTELLIGENTE "ZERO-BLOCK" ---
                if self.chat:
                    try:
                        self.chat.rewind() # On retire le message échoué de l'historique local
                    except: pass

                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "quota" in err_str or "resource exhausted" in err_str
                
                if is_rate_limit:
                    UnifiedLogger.write("AI_CORE", "WARNING", f"🛑 Quota épuisé sur la clé ...{self.current_key[-6:]}. Rotation immédiate.")
                    
                    # 1. Punition & Exclusion de la clé fautive
                    self.key_mgr.report_error(self.current_key, exception=e, model_name=self.model_name)
                    old_key = self.current_key
                    
                    # 2. Recherche nouvelle clé (en excluant spécifiquement celle qui vient d'échouer)
                    new_key = self.key_mgr.get_key(self.model_name, exclude_key=old_key)
                    
                    if new_key:
                        UnifiedLogger.write("AI_CORE", "INFO", f"🔄 Bascule vers nouvelle clé : ...{new_key[-6:]}")
                        # 3. Réinitialisation de la session avec la nouvelle clé (et préservation historique)
                        try:
                            self._init_chat(key=new_key)
                            retry_count += 1
                            continue # On boucle immédiatement pour réessayer avec la nouvelle clé
                        except Exception as init_err:
                            UnifiedLogger.write("AI_CORE", "CRITICAL", f"Echec init nouvelle clé: {init_err}")
                            # Si la nouvelle clé est invalide aussi, la boucle continuera jusqu'à max_retries
                            retry_count += 1
                            continue
                    else:
                        UnifiedLogger.write("AI_CORE", "CRITICAL", "❌ Plus aucune clé disponible (Pool épuisé) !")
                        raise QuotaExceededException("Toutes les clés sont épuisées.")
                
                else:
                    # Erreur autre (API invalide, 500 server error, etc) -> Pas de retry infini pour ça
                    UnifiedLogger.write("AI_CORE", "ERROR", f"Echec non-quota: {e}")
                    self.key_mgr.report_error(self.current_key, exception=e, model_name=self.model_name)
                    raise e
        
        raise QuotaExceededException(f"Echec Gemini après {retry_count} tentatives (Pool épuisé).")
    
    @trace_action(source="sessions")
    def _log_metrics(self, start_time, response):
        duration = time.time() - start_time
        try:
            from features.TokenManager import TokenManager
        except ImportError:
            TokenManager = None

        try:
            if not hasattr(response, 'usage_metadata') or not response.usage_metadata:
                return

            usage = response.usage_metadata
            
            if TokenManager:
                TokenManager.add_usage(self.model_name, self.current_key, usage.prompt_token_count, usage.candidates_token_count)
            
            metrics_data = {
                "model": self.model_name, 
                "agent": self.agent_name or "Gemini", # <--- Fallback ajouté
                "in": usage.prompt_token_count, 
                "out": usage.candidates_token_count, 
                "time": f"{duration:.2f}s",
                "provider": "Gemini"
            }
            UnifiedLogger.write("AI_CORE", "METRICS", "Usage", metrics_data)
            
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARNING", f"Pas de métriques: {e}")

# --- CLASSE GEMINI CLI SESSION (PONT CLI) ---
class GeminiCliSession(BaseSession):
    """
    Session utilisant le CLI officiel `google-gemini/gemini-cli` pour certains modèles.
    Permet l'utilisation gratuite via le CLI au lieu de l'API payante.
    """
    def __init__(self, key_manager, model_name="gemini-2.5-flash", system_instruction=None, agent_name=None):
        self.key_mgr = key_manager  # Conservé pour compatibilité mais non utilisé
        self.model_name = model_name
        self.agent_name = agent_name
        self.system_instruction = system_instruction
        self.history = []
        
        # Recherche du CLI avec gestion Windows (peut être gemini.cmd, gemini.exe, etc.)
        self.cli_path = self._find_gemini_cli()
        if not self.cli_path:
            raise FatalKeyError(
                "Le CLI 'gemini' n'est pas installé ou n'est pas dans le PATH.\n"
                "Installez-le avec: npm install -g @google/gemini-cli\n"
                "Puis authentifiez-vous: gemini auth login"
            )

        # Initialisation d'un environnement isolé pour éviter le chargement automatique de GEMINI.md
        # (global/projet) et contrôler le system prompt du CLI.
        self._cli_workdir = None
        self._cli_env = None
        self._init_cli_isolation()

        UnifiedLogger.write(
            "AI_CORE",
            "CLI_BRIDGE",
            f"🌉 Pont CLI activé pour {model_name} (path: {self.cli_path})"
        )

    def _get_cli_bridge_cfg(self):
        """
        Lit la config depuis app_settings.json (APP_SETTINGS) avec defaults sûrs.
        """
        cfg = APP_SETTINGS.get("cli_bridge", {}) if isinstance(APP_SETTINGS, dict) else {}

        # Compat: ancien format (enabled/models uniquement)
        isolation = cfg.get("isolation", {}) if isinstance(cfg.get("isolation", {}), dict) else {}
        prompt_limits = cfg.get("prompt_limits", {}) if isinstance(cfg.get("prompt_limits", {}), dict) else {}
        system_md = cfg.get("system_md", {}) if isinstance(cfg.get("system_md", {}), dict) else {}

        def _to_int(x, default):
            try:
                return int(float(x))
            except Exception:
                return default

        ui_lang = (APP_SETTINGS.get("ui_settings", {}) if isinstance(APP_SETTINGS, dict) else {}).get("language", "fr")

        return {
            "max_history_turns": _to_int(cfg.get("max_history_turns", 3), 3),
            "prompt_limits": {
                "total": _to_int(prompt_limits.get("total", 24000), 24000),
                "arch": _to_int(prompt_limits.get("arch", 7000), 7000),
                "tree": _to_int(prompt_limits.get("tree", 7000), 7000),
                "ltm": _to_int(prompt_limits.get("ltm", 4000), 4000),
                "rag": _to_int(prompt_limits.get("rag", 8000), 8000),
                "history": _to_int(prompt_limits.get("history", 6000), 6000),
                "message": _to_int(prompt_limits.get("message", 6000), 6000),
            },
            "isolation": {
                "enabled": bool(isolation.get("enabled", True)),
                "context_file_name": str(isolation.get("context_file_name", "__AIMODDING_DISABLED__.md")),
                "discovery_max_dir": _to_int(isolation.get("discovery_max_dir", 1), 1),
            },
            "system_md": {
                "language": str(system_md.get("language", ui_lang or "fr")),
                "extra": str(system_md.get("extra", "")),
            },
            "debug_mode": bool((APP_SETTINGS.get("system_settings", {}) if isinstance(APP_SETTINGS, dict) else {}).get("debug_mode", False)),
        }

    def _init_cli_isolation(self):
        """
        Crée un workdir temporaire avec une config projet `.gemini/settings.json` afin de
        neutraliser la mémoire hiérarchique GEMINI.md du Gemini CLI, et remplace le system prompt
        intégré via `GEMINI_SYSTEM_MD` + `.gemini/system.md`.
        """
        if self._cli_workdir:
            return

        cfg = self._get_cli_bridge_cfg()
        if not cfg["isolation"]["enabled"]:
            # Mode “non isolé” : on ne crée pas de workdir dédié, le CLI utilisera son comportement standard.
            self._cli_workdir = None
            self._cli_env = dict(os.environ)
            return

        workdir = tempfile.mkdtemp(prefix="aimodding_gemini_cli_")
        gemini_dir = os.path.join(workdir, ".gemini")
        os.makedirs(gemini_dir, exist_ok=True)

        # 1) System prompt contrôlé (remplace le prompt intégré du CLI)
        system_md_path = os.path.join(gemini_dir, "system.md")
        try:
            system_md = build_cli_system_md(
                self.system_instruction,
                language=cfg["system_md"]["language"],
                extra=cfg["system_md"]["extra"],
            )
            with open(system_md_path, "w", encoding="utf-8") as f:
                f.write(system_md)
        except Exception as e:
            # On ne bloque pas le bridge si l'écriture échoue, mais on log.
            UnifiedLogger.write("AI_CORE", "WARNING", f"CLI Bridge: échec écriture system.md: {e}")

        # 2) Settings projet: désactiver la mémoire (GEMINI.md) en choisissant un filename inexistant
        # + Configuration MCP pour notre serveur d'outils
        settings_path = os.path.join(gemini_dir, "settings.json")
        
        # Calculer le chemin du projet (racine du workspace)
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        
        settings = {
            "context": {
                "fileName": cfg["isolation"]["context_file_name"],
                "discoveryMaxDir": cfg["isolation"]["discovery_max_dir"],
                "includeDirectories": [],
                "loadMemoryFromIncludeDirectories": False
            },
            # Configuration MCP pour notre serveur d'outils AiModding-Companion
            "mcpServers": {
                "aimodding-tools": {
                    "command": sys.executable,  # python (ou python.exe sur Windows)
                    "args": ["-m", "ai_core.mcp_server"],
                    "cwd": str(project_root.absolute()),  # Racine du projet (chemin absolu)
                    "trust": True,  # Bypass confirmations (on fait confiance à nos propres outils)
                    "timeout": 30000  # 30 secondes
                }
            }
        }
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            UnifiedLogger.write(
                "AI_CORE",
                "CLI_BRIDGE",
                f"✅ Configuration MCP ajoutée dans {settings_path} (serveur: aimodding-tools)"
            )
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARNING", f"CLI Bridge: échec écriture settings.json: {e}")

        # 3) Env isolé (pas de .env dans le workdir), et forçage system.md
        env = dict(os.environ)
        env["GEMINI_SYSTEM_MD"] = "1"  # 1/true => ./ .gemini/system.md

        self._cli_workdir = workdir
        self._cli_env = env

        # Nettoyage à la fin du process (best-effort)
        atexit.register(lambda: shutil.rmtree(workdir, ignore_errors=True))
    
    def _find_gemini_cli(self):
        """
        Trouve le chemin complet du CLI gemini.
        Sur Windows, npm installe les commandes avec .cmd extension.
        """
        import sys
        import os
        
        # Liste des noms possibles à chercher
        candidates = ["gemini"]
        if sys.platform == "win32":
            candidates.extend(["gemini.cmd", "gemini.exe", "gemini.ps1"])
        
        for cmd in candidates:
            path = shutil.which(cmd)
            if path:
                return path
        
        # Fallback Windows : chercher dans les chemins npm standards
        if sys.platform == "win32":
            npm_paths = [
                os.path.join(os.environ.get("APPDATA", ""), "npm", "gemini.cmd"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "npm", "gemini.cmd"),
                os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Roaming", "npm", "gemini.cmd"),
            ]
            for npm_path in npm_paths:
                if os.path.exists(npm_path):
                    return npm_path
        
        return None

    def _create_msg(self, role, text):
        """Crée un message au format standard."""
        return {"role": role, "content": text}

    def _build_full_prompt(self, message, rag_context=None):
        """
        Construit le prompt complet pour le CLI (stateless) en format atomique (DeepSeek-like).
        Note: Le system prompt principal est géré via `.gemini/system.md` (GEMINI_SYSTEM_MD).
        """
        try:
            comps = GlobalCacheManager.get_components() if GlobalCacheManager else {}
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARNING", f"CLI Bridge: échec get_components: {e}")
            comps = {}

        cfg = self._get_cli_bridge_cfg()
        prompt, meta = build_cli_prompt(
            message=message if isinstance(message, str) else str(message),
            rag_context=rag_context,
            history=self.history,
            cache_components=comps,
            max_history_turns=cfg["max_history_turns"],
            limits=cfg["prompt_limits"],
        )
        # On attache la méta pour logs (sans exposer les données)
        self._last_prompt_meta = meta
        return prompt

    @trace_action(source="sessions")
    def send_message(self, message, stream=False, tool_config=None, rag_context=None):
        """
        Envoie un message via le CLI gemini.
        Args:
            message: Message utilisateur
            stream: Si True, retourne un générateur pour le streaming
            tool_config: Configuration outils (optionnel, le CLI supporte les outils natifs et personnalisés)
            rag_context: Contexte RAG à injecter
        """
        cfg = self._get_cli_bridge_cfg()

        # Pour Windows (gemini.cmd), on évite de passer un prompt long en argument (limite cmd.exe ~8191 chars).
        # gemini-cli supporte stdin + --prompt (append): on met le contexte sur stdin, et le message court en --prompt.
        # NB: --prompt est indiqué deprecated côté CLI, mais reste la voie la plus robuste pour concatener stdin+message.
        try:
            comps = GlobalCacheManager.get_components() if GlobalCacheManager else {}
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARNING", f"CLI Bridge: échec get_components: {e}")
            comps = {}

        from ai_core.prompt_builders import _truncate  # usage interne pour sécuriser l’arg --prompt
        msg_str = message if isinstance(message, str) else str(message)
        msg_arg, msg_tr = _truncate(msg_str, int(cfg["prompt_limits"].get("message", 6000)))

        stdin_prompt, stdin_meta = build_cli_prompt(
            message="",  # message via --prompt
            rag_context=rag_context,
            history=self.history,
            cache_components=comps,
            max_history_turns=cfg["max_history_turns"],
            limits=cfg["prompt_limits"],
            defer_message=True,
        )

        # Attache meta pour logs
        self._last_prompt_meta = stdin_meta

        # Payload Log (logs/) - Structure OPTIMISÉE (pas de duplication avec stdin_prompt)
        # NOTE: Le vrai contexte (Arch, Tree, LTM, RAG) est dans stdin_prompt, pas ici
        # messages_log est utilisé uniquement pour le logging, pas pour l'exécution
        messages_log = []
        
        # 1. INSTRUCTIONS AGENT (System) - Version courte pour le log
        if self.system_instruction:
            sys_content = str(self.system_instruction)
            if len(sys_content) > 2000:
                sys_content = sys_content[:2000] + "... [tronqué - voir stdin_prompt pour version complète]"
            messages_log.append({
                "role": "system",
                "content": f"=== INSTRUCTIONS AGENT ({self.model_name}) ===\n{sys_content}"
            })
        
        # 2. NOTE: Les composants (Arch, Tree, LTM, RAG) sont dans stdin_prompt, pas ici
        # Pour le log, on ajoute juste une note référençant stdin_prompt
        messages_log.append({
            "role": "system",
            "content": "NOTE: Contexte complet (Arch, Tree, LTM, RAG) disponible dans stdin_prompt (voir cli_specific.meta)"
        })
        
        # 3. HISTORIQUE CONVERSATIONNEL - Version nettoyée et tronquée
        # IMPORTANT: Nettoyer l'historique pour enlever le RAG dupliqué ET la mémoire consolidée
        skip_next_ack = False  # Flag pour ignorer le message "Bien reçu" qui suit la mémoire consolidée
        for msg in self.history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            # NETTOYAGE: Si c'est un message user qui contient du RAG mélangé ou la mémoire consolidée, on l'extrait
            if content and role == "user":
                content_str = str(content)
                # Ignorer les messages qui contiennent la mémoire consolidée (déjà dans stdin_prompt)
                if "--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---" in content_str:
                    skip_next_ack = True  # Le prochain message assistant sera l'ack "Bien reçu"
                    continue  # Skip ce message, il est déjà dans stdin_prompt
                
                # Pattern: "--- RAG CONTEXT ---\n...\n\n--- MESSAGE ---\n<message réel>"
                if "--- RAG CONTEXT ---" in content_str and "--- MESSAGE ---" in content_str:
                    parts = content_str.split("--- MESSAGE ---")
                    if len(parts) > 1:
                        content = parts[-1].strip()
                # Aussi nettoyer si le message contient "--- RAG CONTEXT ---" (même sans séparateur MESSAGE)
                elif "--- RAG CONTEXT ---" in content_str:
                    if "--- MESSAGE ---" in content_str:
                        parts = content_str.split("--- MESSAGE ---")
                        content = parts[-1].strip() if len(parts) > 1 else ""
                    else:
                        # Si pas de séparateur, on cherche le début du contenu réel après RAG
                        # Pattern possible: "--- RAG CONTEXT ---\n\n--- 📂 DOCS TECHNIQUE ---\n..."
                        lines = content_str.split("\n")
                        in_rag = False
                        cleaned_lines = []
                        for i, line in enumerate(lines):
                            if "--- RAG CONTEXT ---" in line:
                                in_rag = True
                                continue
                            # Si on est dans RAG et qu'on trouve un pattern de contenu RAG, continuer à ignorer
                            if in_rag:
                                # Si on trouve "--- 📂" ou autre pattern de contenu RAG, continuer à ignorer
                                if "--- 📂" in line or "(Dist:" in line:
                                    continue
                                # Si ligne vide après RAG, on peut commencer à garder
                                if line.strip() == "":
                                    # Vérifier la ligne suivante
                                    if i + 1 < len(lines) and "--- 📂" not in lines[i + 1] and "(Dist:" not in lines[i + 1]:
                                        in_rag = False
                                    continue
                                # Si on trouve du contenu réel (pas de pattern RAG), on sort du mode RAG
                                if "--- 📂" not in line and "(Dist:" not in line:
                                    in_rag = False
                                    cleaned_lines.append(line)
                            else:
                                cleaned_lines.append(line)
                        content = "\n".join(cleaned_lines).strip()
                        # Si le contenu nettoyé est vide ou ne contient que des patterns RAG, on skip
                        if not content or content.startswith("--- 📂") or "(Dist:" in content[:50]:
                            continue
                else:
                    content = content_str
            
            # Ignorer le message assistant "Bien reçu" qui suit la mémoire consolidée
            if skip_next_ack and role == "assistant" and "Bien reçu. Mémoire mise à jour" in str(content):
                skip_next_ack = False
                continue
            
            if content:
                # Tronquer chaque message historique à 2000 chars max pour le log
                content_str = str(content)
                if len(content_str) > 2000:
                    content_str = content_str[:2000] + "... [tronqué]"
                messages_log.append({"role": role, "content": content_str})
        
        # 4. INSTRUCTION FOCUS (System) - juste avant le dernier message user
        messages_log.append({
            "role": "system",
            "content": "⚠️ INSTRUCTION : Focus sur la demande ci-dessous."
        })
        
        # 5. MESSAGE ACTUEL (User) - séparé, sans RAG mélangé, tronqué à 2000 chars
        msg_str_truncated = msg_str[:2000] + ("... [tronqué]" if len(msg_str) > 2000 else "")
        messages_log.append({"role": "user", "content": msg_str_truncated})
        
        cli_payload = {
            "model": self.model_name,
            "agent": self.agent_name,
            "messages": messages_log,
            "stream": stream,
            "cli_specific": {
                "stdin_prompt_length": len(stdin_prompt) if stdin_prompt else 0,
                "message_arg_length": len(msg_arg) if msg_arg else 0,
                "meta": {
                    "total_chars": stdin_meta.total_chars,
                    "sizes": stdin_meta.sizes,
                    "truncated": stdin_meta.truncated
                }
            }
        }
        _save_payload_log("gemini_cli", self.model_name, cli_payload)

        cmd = [
            self.cli_path,
            "--model",
            self.model_name,
            "--output-format",
            "text",
            "--prompt",
            msg_arg,
        ]
        
        # Diagnostic léger : tailles/troncature (sans contenu sensible)
        try:
            meta = getattr(self, "_last_prompt_meta", None)
            if meta:
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    "CLI Bridge prompt meta",
                    {
                        "model": self.model_name,
                        "cwd": os.path.basename(self._cli_workdir or ""),
                        "total_chars": meta.total_chars,
                        "sizes": meta.sizes,
                        "truncated": meta.truncated,
                        "prompt_arg_truncated": bool(msg_tr),
                    },
                )
        except Exception:
            pass

        UnifiedLogger.write(
            "AI_CORE",
            "START",
            f"Gemini CLI ({self.model_name}) generating...",
            {"prompt_preview": (stdin_prompt[:80] + " ..." if len(stdin_prompt) > 80 else stdin_prompt)},
        )
        
        try:
            start_t = time.time()
            
            if stream:
                # Mode streaming : on lit stdout ligne par ligne
                def cli_generator():
                    try:
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            stdin=subprocess.PIPE,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            cwd=self._cli_workdir or os.getcwd(),
                            env=self._cli_env
                        )

                        # Envoyer le contexte sur stdin, puis fermer pour déclencher l’exécution non-interactive
                        try:
                            process.stdin.write(stdin_prompt)
                            if not stdin_prompt.endswith("\n"):
                                process.stdin.write("\n")
                        finally:
                            try:
                                process.stdin.close()
                            except Exception:
                                pass
                        
                        full_response = ""
                        for line in process.stdout:
                            if line.strip():
                                full_response += line
                                yield line
                        
                        # Attente de la fin du processus
                        process.wait()
                        
                        if process.returncode != 0:
                            error_output = process.stderr.read()
                            raise Exception(f"CLI Error (code {process.returncode}): {error_output}")
                        
                        # Ajout à l'historique
                        self.history.append(self._create_msg("user", message))
                        self.history.append(self._create_msg("assistant", full_response))
                        
                        duration = time.time() - start_t
                        UnifiedLogger.write("AI_CORE", "SUCCESS", f"Gemini CLI Stream terminé ({duration:.2f}s)")
                        
                    except FileNotFoundError:
                        raise FatalKeyError("Commande 'gemini' introuvable. Vérifiez l'installation du CLI.")
                    except Exception as e:
                        UnifiedLogger.write("AI_CORE", "ERROR", f"Gemini CLI Exception: {e}")
                        raise e
                
                return cli_generator()
            
            else:
                # Mode non-stream : on capture toute la sortie
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    input=stdin_prompt,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    cwd=self._cli_workdir or os.getcwd(),
                    env=self._cli_env,
                    timeout=120
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr.strip() or "Erreur inconnue du CLI"
                    if "not logged in" in error_msg.lower() or "authentication" in error_msg.lower():
                        raise FatalKeyError(
                            f"CLI non authentifié. Exécutez: gemini auth login\n"
                            f"Détails: {error_msg}"
                        )
                    raise Exception(f"CLI Error (code {result.returncode}): {error_msg}")
                
                content = result.stdout.strip()
                
                # Ajout à l'historique
                self.history.append(self._create_msg("user", message))
                self.history.append(self._create_msg("assistant", content))
                
                duration = time.time() - start_t
                UnifiedLogger.write("AI_CORE", "SUCCESS", f"Gemini CLI terminé ({duration:.2f}s)")
                
                # Retour au format UniversalResponseWrapper pour compatibilité
                return UniversalResponseWrapper(content, None)
        
        except subprocess.TimeoutExpired:
            raise Exception("Timeout: Le CLI a pris plus de 120 secondes.")
        except FileNotFoundError:
            raise FatalKeyError("Commande 'gemini' introuvable. Vérifiez l'installation du CLI.")
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "ERROR", f"Gemini CLI Exception: {e}")
            raise e

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

@trace_action(source="sessions")
def call_ai_robust(session_or_agent, prompt, mode="fast", disposable=False, force_text=False, cache_name=None, stream=False, rag_context=None):
    from .factory import SessionFactory
    try:
        session = session_or_agent.session if hasattr(session_or_agent, 'session') else session_or_agent
        if not session: 
            session = SessionFactory.create_session(model_type=mode, cache_name=cache_name)
        
        tool_config = None
        if force_text: tool_config = {'function_calling_config': {'mode': 'none'}}

        # Historique jetable
        hist_bkp = None
        if disposable and hasattr(session, 'chat'): 
            try: hist_bkp = list(session.chat.history)
            except: pass

        # [V5] Appel API Unifié 
        # Toutes les sessions (DeepSeek, Gemini, Groq) acceptent désormais rag_context
        response = session.send_message(prompt, stream=stream, tool_config=tool_config, rag_context=rag_context)
        
        # Restauration historique si mode jetable
        if disposable and hasattr(session, 'chat'): 
            try: session.chat.history = hist_bkp
            except: pass
        
        if stream: return response
        return response.text if hasattr(response, 'text') else str(response)

    except Exception as e:
        err_msg = str(e)
        UnifiedLogger.write("AI_CORE", "ERROR", f"Call AI Error: {err_msg}")
        # En cas d'erreur sur un stream, on renvoie un itérateur vide pour éviter de planter le consommateur
        if stream: return iter([])
        return f"[Erreur IA] {err_msg}"
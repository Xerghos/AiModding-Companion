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
from threading import Lock, Thread
import threading
from queue import Queue, Empty
import subprocess
import shutil
import os
import sys
import tempfile
import atexit
from typing import Dict, Any, List, Optional

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


def _save_response_log(session_type: str, model_name: str, response_data: dict, extra_meta: dict = None):
    """
    Sauvegarde une réponse complète dans logs/ avec timestamp.
    Args:
        session_type: "gemini_cli"
        model_name: nom du modèle utilisé
        response_data: la réponse complète (texte, métriques, etc.)
        extra_meta: métadonnées additionnelles
    """
    try:
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%d-%b_%Hh%M_%S")
        safe_model = model_name.replace("/", "_").replace(":", "_")
        filename = f"response_{session_type}_{safe_model}_{timestamp}.json"
        filepath = os.path.join(logs_dir, filename)
        
        log_content = {
            "timestamp": datetime.datetime.now().isoformat(),
            "session_type": session_type,
            "model": model_name,
            "response": response_data
        }
        if extra_meta:
            log_content["meta"] = extra_meta
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(log_content, f, indent=2, ensure_ascii=False)
        
        UnifiedLogger.write("AI_CORE", "RESPONSE_LOG", f"📄 Réponse sauvegardée: {filename}")
        
    except Exception as e:
        UnifiedLogger.write("AI_CORE", "WARN", f"Echec sauvegarde réponse: {e}")


def _save_codeassist_payload_log(model_name: str, payload_data: dict, extra_meta: dict = None):
    """
    Sauvegarde un payload CodeAssist dans logs/ avec timestamp.
    OPTIMISATION: Écriture asynchrone pour ne pas bloquer le thread principal.
    """
    def save_async():
        """Thread pour l'écriture asynchrone du fichier."""
        try:
            logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%d-%b_%Hh%M_%S")
            safe_model = model_name.replace("/", "_").replace(":", "_")
            filename = f"codeassist_final_{safe_model}_{timestamp}.json"
            filepath = os.path.join(logs_dir, filename)
            
            log_content = {
                "timestamp": datetime.datetime.now().isoformat(),
                "session_type": "codeassist_final",
                "model": model_name,
                "payload": payload_data
            }
            if extra_meta:
                log_content["meta"] = extra_meta
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(log_content, f, indent=2, ensure_ascii=False)
            
            UnifiedLogger.write("AI_CORE", "CODEASSIST_PAYLOAD_LOG", f"📤 Payload CodeAssist final sauvegardé: {filename}")
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARN", f"Echec sauvegarde payload CodeAssist: {e}")
    
    # Lancer l'écriture en arrière-plan dans un thread daemon
    thread = Thread(target=save_async, daemon=True)
    thread.start()


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

# --- CLASSE POOL DE PROCESSUS CLI (OPTIMISATION PERFORMANCES) ---
class CliProcessPool:
    """
    Pool de processus CLI préchauffés pour réduire le temps de découverte MCP.
    Maintient un processus "prêt" en arrière-plan pour la prochaine requête.
    """
    def __init__(self, cli_path, model_name, cli_workdir, cli_env, mcp_http_available):
        self.cli_path = cli_path
        self.model_name = model_name
        self.cli_workdir = cli_workdir
        self.cli_env = cli_env
        self.mcp_http_available = mcp_http_available
        
        # Processus prêt à être utilisé (None si aucun disponible)
        self._ready_process = None
        self._ready_process_lock = threading.Lock()
        self._prewarm_thread = None
        
        # Démarrer le préchauffage en arrière-plan
        self._start_prewarm()
    
    def _start_prewarm(self):
        """Démarre un thread de préchauffage pour maintenir un processus prêt."""
        def prewarm_worker():
            """Worker qui maintient un processus prêt."""
            while True:
                try:
                    # Attendre un peu avant de créer le processus
                    time.sleep(1.0)
                    
                    with self._ready_process_lock:
                        # Si on a déjà un processus prêt, ne pas en créer un autre
                        if self._ready_process is not None:
                            # Vérifier si le processus est toujours valide
                            if self._ready_process.poll() is None:
                                # Processus toujours actif, continuer
                                continue
                            else:
                                # Processus terminé, nettoyer
                                self._ready_process = None
                        
                        # Créer un nouveau processus de test pour préchauffer
                        # Ce processus sera utilisé pour la prochaine requête
                        test_cmd = [
                            self.cli_path,
                            "--model",
                            self.model_name,
                            "--output-format",
                            "text",
                            "--prompt",
                            "test"
                        ]
                        
                        process = subprocess.Popen(
                            test_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            stdin=subprocess.PIPE,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            bufsize=65536,
                            cwd=self.cli_workdir or os.getcwd(),
                            env=self.cli_env
                        )
                        
                        # Vérifier que le processus démarre correctement
                        time.sleep(0.1)
                        if process.poll() is None:
                            # Processus actif, le marquer comme prêt
                            # Note: Ce processus sera utilisé pour tester la disponibilité MCP
                            # mais ne sera pas réutilisé directement car subprocess ne le permet pas
                            self._ready_process = process
                            UnifiedLogger.write(
                                "AI_CORE",
                                "DEBUG",
                                f"CLI Pool: Processus préchauffé créé (PID: {process.pid})"
                            )
                            
                except Exception as e:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "DEBUG",
                        f"CLI Pool: Erreur préchauffage (non bloquant): {e}"
                    )
                    time.sleep(5.0)  # Attendre plus longtemps en cas d'erreur
        
        self._prewarm_thread = Thread(target=prewarm_worker, daemon=True)
        self._prewarm_thread.start()
    
    def get_process(self, cmd):
        """
        Obtient un processus pour la commande donnée.
        Pour l'instant, crée toujours un nouveau processus car subprocess ne peut être réutilisé.
        Mais le processus préchauffé garantit que Node.js/MCP sont en cache.
        """
        # Toujours créer un nouveau processus car subprocess ne peut être réutilisé
        # Le processus préchauffé sert juste à avoir Node.js/MCP en cache système
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=65536,
            cwd=self.cli_workdir or os.getcwd(),
            env=self.cli_env
        )
        
        # Nettoyer le processus prêt s'il existe (il a servi son but)
        with self._ready_process_lock:
            if self._ready_process is not None:
                try:
                    if self._ready_process.poll() is None:
                        self._ready_process.terminate()
                        try:
                            self._ready_process.wait(timeout=1.0)
                        except subprocess.TimeoutExpired:
                            self._ready_process.kill()
                            self._ready_process.wait()
                except Exception:
                    pass
                self._ready_process = None
        
        return process

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
        
        # Buffer statique pour optimisation de l'écriture stdin
        # Contient la partie statique du prompt (Repo Map/Arch, Tree, LTM) qui ne change que quand le cache change
        self._static_prompt_buffer = None
        self._static_buffer_cache_hash = None  # Hash pour détecter les changements du cache
        
        # Pool de processus pré-chauffés (pour réutilisation)
        # Initialisé après _init_cli_isolation pour avoir accès à cli_workdir et cli_env
        self._process_pool = None

        UnifiedLogger.write(
            "AI_CORE",
            "CLI_BRIDGE",
            f"🌉 Pont CLI activé pour {model_name} (path: {self.cli_path})"
        )
        
        # OPTIMISATION: Pré-chauffer un processus en arrière-plan
        # Cela élimine le délai de démarrage Node.js + initialisation MCP pour la première requête
        self._prewarm_process()

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
        
        # Calculer le chemin du projet (racine du workspace) - pré-calculé une seule fois
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        project_root_abs = str(project_root.absolute())  # Pré-calculer le chemin absolu
        
        # Configuration MCP HTTP/SSE pour utiliser le serveur long-running déjà démarré
        # Le serveur MCP HTTP est démarré au lancement de l'application (voir run.py)
        # Cela évite de lancer un nouveau processus Python à chaque requête
        mcp_http_port = int(os.environ.get("MCP_HTTP_PORT", "8000"))
        mcp_http_host = os.environ.get("MCP_HTTP_HOST", "127.0.0.1")
        # FastMCP expose l'endpoint SSE à /mcp (pas /mcp/sse)
        # gemini-cli détecte automatiquement le transport SSE depuis cette URL
        mcp_server_url = f"http://{mcp_http_host}:{mcp_http_port}/mcp"
        
        # Vérifier que le serveur MCP HTTP est disponible avant de l'utiliser
        # On fait plusieurs tentatives car le serveur peut être en cours de démarrage
        self._mcp_http_available = False
        health_url = f"http://{mcp_http_host}:{mcp_http_port}/health"
        
        import time
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                import requests
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    self._mcp_http_available = True
                    tools_count = response.json().get('tools_count', 0)
                    UnifiedLogger.write(
                        "AI_CORE",
                        "DEBUG",
                        f"✅ Serveur MCP HTTP disponible sur {health_url} ({tools_count} outils, tentative {attempt + 1}/{max_retries})"
                    )
                    break
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "WARNING",
                        f"⚠️ Serveur MCP HTTP non disponible ({health_url}) après {max_retries} tentatives: {e}. Utilisation de stdio en fallback."
                    )
        
        # Configuration SSE/HTTP si disponible, sinon fallback sur stdio
        # NOTE: gemini-cli détecte automatiquement le transport SSE si on utilise "url"
        # (pas besoin de la clé "transport" qui n'est pas reconnue)
        if self._mcp_http_available:
            mcp_server_config = {
                "url": mcp_server_url,  # URL SSE - gemini-cli détecte automatiquement le transport
                "trust": True,
                "timeout": 30000
            }
        else:
            # Fallback sur stdio si le serveur HTTP n'est pas disponible
            mcp_server_config = {
                "command": sys.executable,
                "args": ["-m", "ai_core.mcp_server"],
                "cwd": project_root_abs,  # Chemin absolu pré-calculé
                "trust": True,
                "timeout": 30000
            }
        
        settings = {
            "context": {
                "fileName": cfg["isolation"]["context_file_name"],
                "discoveryMaxDir": cfg["isolation"]["discovery_max_dir"],
                "includeDirectories": [],
                "loadMemoryFromIncludeDirectories": False
            },
            "mcpServers": {
                "aimodding-tools": mcp_server_config
            }
        }
        
        # OPTIMISATION: Charger le cache MCP si disponible
        # Cela évite à gemini-cli de redécouvrir les outils à chaque requête
        # Note: Avec HTTP/SSE, la découverte est beaucoup plus rapide car le serveur reste en vie
        try:
            from ai_core.mcp_cache import load_mcp_cache, save_mcp_cache
            from ai_core.mcp_server import get_mcp_tools_for_cache
            
            # Charger le cache MCP
            cached_tools = load_mcp_cache(mcp_server_config)
            if cached_tools is None:
                # Cache invalide ou inexistant, pré-calculer les outils pour le cache
                # (gemini-cli les découvrira quand même, mais on peut pré-calculer pour le cache)
                try:
                    tools_for_cache = get_mcp_tools_for_cache()
                    save_mcp_cache(mcp_server_config, tools_for_cache)
                    UnifiedLogger.write(
                        "AI_CORE",
                        "DEBUG",
                        f"CLI Cache MCP: {len(tools_for_cache)} outils pré-calculés et mis en cache"
                    )
                except Exception as e:
                    UnifiedLogger.write(
                        "AI_CORE",
                        "DEBUG",
                        f"CLI Cache MCP: échec pré-calcul (non bloquant): {e}"
                    )
            else:
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    f"CLI Cache MCP: {len(cached_tools)} outils chargés depuis le cache"
                )
        except ImportError:
            # Module de cache non disponible, continuer sans cache
            pass
        except Exception as e:
            # Ne pas bloquer si le cache échoue
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"CLI Cache MCP: erreur (non bloquant): {e}"
            )
        try:
            # Minifier le JSON pour réduire la taille (pas d'indentation, séparateurs compacts)
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=None, separators=(',', ':'))
            # Message de log adapté selon le transport utilisé
            if self._mcp_http_available:
                UnifiedLogger.write(
                    "AI_CORE",
                    "CLI_BRIDGE",
                    f"✅ Configuration MCP HTTP/SSE ajoutée dans {settings_path} (serveur: aimodding-tools, URL: {mcp_server_url})"
                )
            else:
                UnifiedLogger.write(
                    "AI_CORE",
                    "CLI_BRIDGE",
                    f"✅ Configuration MCP stdio ajoutée dans {settings_path} (serveur: aimodding-tools, fallback)"
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
        
        # OPTIMISATION: Initialiser le pool de processus après avoir configuré l'isolation
        # Cela permet de maintenir des processus préchauffés pour réduire le temps de découverte MCP
        try:
            self._process_pool = CliProcessPool(
                self.cli_path,
                self.model_name,
                self._cli_workdir,
                self._cli_env,
                self._mcp_http_available
            )
        except Exception as e:
            UnifiedLogger.write(
                "AI_CORE",
                "WARNING",
                f"CLI Pool: Échec initialisation (non bloquant): {e}"
            )
    
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
    
    def _prewarm_process(self):
        """
        Pré-chauffe un processus gemini-cli en arrière-plan pour éliminer le délai de démarrage.
        Démarre Node.js, charge les modules, et initialise le runtime MCP.
        Le processus se termine après un test simple, mais Node.js et les modules restent en cache.
        """
        def prewarm_thread():
            """Thread en arrière-plan pour pré-chauffer le processus."""
            try:
                # Attendre un peu pour ne pas bloquer l'initialisation
                time.sleep(0.5)
                
                # Créer une commande de test simple (juste pour démarrer Node.js et charger les modules)
                test_cmd = [
                    self.cli_path,
                    "--model",
                    self.model_name,
                    "--output-format",
                    "text",
                    "--prompt",
                    "test",  # Message minimal pour déclencher le démarrage
                ]
                
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    "CLI Pré-chauffage: démarrage processus test en arrière-plan..."
                )
                
                prewarm_start = time.time()
                
                # Démarrer le processus (il se terminera rapidement après avoir chargé les modules)
                process = subprocess.Popen(
                    test_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=65536,
                    cwd=self._cli_workdir or os.getcwd(),
                    env=self._cli_env
                )
                
                # Écrire un message minimal et fermer stdin
                try:
                    process.stdin.write("test\n")
                    process.stdin.close()
                except Exception:
                    pass
                
                # Lire rapidement la sortie (ou timeout)
                try:
                    # Attendre max 5 secondes pour le pré-chauffage
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Si le processus prend trop de temps, le tuer
                    process.kill()
                    process.wait()
                
                prewarm_duration = (time.time() - prewarm_start) * 1000
                
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    f"CLI Pré-chauffage terminé en {prewarm_duration:.0f}ms (Node.js et modules chargés en cache)"
                )
                
            except Exception as e:
                # Ne pas bloquer si le pré-chauffage échoue
                UnifiedLogger.write(
                    "AI_CORE",
                    "WARNING",
                    f"CLI Pré-chauffage échoué (non bloquant): {e}"
                )
        
        # Lancer le thread de pré-chauffage en arrière-plan
        prewarm_thread_obj = Thread(target=prewarm_thread, daemon=True)
        prewarm_thread_obj.start()

    def _create_msg(self, role, text):
        """Crée un message au format standard."""
        return {"role": role, "content": text}
    
    def _get_cache_hash(self, cache_components: Dict[str, Any]) -> str:
        """
        Calcule un hash simple des composants du cache pour détecter les changements.
        
        Args:
            cache_components: Dictionnaire des composants du cache (repo_map, arch, tree, ltm)
            
        Returns:
            Hash string représentant l'état actuel du cache
        """
        import hashlib
        # Créer une représentation simple des composants statiques
        static_keys = ["repo_map", "arch", "tree", "ltm"]
        static_data = {k: str(cache_components.get(k, "")) for k in static_keys}
        # Sérialiser et hasher
        data_str = json.dumps(static_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode('utf-8')).hexdigest()
    
    def _update_static_buffer(self, cache_components: Dict[str, Any], limits: Dict[str, int], max_history_turns: int):
        """
        Met à jour le buffer statique avec la partie statique du prompt.
        Appelée quand le cache change ou si le buffer n'existe pas encore.
        
        Args:
            cache_components: Composants du cache (repo_map, arch, tree, ltm)
            limits: Limites de troncature pour chaque section
            max_history_turns: Nombre de tours d'historique (non utilisé pour la partie statique)
        """
        from ai_core.prompt_builders import build_cli_prompt_split
        
        # Construire uniquement la partie statique (sans RAG, history, message)
        static_part, _, meta = build_cli_prompt_split(
            message="",  # Pas de message pour la partie statique
            rag_context=None,  # Pas de RAG pour la partie statique
            history=[],  # Pas d'historique pour la partie statique
            cache_components=cache_components,
            max_history_turns=max_history_turns,
            limits=limits,
            defer_message=True,
        )
        
        self._static_prompt_buffer = static_part
        self._static_buffer_cache_hash = self._get_cache_hash(cache_components)
        
        UnifiedLogger.write(
            "AI_CORE",
            "DEBUG",
            f"CLI Buffer statique mis à jour: {len(static_part)} chars (hash: {self._static_buffer_cache_hash[:8]}...)"
        )
    
    def _get_dynamic_prompt(self, message: str, rag_context: Optional[str], history: List[Dict[str, Any]], 
                           cache_components: Dict[str, Any], limits: Dict[str, int], max_history_turns: int) -> str:
        """
        Construit uniquement la partie dynamique du prompt (RAG Context, History, Message).
        
        Args:
            message: Message utilisateur
            rag_context: Contexte RAG
            history: Historique de conversation
            cache_components: Composants du cache (requis pour build_cli_prompt_split, mais seule la partie dynamique est utilisée)
            limits: Limites de troncature
            max_history_turns: Nombre de tours d'historique
            
        Returns:
            Partie dynamique du prompt (string)
        """
        from ai_core.prompt_builders import build_cli_prompt_split
        
        # Construire les deux parties, mais on n'utilisera que la partie dynamique
        # La partie statique sera ignorée car on utilisera le buffer
        _, dynamic_part, _ = build_cli_prompt_split(
            message=message,
            rag_context=rag_context,
            history=history,
            cache_components=cache_components,  # Requis pour la fonction, mais seule dynamic_part est utilisée
            max_history_turns=max_history_turns,
            limits=limits,
            defer_message=False,
        )
        
        return dynamic_part

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

        from ai_core.prompt_builders import _truncate  # usage interne pour sécuriser l'arg --prompt
        msg_str = message if isinstance(message, str) else str(message)
        msg_arg, msg_tr = _truncate(msg_str, int(cfg["prompt_limits"].get("message", 6000)))

        # OPTIMISATION: Utiliser le buffer statique + concaténation rapide
        # 1. Vérifier si le buffer statique est à jour
        current_cache_hash = self._get_cache_hash(comps)
        buffer_needs_update = (
            self._static_prompt_buffer is None or 
            self._static_buffer_cache_hash != current_cache_hash
        )
        
        if buffer_needs_update:
            concat_start = time.time()
            self._update_static_buffer(comps, cfg["prompt_limits"], cfg["max_history_turns"])
            concat_time = (time.time() - concat_start) * 1000
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"CLI Buffer statique mis à jour en {concat_time:.2f}ms"
            )
        else:
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"CLI Buffer statique réutilisé (hash: {current_cache_hash[:8]}...)"
            )
        
        # 2. Construire uniquement la partie dynamique
        dynamic_start = time.time()
        dynamic_part = self._get_dynamic_prompt(
            message="",  # message via --prompt
            rag_context=rag_context,
            history=self.history,
            cache_components=comps,
            limits=cfg["prompt_limits"],
            max_history_turns=cfg["max_history_turns"],
        )
        dynamic_time = (time.time() - dynamic_start) * 1000
        
        # 3. Concaténer rapidement statique + dynamique
        concat_start = time.time()
        if self._static_prompt_buffer and dynamic_part:
            stdin_prompt = f"{self._static_prompt_buffer}\n\n{dynamic_part}"
        elif self._static_prompt_buffer:
            stdin_prompt = self._static_prompt_buffer
        elif dynamic_part:
            stdin_prompt = dynamic_part
        else:
            stdin_prompt = ""
        concat_time = (time.time() - concat_start) * 1000
        
        UnifiedLogger.write(
            "AI_CORE",
            "DEBUG",
            f"CLI Prompt construit: dynamique en {dynamic_time:.2f}ms, concaténation en {concat_time:.2f}ms, total: {len(stdin_prompt)} chars"
        )
        
        # Créer une meta simplifiée pour compatibilité (on n'a pas la meta complète car on a construit séparément)
        # On va recalculer les tailles pour la meta
        from ai_core.prompt_builders import PromptBuildMeta
        stdin_meta = PromptBuildMeta(
            total_chars=len(stdin_prompt),
            truncated={},  # On ne track pas la troncature dans ce mode optimisé
            sizes={}  # On ne track pas les tailles individuelles dans ce mode optimisé
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
        history_size_before = len(self.history)
        UnifiedLogger.write(
            "AI_CORE",
            "DEBUG",
            f"CLI Bridge: Traitement historique - {history_size_before} messages dans self.history"
        )
        
        skip_next_ack = False  # Flag pour ignorer le message "Bien reçu" qui suit la mémoire consolidée
        history_messages_added = 0
        history_messages_skipped = 0
        
        # Normaliser l'historique pour gérer les deux formats possibles :
        # Format 1: {"role": "...", "content": "..."} (format standard)
        # Format 2: {"role": "...", "parts": [{"text": "..."}]} (format Gemini CLI)
        normalized_history = []
        for msg in self.history:
            if isinstance(msg, dict):
                role = msg.get('role', 'user')
                # Normaliser "model" -> "assistant" pour compatibilité
                if role == "model":
                    role = "assistant"
                
                # Extraire le contenu selon le format
                content = msg.get('content', '')
                if not content and 'parts' in msg:
                    # Format Gemini CLI: extraire depuis parts
                    parts = msg.get('parts', [])
                    if parts and isinstance(parts[0], dict):
                        content = parts[0].get('text', '')
                
                normalized_history.append({"role": role, "content": str(content) if content else ""})
            else:
                # Format inconnu, essayer d'extraire role et content
                role = getattr(msg, 'role', 'user')
                if role == "model":
                    role = "assistant"
                content = getattr(msg, 'content', '') or (getattr(msg, 'parts', [{}])[0].get('text', '') if hasattr(msg, 'parts') else '')
                normalized_history.append({"role": role, "content": str(content) if content else ""})
        
        UnifiedLogger.write(
            "AI_CORE",
            "DEBUG",
            f"CLI Bridge: Historique normalisé - {len(normalized_history)} messages (format original: {len(self.history)})"
        )
        
        for msg in normalized_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            # NETTOYAGE: Si c'est un message user qui contient du RAG mélangé ou la mémoire consolidée, on l'extrait
            if content and role == "user":
                content_str = str(content)
                # Ignorer les messages qui contiennent la mémoire consolidée (déjà dans stdin_prompt)
                if "--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---" in content_str:
                    skip_next_ack = True  # Le prochain message assistant sera l'ack "Bien reçu"
                    history_messages_skipped += 1
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
                            history_messages_skipped += 1
                            continue
                else:
                    content = content_str
            
            # Ignorer le message assistant "Bien reçu" qui suit la mémoire consolidée
            if skip_next_ack and role == "assistant" and "Bien reçu. Mémoire mise à jour" in str(content):
                skip_next_ack = False
                history_messages_skipped += 1
                continue
            
            # Vérifier si le contenu est vide après nettoyage
            if not content or not str(content).strip():
                # Contenu vide après nettoyage, on skip
                history_messages_skipped += 1
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    f"CLI Bridge: Message {role} ignoré (contenu vide après nettoyage)"
                )
                continue
            
            # Tronquer chaque message historique à 2000 chars max pour le log
            content_str = str(content)
            if len(content_str) > 2000:
                content_str = content_str[:2000] + "... [tronqué]"
            messages_log.append({"role": role, "content": content_str})
            history_messages_added += 1
        
        # Log du résultat du traitement de l'historique
        UnifiedLogger.write(
            "AI_CORE",
            "DEBUG",
            f"CLI Bridge: Historique traité - {history_messages_added} messages ajoutés, {history_messages_skipped} messages ignorés/filtrés"
        )
        if history_size_before > 0 and history_messages_added == 0:
            UnifiedLogger.write(
                "AI_CORE",
                "WARNING",
                f"CLI Bridge: Tous les messages de l'historique ({history_size_before}) ont été filtrés ou ignorés"
            )
        
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
        # NOTE: On ne sauvegarde PAS le payload CLI intermédiaire pour GeminiCliSession
        # On garde uniquement le payload CodeAssist final (codeassist_final_*.json)
        # _save_payload_log("gemini_cli", self.model_name, cli_payload)  # Désactivé

        # Reconstruire et logger le payload FINAL CodeAssist
        try:
            final_ca_payload = self._build_codeassist_final_payload(
                stdin_prompt=stdin_prompt,
                msg_arg=msg_arg,
                model_name=self.model_name
            )
            
            # Accéder à la structure "request" qui contient les champs réels
            request_payload = final_ca_payload.get("request", final_ca_payload)
            
            # Calculer les métriques complètes du payload final
            system_instruction_text = ""
            if "systemInstruction" in request_payload:
                si = request_payload["systemInstruction"]
                if isinstance(si, dict) and "parts" in si:
                    system_instruction_text = " ".join(part.get("text", "") for part in si["parts"])
                elif isinstance(si, str):
                    system_instruction_text = si
            
            contents_text = ""
            if "contents" in request_payload:
                for content in request_payload["contents"]:
                    if "parts" in content:
                        contents_text += " ".join(part.get("text", "") for part in content["parts"] if "text" in part)
            
            # Calculer la taille des outils (sérialisé en JSON)
            tools_json = ""
            tools_count = 0
            if "tools" in request_payload and request_payload["tools"]:
                # Les outils sont dans une liste, chaque élément a "functionDeclarations"
                for tool_group in request_payload["tools"]:
                    if "functionDeclarations" in tool_group:
                        tools_count += len(tool_group["functionDeclarations"])
                # Sérialiser les outils pour calculer leur taille
                try:
                    tools_json = json.dumps(request_payload["tools"], indent=2, ensure_ascii=False)
                except Exception:
                    tools_json = str(request_payload["tools"])
            
            # Sérialiser le payload complet pour calculer la taille totale
            payload_json = json.dumps(final_ca_payload, indent=2, ensure_ascii=False)
            total_payload_size = len(payload_json.encode('utf-8'))  # Taille en bytes
            total_payload_chars = len(payload_json)  # Nombre de caractères
            
            # Total input = systemInstruction + contents + tools (sérialisés)
            total_input_chars = len(system_instruction_text) + len(contents_text) + len(tools_json)
            
            # Stocker les métriques du payload final pour les utiliser dans _log_metrics
            self._last_payload_input_chars = total_input_chars
            self._last_payload_estimated_tokens = int(total_input_chars / 3.5)
            
            _save_codeassist_payload_log(
                self.model_name,
                final_ca_payload,
                {
                    "system_instruction_length": len(system_instruction_text),
                    "contents_length": len(contents_text),
                    "tools_json_length": len(tools_json),
                    "tools_count": tools_count,
                    "total_input_chars": total_input_chars,
                    "total_payload_chars": total_payload_chars,
                    "total_payload_size_bytes": total_payload_size,
                    "total_payload_size_kb": round(total_payload_size / 1024, 2),
                    "estimated_tokens": int(total_input_chars / 3.5),
                    "has_tool_config": "toolConfig" in request_payload,
                    "payload_structure": {
                        "has_contents": "contents" in request_payload,
                        "has_system_instruction": "systemInstruction" in request_payload,
                        "has_tools": "tools" in request_payload and bool(request_payload.get("tools")),
                        "has_tool_config": "toolConfig" in request_payload,
                        "has_generation_config": "generationConfig" in request_payload
                    }
                }
            )
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARN", f"Echec reconstruction payload CodeAssist: {e}")

        cmd = [
            self.cli_path,
            "--model",
            self.model_name,
            "--output-format",
            "text",
            "--prompt",
            msg_arg,
        ]
        
        # Logger la commande exécutée (sans le prompt complet pour éviter le spam)
        UnifiedLogger.write(
            "AI_CORE",
            "DEBUG",
            f"CLI Commande: {self.cli_path} --model {self.model_name} --output-format text --prompt [{(len(msg_arg))} chars]"
        )
        UnifiedLogger.write(
            "AI_CORE",
            "DEBUG",
            f"CLI CWD: {self._cli_workdir or os.getcwd()}"
        )
        UnifiedLogger.write(
            "AI_CORE",
            "DEBUG",
            f"CLI Transport MCP: {'HTTP/SSE' if self._mcp_http_available else 'stdio'}"
        )
        
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
                        "history_size": history_size_before,
                        "messages_log_count": len(messages_log),
                        "history_in_messages_log": history_messages_added,
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
                        # Mesure du temps de démarrage du processus
                        process_start = time.time()
                        
                        # OPTIMISATION: Utiliser le pool de processus si disponible
                        if hasattr(self, '_process_pool') and self._process_pool:
                            process = self._process_pool.get_process(cmd)
                        else:
                            # Fallback: créer un nouveau processus
                            process = subprocess.Popen(
                                cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdin=subprocess.PIPE,
                                text=True,
                                encoding='utf-8',
                                errors='replace',
                                bufsize=65536,  # Buffer de 64KB pour réduire les appels système
                                cwd=self._cli_workdir or os.getcwd(),
                                env=self._cli_env
                            )
                        process_created = time.time()
                        
                        # Vérifier immédiatement si le processus est toujours actif
                        if process.poll() is not None:
                            # Le processus s'est terminé immédiatement - lire stderr pour comprendre pourquoi
                            try:
                                stderr_output = process.stderr.read()
                                if stderr_output:
                                    UnifiedLogger.write(
                                        "AI_CORE",
                                        "ERROR",
                                        f"CLI Process terminé immédiatement (code: {process.poll()}): {stderr_output[:1000]}"
                                    )
                            except Exception:
                                pass
                            raise Exception(f"Processus gemini-cli terminé immédiatement après création (code: {process.poll()})")
                        
                        UnifiedLogger.write(
                            "AI_CORE",
                            "DEBUG",
                            f"CLI Process créé en {(process_created - process_start)*1000:.0f}ms (PID: {process.pid})"
                        )

                        # OPTIMISATION: Écriture stdin asynchrone dans un thread séparé
                        # Cela évite le blocage pendant que le processus démarre et découvre les outils MCP
                        stdin_start = time.time()
                        stdin_write_error = [None]  # Liste pour capturer l'erreur depuis le thread
                        stdin_write_complete = [False]  # Flag pour indiquer la fin de l'écriture
                        
                        def write_stdin_async(process, full_prompt):
                            """Écrit stdin dans un thread séparé pour éviter le blocage."""
                            try:
                                # Attendre un peu pour que le processus soit prêt (évite les erreurs de timing)
                                # Avec SSE, gemini-cli peut prendre un peu plus de temps pour initialiser la connexion MCP
                                import time
                                wait_time = 0.2 if self._mcp_http_available else 0.1  # Plus de temps si SSE
                                time.sleep(wait_time)
                                
                                # Vérifier que le processus est toujours actif avant d'écrire
                                if process.poll() is not None:
                                    # Le processus s'est terminé avant qu'on puisse écrire
                                    exit_code = process.poll()
                                    # Lire stderr pour comprendre pourquoi
                                    stderr_msg = ""
                                    try:
                                        if process.stderr:
                                            # Essayer de lire stderr de manière non-bloquante
                                            import select
                                            import sys
                                            if sys.platform != 'win32':
                                                # Sur Unix, on peut utiliser select
                                                if select.select([process.stderr], [], [], 0)[0]:
                                                    stderr_msg = process.stderr.read()
                                            else:
                                                # Sur Windows, essayer de lire directement
                                                try:
                                                    stderr_msg = process.stderr.read(1000)
                                                except Exception:
                                                    pass
                                    except Exception:
                                        pass
                                    
                                    error_msg = f"Processus terminé avant écriture stdin (code: {exit_code})"
                                    if stderr_msg:
                                        error_msg += f" - stderr: {stderr_msg[:500]}"
                                    
                                    UnifiedLogger.write(
                                        "AI_CORE",
                                        "ERROR",
                                        f"CLI Erreur stdin: {error_msg}"
                                    )
                                    raise Exception(error_msg)
                                
                                # Vérifier que stdin est toujours ouvert
                                if process.stdin is None:
                                    raise Exception("stdin est None - le processus n'a pas de stdin")
                                if process.stdin.closed:
                                    raise Exception("stdin est déjà fermé - le processus a peut-être terminé")
                                
                                # Écrire le prompt
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "DEBUG",
                                    f"CLI Écriture stdin: {len(full_prompt)} caractères (transport: {'SSE' if self._mcp_http_available else 'stdio'})"
                                )
                                
                                process.stdin.write(full_prompt)
                                if not full_prompt.endswith("\n"):
                                    process.stdin.write("\n")
                                process.stdin.flush()  # Forcer l'écriture
                                process.stdin.close()
                                stdin_write_complete[0] = True
                                
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "DEBUG",
                                    "CLI stdin écrit avec succès"
                                )
                                
                            except Exception as e:
                                stdin_write_error[0] = e
                                
                                # Log détaillé de l'erreur
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "ERROR",
                                    f"CLI Erreur écriture stdin: {str(e)} (transport: {'SSE' if self._mcp_http_available else 'stdio'})"
                                )
                                
                                # Log l'erreur stderr si disponible pour diagnostic
                                try:
                                    if process.stderr:
                                        # Lire stderr de manière non-bloquante
                                        import select
                                        import sys
                                        if sys.platform != 'win32':
                                            # Sur Unix, on peut utiliser select
                                            if select.select([process.stderr], [], [], 0)[0]:
                                                stderr_output = process.stderr.read()
                                                if stderr_output:
                                                    UnifiedLogger.write(
                                                        "AI_CORE",
                                                        "DEBUG",
                                                        f"CLI stderr (erreur stdin): {stderr_output[:500]}"
                                                    )
                                        else:
                                            # Sur Windows, essayer de lire directement
                                            try:
                                                stderr_output = process.stderr.read(1000)
                                                if stderr_output:
                                                    UnifiedLogger.write(
                                                        "AI_CORE",
                                                        "DEBUG",
                                                        f"CLI stderr (erreur stdin): {stderr_output[:500]}"
                                                    )
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                                
                                # Fermer stdin proprement
                                try:
                                    if process.stdin and not process.stdin.closed:
                                        process.stdin.close()
                                except Exception:
                                    pass
                        
                        # Lancer le thread d'écriture stdin immédiatement
                        stdin_thread = Thread(target=write_stdin_async, args=(process, stdin_prompt), daemon=True)
                        stdin_thread.start()
                        
                        # On continue immédiatement à lire stdout pendant que stdin s'écrit en arrière-plan
                        # Le thread se terminera automatiquement quand stdin sera fermé
                        stdin_sent = time.time()
                        UnifiedLogger.write(
                            "AI_CORE",
                            "DEBUG",
                            f"CLI stdin écriture asynchrone lancée ({len(stdin_prompt)} chars) en {(stdin_sent - stdin_start)*1000:.2f}ms"
                        )
                        
                        # OPTIMISATION: Lecture stdout non-bloquante avec thread + queue
                        # Permet de détecter rapidement la première ligne sans bloquer
                        stdout_queue = Queue()
                        stdout_finished = [False]  # Flag pour indiquer la fin de la lecture
                        stdout_error = [None]  # Capturer les erreurs depuis le thread
                        
                        # OPTIMISATION: Lecture stderr non-bloquante pour diagnostiquer les erreurs
                        stderr_queue = Queue()
                        stderr_finished = [False]
                        stderr_lines = []  # Capturer toutes les lignes stderr pour diagnostic
                        
                        def read_stdout_thread(process, queue, finished_flag, error_flag):
                            """Thread qui lit stdout et met les lignes dans la queue."""
                            try:
                                for line in process.stdout:
                                    queue.put(line)
                                finished_flag[0] = True
                            except Exception as e:
                                error_flag[0] = e
                                finished_flag[0] = True
                        
                        def read_stderr_thread(process, queue, finished_flag, lines_list):
                            """Thread qui lit stderr et met les lignes dans la queue + liste."""
                            try:
                                for line in process.stderr:
                                    line_text = line.strip()
                                    if line_text:
                                        lines_list.append(line_text)
                                        queue.put(line_text)
                                        # Logger immédiatement les erreurs stderr pour diagnostic
                                        UnifiedLogger.write(
                                            "AI_CORE",
                                            "DEBUG",
                                            f"CLI stderr: {line_text[:500]}"
                                        )
                                finished_flag[0] = True
                            except Exception as e:
                                UnifiedLogger.write(
                                    "AI_CORE",
                                    "DEBUG",
                                    f"CLI Erreur lecture stderr: {e}"
                                )
                                finished_flag[0] = True
                        
                        # Lancer les threads de lecture stdout et stderr
                        stdout_thread = Thread(
                            target=read_stdout_thread,
                            args=(process, stdout_queue, stdout_finished, stdout_error),
                            daemon=True
                        )
                        stdout_thread.start()
                        
                        stderr_thread = Thread(
                            target=read_stderr_thread,
                            args=(process, stderr_queue, stderr_finished, stderr_lines),
                            daemon=True
                        )
                        stderr_thread.start()
                        
                        # Mesure du temps avant la première ligne de sortie
                        first_line_received = False
                        first_line_time = None
                        full_response = ""
                        
                        # Lire depuis la queue de manière non-bloquante
                        while not stdout_finished[0] or not stdout_queue.empty():
                            try:
                                # Timeout court pour éviter de bloquer indéfiniment
                                line = stdout_queue.get(timeout=0.1)
                                
                                if not first_line_received:
                                    first_line_time = time.time()
                                    first_line_delay = (first_line_time - stdin_sent) * 1000
                                    UnifiedLogger.write(
                                        "AI_CORE",
                                        "DEBUG",
                                        f"CLI Première ligne reçue après {first_line_delay:.0f}ms (découverte MCP + construction payload + latence réseau)"
                                    )
                                    first_line_received = True
                                
                                if line.strip():
                                    full_response += line
                                    yield line
                                    
                            except Empty:
                                # Pas de ligne disponible, continuer la boucle
                                continue
                        
                        # Vérifier s'il y a eu une erreur dans le thread de lecture
                        if stdout_error[0]:
                            raise Exception(f"Erreur lecture stdout: {stdout_error[0]}")
                        
                        # Attendre que les threads se terminent
                        stdout_thread.join(timeout=1.0)
                        stderr_thread.join(timeout=1.0)
                        
                        # Logger toutes les erreurs stderr capturées si le processus s'est terminé sans sortie
                        if not first_line_received and stderr_lines:
                            UnifiedLogger.write(
                                "AI_CORE",
                                "ERROR",
                                f"CLI Aucune sortie stdout, mais {len(stderr_lines)} lignes stderr capturées: {stderr_lines[:10]}"
                            )
                        
                        # Attente de la fin du processus
                        process.wait()
                        process_end = time.time()
                        
                        # Vérifier si l'écriture stdin a terminé et s'il y a eu une erreur
                        if stdin_write_error[0]:
                            raise Exception(f"Erreur écriture stdin: {stdin_write_error[0]}")
                        
                        # Attendre que le thread stdin se termine (devrait déjà être terminé)
                        stdin_thread.join(timeout=1.0)  # Timeout de 1s pour éviter de bloquer indéfiniment
                        if stdin_thread.is_alive():
                            UnifiedLogger.write(
                                "AI_CORE",
                                "WARNING",
                                "CLI Thread stdin n'a pas terminé dans les temps (timeout 1s)"
                            )
                        
                        # Calculer le temps réel d'écriture stdin (approximatif, car asynchrone)
                        # On utilise le temps jusqu'à la première ligne comme proxy
                        stdin_write_complete_time = first_line_time if first_line_received else stdin_sent
                        stdin_duration_ms = (stdin_write_complete_time - stdin_start) * 1000
                        
                        # Logs détaillés des timings
                        total_duration = (process_end - process_start) * 1000
                        process_creation_ms = (process_created - process_start) * 1000
                        first_line_delay_ms = (first_line_time - stdin_sent) * 1000 if first_line_received else 0
                        streaming_duration_ms = (process_end - first_line_time) * 1000 if first_line_received else 0
                        
                        UnifiedLogger.write(
                            "AI_CORE",
                            "DEBUG",
                            "CLI Timing Breakdown",
                            {
                                "process_creation_ms": process_creation_ms,
                                "stdin_write_ms": stdin_duration_ms,
                                "first_line_delay_ms": first_line_delay_ms,
                                "streaming_duration_ms": streaming_duration_ms,
                                "total_ms": total_duration,
                                "response_length": len(full_response)
                            }
                        )
                        
                        if process.returncode != 0:
                            error_output = process.stderr.read()
                            raise Exception(f"CLI Error (code {process.returncode}): {error_output}")
                        
                        # Ajout à l'historique
                        self.history.append(self._create_msg("user", message))
                        self.history.append(self._create_msg("assistant", full_response))
                        
                        # Calculer le texte d'entrée total
                        input_text_total = (stdin_prompt or "") + "\n" + (msg_arg or "")
                        
                        duration = time.time() - start_t
                        
                        # NOTE: On ne sauvegarde PAS la réponse pour GeminiCliSession
                        # Le payload CodeAssist final contient déjà toutes les informations nécessaires
                        # _save_response_log("gemini_cli", self.model_name, response_log_data, {...})  # Désactivé
                        
                        # Logger les métriques
                        self._log_metrics(start_t, input_text_total, full_response)
                        
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
                
                # Calculer le texte d'entrée total
                input_text_total = (stdin_prompt or "") + "\n" + (msg_arg or "")
                
                duration = time.time() - start_t
                
                # NOTE: On ne sauvegarde PAS la réponse pour GeminiCliSession
                # Le payload CodeAssist final contient déjà toutes les informations nécessaires
                # _save_response_log("gemini_cli", self.model_name, response_log_data, {...})  # Désactivé
                
                # Logger les métriques
                self._log_metrics(start_t, input_text_total, content)
                
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

    def _build_codeassist_final_payload(
        self,
        stdin_prompt: str,
        msg_arg: str,
        model_name: str
    ) -> dict:
        """
        Reconstruit le payload FINAL que gemini-cli envoie à CodeAssist.
        Inclut le contexte complet, le message, et tous les outils MCP.
        
        Args:
            stdin_prompt: Le contexte complet (Arch, Tree, LTM, RAG)
            msg_arg: Le message utilisateur
            model_name: Nom du modèle
            
        Returns:
            Payload CodeAssist complet au format CAGenerateContentRequest
        """
        from ai_core.code_assist_converter import to_generate_content_request
        from config.tools_schema import TOOLS_SCHEMA
        
        # Construire les messages au format Gemini API
        # Le stdin_prompt devient le systemInstruction
        # Le msg_arg devient le contenu utilisateur
        messages = [
            {"role": "user", "content": msg_arg}
        ]
        
        # Récupérer les outils MCP (via TOOLS_SCHEMA pour l'instant)
        # Note: gemini-cli découvre les outils via le serveur MCP configuré dans .gemini/settings.json
        # On utilise TOOLS_SCHEMA comme approximation des outils disponibles
        tools = TOOLS_SCHEMA if TOOLS_SCHEMA else None
        
        # Construire le payload CodeAssist final
        # IMPORTANT: stdin_prompt est inclus intégralement sans troncature
        # IMPORTANT: tools contient TOUS les outils MCP avec leurs schémas complets
        ca_payload = to_generate_content_request(
            model=model_name,
            messages=messages,
            system_instruction=stdin_prompt,  # Le contexte complet devient systemInstruction (18-25kb)
            tools=tools,  # Tous les outils MCP complets (20-30kb)
            function_calling_mode="AUTO",  # Mode par défaut pour gemini-cli
            temperature=0.7,
            **{}
        )
        
        # Vérification post-construction : s'assurer que le payload contient bien tout
        request_payload = ca_payload.get("request", ca_payload)
        if "systemInstruction" not in request_payload:
            UnifiedLogger.write("AI_CORE", "WARNING", "Payload CodeAssist: systemInstruction manquant")
        if "tools" not in request_payload or not request_payload.get("tools"):
            UnifiedLogger.write("AI_CORE", "WARNING", "Payload CodeAssist: tools manquants ou vides")
        if "toolConfig" not in request_payload:
            UnifiedLogger.write("AI_CORE", "WARNING", "Payload CodeAssist: toolConfig manquant")
        
        return ca_payload

    def _log_metrics(self, start_time, input_text, output_text):
        """
        Logge les métriques d'usage pour GeminiCliSession.
        Estime les tokens à partir de la taille du texte (approximation: 1 token ≈ 3.5 caractères).
        Utilise les métriques du payload final CodeAssist si disponibles (inclut les outils).
        
        Args:
            start_time: Temps de début (time.time())
            input_text: Texte d'entrée complet (stdin_prompt + msg_arg) - utilisé comme fallback
            output_text: Texte de sortie (réponse complète)
        """
        duration = time.time() - start_time
        
        try:
            from features.TokenManager import TokenManager
        except ImportError:
            TokenManager = None
        
        # Utiliser les métriques du payload final CodeAssist si disponibles (inclut les outils)
        # Sinon, utiliser l'estimation basée sur input_text (fallback)
        if hasattr(self, '_last_payload_estimated_tokens') and self._last_payload_estimated_tokens:
            in_tok = self._last_payload_estimated_tokens
        else:
            # Estimation des tokens (ratio plus précis pour contenu mixte: 1 token ≈ 3.5 caractères)
            # Pour Gemini avec contenu mixte (code + texte + markdown), 3.5 est plus précis que 4
            in_tok = int(len(input_text) / 3.5) if input_text else 0
        
        out_tok = int(len(output_text) / 3.5) if output_text else 0
        
        # Enregistrer dans TokenManager si disponible
        if TokenManager:
            # Pour CLI, on n'a pas de clé API, donc on passe None
            # TokenManager gérera le cas où current_key est None
            try:
                TokenManager.add_usage(self.model_name, None, in_tok, out_tok)
            except Exception:
                pass  # Ne pas bloquer si TokenManager échoue
        
        # Construire les métriques au même format que GeminiSession
        metrics_data = {
            "model": self.model_name,
            "agent": self.agent_name or "Fast",  # Fallback sur "Fast" si None
            "in": in_tok,
            "out": out_tok,
            "time": f"{duration:.2f}s",
            "provider": "Gemini CLI"  # Distinguer du provider "Gemini" standard
        }
        
        UnifiedLogger.write("AI_CORE", "METRICS", "Usage", metrics_data)

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
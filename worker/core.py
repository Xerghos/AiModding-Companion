import threading
import queue
import time
import traceback
import os
import json
import re
import features.audio as audio_manager
from concurrent.futures import ThreadPoolExecutor

# --- Imports Configuration (Modularisés) ---
from config.settings import APP_SETTINGS
from config.paths import get_path
from config.logs import get_logger
from features.UnifiedLogger import UnifiedLogger
from features.Documentation import task_documenter_fichier_atomique

# --- Imports AI Core (Modularisés) ---
from ai_core.factory import SessionFactory
from ai_core.sessions import call_ai_robust
from features.Decorators import trace_action

# --- Imports Features (Optionnels / Lazy) ---
try:
    from features.CacheManager import GlobalCacheManager
except ImportError:
    GlobalCacheManager = None

try:
    from features.context import database
except ImportError:
    database = None

# Import du Gestionnaire de Mémoire Centralisé
try:
    from features.SemanticMemory import GlobalMemoryManager
except ImportError:
    GlobalMemoryManager = None
    # On loggue l'erreur mais on ne bloque pas le démarrage
    UnifiedLogger.write("WORKER", "WARNING", "SemanticMemory non trouvé. Mode sans mémoire persistante.")

try:
    from agents.agent_personas import META_INSTRUCTIONS, SWARM_AGENTS
    # AJOUTER CETTE LIGNE :
    from agents.swarm_manager import create_agent 
except ImportError:
    META_INSTRUCTIONS = "Tu es un Assistant IA Expert."
    SWARM_AGENTS = {}
    # Et définir un fallback si nécessaire, ou laisser planter si critique
    create_agent = None

analyze_request_and_dispatch = None 
try:
    import features.CodeQuality as CodeQuality
    import features.Documentation as Documentation
    import features.Refactoring as Refactoring
    import features.ProjectManager as ProjectManager
    import features.GitActions as GitActions
    import features.BackupManager as BackupManager
    import features.core_backup as core_backup
    
    from features.ai_helper import analyze_request_and_dispatch
except ImportError as e:
    UnifiedLogger.write("WORKER", "CRITICAL", f"Erreur critique imports Features: {e}")

log = get_logger("worker.core")
FULL_CHAT_HISTORY_FILE = "full_chat_history.json"

class Worker(threading.Thread):
    """
    Worker Thread Principal (V24 - Architecture Modulaire & Stabilisée).
    Gère le Chat, la Mémoire, et les Agents Persistants.
    """
    def __init__(self, task_queue, response_queue, stop_event):
        super().__init__()
        self.task_queue = task_queue
        self.response_queue = response_queue
        self.stop_event = stop_event
        self.daemon = True
        
        self.main_session = None 
        # Sessions persistantes pour les agents (Swarm)
        self.agent_sessions = {} 
        self.abort_current_stream = False
        self.bg_task_desc = None
        self.current_task_desc = None
        # [AJOUT] Suivi de la tâche en cours pour l'affichage Queue
        self.current_task_desc = None
        self.reasoning_active = False
        self.bg_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="SwarmWorker")
        
        # [NOUVEAU] Timer pour l'automaintenance
        self.last_arch_update = time.time()
        
        # Init Config interne
        self._refresh_config()
    
    @trace_action(source="core")
    def _refresh_config(self):
        """Hot Reload : Met à jour les variables internes."""
        try:
            from config.settings import reload_app_settings, APP_SETTINGS
            reload_app_settings()
            
            self.autonomy_mode = APP_SETTINGS.get("swarm_settings", {}).get("autonomy_level", "supervised")
            self.max_react_depth = int(APP_SETTINGS.get("agents_config", {}).get("react_max_steps_cloud", 10))
            self.rag_enabled = True 
            
            log.info(f"🔥 Hot Reload Worker effectué : Autonomie={self.autonomy_mode}")
        except Exception as e:
            log.error(f"Erreur Hot Reload Worker: {e}")

    @trace_action(source="core")
    def get_main_session(self):
        """Lazy loading de la session avec RESTAURATION COMPLÈTE."""
        if not self.main_session:
            log.info("Création de la session Chat Principale...")
            self.main_session = SessionFactory.create_session(
                model_type="fast", 
                system_instruction=META_INSTRUCTIONS
            )
            # Chargement Historique via SemanticMemory
            if GlobalMemoryManager:
                GlobalMemoryManager.load_history_into_session(self.main_session)
            else:
                # Fallback manuel si SemanticMemory absent (Robustesse)
                try:
                    history_path = get_path(FULL_CHAT_HISTORY_FILE)
                    if os.path.exists(history_path):
                        with open(history_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        # Logique simple de restauration si nécessaire
                except: pass
                
        return self.main_session

    @trace_action(source="core")
    def _warmup_caches(self):
        """Préchauffage des caches."""
        if not GlobalCacheManager: return
        try:
            ai_conf = APP_SETTINGS.get("ai_engine", {}).get("cloud_models_registry", {})
            required_models = {ai_conf.get("fast", "gemini-1.5-flash")}
            api_key = APP_SETTINGS.get("api_keys", {}).get("google_gemini", "").split(',')[0]
            
            if api_key:
                for model in required_models:
                    if "gemini" in model.lower():
                        GlobalCacheManager.get_or_create_cache(api_key, model)
        except Exception: pass

    @trace_action(source="core")
    def _perform_startup_audit(self):
        try:
            if hasattr(SessionFactory, 'audit_all_providers'):
                SessionFactory.audit_all_providers()
        except: pass

    # --- RAG ---

    @trace_action(source="core")
    def _retrieve_rag_context(self, query):
        """
        Récupère le contexte hybride avec Repo Map.
        Retourne un dict avec les composants séparés pour injection en blocs distincts.
        """
        if not database or not self.rag_enabled or len(query) < 3: 
            return {"repo_map": None, "docs": None, "ltm": None}
        
        rag_components = {"repo_map": None, "docs": None, "ltm": None}
        
        # A. Repo Map (contexte structurel global)
        try:
            from features.context.repo_map import get_repo_map_generator
            db_path = get_path(APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid"))
            repo_map_gen = get_repo_map_generator(db_path)
            # Pas de limite : Repo Map complète (non tronquée)
            repo_map = repo_map_gen.get_repo_map_for_context(max_chars=None)
            if repo_map:
                rag_components["repo_map"] = repo_map
        except Exception as e:
            log.debug(f"Repo Map non disponible: {e}")
        
        # B. Documents (RAG Hybride) - Style Cursor
        try:
            db_path = get_path(APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid"))
            # Utiliser la recherche hybride (FAISS + FTS5 avec RRF, k=60 comme Cursor)
            # Récupérer plus de candidats initialement pour meilleur filtrage (style Cursor: 50-100 candidats)
            # On prend 15 candidats puis on filtre par seuil RRF pour obtenir les 3-5 meilleurs
            results, _ = database.search_hybrid(query, db_path, max_results=15, use_hybrid=True)
            
            doc_ctx_lines = []
            if results:
                log.debug(f"RAG: {len(results)} résultats initiaux de la recherche hybride")
                
                # Seuil de pertinence RRF (selon doc Cursor: scores typiquement 0.01-0.03 pour bons résultats)
                # Seuil plus strict pour ne montrer que les résultats les plus pertinents (style Cursor)
                RRF_THRESHOLD = 0.01
                
                # Budget total de contexte pour les docs RAG (style Cursor - plus sélectif)
                # Limite réduite pour privilégier la qualité sur la quantité
                MAX_TOTAL_CHARS = 3000
                total_chars = 0
                
                # Déduplication par source (éviter plusieurs chunks du même fichier)
                seen_sources = set()
                
                # Compteurs pour diagnostic
                filtered_count = 0
                accepted_count = 0
                
                # Décompacter les résultats avec métadonnées (compatibilité avec ancien format)
                for result in results:
                    # Gérer l'ancien format (3 éléments) et le nouveau format (7 éléments)
                    if len(result) == 3:
                        src, content, score = result
                        ast_type, parent_context, start_line, end_line = None, None, None, None
                    else:
                        src, content, score, ast_type, parent_context, start_line, end_line = result[:7]
                    
                    if "memory://" in src:
                        continue
                    
                    # Filtrer par seuil de pertinence RRF (comme Cursor)
                    should_skip = False
                    if isinstance(score, (int, float)):
                        # Les scores RRF varient typiquement de 0.01 à 0.03 pour les bons résultats (k=60)
                        # Si le score est > 1.0, c'est probablement une distance vectorielle (pas RRF)
                        # Dans ce cas, on accepte seulement si distance < 2.5 (très proche)
                        if score >= 1.0:
                            # C'est probablement une distance L2, pas un score RRF
                            if score > 2.5:  # Distance trop grande
                                should_skip = True
                                filtered_count += 1
                            # On accepte mais on note que c'est une distance, pas un score RRF
                        elif score < RRF_THRESHOLD:
                            should_skip = True
                            filtered_count += 1  # Score RRF trop faible, résultat peu pertinent
                    else:
                        should_skip = True
                        filtered_count += 1  # Score invalide
                    
                    if should_skip:
                        continue
                    
                    # Éviter les doublons par source (même fichier)
                    source_key = os.path.basename(src) if src else ""
                    if source_key in seen_sources:
                        filtered_count += 1
                        continue  # Déjà traité ce fichier
                    seen_sources.add(source_key)
                    accepted_count += 1
                    
                    # Vérifier le budget de contexte restant
                    remaining_chars = MAX_TOTAL_CHARS - total_chars
                    if remaining_chars <= 200:  # Pas assez d'espace pour un chunk significatif
                        break
                    
                    # Troncature intelligente pour préserver la structure sémantique (style Cursor)
                    chunk_display = content
                    needs_truncation = len(content) > remaining_chars
                    
                    if needs_truncation:
                        truncate_pos = remaining_chars - 100  # Marge pour "... [tronqué]"
                        
                        # 1. Si end_line est disponible, utiliser le contenu réel jusqu'à cette ligne
                        # (le chunk devrait déjà être délimité par start_line et end_line, donc normalement pas nécessaire)
                        # Mais si le contenu stocké est plus long que prévu, on peut tronquer
                        
                        # 2. Chercher des frontières sémantiques naturelles (dé-indentation, lignes vides)
                        # Analyser les lignes autour de truncate_pos pour trouver une frontière de bloc
                        lines = content[:truncate_pos + 500].split('\n')  # Analyser un peu plus loin
                        truncate_line_idx = None
                        target_char_count = truncate_pos
                        
                        # Compter les caractères jusqu'à chaque ligne
                        char_count = 0
                        for i, line in enumerate(lines):
                            line_with_newline = line + '\n'
                            next_char_count = char_count + len(line_with_newline)
                            
                            if next_char_count > target_char_count:
                                # On cherche une frontière sémantique dans les lignes précédentes
                                # Chercher en arrière (jusqu'à 10 lignes) une frontière naturelle
                                for j in range(i, max(0, i - 10), -1):
                                    if j == 0:
                                        truncate_line_idx = 0
                                        break
                                    
                                    prev_line = lines[j - 1] if j > 0 else ""
                                    curr_line = lines[j]
                                    
                                    # Frontière : ligne vide ou dé-indentation significative
                                    if prev_line.strip() == "":
                                        truncate_line_idx = j - 1
                                        break
                                    # Dé-indentation : ligne précédente avait plus d'indentation que la suivante
                                    # (mais pas si c'est juste une ligne de code normale)
                                    elif j < len(lines) - 1:
                                        prev_indent = len(prev_line) - len(prev_line.lstrip())
                                        next_indent = len(curr_line) - len(curr_line.lstrip())
                                        # Dé-indentation significative (retour au niveau parent)
                                        if prev_indent > 0 and next_indent < prev_indent - 2:
                                            truncate_line_idx = j - 1
                                            break
                                
                                if truncate_line_idx is None:
                                    truncate_line_idx = i - 1 if i > 0 else 0
                                break
                            
                            char_count = next_char_count
                        
                        # Si on a trouvé une bonne frontière, utiliser cette ligne
                        if truncate_line_idx is not None and truncate_line_idx < len(lines):
                            truncated_lines = lines[:truncate_line_idx + 1]
                            chunk_display = '\n'.join(truncated_lines).rstrip() + "\n... [tronqué à la frontière sémantique]"
                        else:
                            # Fallback : chercher une nouvelle ligne proche
                            last_newline = content.rfind('\n', 0, truncate_pos)
                            if last_newline > truncate_pos * 0.7:  # Au moins 70% de la limite atteinte
                                chunk_display = content[:last_newline] + "\n... [tronqué]"
                            else:
                                # Fallback: couper à un espace si pas de nouvelle ligne proche
                                last_space = content.rfind(' ', 0, truncate_pos)
                                if last_space > truncate_pos * 0.8:
                                    chunk_display = content[:last_space] + " ... [tronqué]"
                                else:
                                    # Dernier recours: troncature brute avec indication
                                    chunk_display = content[:truncate_pos] + " ... [tronqué]"
                    
                    # Construire le header enrichi avec métadonnées
                    header_parts = []
                    if start_line and end_line:
                        header_parts.append(f"{os.path.basename(src)}:{start_line}-{end_line}")
                    else:
                        header_parts.append(os.path.basename(src))
                    
                    if ast_type:
                        header_parts.append(f"type: {ast_type}")
                    
                    if parent_context:
                        # Extraire seulement le nom de la fonction/classe du parent context
                        parent_parts = parent_context.split('>')
                        if len(parent_parts) > 1:
                            last_part = parent_parts[-1].strip()
                            # Extraire le nom de fonction/classe si présent
                            if ':' in last_part:
                                func_or_class = last_part.split(':')[-1].strip()
                                header_parts.append(f"context: {func_or_class}")
                    
                    # Format structuré avec score et métadonnées
                    if score < 1.0:
                        score_label = "Score RRF"
                    else:
                        score_label = "Distance"
                    score_str = f"{score:.4f}"
                    
                    header = f"• [{' | '.join(header_parts)}] ({score_label}: {score_str})"
                    doc_ctx_lines.append(f"{header}:\n{chunk_display}")
                    total_chars += len(chunk_display)
                
                if doc_ctx_lines:
                    # Limiter à 3 résultats maximum après filtrage (style Cursor - privilégier qualité sur quantité)
                    max_display_results = min(3, len(doc_ctx_lines))
                    rag_components["docs"] = "\n\n".join(doc_ctx_lines[:max_display_results])
                    log.debug(f"RAG: {accepted_count} résultats acceptés, {filtered_count} filtrés, {len(doc_ctx_lines)} affichés")
                else:
                    # Log pour diagnostic si aucun résultat ne passe les filtres
                    log.warning(f"RAG: {len(results)} résultats initiaux, mais aucun n'a passé les filtres ({filtered_count} filtrés, {accepted_count} acceptés)")
                    # Accepter quand même les 3 premiers résultats même avec scores faibles pour éviter un bloc vide
                    log.info("RAG: Fallback - acceptation des 3 premiers résultats malgré filtres")
                    fallback_sources = set()
                    for i, result in enumerate(results[:3]):
                        # Gérer l'ancien et nouveau format
                        if len(result) == 3:
                            src, content, score = result
                            ast_type, parent_context, start_line, end_line = None, None, None, None
                        else:
                            src, content, score, ast_type, parent_context, start_line, end_line = result[:7]
                        
                        if "memory://" in src:
                            continue
                        source_key = os.path.basename(src) if src else ""
                        if source_key in fallback_sources:
                            continue
                        fallback_sources.add(source_key)
                        chunk_preview = content[:800] + ("..." if len(content) > 800 else "")
                        score_str = f"{score:.4f}"
                        score_label = "Score RRF" if score < 1.0 else "Distance"
                        
                        # Header enrichi pour fallback aussi
                        header_parts = [source_key]
                        if start_line and end_line:
                            header_parts[0] = f"{source_key}:{start_line}-{end_line}"
                        if ast_type:
                            header_parts.append(f"type: {ast_type}")
                        
                        header = f"• [{' | '.join(header_parts)}] ({score_label}: {score_str})"
                        doc_ctx_lines.append(f"{header}:\n{chunk_preview}")
                    if doc_ctx_lines:
                        rag_components["docs"] = "\n\n".join(doc_ctx_lines)
        except Exception as e: 
            log.warning(f"RAG Error: {e}", exc_info=True)

        # C. Souvenirs (LTM)
        try:
            if GlobalMemoryManager:
                ltm_ctx = GlobalMemoryManager.retrieve_relevant_context(query)
                if ltm_ctx: 
                    rag_components["ltm"] = ltm_ctx
        except: pass

        # Retourner le dict même s'il est vide pour compatibilité
        return rag_components

    # --- AGENTS (SWARM) ---

    @trace_action(source="core")
    def _handle_agent_task(self, payload):
        """Exécute une tâche via un agent spécialisé (Swarm V2 - Context Aware)."""
        if not create_agent:
            self.response_queue.put({"type": "error", "text": "Swarm Manager non disponible."})
            return

        role = payload.get("agent_role", "assistant") # Ou 'agent_type' selon l'appelant
        if not role or role == "assistant": role = payload.get("agent_type", "ROUTER")
        
        prompt = payload.get("prompt", "")
        task_id = payload.get("task_id", "unknown")
        
        log.info(f"🤖 Swarm: Activation Agent '{role}' pour tâche '{task_id}'...")

        # --- 1. CONSTRUCTION DU CONTEXTE INTELLIGENT (RAG + STM) ---
        # A. Contexte Long Terme (RAG / Base de connaissance)
        rag_context = self._retrieve_rag_context(prompt)
        
        # B. Contexte Court Terme (Discussion récente)
        stm_context = ""
        if self.main_session and hasattr(self.main_session, 'history'):
            # On récupère les 6 derniers messages pour avoir le fil de la conversation
            try:
                # Gestion compatible Gemini/Groq (objets ou dicts)
                msgs = self.main_session.history[-6:]
                for m in msgs:
                    r = m.role if hasattr(m, 'role') else m.get('role', '?')
                    c = m.parts[0].text if hasattr(m, 'parts') else m.get('content', '')
                    stm_context += f"[{r.upper()}]: {str(c)[:500]}...\n"
            except Exception as e:
                log.warning(f"Erreur lecture historique STM: {e}")

        final_context = (
            f"--- 🧠 CONTEXTE RAG (DOCUMENTATION & SOUVENIRS) ---\n{rag_context}\n\n"
            f"--- 💬 CONTEXTE STM (DISCUSSION RÉCENTE) ---\n{stm_context}"
        )

        # --- 2. CRÉATION & EXÉCUTION ---
        try:
            # L'agent est créé à la volée avec son contexte frais ET le mode de raisonnement
            agent = create_agent(
                role, 
                initial_context=final_context, 
                reasoning_mode=self.reasoning_active  # <--- AJOUTER ICI
            )
            
            # Exécution Synchrone
            response = agent.execute_task(prompt)
            
            # Extraction du texte propre
            final_text = response.text if hasattr(response, 'text') else str(response)
            
            self.response_queue.put({
                "type": "agent_response",
                "role": role,
                "text": final_text,
                "task_id": task_id
            })
            
        except Exception as e:
            log.error(f"Erreur Agent {role}: {e}\n{traceback.format_exc()}")
            self.response_queue.put({
                "type": "error",
                "text": f"Agent {role} failed: {e}",
                "task_id": task_id
            })

    # --- HANDLERS UI ---

    @trace_action(source="core")
    def _save_and_display(self, text, role="assistant"):
        if GlobalMemoryManager and self.main_session:
            GlobalMemoryManager.save_session_history(self.main_session)
        self.response_queue.put({"type": "chat_response", "text": text, "action": "chat"})
    
    @trace_action(source="core")
    def _execute_tool(self, tool_function, args, kwargs):
        """Exécute une fonction d'outil avec gestion d'erreurs."""
        tool_name = tool_function.__name__
        UnifiedLogger.write("WORKER", "TOOL_START", f"Exécution {tool_name}", {"args": str(args)[:200]})
        
        try:
            # Validation sommaire
            if not isinstance(args, (list, tuple)):
                raise ValueError(f"Arguments positionnels invalides pour {tool_name}")

            result = tool_function(*args, **kwargs)
            UnifiedLogger.write("WORKER", "TOOL_END", f"Succès {tool_name}")
            return result

        except Exception as e:
            UnifiedLogger.write("WORKER", "TOOL_ERROR", f"Echec {tool_name}", {"error": str(e), "trace": traceback.format_exc()})
            self.response_queue.put({
                'type': 'error', 
                'text': f"Erreur outil '{tool_name}': {e}"
            })
            return None

    # --- HANDLERS DIRECTS ---

    @trace_action(source="core")
    def _handle_analyze_file(self, payload):
        """Audit de code direct (Bouton UI)."""
        if CodeQuality:
            res = self._execute_tool(CodeQuality.execute_verifier_code, 
                                     [payload.get('file_path'), payload.get('prompt', ''), self.get_main_session(), "action_log.json", self.response_queue], {})
            if res: self._save_and_display(res)
        else:
            self.response_queue.put({'type': 'error', 'text': "Module CodeQuality non chargé."})

    @trace_action(source="core")
    def _handle_refactor(self, payload):
        """Refactoring direct (Bouton UI)."""
        if Refactoring:
            res = self._execute_tool(Refactoring.execute_refactoriser_code,
                                     [payload.get('file_path'), payload.get('prompt', ''), self.get_main_session(), "action_log.json", self.response_queue],
                                     {'auto_apply': False}) # Sécurité
            if res: self._save_and_display(res)
        else:
            self.response_queue.put({'type': 'error', 'text': "Module Refactoring non chargé."})

    @trace_action(source="core")
    def _handle_gen_doc(self, payload):
        """Documentation directe (Bouton UI)."""
        if Documentation:
            res = self._execute_tool(Documentation.execute_generer_documentation,
                                     [payload.get('file_path'), "resume", self.get_main_session(), "action_log.json", self.response_queue, self.task_queue], {})
            if res: self._save_and_display(res)
        else:
            self.response_queue.put({'type': 'error', 'text': "Module Documentation non chargé."})

    @trace_action(source="core")
    def _handle_chat_stream(self, payload):
        """Gère le flux de discussion avec le support RAG V5 Atomique."""
        try:
            self.bg_task_desc = f"🤖 Génération réponse..."
            self.abort_current_stream = False
            self.response_queue.put({'type': 'ui_stream_start'})
            
            session = self.get_main_session()
            user_msg = payload.get("message", "")
            
            # Récupération du contexte RAG (Document + Mémoire LTM)
            rag = self._retrieve_rag_context(user_msg)
            
            # [CORRECTION V5] On ne fusionne PLUS le RAG dans le prompt.
            # On le passe comme argument séparé pour injection dans le Bloc 4.
            prompt = user_msg
            
            # Appel Robuste avec passage du RAG Context
            response_gen = call_ai_robust(session, prompt, stream=True, rag_context=rag)
            
            full_text = ""
            has_received_content = False
            
            if response_gen:
                try:
                    for chunk in response_gen:
                        if self.abort_current_stream:
                            self.response_queue.put({'type': 'ui_stream_chunk', 'text': "\n[INTERROMPU]"})
                            break
                        
                        # Gérer différents formats de chunks
                        txt = None
                        if hasattr(chunk, 'text'):
                            txt = chunk.text
                        elif isinstance(chunk, str):
                            txt = chunk
                        else:
                            # Essayer de convertir en string
                            txt = str(chunk) if chunk else None
                        
                        if txt and txt.strip():
                            full_text += txt
                            has_received_content = True
                            self.response_queue.put({'type': 'ui_stream_chunk', 'text': txt})
                except StopIteration:
                    # Itérateur terminé normalement
                    pass
                except Exception as stream_err:
                    log.error(f"Erreur lors du stream: {stream_err}")
                    if not has_received_content:
                        # Si on n'a rien reçu, c'est un problème
                        self.response_queue.put({'type': 'ui_stream_chunk', 'text': f"\n[Erreur stream: {stream_err}]"})
            else:
                # response_gen est None ou vide
                log.warning("⚠️ Réponse IA vide reçue (générateur None ou vide).")
                self.response_queue.put({'type': 'ui_stream_chunk', 'text': "\n[⚠️ Aucune réponse reçue de l'IA]"})
            
            self.response_queue.put({'type': 'ui_stream_end'})
            
            if not self.abort_current_stream:
                # 1. Détection !native_tool standard (JSON Strict) - Reconstruit par Session
                native_match = re.search(r"(!native_tool\s*\{.*?\})", full_text, re.DOTALL)
                
                # 2. Détection Hallucination (Backup)
                memory_match = re.search(r"\[TOOL_CALL:\s*(\w+)\((.*?)\)\]", full_text, re.DOTALL)
                
                cmd_to_execute = None

                if native_match:
                    raw_cmd = native_match.group(1).strip()
                    if '"name": "..."' in raw_cmd or "'name': '...'" in raw_cmd:
                        log.warning("🛑 Tentative d'exécution d'un placeholder '...' bloquée.")
                    else:
                        cmd_to_execute = raw_cmd
                
                elif memory_match:
                    tool_name = memory_match.group(1)
                    if "..." in tool_name:
                        log.warning(f"🛑 Tentative d'exécution outil invalide '{tool_name}' bloquée.")
                    else:
                        tool_args_raw = memory_match.group(2).strip()
                        if tool_args_raw.startswith("{") and tool_args_raw.endswith("}"):
                            tool_args = tool_args_raw
                        elif not tool_args_raw:
                            tool_args = "{}"
                        else:
                            tool_args_fixed = re.sub(r"(^|,\s*)(\w+)\s*=", r'\1"\2": ', tool_args_raw)
                            tool_args = f"{{{tool_args_fixed}}}"
                        
                        reconstructed_cmd = f'!native_tool {{"name": "{tool_name}", "args": {tool_args}}}'
                        cmd_to_execute = reconstructed_cmd
                
                if cmd_to_execute:
                    log.info(f"🔧 Outil détecté : {cmd_to_execute[:50]}...")
                    self.task_queue.put({'action': 'command', 'payload': {'command': cmd_to_execute}})
                
                elif not full_text.strip() and not has_received_content:
                    log.warning("⚠️ Réponse IA vide reçue (aucun contenu dans le stream).")
                    # Envoyer un message d'erreur à l'UI
                    self.response_queue.put({'type': 'ui_update', 'widget': 'message', 'text': "⚠️ Réponse IA vide. Vérifiez les logs pour plus de détails."})

        except Exception as e:
            log.error(f"Stream Error: {e}")
            self.response_queue.put({'type': 'ui_stream_end'})
            self.response_queue.put({'type': 'error', 'text': str(e)})
        finally:
            self.bg_task_desc = None

    @trace_action(source="core")
    def run(self):
        # [LOG_CLEANED] log.info("Worker Thread Démarré.")
        UnifiedLogger.write("WORKER", "START", "Démarrage boucle principale.")
        
        if database:
            try: database.init_db(get_path(APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid")))
            except: pass
        
        self._warmup_caches()
        self.bg_executor.submit(self._perform_startup_audit)

        while not self.stop_event.is_set():
            try:
                # [NOUVEAU] --- AUTOMATISATION / MAINTENANCE ---
                now = time.time()
                auto_interval = APP_SETTINGS.get("automation", {}).get("arch_update_interval", 900) # 15 minutes par défaut
                
                if auto_interval > 0 and (now - self.last_arch_update) > auto_interval:
                    if Documentation and hasattr(Documentation, 'execute_update_architecture'):
                        self.last_arch_update = now
                        UnifiedLogger.write("WORKER", "AUTO", "🔄 Maintenance : Mise à jour Architecture Map...")
                        # On lance en background pour ne pas bloquer le loop
                        # On passe les arguments nommés via kwargs pour _execute_tool
                        # La fonction attend (session, action_log_path, result_queue, **kwargs)
                        self.bg_executor.submit(
                            self._execute_tool,
                            Documentation.execute_update_architecture,
                            [], # Pas d'args positionnels
                            {
                                "session": self.get_main_session(),
                                "action_log_path": "action_log.json",
                                "result_queue": self.response_queue, # Pour afficher "Map Updated"
                                "task_queue": self.task_queue
                            }
                        )

                try:
                    # [OPTIMISATION] Timeout court pour réactivité STOP immédiate
                    task = self.task_queue.get(timeout=0.1)
                except queue.Empty:
                    self.current_task_desc = None
                    continue

                msg_type = task.get('type')
                action = task.get('action')
                payload = task.get('payload') or task
                
                # [FEATURE] Mise à jour description pour Queue Window
                self.current_task_desc = f"{msg_type} - {str(payload)[:50]}..."

                if msg_type not in ["ui_update", "get_queue_status"]:
                    UnifiedLogger.write("WORKER", "TASK_RECEIVED", f"Type: {msg_type}, Action: {action}")

                # --- PRE-CHAUFFAGE CLI ---
                if msg_type == 'prewarm_cli':
                    UnifiedLogger.write("WORKER", "INIT", "🔥 Préchauffage CLI demandé...")
                    self.get_main_session() # Initialise la session et déclenche le pre-warm via GeminiCliSession.__init__
                    self.task_queue.task_done()
                    continue

                # --- SIGNAL D'ARRÊT ---
                if msg_type == 'stop_generation':
                    self.abort_current_stream = True
                    UnifiedLogger.write("WORKER", "INFO", "Signal d'arrêt reçu !")
                    # [FIX] Envoi immédiat du signal de fin à l'UI
                    self.response_queue.put({'type': 'ui_stream_end'})
                    self.task_queue.task_done()
                    continue
                # --- OPTIONS MOTEUR ---
                if msg_type == 'set_reasoning_mode':
                    new_state = payload.get('enabled', False)
                    if new_state != self.reasoning_active:
                        self.reasoning_active = new_state
                        UnifiedLogger.write("WORKER", "CONFIG", f"Mode Raisonnement : {'ACTIVÉ' if new_state else 'DÉSACTIVÉ'}")
                        
                        # Bascule dynamique de la session principale
                        if self.main_session:
                            log.info("🔄 Bascule du modèle de la session principale...")
                            try:
                                # 1. On sauvegarde l'historique actuel
                                current_history = self.main_session.history if hasattr(self.main_session, 'history') else []
                                
                                # 2. On détermine le modèle cible
                                target_model = "reasoning" if self.reasoning_active else "fast"
                                
                                # 3. On recrée la session
                                self.main_session = SessionFactory.create_session(
                                    model_type=target_model,
                                    system_instruction=META_INSTRUCTIONS
                                )
                                
                                # 4. On restaure l'historique (Greffe de cerveau)
                                if hasattr(self.main_session, 'chat'):
                                    self.main_session.chat.history = current_history
                                    
                                self.response_queue.put({"type": "ui_update", "widget": "status", "text": f"Mode: {target_model.upper()}"})
                            except Exception as e:
                                log.error(f"Echec bascule modèle: {e}")
                                
                    self.task_queue.task_done()
                    continue
                
                # --- INTROSPECTION (QUEUE) ---
                if msg_type == 'get_queue_status':
                    # [CORRECTION] Priorité à l'activité de fond (Chat)
                    if self.bg_task_desc:
                        current = self.bg_task_desc
                    # Sinon, tâche principale (en ignorant le monitoring lui-même)
                    elif self.current_task_desc and "get_queue_status" not in self.current_task_desc:
                        current = self.current_task_desc
                    else:
                        current = "En attente (Repos)..."
                    
                    waiting = []
                    try:
                        # Copie thread-safe de la queue
                        for t in list(self.task_queue.queue):
                            t_type = t.get('type', 'Inconnu')
                            t_pay = str(t.get('payload', ''))[:30]
                            waiting.append(f"[{t_type}] {t_pay}")
                    except: waiting = ["Erreur lecture file"]
                        
                    self.response_queue.put({
                        "type": "waiting_list_update", 
                        "tasks": {"current": current, "waiting": waiting}
                    })
                    self.task_queue.task_done(); continue

                # --- SYSTEME & OUTILS ---
                if msg_type == 'reload_system':
                    self._refresh_config()
                    if GlobalMemoryManager: GlobalMemoryManager._reload_config()
                    self.response_queue.put({'type': 'config_reloaded'})
                    self.task_queue.task_done(); continue
                
                if msg_type == 'reset_memory':
                    if self.main_session and hasattr(self.main_session, 'chat'):
                        self.main_session.chat.history = []
                        log.info("🧹 Session Chat réinitialisée (RAM).")
                    try:
                        with open(get_path(FULL_CHAT_HISTORY_FILE), 'w', encoding='utf-8') as f: json.dump([], f, ensure_ascii=False)
                    except: pass
                    self.response_queue.put({"type": "ui_update", "widget": "status", "text": "Mémoire vide"})
                    self.task_queue.task_done(); continue

                if msg_type == 'backup_now':
                    if core_backup:
                        try:
                            self.response_queue.put({"type": "ui_update", "widget": "status", "text": "Sauvegarde..."})
                            res = self._execute_tool(core_backup.create_backup, [], {})
                            if res: self.response_queue.put({"type": "ui_update", "widget": "message", "text": f"✅ Backup OK"})
                        except Exception as e:
                            self.response_queue.put({"type": "ui_update", "widget": "message", "text": f"❌ Erreur Backup : {e}"})
                    self.task_queue.task_done(); continue

                if msg_type == 'get_backup_list':
                    if BackupManager: 
                        self._execute_tool(BackupManager.execute_lister_backups, 
                                           [self.get_main_session(), "action_log.json", self.response_queue], {})
                    self.task_queue.task_done(); continue
                
                if msg_type == 'restore_backup':
                    if BackupManager:
                        filename = task.get('filename')
                        res = self._execute_tool(BackupManager.execute_restaurer_backup, 
                                                 [filename, self.get_main_session(), "action_log.json", self.response_queue], {})
                        if res: self.response_queue.put({"type": "ui_update", "widget": "message", "text": res})
                    self.task_queue.task_done(); continue

                # --- ACTIONS DATABASE & AUDIO (RESTORED) ---
                
                if msg_type == 'reindex_db':
                    if database:
                        def progress(msg): self.response_queue.put({"type": "ui_update", "widget": "status", "text": msg})
                        res = self._execute_tool(database.index_project_files, [get_path(".")], {"progress_callback": progress})
                        self.response_queue.put({"type": "ui_update", "widget": "message", "text": f"✅ {res}"})
                    self.task_queue.task_done(); continue

                if msg_type == 'delete_db':
                    if database:
                        res = self._execute_tool(database.delete_local_db, [], {})
                        self.response_queue.put({"type": "ui_update", "widget": "message", "text": f"🗑️ {res}"})
                    self.task_queue.task_done(); continue

                if msg_type == 'start_asr':
                    if hasattr(audio_manager, 'start_listening_thread'):
                        def on_asr_result(text): self.response_queue.put({'type': 'asr_done', 'text': text})
                        audio_manager.start_listening_thread(callback=on_asr_result)
                        self.response_queue.put({"type": "ui_update", "widget": "status", "text": "🎤 Écoute..."})
                    else:
                        self.response_queue.put({'type': 'error', 'text': "Module Audio non dispo."})
                    self.task_queue.task_done(); continue

                if msg_type == 'start_tts':
                    text = payload.get('text', '')
                    if text and hasattr(audio_manager, 'speak_text'):
                        self.bg_executor.submit(audio_manager.speak_text, text)
                        self.response_queue.put({"type": "ui_update", "widget": "status", "text": "🔊 Lecture..."})
                    self.task_queue.task_done(); continue

                # --- ACTIONS DIRECTES (BOUTONS UI) ---
                if msg_type == 'analyze_file':
                    self._handle_analyze_file(payload)
                    self.task_queue.task_done(); continue
                
                if msg_type == 'refactor_file':
                    self._handle_refactor(payload)
                    self.task_queue.task_done(); continue

                if msg_type == 'gen_doc':
                    self._handle_gen_doc(payload)
                    self.task_queue.task_done(); continue

                # --- CHAT & AGENTS ---
                if msg_type == 'agent_task':
                    self._handle_agent_task(payload)
                    self.task_queue.task_done(); continue

                if msg_type in ['user_prompt', 'secondary_user_prompt']:
                    txt = task.get('prompt', '').strip()
                    if txt.startswith('!') or txt.lower() in ['continue', 'go']:
                        action = 'command'; payload = {'command': txt}
                    else:
                        action = 'chat'; payload = {'message': txt}
                        self.response_queue.put({'type': 'chat_start'})

                if action == 'chat':
                    # [BACKGROUND] Lancement threadé pour ne pas bloquer le STOP
                    self.bg_executor.submit(self._handle_chat_stream, payload)
                    if GlobalMemoryManager and self.main_session:
                        self.bg_executor.submit(GlobalMemoryManager.optimize_history, self.main_session)
                
                # ... (Dans la boucle while, méthode run)
                elif action == 'command':
                    cmd = payload.get('command')
                    
                    # [CORRECTIF] Interception avec STREAM vers l'UI
                    if 'lire_fichier' in cmd and 'config/architecture_map.json' in cmd:
                        log.warning("🛑 Optimisation : Relecture Architecture Map bloquée (Déjà en Cache).")
                        
                        self.response_queue.put({'type': 'command_done'})
                        self._save_and_display(f"⚡ **Optimisation Cache :** Lecture disque évitée (Données déjà en mémoire).")
                        
                        if self.main_session:
                            # On force l'IA à enchainer
                            feedback = f"## Résultat Système\n✅ [OPTIMISATION] Fichier DÉJÀ en mémoire (Cache Hit). Ne le relis pas. Résume l'architecture maintenant."
                            
                            # Fonction locale pour gérer le stream et l'affichage
                            def run_continuation():
                                try:
                                    self.response_queue.put({'type': 'ui_stream_start'})
                                    # Appel Streamé
                                    stream_gen = call_ai_robust(self.main_session, feedback, stream=True)
                                    
                                    full_text = ""
                                    for chunk in stream_gen:
                                        if self.abort_current_stream: 
                                            self.response_queue.put({'type': 'ui_stream_chunk', 'text': "\n[INTERROMPU]"})
                                            break
                                        text = str(chunk)
                                        full_text += text
                                        self.response_queue.put({'type': 'ui_stream_chunk', 'text': text})
                                    
                                    self.response_queue.put({'type': 'ui_stream_end'})
                                    
                                    # Sauvegarde Mémoire (Important pour la suite de la conversation)
                                    if GlobalMemoryManager:
                                        GlobalMemoryManager.save_session_history(self.main_session)
                                        
                                except Exception as e:
                                    log.error(f"Erreur continuation: {e}")
                                    self.response_queue.put({'type': 'error', 'text': str(e)})

                            # Lancement en tâche de fond
                            self.bg_executor.submit(run_continuation)
                        
                        self.task_queue.task_done()
                        continue # On passe à la suite sans exécuter la commande "lire_fichier"

                    # ... (La suite du code normal : if analyze_request_and_dispatch ...)
                    if analyze_request_and_dispatch:
                        res = self._execute_tool(analyze_request_and_dispatch, 
                                                [cmd, self.get_main_session(), self.response_queue, self.task_queue], {})
                        
                        self.response_queue.put({'type': 'command_done'})
                        
                        if res: 
                            self._save_and_display(f"⚡ **Résultat :**\n{res}")
                            
                            # [FEEDBACK LOOP STRUCTURÉE - FIX CLEAN DATA]
                            if self.main_session:
                                try:
                                    log.info("🔄 Injection du résultat outil dans la session IA...")
                                    
                                    # [NETTOYAGE] On extrait la "vraie" donnée si c'est du JSON pollué
                                    final_tool_output = res
                                    try:
                                        # Si le résultat ressemble à du JSON, on tente de le parser
                                        if res.strip().startswith("{") and "tool_output" in res:
                                            parsed = json.loads(res)
                                            if "tool_output" in parsed:
                                                final_tool_output = parsed["tool_output"]
                                    except:
                                        pass # Ce n'était pas du JSON, on garde le texte brut
                                    
                                    # [FORMATAGE] On envoie du texte clair, PAS du JSON échappé
                                    feedback_message = (
                                        f"## 🔧 Résultat Commande\n"
                                        f"{final_tool_output}\n\n"
                                        f"> Instruction Système : Le résultat ci-dessus a DÉJÀ été affiché. "
                                        f"Ne le répète pas. Confirme juste la fin de l'opération."
                                    )
                                    
                                    # Envoi en texte simple (plus de json.dumps sur le message entier)
                                    ai_continuation = call_ai_robust(self.main_session, feedback_message, stream=False)
                                    
                                    if ai_continuation:
                                        # On ignore les réponses vides ou redondantes
                                        content_str = str(ai_continuation).strip()
                                        if content_str and "[⚠️ Réponse vide]" not in content_str:
                                            self._save_and_display(content_str)
                                        
                                        # Gestion du chaînage (Auto-Command)
                                        cmd_match = re.search(r"(!native_tool\s*\{.*?\})", content_str, re.DOTALL)
                                        if cmd_match:
                                            next_cmd = cmd_match.group(1).strip()
                                            log.info(f"🔄 Chaînage Auto-Command détecté : {next_cmd[:30]}...")
                                            self.task_queue.put({'action': 'command', 'payload': {'command': next_cmd}})
                                            
                                except Exception as e:
                                    log.error(f"Erreur Feedback Loop IA: {e}")
                    else:
                        self.response_queue.put({'type': 'error', 'text': "Dispatcher non chargé."})
                        

                # [CORRECTIF MAJEUR : PREVENTION HALLUCINATION BOUCLE]
                elif msg_type == 'doc_atomic_task':
                    file_rel = payload.get('file_rel')
                    context_map = payload.get('context_map', '{}')
                    batch_id = payload.get('batch_id')  # [NOUVEAU] Récupération de l'ID du batch
                    
                    try:
                        # Création Stricte de la Session 'writer'
                        # [IMPORTANT] enable_tools=False pour empêcher l'IA d'essayer de relancer des commandes (Boucle infinie)
                        # Si l'utilisateur a configuré "gemini-2.5-flash", SessionFactory doit le charger.
                        doc_session = SessionFactory.create_session("writer", enable_tools=False)
                        
                        if not doc_session:
                             # Cas : Le profil 'writer' n'existe pas dans la config
                             error_msg = "❌ Configuration Invalide : Profil 'writer' introuvable dans settings.py."
                             UnifiedLogger.write("WORKER", "CONFIG_ERROR", error_msg)
                             self._save_and_display(error_msg) # Feedback immédiat à l'utilisateur
                             self.task_queue.task_done()
                             continue

                        # Log pour debug : Quel modèle est réellement chargé ?
                        model_name = "Inconnu"
                        if hasattr(doc_session, 'model') and hasattr(doc_session.model, 'model_name'):
                            model_name = doc_session.model.model_name
                        elif hasattr(doc_session, 'model_name'):
                            model_name = doc_session.model_name
                            
                        UnifiedLogger.write("WORKER", "DOC_START", f"Lancement Thread Doc pour {file_rel} avec modèle: {model_name} (Outils désactivés)")

                        # Lancement Thread avec batch_id
                        self.bg_executor.submit(
                            task_documenter_fichier_atomique, 
                            file_rel,
                            doc_session,
                            self.response_queue,
                            context_map,
                            batch_id  # [NOUVEAU] Passage de l'ID du batch
                        )
                    except Exception as e:
                        err_msg = f"❌ Erreur Lancement Doc ({file_rel}): {e}"
                        log.error(err_msg)
                        self.response_queue.put({'type': 'error', 'text': err_msg})
                    
                    self.task_queue.task_done()

            except Exception as e:
                log.error(f"Erreur Worker Loop: {e}\n{traceback.format_exc()}")
                self.response_queue.put({'type': 'error', 'text': f"Worker Crash: {e}"})
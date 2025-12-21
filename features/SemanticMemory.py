import os
import json
import time
import traceback
import logging
import re

# Imports Configuration
from config.settings import APP_SETTINGS
from config.paths import get_path
from features.UnifiedLogger import UnifiedLogger

# Imports AI Core
from ai_core.factory import SessionFactory
from ai_core.sessions import call_ai_robust, _save_payload_log
from features.Decorators import trace_action

# Imports Database (LTM Connection)
try:
    from features.context import database
except ImportError:
    database = None

log = logging.getLogger("features.SemanticMemory")
FULL_CHAT_HISTORY_FILE = "full_chat_history.json"

class SemanticMemoryManager:
    """
    Gestionnaire de Mémoire Hybride (HMA) - V4.0 (Rolling Summary).
    Transforme l'historique linéaire en : [Socle] + [Résumé Consolidé] + [STM]
    """
    def __init__(self):
        self.stm_window = 4 # Nombre de messages récents à garder intacts (2 tours)
        self.compression_threshold = 2000 # Seuil en caractères pour déclencher la consolidation
        self.max_active_tokens = 50000 # Legacy (gardé pour compatibilité config)
        self.ltm_enabled = False
        self.enabled = True
        self._reload_config()

    @trace_action(source="SemanticMemory")
    def _reload_config(self):
        """Charge la configuration dynamique."""
        mem_conf = APP_SETTINGS.get("memory_optimization", {})
        self.enabled = mem_conf.get("enabled", True)
        self.stm_window = int(mem_conf.get("active_window", 4))
        self.compression_threshold = int(mem_conf.get("compression_threshold", 2000))
        self.max_active_tokens = int(mem_conf.get("max_active_tokens", 50000))
        self.ltm_enabled = (database is not None)

    # --- 1. GESTION DU CYCLE DE VIE (Robustesse V3.3 Preservée) ---

    @trace_action(source="SemanticMemory")
    def load_history_into_session(self, session):
        """Charge l'historique complet."""
        try:
            history_path = get_path(FULL_CHAT_HISTORY_FILE)
            if not os.path.exists(history_path): 
                UnifiedLogger.write("MEMORY", "LOAD", "Aucun historique trouvé sur disque.")
                return

            with open(history_path, 'r', encoding='utf-8') as f:
                full_history = json.load(f)
            
            max_retention = int(APP_SETTINGS.get("system_settings", {}).get("max_history_retention", 500))
            if len(full_history) > max_retention:
                full_history = full_history[-max_retention:]
                
            gemini_hist = []
            archived_count = 0
            
            for msg in full_history:
                role = "model" if msg.get('role') == "assistant" else "user"
                content = msg.get('content', '')
                if content and str(content).strip():
                    if "📜 [ARCHIVE]" in content: archived_count += 1
                    gemini_hist.append({"role": role, "parts": [{"text": content}]})
            
            if hasattr(session, 'chat'):
                session.chat.history = gemini_hist
                UnifiedLogger.write("MEMORY", "LOAD", f"Historique restauré : {len(gemini_hist)} msgs ({archived_count} archives).")
                
        except Exception as e:
            log.error(f"Erreur chargement mémoire : {e}")

    @trace_action(source="SemanticMemory")
    def save_session_history(self, session):
        """Sauvegarde sur disque."""
        try:
            if not hasattr(session, 'chat'): return
            history_path = get_path(FULL_CHAT_HISTORY_FILE)
            serializable = []
            
            for msg in session.chat.history:
                role = "user"
                if hasattr(msg, 'role'): role = "assistant" if msg.role == "model" else "user"
                elif isinstance(msg, dict): role = msg.get('role', 'user')
                
                # Extraction robuste (V3.3 Smart Unpacking)
                content = self._extract_text(msg)
                
                serializable.append({"role": role, "content": content})
            
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(serializable, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            log.error(f"Erreur sauvegarde mémoire : {e}")

    # --- 2. PIPELINE DE CONSOLIDATION (ROLLING SUMMARY V4) ---

    @trace_action(source="SemanticMemory")
    def optimize_history(self, session):
        """
        Fusionne les vieux messages en un seul bloc narratif.
        Remplace l'ancienne logique de compression unitaire.
        Structure cible : [Résumé Consolidé] + [Ack] + [STM (n derniers messages)]
        """
        if not hasattr(session, 'chat') or not self.enabled: 
            self.save_session_history(session)
            return

        try:
            history = list(session.chat.history)
            
            # Si on a moins de messages que la fenêtre active + buffer, on ne fait rien
            if len(history) <= self.stm_window + 1:
                self.save_session_history(session)
                return

            # Séparation : Archive (Vieux) vs Active (Récent)
            # On garde les 'stm_window' derniers messages intacts
            active_slice = history[-self.stm_window:]
            archive_slice = history[:-self.stm_window]
            
            # Calcul du volume à compresser
            archive_text = ""
            for msg in archive_slice:
                archive_text += self._extract_text(msg) + "\n"
            
            # Si le volume est faible, pas besoin de déclencher l'IA coûteuse
            if len(archive_text) < self.compression_threshold:
                self.save_session_history(session)
                return

            UnifiedLogger.write("MEMORY", "COMPRESS_START", f"Consolidation de {len(archive_slice)} blocs ({len(archive_text)} chars)...")

            # --- GÉNÉRATION DU RÉSUMÉ (ROLLING SUMMARY) ---
            summary_content = self._generate_rolling_summary(archive_text)
            
            if summary_content:
                # Création du nouveau message unique (Role: User pour forcer l'attention)
                summary_msg = {
                    "role": "user", 
                    "parts": [{"text": f"--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---\n{summary_content}\n\n(Fin du Résumé - Reprise de la session ci-dessous)"}]
                }
                
                # Injection de la réponse système pour valider la mémoire (Ack)
                # Cela stabilise le modèle qui s'attend souvent à une réponse après un message user
                ack_msg = {
                    "role": "model",
                    "parts": [{"text": "Bien reçu. Mémoire mise à jour. Je suis prêt pour la suite des opérations."}]
                }

                # Reconstruction de l'historique : [Résumé] + [Ack] + [STM]
                new_history = [summary_msg, ack_msg] + active_slice
                
                # Application atomique
                session.chat.history = new_history
                UnifiedLogger.write("MEMORY", "SYNC", f"✅ Consolidation terminée. Blocs: {len(history)} -> {len(new_history)}")
                
                # Sauvegarde immédiate du nouvel état
                self.save_session_history(session)
            else:
                UnifiedLogger.write("MEMORY", "WARNING", "Génération du résumé échouée ou vide.")

        except Exception as e:
            log.error(f"Erreur optimisation mémoire : {e}\n{traceback.format_exc()}")

    def _generate_rolling_summary(self, text_block):
        """
        Appelle un modèle 'compressor' pour synthétiser le bloc d'archives.
        """
        try:
            # On utilise un modèle rapide (Flash) sans outils pour éviter les boucles
            model_name = "compressor" 
            session = SessionFactory.create_session(model_type=model_name, enable_tools=False)
            
            from datetime import datetime
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            prompt = (
                "Tu es le Gardien de la Mémoire du projet AiModding.\n"
                "Ta mission est de consolider l'historique de conversation ci-dessous en un résumé technique structuré.\n\n"
                "STRUCTURE REQUISE :\n"
                "1. Organisation par périodes temporelles (dates approximatives si disponibles, sinon 'Récent' / 'Antérieur')\n"
                "2. Groupement par thèmes techniques :\n"
                "   - UI/Interface (widgets, fenêtres, interfaces utilisateur)\n"
                "   - Backend/API (logique métier, endpoints, services)\n"
                "   - RAG/Context (recherche, base de connaissances, embedding)\n"
                "   - Architecture (structure du projet, organisation du code)\n"
                "   - Débogage/Bugs (erreurs corrigées, problèmes résolus)\n"
                "   - Features (nouvelles fonctionnalités ajoutées)\n"
                "   - Configuration/Settings (paramètres, configuration)\n"
                "3. Format markdown avec headers (## pour périodes, ### pour thèmes)\n"
                "4. Chaque élément doit inclure le nom de fichier entre crochets [fichier.py] et une date approximative si disponible\n\n"
                "EXEMPLES DE FORMAT :\n"
                "## Période Récente (2025-12-20)\n"
                "### UI/Interface\n"
                "- [widgets.py] Ajout TextEditorWithLineNumbers (2025-12-19)\n"
                "### RAG/Context\n"
                "- [database.py] Implémentation recherche hybride FTS5+FAISS (2025-12-18)\n\n"
                "## Période Antérieure (2025-12-01 à 2025-12-17)\n"
                "### Architecture\n"
                "- [CacheManager.py] Migration vers architecture atomique (2025-12-10)\n\n"
                "RÈGLES DE COMPRESSION :\n"
                "1. Conserve les faits techniques : noms de fichiers modifiés, erreurs rencontrées, décisions d'architecture.\n"
                "2. Ignore les politesses ('bonjour', 'merci') et le bavardage.\n"
                "3. Si un résumé précédent existe déjà au début du texte, intègre-le et mets-le à jour en respectant la structure.\n"
                "4. Sois concis mais exhaustif sur les données (chemins, fonctions clés).\n"
                "5. Limite totale : environ 5000 caractères maximum.\n"
                "--- DÉBUT DU BLOC À COMPRESSER ---\n"
                f"{text_block[:50000]}\n" # Sécurité taille max
                "--- FIN DU BLOC ---"
            )
            
            # Payload Log spécifique Compressor (logs/)
            real_model = getattr(session, 'model_name', 'unknown')
            compressor_payload = {
                "prompt": prompt[:15000],  # Truncate for log
                "text_block_length": len(text_block),
                "text_block_preview": text_block[:500] if text_block else ""
            }
            _save_payload_log("compressor", real_model, compressor_payload, {"source": "SemanticMemory"})
            
            # Désactiver le log GeminiSession pour éviter le double log
            # (on a déjà loggé spécifiquement pour le compresseur)
            if hasattr(session, '_skip_payload_log'):
                session._skip_payload_log = True
            else:
                setattr(session, '_skip_payload_log', True)
            
            # Appel force_text=True pour éviter tout JSON parasite
            summary = call_ai_robust(session, prompt, force_text=True)
            
            # Réactiver le log pour les prochains appels (nettoyage)
            if hasattr(session, '_skip_payload_log'):
                session._skip_payload_log = False
            
            # Validation basique
            if not summary or len(summary) < 10 or "[⚠️" in summary:
                return None
                
            return summary.strip()
            
        except Exception as e:
            log.warning(f"Echec génération résumé : {e}")
            return None

    # --- 3. RAG / LTM (Lecture Seule pour Context Injection V4) ---
    
    def get_compressed_history_block(self):
        """
        Retourne l'historique archivé pour le Context Stuffing.
        Dans l'architecture V4 Rolling Summary, l'historique est DÉJÀ dans la session (sous forme de résumé).
        Cependant, pour le contexte système, on extrait le résumé consolidé depuis l'historique si présent.
        """
        try:
            # Si on peut accéder à l'historique global, extraire le résumé consolidé
            history_path = get_path(FULL_CHAT_HISTORY_FILE)
            if not os.path.exists(history_path):
                return ""
            
            with open(history_path, 'r', encoding='utf-8') as f:
                full_history = json.load(f)
            
            # Chercher le message contenant le résumé consolidé
            for msg in reversed(full_history):  # Chercher du plus récent au plus ancien
                content = msg.get('content', '')
                if isinstance(content, str) and "📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ)" in content:
                    # Extraire le contenu du résumé (enlever le header)
                    summary = content.replace("--- 📜 MÉMOIRE DU PROJET (RÉSUMÉ CONSOLIDÉ) ---", "", 1).strip()
                    # Enlever le footer "(Fin du Résumé...)"
                    summary = re.sub(r"\(Fin du Résumé.*\)", "", summary, flags=re.IGNORECASE).strip()
                    if summary:
                        # Limiter à 5000 caractères pour éviter de saturer le contexte
                        if len(summary) > 5000:
                            summary = summary[:5000] + "\n... (tronqué)"
                        return f"--- 📜 MÉMOIRE LONG TERME (Résumé Consolidé) ---\n{summary}"
        
        except Exception as e:
            log.debug(f"Erreur extraction LTM depuis historique: {e}")
        
        return ""

    @trace_action(source="SemanticMemory")
    def retrieve_relevant_context(self, user_query):
        """Recherche vectorielle (RAG) sur la base de connaissances."""
        if not self.ltm_enabled or not database: return ""
        try:
            results = []
            if hasattr(database, 'search_memories'):
                results = database.search_memories(user_query, n_results=3)
            elif hasattr(database, 'search_vector_db'):
                db_path = get_path(APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid"))
                raw_results, _ = database.search_vector_db(user_query, db_path, max_results=3)
                results = raw_results 

            if not results: return ""
            
            ctx = "\n--- 🕰️ SOUVENIRS PERTINENTS (LTM) ---\n"
            seen = set()
            for res in results:
                # Gestion des différents formats de retour possibles (tuple ou objet)
                if isinstance(res, tuple):
                    content = res[1] if len(res) > 1 else str(res[0])
                else:
                    content = str(res)
                
                # Dédoublonnage simple (basé sur le début de la chaine)
                signature = content[:50]
                if signature not in seen:
                    ctx += f"• {content}\n"
                    seen.add(signature)
            
            # On retourne le contexte seulement s'il y a des éléments uniques
            return ctx if len(seen) > 0 else ""
            
        except Exception as e:
            log.error(f"Erreur Lecture LTM: {e}")
        return ""

    # --- 4. HELPERS ROBUSTES (V3.3 SMART UNPACKING - CONSERVÉS) ---

    def _clean_json_string(self, text):
        """Tente de parser récursivement une chaîne JSON pour en extraire le texte utile."""
        if not isinstance(text, str): return str(text)
        
        # Si ça ressemble à du JSON
        if text.strip().startswith("{") and "}" in text:
            try:
                data = json.loads(text)
                
                # Cas 1 : "tool_output" standard
                if "tool_output" in data:
                    return self._clean_json_string(data["tool_output"])
                
                # Cas 2 : "result"
                if "result" in data:
                    return self._clean_json_string(data["result"])
                
                # Cas 3 : C'est juste un dict, on le convertit proprement en JSON lisible
                return json.dumps(data, ensure_ascii=False)
            except:
                pass # Ce n'était pas du JSON valide, on garde le texte brut
        
        return text

    @trace_action(source="SemanticMemory")
    def _extract_text(self, message):
        """Extrait et NETTOIE tout le contenu textuel."""
        text_parts = []
        try:
            # Cas 1: Objet Gemini Natif (protobuf wrapper)
            if hasattr(message, 'parts'):
                for part in message.parts:
                    # A. Texte standard
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                    
                    # B. Appel de fonction
                    if hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        args = dict(fc.args) if hasattr(fc, 'args') else {}
                        text_parts.append(f"[TOOL_CALL: {fc.name}({args})]")
                    
                    # C. Réponse de fonction
                    if hasattr(part, 'function_response') and part.function_response:
                        fr = part.function_response
                        try:
                            if hasattr(fr, 'response'):
                                # Conversion en dict
                                resp_data = dict(fr.response)
                                
                                # [FIX V3.3] Nettoyage Intelligent
                                # On cherche la valeur pertinente (result, output, etc)
                                raw_value = resp_data.get('result', resp_data)
                                clean_content = self._clean_json_string(str(raw_value))
                                
                                text_parts.append(f"[TOOL_RESULT: {fr.name}]\nPayload: {clean_content}")
                            else:
                                text_parts.append(f"[TOOL_RESULT: {fr.name}]")
                        except Exception as e:
                            text_parts.append(f"[TOOL_RESULT: {fr.name} - Error: {e}]")

            # Cas 2: Dictionnaire (Legacy/Serialized)
            elif isinstance(message, dict):
                # Fallback content simple
                if 'content' in message and message['content']:
                    text_parts.append(str(message['content']))
                
                # Gestion parts (serialized)
                parts = message.get('parts', [])
                if isinstance(parts, list):
                    for p in parts:
                        if isinstance(p, dict):
                            if 'text' in p: text_parts.append(p['text'])
                            
        except Exception as e:
            log.warning(f"Erreur extraction texte: {e}")
            return ""
            
        return "\n".join(text_parts).strip()

    @trace_action(source="SemanticMemory")
    def _update_message_text(self, message, new_text):
        """Met à jour le texte en préservant la structure si possible."""
        try:
            # Cas 1: Objet Gemini Natif
            if hasattr(message, 'parts'):
                found_text = False
                for part in message.parts:
                    if hasattr(part, 'text'): # On écrase le premier slot texte
                        part.text = new_text
                        found_text = True
                        break
                if not found_text: pass 

            # Cas 2: Dictionnaire
            elif isinstance(message, dict):
                if 'parts' in message and isinstance(message['parts'], list):
                    if len(message['parts']) > 0 and isinstance(message['parts'][0], dict):
                        message['parts'][0]['text'] = new_text
                    else:
                        message['parts'] = [{'text': new_text}]
                else:
                    message['content'] = new_text
        except Exception as e:
            log.error(f"Erreur update message: {e}")

GlobalMemoryManager = SemanticMemoryManager()

# --- WRAPPERS POUR LE DISPATCHER (ai_helper) ---

def execute_sauvegarder_memoire(cle, valeur, session, action_log_path, result_queue, **kwargs):
    """
    Sauvegarde une information explicite dans la mémoire à long terme.
    """
    if not GlobalMemoryManager.ltm_enabled or not database:
        return "❌ Mémoire à long terme (LTM) non disponible (Base de données absente)."
    
    try:
        # [CORRECTIF V3.3] Utilisation de store_memory (nouveau standard)
        success = False
        if hasattr(database, 'store_memory'):
            meta = {
                "source": "user_explicit",
                "key": cle,
                "timestamp": time.time()
            }
            database.store_memory(valeur, metadata=meta)
            success = True
        
        # Fallback Legacy (Robustesse)
        elif hasattr(database, 'add_memory_fragment'):
            entry = f"SOUVENIR UTILISATEUR | Sujet: {cle} | Contenu: {valeur}"
            database.add_memory_fragment(entry)
            success = True
            
        if success:
            # On log l'action
            from features.Shared import log_action
            log_action("sauvegarder_memoire", f"Clé: {cle}", "Mémoire", action_log_path)
            return f"✅ Information mémorisée avec succès : **[{cle}]** {valeur}"
        else:
            return "❌ Erreur interne : Aucune méthode de sauvegarde compatible trouvée dans la base."
            
    except Exception as e:
        return f"❌ Erreur lors de la sauvegarde en mémoire : {e}"

def execute_rechercher_memoire(requete, session, action_log_path, result_queue, **kwargs):
    """
    Recherche active dans la mémoire sémantique.
    """
    if not GlobalMemoryManager.ltm_enabled:
        return "❌ Mémoire à long terme non disponible."
        
    try:
        # On utilise la méthode existante du Manager (qui est maintenant corrigée)
        results = GlobalMemoryManager.retrieve_relevant_context(requete)
        
        from features.Shared import log_action
        log_action("rechercher_memoire", f"Requête: {requete}", "Mémoire", action_log_path)
        
        if not results:
            return "📭 Aucun souvenir pertinent trouvé pour cette requête."
            
        return f"🔎 **Résultats de la recherche mémoire :**\n{results}"
    except Exception as e:
        return f"❌ Erreur recherche mémoire : {e}"
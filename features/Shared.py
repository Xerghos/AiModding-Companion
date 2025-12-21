import os
import json
import logging
import ast
import time
from config.paths import get_path
from config.settings import APP_SETTINGS
from features.Decorators import trace_action

# Logger spécifique
log = logging.getLogger("features.Shared")

# --- FONCTIONS UTILITAIRES EXISTANTES (Log, Backup, Syntaxe) ---

@trace_action(source="Shared")
def log_action(action_type, details, target, log_path="action_log.json"):
    """Enregistre une action dans le journal d'audit JSON."""
    try:
        entry = {
            "timestamp": time.time(),
            "action": action_type,
            "details": details,
            "target": target
        }
        abs_log_path = get_path(log_path)
        
        if os.path.exists(abs_log_path):
            with open(abs_log_path, 'r', encoding='utf-8') as f:
                try: logs = json.load(f)
                except: logs = []
        else:
            logs = []
            
        logs.append(entry)
        if len(logs) > 1000: logs = logs[-1000:]
            
        with open(abs_log_path, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"Erreur Log Action: {e}")

@trace_action(source="Shared")
def _creer_backup_snapshot():
    """Wrapper pour le backup manager."""
    try:
        from features import core_backup
        return core_backup.create_backup()
    except Exception as e:
        log.error(f"Erreur Backup Snapshot: {e}")
        return None

@trace_action(source="Shared")
def verifier_syntaxe_python(code, filename="temp.py"):
    """Vérifie la syntaxe Python."""
    try:
        ast.parse(code, filename=filename)
        return True, "Syntaxe Valide"
    except SyntaxError as e:
        error_msg = f"Erreur ligne {e.lineno}: {e.msg}"
        return False, error_msg
    except Exception as e:
        return False, str(e)

# --- [MIGRATION & UNIFICATION] OMNISCIENT RESOLVER ---

class OmniscientResolver:
    """
    Le GPS Central du Projet.
    Stratégie en cascade :
    1. Exactitude (O(1)) -> Instantané.
    2. Heuristique (Dictionnaire) -> Instantané.
    3. Fuzzy Search (Algorithme) -> Rapide (~10-50ms).
    4. RAG (Base Vectorielle) -> Moyen (~200ms).
    5. IA Sémantique (LLM Router) -> Lent (~1s) - DERNIER RECOURS.
    """

    @staticmethod
    @trace_action(source="Shared")
    def _get_recency_score(filepath):
        try:
            mtime = os.path.getmtime(filepath)
            age = time.time() - mtime
            if age < 3600: return 10
            if age < 86400: return 5
            return 0
        except: return 0

    @staticmethod
    @trace_action(source="Shared")
    def resolve(query, allow_ai=False):
        """
        Résout un chemin flou vers un chemin réel relatif.
        :param allow_ai: Si True, autorise l'appel au LLM en dernier recours.
                         Par défaut False pour les outils automatiques (CodeQuality) afin d'éviter la latence.
        """
        if not query: return None
        query_clean = query.strip()
        project_root = get_path(".")
        
        # --- NIVEAU 1 : EXACTITUDE & DICTIONNAIRE (Instant) ---
        
        # A. Check direct
        abs_p = get_path(query_clean)
        if os.path.exists(abs_p):
            return os.path.relpath(abs_p, project_root).replace('\\', '/')

        # B. Dictionnaire Critique (Fichiers fréquents mal nommés)
        COMMON_LOCATIONS = {
            "settings.py": "config/settings.py",
            "database.py": "features/context/database.py",
            "architecture_map.json": "config/architecture_map.json",
            "app_settings.json": "app_settings.json",
            "main_window.py": "ui/main_window.py",
            "core.py": "worker/core.py",
            "rag.py": "features/context/rag.py",
            "agent_personas.py": "agents/agent_personas.py",
            "SearchEngine.py": "features/SearchEngine.py"
        }
        if query_clean in COMMON_LOCATIONS:
            guess = COMMON_LOCATIONS[query_clean]
            if os.path.exists(get_path(guess)):
                log.info(f"💡 Omniscient (Dict): '{query}' -> '{guess}'")
                return guess

        # C. Extensions implicites
        candidates = [query_clean + ".py", query_clean + ".json", query_clean + ".md"]
        for cand in candidates:
            if os.path.exists(get_path(cand)):
                return cand

        # --- NIVEAU 2 : FUZZY SEARCH (Rapide) ---
        
        best_fuzzy = None
        best_score = 0
        query_parts = query_clean.lower().replace("_", " ").split()
        
        IGNORED = [".git", "__pycache__", "venv", "env", "node_modules", "db", "logs", "dist", "build"]

        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in IGNORED]
            
            # Recherche Fichiers
            for f in files:
                f_path = os.path.join(root, f)
                f_lower = f.lower()
                score = 0
                
                # Match exact nom de fichier (hors dossier)
                if f_lower == query_clean.lower(): score += 100
                elif query_clean.lower() in f_lower: score += 60
                else:
                    # Match partiel
                    matches = sum(1 for part in query_parts if part in f_lower and len(part) > 2)
                    if matches > 0: score += (matches * 20)

                if score > 0:
                    score += OmniscientResolver._get_recency_score(f_path)

                if score > best_score:
                    best_score = score
                    best_fuzzy = os.path.relpath(f_path, project_root).replace('\\', '/')

        # Seuil de confiance Fuzzy
        if best_fuzzy and best_score > 80:
            log.info(f"💡 Omniscient (Fuzzy): '{query}' -> '{best_fuzzy}' (Score: {best_score})")
            return best_fuzzy

        # --- NIVEAU 3 : RAG (Base Vectorielle) ---
        # Nécessite un import local pour éviter le cycle au chargement du module
        rag_candidate = None
        try:
            from features.context import database
            if database and len(query_clean) > 3:
                db_path = get_path(APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid"))
                results, _ = database.search_vector_db(query, db_path, max_results=1)
                if results:
                    top_source, _, top_score_str = results[0]
                    # Note : Dans SearchEngine, le seuil était 0.45. Ici on reste strict.
                    # Adaptez le seuil selon votre métrique de distance (rappel : < 1.5 pour FAISS L2 est bien)
                    if float(top_score_str) < 1.5: 
                        clean_source = top_source.replace("LocalFile: ", "").strip()
                        rag_candidate = clean_source
                        log.info(f"💡 Omniscient (RAG): '{query}' -> '{clean_source}'")
        except ImportError: pass # Pas de DB dispo, on continue
        except Exception: pass

        if rag_candidate: return rag_candidate

        # --- NIVEAU 4 : IA SEMANTIQUE (Coûteux - Optionnel) ---
        if allow_ai:
            return OmniscientResolver._semantic_ai_resolve(query)

        # Dernier recours : Fuzzy moyen si on n'a rien d'autre
        if best_fuzzy and best_score > 40:
            return best_fuzzy

        return None

    @staticmethod
    @trace_action(source="Shared")
    def _semantic_ai_resolve(query):
        """Appel coûteux à l'IA pour comprendre le concept."""
        try:
            from ai_core.factory import SessionFactory
            from ai_core.sessions import call_ai_robust
            
            # Liste allégée pour le prompt
            structure_sample = "config/, features/, worker/, ui/, agents/"
            
            session = SessionFactory.create_session(model_type="router")
            prompt = (
                f"Tu es un résolveur de chemin système. Projet : [{structure_sample}].\n"
                f"Recherche utilisateur : '{query}'.\n"
                f"Quel est le chemin relatif probable ? (Réponds juste le chemin ou 'None')"
            )
            result = call_ai_robust(session, prompt, force_text=True, disposable=True).strip().strip("'\"`")
            
            if result and result != "None" and os.path.exists(get_path(result)):
                log.info(f"💡 Omniscient (AI): '{query}' -> '{result}'")
                return result
        except: pass
        return None

# Alias pour compatibilité avec l'ancien nom proposé
smart_resolve_path = lambda q: OmniscientResolver.resolve(q, allow_ai=False)
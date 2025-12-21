import os
import logging
import fnmatch
import time # [AJOUT]
import difflib # [AJOUT] Pour le Fuzzy match simple si besoin, ou on garde la logique manuelle

# Imports Configuration
from config.paths import get_path
from config.logs import get_logger
from config.constants import SUPPORTED_FILE_EXTENSIONS
from config.settings import APP_SETTINGS # [AJOUT] Pour RAG Path
# Imports Features & Core
from features.Shared import smart_resolve_path, log_action
from features.Decorators import trace_action
# [AJOUT] Imports pour l'IA et la DB
from ai_core.factory import SessionFactory
from ai_core.sessions import call_ai_robust

try:
    import features.context.database as database
except ImportError:
    database = None

log = get_logger("features.SearchEngine")

# Dossiers à ignorer systématiquement pour la recherche
IGNORED_DIRS = {
    ".git", "__pycache__", "venv", "env", "node_modules", "db", 
    "logs", "dist", "build", ".idea", ".vscode", "coverage", 
    "backup", "backups", "Documentation", "bin", "obj"
}

# Fichiers techniques à ignorer (bruit)
IGNORED_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "action_log.json",
    "full_chat_history.json", "prompt_history.json", "architecture_map.json",
    ".DS_Store", "Thumbs.db"
}

class OmniscientResolver:
    """
    Moteur de résolution de chemin intelligent (Portage Legacy V2).
    Stratégie : Exact -> Fuzzy -> RAG -> IA Sémantique.
    """

    @staticmethod
    def _get_recency_score(filepath):
        try:
            mtime = os.path.getmtime(filepath)
            age_seconds = time.time() - mtime
            if age_seconds < 3600: return 10    # 1 heure
            if age_seconds < 86400: return 5    # 24 heures
            if age_seconds < 604800: return 2   # 1 semaine
            return 0
        except: return 0

    @staticmethod
    def _get_project_structure_light():
        """Liste légère racine pour l'IA."""
        try:
            root = get_path(".")
            items = sorted(os.listdir(root))
            valid = [i for i in items if i not in IGNORED_DIRS]
            return ", ".join(valid)
        except: return ""

    @staticmethod
    def _semantic_resolve(query):
        """Demande au Router de deviner le chemin."""
        try:
            structure = OmniscientResolver._get_project_structure_light()
            # Utilisation du modèle rapide (Router)
            session = SessionFactory.create_session(model_type="router")
            
            prompt = (
                f"Tu es un résolveur de chemin système. Projet racine : [{structure}].\n"
                f"L'utilisateur cherche : '{query}'.\n"
                f"Quel est le chemin relatif exact (fichier ou dossier) le plus probable ?\n"
                f"Réponds UNIQUEMENT le chemin (string). Si introuvable, réponds 'None'."
            )
            
            result = call_ai_robust(session, prompt, mode="fast", disposable=True).strip().strip("'\"`")
            if result and result != "None" and os.path.exists(get_path(result)):
                log.info(f"🧠 Omniscient AI: '{query}' -> '{result}'")
                return result
        except Exception as e:
            log.warning(f"Omniscient AI Fail: {e}")
        return None

    @staticmethod
    def resolve(query):
        """
        Point d'entrée principal pour trouver un fichier flou.
        """
        if not query: return None
        clean_q = query.strip().lower()
        root = get_path(".")
        
        # 1. EXACTITUDE & EXTENSIONS COMMUNES
        candidates = [query, query + ".py", query + ".json", query + ".md", query.replace(" ", "_")]
        for c in candidates:
            if os.path.exists(get_path(c)): return c

        # 2. FUZZY SEARCH (Score basé sur le nom et la récence)
        best_fuzzy = None
        best_score = 0
        q_parts = clean_q.replace("_", " ").split()
        
        for r, d, f in os.walk(root):
            if any(ig in r for ig in IGNORED_DIRS): continue
            
            for file in f:
                if file in IGNORED_FILES: continue
                f_lower = file.lower()
                score = 0
                
                if f_lower == clean_q: score += 100
                elif clean_q in f_lower: score += 60
                elif f_lower in clean_q: score += 70
                else:
                    matches = sum(1 for p in q_parts if p in f_lower and len(p) > 2)
                    if matches > 0: score += (matches * 20)
                
                if score > 0:
                    score += OmniscientResolver._get_recency_score(os.path.join(r, file))
                
                if score > best_score:
                    best_score = score
                    best_fuzzy = os.path.relpath(os.path.join(r, file), root)

        # 3. RAG (Recherche Vectorielle)
        rag_candidate = None
        if len(clean_q) > 3 and database:
            try:
                db_p = get_path(APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid"))
                # On utilise la recherche DB existante
                # Attention: il faut que database.search_vector_db soit importé/accessible
                results, _ = database.search_vector_db(query, db_p, max_results=1)
                if results:
                    # Format result: (Source, Content, Score)
                    src, _, score_str = results[0]
                    if float(score_str) > 0.45: # Seuil de confiance
                        rag_candidate = src.replace("LocalFile: ", "").strip()
                        # Vérif existence physique
                        if not os.path.exists(get_path(rag_candidate)): rag_candidate = None
            except Exception: pass

        # 4. ARBITRAGE FINAL
        if best_fuzzy and best_score > 85: return best_fuzzy
        if rag_candidate: 
            log.info(f"🧠 Omniscient RAG: '{query}' -> '{rag_candidate}'")
            return rag_candidate
        
        # Dernier recours : IA Sémantique
        ai_guess = OmniscientResolver._semantic_resolve(query)
        if ai_guess: return ai_guess
        
        if best_fuzzy and best_score > 40: return best_fuzzy
        
        return None
    
@trace_action(source="SearchEngine")
def execute_recherche_texte(query, path=".", session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Recherche une chaîne de caractères dans le contenu des fichiers (Grep-like).
    Args:
        query (str): Le texte à chercher.
        path (str): Le dossier racine de la recherche (par défaut '.').
    """
    # Robustesse sur les arguments
    search_query = query or kwargs.get('query')
    search_path = path or kwargs.get('path', ".")
    
    if not search_query or len(search_query.strip()) < 2:
        return "⚠️ La requête de recherche est trop courte (min 2 caractères)."

    abs_path = smart_resolve_path(search_path)
    if not os.path.exists(abs_path):
        return f"❌ Chemin introuvable : {search_path}"

    if result_queue:
        result_queue.put({"type": "ui_update", "widget": "status", "text": f"🔎 Recherche '{search_query}'..."})

    matches = []
    scanned_count = 0
    hit_count = 0
    file_hit_count = 0
    
    # Recherche insensible à la casse
    query_lower = search_query.lower()

    try:
        # Liste des fichiers à scanner
        files_to_scan = []
        
        if os.path.isfile(abs_path):
            files_to_scan = [abs_path]
        else:
            for root, dirs, files in os.walk(abs_path):
                # Filtrage des dossiers in-place
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
                
                for f in files:
                    if f in IGNORED_FILES: continue
                    # On accepte les extensions supportées + quelques configs
                    if f.endswith(SUPPORTED_FILE_EXTENSIONS) or f in ["Dockerfile", "requirements.txt", ".env.example", "Makefile"]:
                        files_to_scan.append(os.path.join(root, f))

        # Scan du contenu
        for file_path in files_to_scan:
            scanned_count += 1
            try:
                rel_path = os.path.relpath(file_path, get_path("."))
                
                # Lecture tolérante aux erreurs d'encodage
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                if query_lower in content.lower():
                    file_hit_count += 1
                    lines = content.splitlines()
                    
                    for i, line in enumerate(lines):
                        if query_lower in line.lower():
                            hit_count += 1
                            # Formatage : Chemin:Ligne : Contenu
                            matches.append(f"- `{rel_path}:{i+1}` : {line.strip()[:200]}")
                            
                            # Limite par fichier pour éviter le flood
                            if hit_count > 200: break 
                    
                    if hit_count > 200: break # Circuit breaker global
            except Exception: pass

        # Rapport
        if not matches:
            return f"📭 Aucun résultat trouvé pour '{search_query}' dans {scanned_count} fichiers scannés."

        if action_log_path:
            log_action("rechercher_texte", f"Query: {search_query} | Hits: {hit_count}", "SearchEngine", action_log_path)

        header = f"🔎 **Résultats de recherche pour '{search_query}'**\n"
        header += f"Trouvé : {hit_count} occurrences dans {file_hit_count} fichiers (sur {scanned_count} scannés).\n\n"
        
        # Tronquer si trop long pour l'IA
        if len(matches) > 50:
            truncated = matches[:50]
            footer = f"\n... et {len(matches) - 50} autres résultats."
            return header + "\n".join(truncated) + footer
        
        return header + "\n".join(matches)

    except Exception as e:
        log.error(f"Erreur recherche texte : {e}")
        return f"❌ Erreur technique lors de la recherche : {e}"

@trace_action(source="SearchEngine")
def execute_rechercher_fichiers(pattern, chemin_racine=".", session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Recherche des fichiers par nom (Glob Pattern).
    Args:
        pattern (str): Motif (ex: *.py, test_*)
        chemin_racine (str): Dossier de départ.
    """
    search_pattern = pattern or kwargs.get('pattern')
    root_dir = chemin_racine or kwargs.get('chemin_racine', ".")
    
    if not search_pattern:
        return "❌ Erreur : Motif de recherche (pattern) manquant."

    abs_root = smart_resolve_path(root_dir)
    matches = []
    
    try:
        for root, dirs, files in os.walk(abs_root):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            
            for filename in fnmatch.filter(files, search_pattern):
                full_path = os.path.join(root, filename)
                matches.append(os.path.relpath(full_path, get_path(".")))
                
        if not matches:
            return f"📭 Aucun fichier ne correspond au motif `{search_pattern}` dans `{root_dir}`."
            
        return f"📂 **Fichiers trouvés ({len(matches)}) :**\n" + "\n".join([f"- `{m}`" for m in matches[:100]])

    except Exception as e:
        return f"❌ Erreur recherche fichiers : {e}"

@trace_action(source="SearchEngine")
def omniscient_resolve_path(query):
    """Wrapper pour l'Omniscient Resolver."""
    return OmniscientResolver.resolve(query)
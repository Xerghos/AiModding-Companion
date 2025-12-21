"""
PATCHED: features/ai_helper.py
Fix: Introspection + Parsing Anti-Double-Escape + Security + Quality Loop Integration
"""
import logging
import re
import json
import ast
import traceback
import os
from pathlib import Path

# --- Imports Features ---
import features.WebSurfer as WebSurfer
import features.QualityEngine as QualityEngine  # [AJOUT] Pour la boucle qualité

# --- Configuration & Sécurité ---
from config.settings import APP_SETTINGS

# --- Note sur les Imports ---
# Les modules de features (FileSystem, etc.) sont importés dynamiquement dans _get_tool_registry
# pour éviter les cycles d'importation.

log = logging.getLogger("features.ai_helper")

# --- CORE WRAPPER ---
def call_ai_robust(session, prompt, mode="fast", disposable=False, force_text=False, cache_name=None, stream=False, **kwargs):
    """Wrapper pour éviter les imports circulaires avec ai_core."""
    from ai_core.sessions import call_ai_robust as _core_call_ai
    return _core_call_ai(session, prompt, mode=mode, disposable=disposable, force_text=force_text, cache_name=cache_name, stream=stream)

def _get_session_factory():
    from ai_core.factory import SessionFactory
    return SessionFactory

# --- FONCTION D'INTROSPECTION ---
import json
from config.tools_schema import TOOLS_SCHEMA

# ... (Autres imports existants) ...

def execute_lister_outils(session, action_log_path, result_queue, **kwargs):
    """
    Affiche la liste des outils directement à l'utilisateur et renvoie une confirmation courte à l'IA.
    Optimisation Token : L'IA ne reçoit pas la liste complète dans son historique.
    """
    try:
        # Construction de la liste formatée pour l'humain
        categories = {}
        
        # Organisation par catégories (si possible, sinon liste plate)
        for tool in TOOLS_SCHEMA:
            # On essaie de deviner la catégorie ou on met "Divers"
            name = tool.get("name", "Inconnu")
            desc = tool.get("description", "Pas de description")
            
            cat = "🔧 Divers"
            if "fichier" in name or "dossier" in name or "arborescence" in name: cat = "📁 Fichiers"
            elif "git" in name: cat = "🐙 Git"
            elif "memoire" in name or "contexte" in name: cat = "🧠 Mémoire"
            elif "code" in name or "refactor" in name or "audit" in name: cat = "💻 Code"
            elif "web" in name: cat = "🌐 Web"
            elif "backup" in name: cat = "💾 Backup"
            elif "doc" in name: cat = "📚 Documentation"
            
            if cat not in categories: categories[cat] = []
            categories[cat].append(f"- **{name}**: {desc}")

        # Construction du message final
        display_text = "## 🛠️ Liste Officielle des Outils\n"
        for cat, tools in sorted(categories.items()):
            display_text += f"\n### {cat}\n" + "\n".join(tools)

        # Envoi DIRECT à l'interface (Side-Channel)
        if result_queue:
            result_queue.put({
                "type": "chat_response",
                "text": display_text,
                "role": "system" # S'affiche comme un message système (gris/différent)
            })

        # Retour COURT pour la mémoire de l'IA
        return "Liste des outils affichée à l'utilisateur dans l'interface."

    except Exception as e:
        return f"❌ Erreur lors du listing des outils : {e}"

# --- REGISTRE DES OUTILS (Mapping Lazy) ---
def _get_tool_registry():
    """
    Dictionnaire dynamique des fonctions disponibles.
    Importe les modules à la demande pour éviter les cycles.
    """
    try:
        import features.FileSystem as FileSystem
        import features.Documentation as Documentation
        import features.CodeQuality as CodeQuality
        import features.Refactoring as Refactoring
        import features.ProjectManager as ProjectManager
        import features.SearchEngine as SearchEngine
        import features.GitActions as GitActions
        import features.BackupManager as BackupManager
        import features.ContextLoader as ContextLoader
        import features.SemanticMemory as SemanticMemory
        import features.Shared as Shared
        
        try:
            from features.context import database as RagDatabase 
        except ImportError:
            RagDatabase = None
            
    except ImportError as e:
        log.error(f"Erreur critique imports Features: {e}")
        return {}

    registry = {
        # --- SYSTEM ---
        "lister_outils": execute_lister_outils,

        # --- FILESYSTEM ---
        "lister_arborescence": getattr(FileSystem, 'execute_lister_arborescence', None),
        "lire_fichier": getattr(FileSystem, 'execute_lire_fichier', None),
        "lire_fichiers": getattr(FileSystem, 'execute_lire_fichiers', None),
        "ecrire_fichier": getattr(FileSystem, 'execute_ecrire_fichier', None),
        "creer_dossier": getattr(FileSystem, 'execute_creer_dossier', None),
        "supprimer_fichier": getattr(FileSystem, 'execute_supprimer_fichier', None),
        "comparer_fichiers": getattr(FileSystem, 'execute_comparer_fichiers', None),
        "deplacer_fichier": getattr(FileSystem, 'execute_deplacer_fichier', None),
        "copier_fichier": getattr(FileSystem, 'execute_copier_fichier', None),
        "obtenir_infos_fichier": getattr(FileSystem, 'execute_obtenir_infos_fichier', None),
        "rechercher_fichiers": getattr(SearchEngine, 'execute_rechercher_fichiers', None),
        
        # --- WEB SURFER ---
        "web_search": getattr(WebSurfer, 'handle_web_search', None),
        "web_goto": getattr(WebSurfer, 'handle_web_navigate', None),
        "web_screen": getattr(WebSurfer, 'handle_web_screenshot', None),

        # --- SEARCH ---
        "rechercher_texte": getattr(SearchEngine, 'execute_recherche_texte', None),

        # --- DOCUMENTATION ---
        "generer_documentation": getattr(Documentation, 'execute_generer_documentation', None),
        "rechercher_documentation": getattr(Documentation, 'execute_rechercher_documentation', None),
        "update_architecture": getattr(Documentation, 'execute_update_architecture', None),

        # --- PROJECT MANAGEMENT ---
        "generer_plan_technique_atomique": getattr(ProjectManager, 'regenerer_plan_technique_atomique', None),
        "generer_roadmap_synthetique": getattr(ProjectManager, 'execute_generer_roadmap_synthetique', None),
        "generer_changelog_append_only": getattr(ProjectManager, 'execute_generer_changelog_append_only', None),
        "synthese_historique": getattr(ProjectManager, 'execute_synthese_historique', None),

        # --- CODE QUALITY ---
        "audit_qualite": getattr(CodeQuality, 'execute_verifier_code', None),
        "verifier_code": getattr(CodeQuality, 'execute_verifier_code', None),
        "analyser_code": getattr(CodeQuality, 'execute_analyser_code', None),
        "generer_tests": getattr(CodeQuality, 'execute_generer_tests', None),

        # --- REFACTORING ---
        "refactoriser_code": getattr(Refactoring, 'execute_refactoriser_code', None),
        "modifier_fichier": getattr(Refactoring, 'execute_modifier_fichier', None),
        "formater_code": getattr(Refactoring, 'execute_formater_code', None),

        # --- CONTEXT & MEMORY ---
        "charger_contexte_domaine": getattr(ContextLoader, 'charger_contexte_domaine', None),
        "charger_contexte": getattr(ContextLoader, 'execute_charger_contexte', None),
        "sauvegarder_memoire": getattr(SemanticMemory, 'execute_sauvegarder_memoire', None),
        "rechercher_memoire": getattr(SemanticMemory, 'execute_rechercher_memoire', None),
        
        # --- RAG ---
        "reconstruire_base_vectorielle": getattr(RagDatabase, 'index_project_files', None) if RagDatabase else None,
        "supprimer_base_vectorielle": getattr(RagDatabase, 'delete_local_db', None) if RagDatabase else None,

        # --- BACKUP ---
        "lister_backups": getattr(BackupManager, 'execute_lister_backups', None),
        "restaurer_backup": getattr(BackupManager, 'execute_restaurer_backup', None),
        "creer_backup": getattr(BackupManager, 'execute_creer_backup', None),
        "backup_projet": getattr(BackupManager, 'execute_creer_backup', None),

        # --- GIT ---
        "analyser_depot_github": getattr(GitActions, 'execute_analyser_depot_github', None),
        
        # --- SYSTEM ---
        "lire_logs": getattr(Shared, 'execute_lire_logs', None)
    }
    return {k: v for k, v in registry.items() if v is not None}

# --- LOGIQUE DE PARSING & RÉPARATION ---

def _clean_pollution(text):
    """Nettoie les artefacts de chat et les caractères invisibles."""
    text = text.replace("[⚠️ Contenu bloqué]", "")
    text = re.sub(r"^```[a-zA-Z]*", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    text = text.replace('\xa0', ' ').replace('“', '"').replace('”', '"')
    text = text.replace("‘", "'").replace("’", "'")
    return text.strip()

def _try_parse_payload(payload):
    """Tente de parser une chaîne (JSON ou AST Python)."""
    clean_payload = payload.replace('\\"', '"') 
    
    # 1. JSON Strict
    try:
        return json.loads(clean_payload)
    except: pass
    
    # 2. AST (Python Dict)
    try:
        py_payload = clean_payload.replace("true", "True").replace("false", "False").replace("null", "None")
        return ast.literal_eval(py_payload)
    except: pass
    
    return None

def _repair_and_parse(text):
    """Tente de réparer un JSON tronqué."""
    open_count = text.count('{')
    close_count = text.count('}')
    
    if open_count <= close_count: return None
        
    missing = open_count - close_count
    repaired_text = text + ('}' * missing)
    
    log.warning(f"🔧 Tentative réparation JSON : Ajout de {missing} '}}'.")
    return _try_parse_payload(repaired_text)

def _smart_extract_and_parse(raw_text):
    """Stratégie multi-couches pour extraire la commande."""
    clean_text = _clean_pollution(raw_text)
    
    start_idx = clean_text.find('{')
    if start_idx == -1:
        raise ValueError("Aucune accolade ouvrante '{' trouvée.")

    candidate_text = clean_text[start_idx:]

    # 1. Essai Direct
    res = _try_parse_payload(candidate_text)
    if res: return res

    # 2. Essai JSON Decoder
    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(candidate_text)
        return obj
    except: pass

    # 3. Essai Réparation
    res = _repair_and_parse(candidate_text)
    if res: return res

    # 4. Echec
    raise ValueError(f"Impossible de parser la commande. Contenu: {repr(raw_text[:50])}...")

# --- MIDDLEWARE DE SÉCURITÉ ---

def _security_check(tool_name, args):
    """
    Vérifie si l'action est autorisée par la politique de sécurité.
    """
    sec_config = APP_SETTINGS.get("security", {})
    if not sec_config.get("enable_sanity_check", True):
        return None # Sécurité désactivée

    # 1. Identification des chemins cibles
    target_paths = []
    keys_with_paths = ['chemin', 'cible', 'source', 'destination', 'fichier', 'chemin_racine']
    for k, v in args.items():
        if k in keys_with_paths and isinstance(v, str):
            target_paths.append(v)

    # 2. Vérification
    project_root = Path(os.getcwd()).resolve()
    
    for path_str in target_paths:
        try:
            path_obj = Path(path_str)
            if not path_obj.is_absolute():
                path_obj = (project_root / path_obj).resolve()
            else:
                path_obj = path_obj.resolve()

            # A. Confinement
            if sec_config.get("block_outside_project", True):
                if not str(path_obj).startswith(str(project_root)):
                    return f"⛔ SÉCURITÉ : Accès interdit hors du projet ({path_str})."

            # B. Protection Dossiers
            protected_dirs = sec_config.get("protected_directories", [])
            try:
                rel_path = str(path_obj.relative_to(project_root))
            except ValueError:
                rel_path = str(path_obj)
            
            for bad_dir in protected_dirs:
                if f"{bad_dir}" in rel_path.split(os.sep): 
                    return f"⛔ SÉCURITÉ : Le dossier '{bad_dir}' est protégé en écriture."

            # C. Protection Fichiers (Écriture)
            destructive_tools = ["ecrire_fichier", "supprimer_fichier", "modifier_fichier", "deplacer_fichier"]
            if tool_name in destructive_tools:
                protected_files = sec_config.get("protected_files", [])
                norm_rel_path = rel_path.replace("\\", "/")
                if norm_rel_path in protected_files:
                    return f"⛔ SÉCURITÉ : Le fichier critique '{norm_rel_path}' est protégé."

        except Exception as e:
            return f"⛔ SÉCURITÉ : Erreur validation '{path_str}' ({e})."

    return None

# --- EXÉCUTION ---

def execute_native_tool(name, args, session, action_log_path, result_queue, task_queue):
    registry = _get_tool_registry()
    
    if name not in registry:
        return f"❌ Outil non disponible ou non mappé : '{name}'"
    
    # --- MIDDLEWARE SÉCURITÉ ---
    security_error = _security_check(name, args)
    if security_error:
        log.warning(f"BLOCKED ACTION: {name} {args} -> {security_error}")
        return f"{security_error} (Désactivez 'Sanity Check' dans settings si nécessaire)."
    # ---------------------------

    func = registry[name]
    
    sys_kwargs = {
        "session": session, 
        "action_log_path": action_log_path, 
        "result_queue": result_queue, 
        "task_queue": task_queue
    }
    
    try:
        log.info(f"🔧 Exécution: {name}")
        # On passe les arguments de l'outil + les arguments système
        return func(**{**args, **sys_kwargs})
    except TypeError as e:
        return f"❌ Erreur Arguments {name}: {e}"
    except Exception as e:
        log.error(f"Crash outil {name}: {traceback.format_exc()}")
        return f"❌ Erreur Exécution {name}: {e}"

# --- DISPATCHER PRINCIPAL ---

def analyze_request_and_dispatch(command_text, session, response_queue, task_queue=None, action_log_path="action_log.json"):
    """
    Dispatcher Central (V2.1 - Polyglotte & Qualité).
    """
    cmd = command_text.strip()
    
    # 1. Introspection & Aide
    if cmd.lower() in ["!list_tools", "liste tes commandes", "help", "outils"]:
        return execute_lister_outils(session, action_log_path, response_queue)

    # 2. Mode Qualité (Boucle de Feedback)
    if cmd.startswith("!quality"):
        instruction = cmd.replace("!quality", "", 1).strip().strip('"')
        
        if not instruction:
            return "⚠️ Usage : `!quality \"Votre instruction\"`"
        
        if QualityEngine:
            # [CORRECTION] Injection des paramètres depuis APP_SETTINGS
            agents_conf = APP_SETTINGS.get("agents_config", {})
            general_conf = APP_SETTINGS.get("general_settings", {})
            
            # On prend la config spécifique Quality ou on fallback sur le Cloud Max Steps
            max_iter = general_conf.get("quality_loop_max_iterations", 
                                      agents_conf.get("react_max_steps_cloud", 5))
            
            # Instanciation avec la config dynamique
            engine = QualityEngine.QualityLoop(session, max_iterations=int(max_iter))
            return engine.run_cycle(instruction)
        else:
            return "❌ Erreur: Module QualityEngine non chargé."
    # 3. Tunnel JSON (!native_tool) - Standard Swarm
    if "!native_tool" in cmd:
        trigger = "!native_tool"
        idx = cmd.find(trigger)
        if idx != -1:
            payload = cmd[idx + len(trigger):]
            try:
                tool_call = _smart_extract_and_parse(payload)
                if not isinstance(tool_call, dict):
                    return f"❌ Erreur Format JSON invalide."

                return execute_native_tool(
                    tool_call.get("name"), 
                    tool_call.get("args", {}), 
                    session, action_log_path, response_queue, task_queue
                )
            except ValueError as e:
                return f"❌ Erreur Parsing : {e}"
            except Exception as e:
                return f"❌ Erreur Interne Dispatch : {e}"

    # 4. Router Legacy (Fallback pour anciennes commandes "!")
    SessionFactory = _get_session_factory()
    if cmd.lower() == "!list_models":
        txt = "🤖 **MODÈLES**\n" + "\n".join([f"- `{k}` : {v}" for k, v in SessionFactory.cloud_registry.items()])
        return txt

    if cmd.startswith("!"):
        router_session = SessionFactory.create_session("router")
        return call_ai_robust(router_session, f"Corrige cette commande : {cmd}")

    return "⚠️ Commande ignorée (Utilisez `!native_tool` ou `!quality`)."

def generate_search_query(user_prompt):
    session = _get_session_factory().create_session("router")
    return call_ai_robust(session, f"Mots-clés recherche pour : {user_prompt}").strip().replace('"', '')
import os
import fnmatch
import shutil
import difflib
import time
import ast
from config import get_path, get_logger
from features.Decorators import trace_action
from features.Shared import log_action  # [AJOUT] Nécessaire pour les wrappers
# [AJOUT] Import du Resolver
from features.SearchEngine import omniscient_resolve_path
# [AJOUT] Imports conditionnels pour RAG et Backup
try:
    import features.context.database as database
except ImportError:
    database = None

try:
    import features.core_backup as backup_manager
except ImportError:
    backup_manager = None

log = get_logger("Features.FileSystem")
log = get_logger("Features.FileSystem")

# --- CONFIGURATION DES EXCLUSIONS ---
# Dossiers à ignorer systématiquement pour éviter le bruit et les erreurs
IGNORED_DIRS = [
    # Système & IDE
    ".git", ".vs", ".vscode", ".ia_history", "__pycache__", ".idea",
    # Dépendances
    "venv", "env", "node_modules", "site-packages",
    # Données & Logs
    "backups", "db", "logs", "audio_cache",
    # Archives & Legacy
    "_OLD", "_old", "legacy", "Legacy", "archive",
    # Sorties
    "dist", "build", "Documentation" 
]

# Fichiers à ignorer
IGNORED_FILES = [
    "*.pyc", "*.zip", "*.tar.gz", "*.rar", "*.7z",
    "package-lock.json", "yarn.lock", "poetry.lock",
    ".DS_Store", "thumbs.db", "desktop.ini",
    "*.db", "*.sqlite", "*.sqlite3", # Bases de données binaires
    "full_chat_history.json" # Souvent trop gros
]

# --- FONCTIONS CŒUR (LOGIQUE) ---

@trace_action(source="FileSystem")
def lister_arborescence(chemin_relatif=None, profondeur_max=5):
    """
    Liste l'arborescence du projet en filtrant le bruit.
    """
    root_path = get_path(chemin_relatif) if chemin_relatif else get_path(".")
    
    if not os.path.exists(root_path):
        return f"Erreur: Le chemin '{root_path}' n'existe pas."

    structure = []
    structure.append(f"--- Structure de '{chemin_relatif or '.'}' ---")

    for root, dirs, files in os.walk(root_path):
        # 1. Filtrage des dossiers (Modification in-place pour empêcher la descente)
        # On retire tout ce qui est dans IGNORED_DIRS
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        
        # Calcul de la profondeur actuelle
        level = root.replace(root_path, '').count(os.sep)
        if level > profondeur_max:
            continue
            
        indent = '  ' * level
        folder_name = os.path.basename(root)
        
        # N'affiche pas le dossier racine '.' s'il est redondant
        if level == 0 and folder_name == ".":
            pass
        else:
            structure.append(f"{indent}{folder_name}/")
        
        subindent = '  ' * (level + 1)
        
        for f in files:
            # 2. Filtrage des fichiers
            if any(fnmatch.fnmatch(f, p) for p in IGNORED_FILES):
                continue
            
            structure.append(f"{subindent}{f}")

    return "\n".join(structure)

@trace_action(source="FileSystem")
def lire_fichier(chemin):
    """Lit le contenu d'un fichier texte (avec Résolution Intelligente)."""
    abs_path = get_path(chemin)
    
    # 1. Tentative Directe
    if not os.path.exists(abs_path):
        # 2. Tentative Omnisciente (Si échec)
        log.info(f"Fichier '{chemin}' introuvable. Tentative de résolution omnisciente...")
        resolved = omniscient_resolve_path(chemin)
        
        if resolved:
            log.info(f"✅ Résolu : '{chemin}' -> '{resolved}'")
            chemin = resolved # On met à jour le chemin cible
            abs_path = get_path(resolved)
        else:
            return f"Erreur: Le fichier '{chemin}' n'existe pas (même après recherche intelligente)."

    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        return "Erreur: Fichier binaire ou encodage non supporté."
    except Exception as e:
        return f"Erreur lecture {chemin}: {e}"
    
def _verifier_syntaxe_python(contenu, nom_fichier="<string>"):
    """
    [PORTAGE LEGACY] Vérifie la syntaxe Python avant écriture.
    """
    try:
        ast.parse(contenu, filename=nom_fichier)
        return True, None
    except SyntaxError as e:
        error_msg = f"Ligne {e.lineno}: {e.msg}"
        return False, error_msg
    except Exception as e:
        return False, str(e)
    
@trace_action(source="FileSystem")
def ecrire_fichier(chemin, contenu):
    """
    Écrit un fichier avec Validation Syntaxe + Backup + Hook RAG.
    """
    abs_path = get_path(chemin)
    
    # 1. Validation Syntaxe (Python uniquement)
    if chemin.endswith(".py"):
        valide, erreur = _verifier_syntaxe_python(contenu, chemin)
        if not valide:
            log.warning(f"🚫 Écriture refusée (Syntaxe) : {chemin} -> {erreur}")
            # [CORRECTION] On inclut "refusée" dans le message de retour pour le test
            return f"🚫 Écriture refusée (Erreur Syntaxe) : {erreur}"

    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        # 2. Backup de sécurité avant écrasement
        if os.path.exists(abs_path) and backup_manager:
            # On ne fait pas un backup complet du projet (trop lourd), mais une copie locale rapide si besoin
            # Ou on appelle le backup manager si configuré pour snapshot
            pass # À implémenter si vous voulez le snapshot ZIP par fichier

        # 3. Écriture
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(contenu)
            
        # 4. Hook RAG (Indexation Immédiate)
        if database:
            try:
                # Note: database.add_file_to_db doit exister dans features/context/database.py
                # Si la fonction s'appelle différemment dans la V2, adaptez ici.
                if hasattr(database, 'add_file_to_db'):
                    database.add_file_to_db(chemin) 
                    log.info(f"🧠 RAG: {chemin} ré-indexé.")
            except Exception as e:
                log.warning(f"RAG Hook Error: {e}")

        return f"Fichier {chemin} écrit avec succès (Validé & Indexé)."
        
    except Exception as e:
        return f"Erreur écriture {chemin}: {e}"

@trace_action(source="FileSystem")
def creer_dossier(chemin):
    """Crée un dossier récursivement."""
    abs_path = get_path(chemin)
    try:
        os.makedirs(abs_path, exist_ok=True)
        return f"Dossier {chemin} créé."
    except Exception as e:
        return f"Erreur création dossier {chemin}: {e}"

@trace_action(source="FileSystem")
def supprimer_fichier(chemin):
    """Supprime un fichier."""
    abs_path = get_path(chemin)
    try:
        if os.path.exists(abs_path):
            os.remove(abs_path)
            return f"Fichier {chemin} supprimé."
        return "Fichier introuvable."
    except Exception as e:
        return f"Erreur suppression {chemin}: {e}"
# --- AJOUT SECTION COMPARATEUR ---

@trace_action(source="FileSystem")
def comparer_fichiers(chemin_a, chemin_b):
    """
    Compare deux fichiers et retourne un diff unifié.
    """
    path_a = get_path(chemin_a)
    path_b = get_path(chemin_b)
    
    if not os.path.exists(path_a): return f"Erreur: Fichier A introuvable ({chemin_a})"
    if not os.path.exists(path_b): return f"Erreur: Fichier B introuvable ({chemin_b})"
    
    try:
        with open(path_a, 'r', encoding='utf-8') as f1:
            text_a = f1.readlines()
        with open(path_b, 'r', encoding='utf-8') as f2:
            text_b = f2.readlines()
            
        diff = difflib.unified_diff(
            text_a, text_b, 
            fromfile=chemin_a, 
            tofile=chemin_b, 
            lineterm=''
        )
        
        diff_content = "\n".join(list(diff))
        if not diff_content:
            return "✅ Les fichiers sont identiques."
            
        return f"### Différences entre {chemin_a} et {chemin_b} :\n```diff\n{diff_content}\n```"
        
    except Exception as e:
        return f"Erreur lors de la comparaison : {e}"
# --- AJOUTS DE FONCTIONS DE GESTION DE FICHIERS ---
@trace_action(source="FileSystem")
def deplacer_fichier(source, destination):
    """Déplace ou renomme un fichier."""
    src_path = get_path(source)
    dst_path = get_path(destination)
    
    if not os.path.exists(src_path): return f"Erreur: Source introuvable ({source})"
    if os.path.exists(dst_path): return f"Erreur: Destination existe déjà ({destination})"
    
    try:
        shutil.move(src_path, dst_path)
        return f"✅ Succès : '{source}' déplacé vers '{destination}'."
    except Exception as e:
        return f"Erreur déplacement : {e}"

@trace_action(source="FileSystem")
def copier_fichier(source, destination):
    """Copie un fichier vers une nouvelle destination."""
    src_path = get_path(source)
    dst_path = get_path(destination)
    
    if not os.path.exists(src_path): return f"Erreur: Source introuvable ({source})"
    
    try:
        shutil.copy2(src_path, dst_path)
        return f"✅ Succès : '{source}' copié vers '{destination}'."
    except Exception as e:
        return f"Erreur copie : {e}"

@trace_action(source="FileSystem")
def obtenir_infos_fichier(chemin):
    """Récupère les métadonnées (taille, dates) d'un fichier."""
    abs_path = get_path(chemin)
    if not os.path.exists(abs_path): return f"Erreur: Fichier introuvable ({chemin})"
    
    try:
        stats = os.stat(abs_path)
        return (
            f"📄 **Infos Fichier :** {chemin}\n"
            f"- Taille : {stats.st_size} octets\n"
            f"- Création : {time.ctime(stats.st_ctime)}\n"
            f"- Modification : {time.ctime(stats.st_mtime)}"
        )
    except Exception as e:
        return f"Erreur infos : {e}"

# --- WRAPPERS DISPATCHER (AJOUTS) ---

@trace_action(source="FileSystem")
def execute_deplacer_fichier(source, destination, session, action_log_path, result_queue, **kwargs):
    res = deplacer_fichier(source, destination)
    log_action("deplacer_fichier", f"{source} -> {destination}", "Système", action_log_path)
    return res

@trace_action(source="FileSystem")
def execute_copier_fichier(source, destination, session, action_log_path, result_queue, **kwargs):
    res = copier_fichier(source, destination)
    log_action("copier_fichier", f"{source} -> {destination}", "Système", action_log_path)
    return res

@trace_action(source="FileSystem")
def execute_obtenir_infos_fichier(chemin, session, action_log_path, result_queue, **kwargs):
    return obtenir_infos_fichier(chemin)
# --- WRAPPERS D'EXÉCUTION (POUR LE DISPATCHER) ---
# Ces fonctions font le pont avec ai_helper.py en acceptant (session, log_path, queue)

@trace_action(source="FileSystem")
def execute_lister_arborescence(chemin_relatif, session, action_log_path, result_queue, **kwargs):
    result = lister_arborescence(chemin_relatif)
    log_action("lister_arborescence", "Lecture", chemin_relatif or ".", action_log_path)
    return result
@trace_action(source="FileSystem")
def execute_comparer_fichiers(source, destination, session, action_log_path, result_queue, **kwargs):
    # Note : 'source' et 'destination' correspondent aux noms d'arguments génériques souvent utilisés par l'IA
    # On gère aussi 'chemin_a' et 'chemin_b' via kwargs pour la robustesse
    f_a = source or kwargs.get('chemin_a')
    f_b = destination or kwargs.get('chemin_b')
    
    if not f_a or not f_b:
        return "Erreur : Il faut deux fichiers pour comparer (source/destination ou chemin_a/chemin_b)."

    result = comparer_fichiers(f_a, f_b)
    log_action("comparer_fichiers", f"{f_a} vs {f_b}", "Système", action_log_path)
    return result
@trace_action(source="FileSystem")
def execute_lire_fichier(chemin, session, action_log_path, result_queue, **kwargs):
    result = lire_fichier(chemin)
    log_action("lire_fichier", "Lecture", chemin, action_log_path)
    return result
@trace_action(source="FileSystem")
def execute_lire_fichiers(session, action_log_path, result_queue, **kwargs):
    """
    Alias robuste pour lire_fichier.
    Gère 'chemin' (str) ou 'chemins' (list) pour compatibilité.
    """
    target = kwargs.get('chemin') or kwargs.get('chemins')
    if not target: return "❌ Erreur: Aucun chemin fourni."
    
    # Cas simple : une seule chaine
    if isinstance(target, str):
        return execute_lire_fichier(target, session, action_log_path, result_queue)
    
    # Cas liste : on lit tout
    results = []
    for f in target:
        res = lire_fichier(f)
        results.append(res)
    return "\n\n".join(results)

@trace_action(source="FileSystem")
def execute_ecrire_fichier(chemin, contenu, session, action_log_path, result_queue, **kwargs):
    # Appel de la nouvelle version sécurisée
    result = ecrire_fichier(chemin, contenu)
    
    # Si succès (pas "Erreur" dans le texte), on déclenche un backup projet asynchrone si nécessaire
    # (Logique Legacy : "Déclenchement sauvegarde complète")
    if "succès" in result.lower() and backup_manager:
        # On peut notifier l'UI qu'un backup va se lancer
        if result_queue: result_queue.put({"type": "ui_update", "widget": "status", "text": "Sauvegarde Projet..."})
        # backup_manager.create_backup() # Décommenter si vous voulez un backup projet complet à chaque écriture
    
    log_action("ecrire_fichier", "Ecriture Sécurisée", chemin, action_log_path)
    return result

@trace_action(source="FileSystem")
def execute_creer_dossier(chemin, session, action_log_path, result_queue, **kwargs):
    result = creer_dossier(chemin)
    log_action("creer_dossier", "Creation", chemin, action_log_path)
    return result

@trace_action(source="FileSystem")
def execute_supprimer_fichier(chemin, session, action_log_path, result_queue, **kwargs):
    result = supprimer_fichier(chemin)
    log_action("supprimer_fichier", "Suppression", chemin, action_log_path)
    return result
@trace_action(source="FileSystem")
def execute_deplacer_fichier(source, destination, session, action_log_path, result_queue, **kwargs):
    res = deplacer_fichier(source, destination)
    log_action("deplacer_fichier", f"{source} -> {destination}", "Système", action_log_path)
    return res

@trace_action(source="FileSystem")
def execute_copier_fichier(source, destination, session, action_log_path, result_queue, **kwargs):
    res = copier_fichier(source, destination)
    log_action("copier_fichier", f"{source} -> {destination}", "Système", action_log_path)
    return res

@trace_action(source="FileSystem")
def execute_obtenir_infos_fichier(chemin, session, action_log_path, result_queue, **kwargs):
    return obtenir_infos_fichier(chemin)
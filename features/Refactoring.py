import os
import logging
import re
import ast

# Imports Configuration Modulaire
from config.paths import get_path
from config.logs import get_logger
from config.constants import SUPPORTED_FILE_EXTENSIONS

# Imports Features & Core
from features.Shared import log_action
from ai_core.sessions import call_ai_robust
from features.Decorators import trace_action

# Import Backup Manager (Robuste)
try:
    import features.core_backup as backup_manager
except ImportError:
    try:
        import core_backup as backup_manager
    except ImportError:
        backup_manager = None

# Import Database pour réindexation RAG
try:
    from features.context import database
except ImportError:
    database = None

log = get_logger("features.Refactoring")

# --- UTILITAIRES INTERNES ---

def _verifier_syntaxe_python(code_content, filename="temp.py"):
    """Vérifie si le code Python est syntaxiquement valide via AST."""
    try:
        ast.parse(code_content)
        return True, None
    except SyntaxError as e:
        return False, f"Erreur Syntaxe Ligne {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

def _extraire_code_python(texte_brut):
    """
    Extrait proprement le code Python d'une réponse IA.
    Gère les blocs Markdown, le texte brut et les phrases de politesse.
    """
    content = texte_brut.strip()
    
    # 1. Recherche de blocs de code Markdown (Priorité absolue)
    # On cherche le dernier bloc ou le plus grand pour éviter les exemples partiels
    matches = re.findall(r"```(?:python)?\s*(.*?)```", content, re.DOTALL | re.IGNORECASE)
    if matches:
        # On prend le bloc le plus long (supposé être le code complet)
        return max(matches, key=len).strip()
    
    # 2. Fallback : Nettoyage ligne par ligne si pas de markdown
    lines = content.splitlines()
    cleaned_lines = []
    in_code = False
    
    for line in lines:
        stripped = line.strip()
        # Filtrage des phrases de politesse courantes au début
        if not in_code and (stripped.startswith(("Voici", "Here is", "Sure", "D'accord", "Je vais")) or stripped.endswith(":")):
            continue
        
        # Détection heuristique de début de code
        if (stripped.startswith(("import ", "from ", "def ", "class ", "@", "#", "if __name__"))):
            in_code = True
            
        if in_code:
            cleaned_lines.append(line)
            
    if cleaned_lines:
        return "\n".join(cleaned_lines).strip()
        
    # Si aucun nettoyage n'a marché, on renvoie tout (risque, mais mieux que rien)
    return content 

# --- WRAPPERS DISPATCHER ---

@trace_action(source="Refactoring")
def execute_modifier_fichier(chemin=None, instruction=None, session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Applique une modification ciblée sur un fichier existant.
    Args:
        chemin (str): Chemin relatif du fichier.
        instruction (str): Consigne de modification.
    """
    # Robustesse arguments (gestion kwargs et args positionnels manquants)
    target_path = chemin or kwargs.get('chemin')
    instr = instruction or kwargs.get('instruction')
    
    if not target_path or not instr:
        return "❌ Erreur : Chemin ou instruction manquant pour la modification."

    abs_path = get_path(target_path)
    if not os.path.exists(abs_path):
        return f"❌ Erreur : Fichier '{target_path}' introuvable."
    
    if os.path.isdir(abs_path):
        return "❌ Erreur : Impossible de modifier un dossier entier. Ciblez un fichier."

    # 1. Backup de Sécurité (Obligatoire & Forcé)
    if backup_manager:
        if result_queue: 
            result_queue.put({"type": "ui_update", "widget": "status", "text": "🔒 Backup de sécurité..."})
        try:
            # On force le backup même si le délai n'est pas écoulé (Argument 'force' corrigé précédemment)
            backup_manager.create_backup(comment=f"AUTO: Avant modif {os.path.basename(target_path)}", force=True)
        except Exception as e:
            log.warning(f"Echec backup sécurité: {e}")
    
    # 2. Lecture Contenu
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        if not original_content.strip():
            return f"⚠️ Le fichier {target_path} est vide. Utilisez 'ecrire_fichier' pour le créer."

    except Exception as e:
        return f"❌ Erreur lecture fichier : {e}"

    if result_queue:
        result_queue.put({"type": "ui_update", "widget": "message", "text": f"✍️ Réécriture IA de {target_path}..."})

    # 3. Prompt "Coding Agent" Directif
    prompt = (
        f"Tu es un Expert Python Senior.\n"
        f"TACHE : Appliquer la modification suivante sur le fichier `{target_path}`.\n"
        f"INSTRUCTION : {instr}\n\n"
        f"RÈGLE CRITIQUE : Renvoie UNIQUEMENT le code source complet du fichier mis à jour. "
        f"Pas de texte avant, pas de texte après, pas d'explications.\n"
        f"--- CODE ORIGINAL ---\n{original_content}"
    )

    # Appel IA (Mode Coder/Pro pour la qualité, Force Text pour éviter les boucles)
    response = call_ai_robust(session, prompt, mode="coder", force_text=True)
    new_content = _extraire_code_python(response)

    # 4. Vérification Syntaxe (Safety Check)
    if target_path.endswith(".py"):
        is_valid, error_msg = _verifier_syntaxe_python(new_content)
        if not is_valid:
            log.error(f"Refus écriture {target_path}: {error_msg}")
            # On ne l'écrit PAS, on renvoie l'erreur à l'IA
            return (
                f"🚫 ÉCRITURE REFUSÉE : Le code généré contient des erreurs de syntaxe.\n"
                f"Détail : {error_msg}\n"
                f"L'opération a été annulée pour protéger le projet. Veuillez réessayer."
            )

    # 5. Écriture & Indexation
    try:
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # Réindexation RAG immédiate
        if database:
            try: database.add_file_to_db(abs_path)
            except: pass
        
        if action_log_path:
            log_action("modifier_fichier", instr, target_path, action_log_path)
        
        # Feedback visuel du nouveau contenu
        if result_queue:
            result_queue.put({'type': 'file_content', 'path': abs_path, 'content': new_content})
        
        nb_lignes = len(new_content.splitlines())
        return f"✅ Fichier '{target_path}' modifié avec succès ({nb_lignes} lignes).\n(Un backup a été créé avant la modification)."
        
    except Exception as e:
        return f"❌ Erreur technique lors de l'écriture : {e}"

@trace_action(source="Refactoring")
def execute_refactoriser_code(cible=None, consigne=None, session=None, action_log_path=None, result_queue=None, auto_apply=False, **kwargs):
    """
    Analyse et propose un refactoring. Peut appliquer directement si auto_apply=True.
    """
    target_path = cible or kwargs.get('cible')
    instr = consigne or kwargs.get('consigne')
    
    # Gestion booléenne souple pour l'IA (qui envoie parfois "True" string)
    apply_now = auto_apply or kwargs.get('auto_apply', False)
    if isinstance(apply_now, str):
        apply_now = apply_now.lower() == 'true'

    if not target_path:
        return "❌ Erreur : Cible manquante pour le refactoring."

    abs_path = get_path(target_path)
    if not os.path.exists(abs_path):
        return f"❌ Cible introuvable : {target_path}"

    # FAST-TRACK : Si c'est un fichier unique et qu'on demande l'application
    if apply_now and os.path.isfile(abs_path):
        if result_queue: 
            result_queue.put({"type": "ui_update", "widget": "status", "text": "🚀 Fast-Track Refactoring..."})
        # On délègue tout à modifier_fichier qui est déjà sécurisé
        return execute_modifier_fichier(target_path, instr, session, action_log_path, result_queue)

    # MODE PLANIFICATION (Dossier ou sans auto_apply)
    context_content = ""
    file_count = 0
    
    if os.path.isfile(abs_path):
        with open(abs_path, 'r', encoding='utf-8') as f: 
            context_content = f.read()
            file_count = 1
    elif os.path.isdir(abs_path):
        # Scan rapide (limité)
        for root, _, files in os.walk(abs_path):
            if any(x in root for x in [".git", "__pycache__", "venv", "node_modules"]): continue
            for f in files:
                if f.endswith(SUPPORTED_FILE_EXTENSIONS):
                    try:
                        p = os.path.join(root, f)
                        with open(p, 'r', encoding='utf-8') as fh:
                            content = fh.read()
                            if content.strip():
                                context_content += f"\n--- {f} ---\n{content[:5000]}\n"
                                file_count += 1
                    except: pass
            if len(context_content) > 60000: break # Limite contexte

    if not context_content:
        return f"⚠️ Aucun contenu analysable trouvé dans {target_path}."

    prompt = (
        f"Tu es Architecte Logiciel.\n"
        f"OBJECTIF : {instr}\n"
        f"CIBLE : {target_path} ({file_count} fichiers)\n\n"
        f"Analyse le code ci-dessous et propose un PLAN DE REFACTORING détaillé.\n"
        f"Ne génère pas tout le code, mais explique les étapes, les classes à créer/modifier et les risques.\n"
        f"--- CODE ---\n{context_content[:80000]}"
    )

    if result_queue:
        result_queue.put({"type": "ui_update", "widget": "status", "text": "🧠 Analyse Refactoring..."})

    response = call_ai_robust(session, prompt, mode="architect", force_text=True)
    
    if action_log_path:
        log_action("refactoriser_code", instr, target_path, action_log_path)
        
    return f"📋 **Plan de Refactoring Proposé :**\n\n{response}"

@trace_action(source="Refactoring")
def execute_formater_code(fichier=None, session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Formate le code (Simulation Black/Autopep8 via IA pour l'instant).
    """
    target = fichier or kwargs.get('fichier')
    return execute_modifier_fichier(
        target, 
        "Formate ce code selon les standards PEP8 stricts (indentation, espacement, imports). Ne change pas la logique.", 
        session, action_log_path, result_queue
    )
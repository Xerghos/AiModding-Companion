import os
import logging
import json
import traceback

# Imports Configuration Modulaire
from config.paths import get_path
from config.logs import get_logger
from config.constants import SUPPORTED_FILE_EXTENSIONS

# Imports Features & Core
from features.Shared import smart_resolve_path, log_action
from ai_core.sessions import call_ai_robust
from features.Decorators import trace_action

# Import Backup Manager (Robuste)
try:
    import features.core_backup as backup_manager
except ImportError:
    backup_manager = None

log = get_logger("features.CodeQuality")

# Fichiers à ignorer systématiquement pour l'audit
ALWAYS_IGNORE_FILES = [
    "action_log.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", 
    "Gemfile.lock", "composer.lock", "kb_drive_file_id.json", "gdrive_token.json",
    "full_chat_history.json", "prompt_history.json", "architecture_map.json"
]

@trace_action(source="CodeQuality")
def _lister_fichiers_pertinents(abs_path):
    """
    Retourne une liste nettoyée de fichiers à analyser (exclut les dossiers techniques).
    """
    fichiers = []
    ignored_dirs = {".git", "__pycache__", "venv", "env", "node_modules", ".idea", ".vscode", "build", "dist"}
    
    if os.path.isfile(abs_path):
        return [abs_path]
        
    for root, dirs, files in os.walk(abs_path):
        # Filtrage des dossiers
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        for f in files:
            if f in ALWAYS_IGNORE_FILES: continue
            if f.endswith(SUPPORTED_FILE_EXTENSIONS):
                fichiers.append(os.path.join(root, f))
    return fichiers

# --- WRAPPERS DISPATCHER (STANDARDISÉS) ---

@trace_action(source="CodeQuality")
def execute_verifier_code(chemin, session, action_log_path, result_queue, **kwargs):
    """
    Audit statique (Linting & Sécurité) sur un fichier ou un dossier.
    Commande : audit_qualite, verifier_code
    """
    consigne = kwargs.get('consigne', 'Audit standard (PEP8, Sécurité, Bonnes pratiques)')
    abs_path = smart_resolve_path(chemin)
    
    if not os.path.exists(abs_path):
        return f"❌ Chemin introuvable : {chemin}"

    targets = _lister_fichiers_pertinents(abs_path)
    if not targets:
        return f"⚠️ Aucun fichier éligible trouvé dans {chemin}."

    # Limite pour éviter de saturer le contexte
    if len(targets) > 5:
        return f"⚠️ Trop de fichiers ({len(targets)}). Veuillez cibler un sous-dossier ou un fichier spécifique pour un audit de qualité."

    rapport_global = f"🔍 **Rapport d'Audit Qualité**\nCible : `{chemin}`\nConsigne : {consigne}\n\n"
    has_content = False
    
    for file_path in targets:
        try:
            rel_path = os.path.relpath(file_path, get_path("."))
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip(): 
                rapport_global += f"### 📄 {rel_path}\n⚠️ Fichier vide, audit ignoré.\n\n---\n"
                continue

            if result_queue:
                result_queue.put({"type": "ui_update", "widget": "status", "text": f"Audit en cours : {rel_path}..."})
            
            has_content = True
            prompt = (
                f"Tu es un Expert Code Reviewer (Python/Fullstack).\n"
                f"Analyse le fichier suivant : `{rel_path}`.\n"
                f"Objectif : {consigne}\n\n"
                f"Règles :\n"
                f"1. Identifie les erreurs potentielles (Bugs, Sécurité).\n"
                f"2. Suggère des améliorations de style (PEP8/Linting) et de performance.\n"
                f"3. Sois concis et constructif. Utilise des listes à puces.\n"
                f"--- CODE ---\n{content[:20000]}" # Truncate safety
            )

            # Appel IA (Mode Rapide)
            avis = call_ai_robust(session, prompt, mode="fast", force_text=True)
            rapport_global += f"### 📄 {rel_path}\n{avis}\n\n---\n"

        except Exception as e:
            rapport_global += f"❌ Erreur sur {rel_path} : {e}\n"

    if not has_content:
         return f"⚠️ Les fichiers ciblés dans `{chemin}` sont vides. Aucune matière à auditer."

    log_action("audit_qualite", f"Audit de {len(targets)} fichiers", chemin, action_log_path)
    return rapport_global

@trace_action(source="CodeQuality")
def execute_analyser_code(chemin, session, action_log_path, result_queue, **kwargs):
    """
    Analyse structurelle et sémantique (Architecture, Dépendances, Logique).
    Commande : analyser_code
    """
    abs_path = smart_resolve_path(chemin)
    if not os.path.exists(abs_path): return f"❌ Chemin introuvable : {chemin}"
    
    targets = _lister_fichiers_pertinents(abs_path)
    if not targets: return f"⚠️ Aucun fichier à analyser dans {chemin}."
    
    if len(targets) > 10:
         return f"⚠️ Trop de fichiers ({len(targets)}) pour une analyse approfondie. Ciblez un module spécifique."

    combined_content = ""
    has_real_content = False

    for file_path in targets:
        try:
            rel_path = os.path.relpath(file_path, get_path("."))
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # [FIX CRITIQUE] On ne concatène que si le fichier a du contenu
                if content.strip():
                    combined_content += f"\n--- FICHIER: {rel_path} ---\n{content[:10000]}\n"
                    has_real_content = True
                else:
                    combined_content += f"\n--- FICHIER: {rel_path} (VIDE) ---\n"
        except: pass

    # [FIX CRITIQUE] Si aucun contenu réel, on arrête tout de suite pour ne pas faire halluciner l'IA
    if not has_real_content:
        return f"⚠️ **Analyse impossible :** Les fichiers ciblés (dont `{chemin}`) sont vides ou ne contiennent pas de code analysable."

    if result_queue:
        result_queue.put({"type": "ui_update", "widget": "status", "text": f"Analyse structurelle de {chemin}..."})

    prompt = (
        f"Tu es un Architecte Logiciel Senior.\n"
        f"Analyse la structure et la logique du code fourni ci-dessous (Dossier: {chemin}).\n"
        f"Points à couvrir :\n"
        f"1. Responsabilité des modules (Single Responsibility Principle).\n"
        f"2. Couplage et Dépendances (Sont-elles logiques ?).\n"
        f"3. Complexité Algorithmique (Points chauds).\n"
        f"4. Suggestions de Refactoring Architectural.\n"
        f"--- CODE ---\n{combined_content}"
    )

    # Appel IA (Mode Raisonnement/Pro si possible, sinon Fast)
    analyse = call_ai_robust(session, prompt, mode="pro", force_text=True)
    
    log_action("analyser_code", f"Analyse structurelle de {chemin}", "Système", action_log_path)
    return f"🏗️ **Analyse Structurelle : {chemin}**\n\n{analyse}"

@trace_action(source="CodeQuality")
def execute_generer_tests(chemin_source, session, action_log_path, result_queue, **kwargs):
    """
    Génère des tests unitaires pour un fichier donné.
    Commande : generer_tests
    """
    abs_path = smart_resolve_path(chemin_source)
    if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
        return f"❌ Fichier source introuvable ou invalide : {chemin_source}"

    try:
        rel_path = os.path.relpath(abs_path, get_path("."))
        
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # [FIX] Vérification fichier vide
        if not content.strip():
            return f"⚠️ Impossible de générer des tests : Le fichier `{rel_path}` est vide."

        if result_queue:
             result_queue.put({"type": "ui_update", "widget": "status", "text": f"Génération tests pour {rel_path}..."})
        
        prompt = (
            f"Tu es un Expert QA Automation (Pytest/Unittest).\n"
            f"Génère une suite de tests unitaires complète et robuste pour le fichier : `{rel_path}`.\n"
            f"Contraintes :\n"
            f"- Couvre les cas nominaux et les cas d'erreur (Edge cases).\n"
            f"- Utilise `unittest` ou `pytest` (préfère pytest si pertinent).\n"
            f"- Mock les dépendances externes (fichiers, API, DB) via `unittest.mock`.\n"
            f"- Le code doit être exécutable directement.\n"
            f"- Renvoie UNIQUEMENT le code Python complet dans un bloc de code.\n"
            f"--- CODE SOURCE ---\n{content[:30000]}"
        )
        
        # Appel IA
        response = call_ai_robust(session, prompt, mode="pro", force_text=True)
        
        # Extraction du code (nettoyage markdown)
        code_tests = response
        if "```python" in response:
            code_tests = response.split("```python")[1].split("```")[0].strip()
        elif "```" in response:
             code_tests = response.split("```")[1].split("```")[0].strip()

        # Sauvegarde
        test_filename = f"test_{os.path.basename(abs_path)}"
        test_dir = os.path.dirname(abs_path)
        test_path = os.path.join(test_dir, test_filename)
        
        # Backup si le fichier de test existe déjà (prudence)
        if os.path.exists(test_path) and backup_manager:
             backup_manager.create_backup(f"Backup avant écrasement {test_filename}")

        with open(test_path, 'w', encoding='utf-8') as f:
            f.write(code_tests)
            
        log_action("generer_tests", f"Tests générés : {test_filename}", chemin_source, action_log_path)
        
        return f"✅ Tests générés avec succès : `{test_path}`\n\n```python\n{code_tests[:500]}...\n```"

    except Exception as e:
        log.error(f"Erreur génération tests : {traceback.format_exc()}")
        return f"❌ Erreur technique lors de la génération des tests : {e}"
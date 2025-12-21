import os
import logging
from config import get_path, get_logger
from features.Shared import log_action
# Import standardisé pour éviter les cycles
from ai_core.sessions import call_ai_robust
from features.Decorators import trace_action

# Import optionnel du manager GitHub (Module technique bas niveau)
try:
    import features.github as github_manager
except ImportError:
    github_manager = None

log = get_logger("Features.GitActions")

@trace_action(source="GitActions")
def execute_analyser_depot_github(url, session, action_log_path, result_queue, **kwargs):
    """
    Clone un dépôt GitHub, analyse son contenu et génère un rapport.
    Args:
        url (str): URL HTTPS du dépôt.
    """
    # 1. Vérification Préliminaire
    if not github_manager:
        return "❌ Erreur : Le module technique 'features.github' est manquant ou mal installé."

    target_url = url or kwargs.get('url')
    if not target_url:
        return "❌ Erreur : URL du dépôt manquante."

    try:
        # 2. Feedback UI : Démarrage
        if result_queue:
            result_queue.put({"type": "ui_update", "widget": "status", "text": f"⬇️ Clonage de {target_url}..."})
            result_queue.put({"type": "ui_update", "widget": "message", "text": f"--- Analyse GitHub : {target_url} ---"})

        # 3. Récupération du Contenu (Appel au module technique)
        # On suppose que get_repo_contents_for_analysis retourne un dictionnaire {chemin: contenu}
        # et gère le clonage temporaire.
        repo_data, error = github_manager.get_repo_contents_for_analysis(target_url, result_queue)
        
        if error:
            return f"❌ Échec lors de la récupération du dépôt : {error}"
        
        if not repo_data:
            return "⚠️ Le dépôt semble vide ou ne contient aucun fichier texte analysable."

        # 4. Préparation du Prompt
        file_count = len(repo_data)
        if result_queue:
            result_queue.put({"type": "ui_update", "widget": "status", "text": f"🧠 Analyse IA de {file_count} fichiers..."})

        # Construction du contexte (Concaténation intelligente)
        full_content = ""
        for path, content in repo_data.items():
            full_content += f"\n--- FICHIER: {path} ---\n{content[:8000]}\n" # Limite par fichier

        prompt = (
            f"Tu es un Lead Developer effectuant un audit d'un dépôt externe.\n"
            f"URL : {target_url}\n"
            f"Nombre de fichiers analysés : {file_count}\n\n"
            f"Tâche : Rédige un rapport synthétique comprenant :\n"
            f"1. Objectif probable du projet.\n"
            f"2. Stack technique détectée (Langages, Frameworks).\n"
            f"3. Qualité du code (Rapide aperçu).\n"
            f"4. Points d'intérêt ou fichiers clés.\n\n"
            f"--- CONTENU DU DÉPÔT ---\n{full_content[:60000]}" # Troncation globale de sécurité
        )
        
        # 5. Appel IA (Mode Disposable pour ne pas saturer la mémoire active)
        response = call_ai_robust(session, prompt, mode="pro", disposable=True)
        
        # 6. Sauvegarde et Retour
        repo_name = target_url.rstrip('/').split('/')[-1]
        filename = f"analyse_{repo_name}.md"
        path_rapport = get_path(filename)
        
        try:
            with open(path_rapport, 'w', encoding='utf-8') as f: 
                f.write(f"# Rapport d'analyse : {target_url}\n\n{response}")
            
            # Feedback UI (Ouverture du fichier ou affichage)
            if result_queue:
                result_queue.put({'type': 'file_content', 'path': path_rapport, 'content': response})
                result_queue.put({"type": "ui_update", "widget": "message", "text": f"✅ Analyse terminée : {filename}"})
            
            log_action("analyser_depot_github", target_url, filename, action_log_path)
            
            return f"✅ Analyse terminée. Le rapport a été sauvegardé dans `{filename}` et affiché à l'écran."

        except Exception as e:
            return f"⚠️ Analyse réussie, mais erreur de sauvegarde du rapport : {e}"

    except Exception as e:
        log.error(f"Crash GitActions: {e}")
        return f"❌ Erreur critique lors de l'analyse GitHub : {e}"

@trace_action(source="GitActions")
def create_pr_simulation(branch, session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Simule la création d'une Pull Request (Placeholder pour évolution future).
    Appelé par !creer_pr ou via l'agent Commit.
    """
    if not github_manager:
        return "❌ Module GitHub manquant."
        
    return "🚧 Fonctionnalité 'Créer PR' en cours de développement (V25)."
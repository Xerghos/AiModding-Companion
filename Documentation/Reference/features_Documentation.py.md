# Documentation Technique: `features/Documentation.py`

## 1. En-tête

*   **Titre**: Module de Gestion et Génération de Documentation (DeepDoc)
*   **Description concise**: Ce module centralise les fonctionnalités de génération de documentation pour les fichiers source du projet. Il prend en charge la cartographie de l'architecture via un script externe et la génération de documentation atomique pour des fichiers individuels, intégrant des appels à l'IA, un suivi de progression thread-safe, et un filtrage robuste des sorties. Il gère également la persistance des hashs de fichiers pour éviter de redocumenter des fichiers inchangés et applique des règles d'exclusion définies par l'utilisateur.

*   **Dépendances**:
    *   `os`: Opérations système, chemins de fichiers.
    *   `time`: Pour des pauses courtes (anti-flood).
    *   `logging`: Enregistrement des événements.
    *   `traceback`: Récupération des traces d'erreurs.
    *   `hashlib`: Calcul des hashs de fichiers.
    *   `json`: Manipulation de données JSON.
    *   `subprocess`: Exécution de sous-processus externes.
    *   `sys`: Accès aux paramètres système (ex: `sys.executable`).
    *   `threading`: Gestion de la concurrence pour les compteurs de progression.
    *   `config.settings.APP_SETTINGS`: Paramètres de l'application.
    *   `features.UnifiedLogger.UnifiedLogger`: Système de journalisation unifié.
    *   `config.get_path`: Utilitaire pour les chemins absolus.
    *   `config.get_logger`: Utilitaire pour obtenir un logger.
    *   `config.SUPPORTED_FILE_EXTENSIONS`: Extensions de fichiers reconnues.
    *   `config.charger_json_robuste`: Chargement robuste de fichiers JSON.
    *   `config.sauvegarder_json`: Sauvegarde de fichiers JSON.
    *   `features.Shared.log_action`: Journalisation des actions.
    *   `features.ai_helper.call_ai_robust`: Appel robuste à l'API IA.
    *   `quality.run_quality_process` (Optionnel): Import conditionnel pour le processus de qualité.

## 2. Classes & Fonctions

Ce module ne contient pas de classes définies, uniquement des fonctions.

### `execute_update_architecture`

*   **Signature**: `def execute_update_architecture(session, action_log_path, result_queue, **kwargs)`
*   **Arguments**:
    *   `session` (`object`): Objet de session pour les interactions système.
    *   `action_log_path` (`str`): Chemin du fichier de journalisation des actions.
    *   `result_queue` (`queue.Queue` ou similaire, optionnel): Queue pour envoyer les résultats et mises à jour à l'interface utilisateur.
    *   `**kwargs` (`dict`): Arguments supplémentaires non utilisés directement ici mais passés par le système d'appel.
*   **Retours**: `str`. Un message de statut indiquant le succès ou l'échec de la mise à jour de l'architecture.
*   **Logique interne**:
    Cette fonction agit comme un wrapper et délègue la tâche de mise à jour de la carte d'architecture à un script Python externe situé à `scripts/generate_arch_map.py`.
    1.  Détermine le chemin absolu du script externe.
    2.  Vérifie l'existence du script et renvoie une erreur si introuvable.
    3.  Journalise l'action via `log_action`.
    4.  Si une `result_queue` est fournie, envoie une mise à jour à l'UI.
    5.  Exécute le script externe en tant que sous-processus en utilisant l'interpréteur Python courant (`sys.executable`).
    6.  Capture la sortie et les erreurs du script.
    7.  Renvoie un message de succès si le script s'exécute sans erreur (code de retour 0), sinon renvoie un message d'erreur avec les détails de la sortie d'erreur du script.
    8.  Gère les exceptions internes, journalise les erreurs et renvoie un message d'erreur.

### `_calculate_file_hash`

*   **Signature**: `def _calculate_file_hash(file_path)`
*   **Arguments**:
    *   `file_path` (`str`): Le chemin absolu du fichier dont le hash doit être calculé.
*   **Retours**: `str` (le hash SHA256 hexadécimal) ou `None` en cas d'erreur de lecture.
*   **Logique interne**:
    Calcule le hash SHA256 du contenu d'un fichier.
    1.  Initialise un objet `hashlib.sha256`.
    2.  Ouvre le fichier en mode binaire (`"rb"`).
    3.  Lit le fichier par blocs de 4096 octets pour gérer les gros fichiers efficacement.
    4.  Met à jour l'objet hash avec chaque bloc lu.
    5.  Retourne le hash final sous forme hexadécimale.
    6.  En cas d'erreur (ex: fichier introuvable), capture l'exception et retourne `None`.

### `_lister_fichiers_cibles`

*   **Signature**: `def _lister_fichiers_cibles(cible, strict_mode=True)`
*   **Arguments**:
    *   `cible` (`str`): Le chemin (relatif ou absolu) vers un fichier ou un répertoire.
    *   `strict_mode` (`bool`): Non utilisé dans l'implémentation actuelle, mais pourrait servir à un filtrage plus strict à l'avenir.
*   **Retours**: `list` de `str`. Une liste de chemins absolus de fichiers éligibles.
*   **Logique interne**:
    Cette fonction utilitaire liste les fichiers à cibler pour la documentation.
    1.  Convertit `cible` en chemin absolu.
    2.  Si `cible` est un fichier, l'ajoute directement à la liste.
    3.  Si `cible` est un répertoire, parcourt récursivement tous les fichiers du répertoire et de ses sous-répertoires.
    4.  Applique des exclusions hardcodées (dossiers comme `.git`, `__pycache__`, `venv`, etc.) pour éviter d'analyser des fichiers non pertinents.
    5.  Filtre les fichiers par leurs extensions en utilisant `SUPPORTED_FILE_EXTENSIONS`.
    6.  Exclut également certains fichiers JSON système (ex: `app_settings.json`, `doc_hashes.json`).

### `task_documenter_fichier_atomique`

*   **Signature**: `def task_documenter_fichier_atomique(file_rel_path, doc_session, response_queue, context_map, batch_id=None)`
*   **Arguments**:
    *   `file_rel_path` (`str`): Le chemin relatif du fichier à documenter.
    *   `doc_session` (`object`): Objet de session IA utilisé pour l'appel.
    *   `response_queue` (`queue.Queue` ou similaire): Queue pour envoyer les messages de progression et de résultat à l'UI.
    *   `context_map` (`str`): Contenu JSON (sous forme de chaîne) de la carte d'architecture, utilisé comme contexte pour l'IA.
    *   `batch_id` (`int`, optionnel): Identifiant unique du lot de documentation auquel cette tâche appartient, pour le suivi de progression.
*   **Retours**: `None`. La fonction communique ses résultats via `response_queue`.
*   **Logique interne**:
    Cette fonction est conçue pour être exécutée dans un thread séparé et gère la documentation d'un unique fichier source.
    1.  Vérifie l'existence du fichier et envoie une erreur à la queue si introuvable.
    2.  Lit le code source du fichier.
    3.  Construit un prompt optimisé et directif pour l'IA, demandant une documentation technique complète au format Markdown avec une structure spécifique (En-tête, Classes/Fonctions, Exemple d'usage).
    4.  Appelle l'IA via `call_ai_robust` en mode "writer" et avec `force_text=True` pour s'assurer d'obtenir du texte pur.
    5.  **Filtrage Strict des Outputs (Anti-Déchets)**:
        *   Nettoie le contenu généré par l'IA en supprimant les balises Markdown parasites (ex: `` ```markdown ``).
        *   Vérifie la taille minimale du contenu généré pour rejeter les réponses trop courtes (moins de 50 caractères).
        *   Recherche des phrases interdites (ex: "opération terminée", "voici la documentation", "as an ai") au début du contenu pour filtrer les réponses conversationnelles ou non pertinentes de l'IA.
    6.  Si le contenu est validé, détermine un nom de fichier sûr pour la documentation (`.md`).
    7.  Crée le répertoire de destination (`Documentation/Reference/`) si nécessaire.
    8.  Écrit le contenu nettoyé dans le fichier Markdown correspondant.
    9.  Envoie des messages de succès à `UnifiedLogger` et des mises à jour à la `response_queue` (pour l'UI et le suivi de progression).
    10. Si un `batch_id` est fourni, décrémente le compteur de tâches restantes pour ce lot via `_decrement_doc_counter`.
    11. Gère les exceptions, journalise les erreurs et envoie des messages d'erreur à la `response_queue`.

### `_decrement_doc_counter`

*   **Signature**: `def _decrement_doc_counter(batch_id, response_queue)`
*   **Arguments**:
    *   `batch_id` (`int`): L'identifiant unique du lot de documentation.
    *   `response_queue` (`queue.Queue` ou similaire): La queue pour envoyer les messages de progression et le message final à l'UI.
*   **Retours**: `None`.
*   **Logique interne**:
    Fonction thread-safe pour décrémenter le compteur de tâches restantes d'un lot de documentation.
    1.  Utilise un verrou (`_doc_progress_lock`) pour assurer l'accès thread-safe aux compteurs globaux `_doc_progress_trackers`.
    2.  Décrémente le compteur `remaining` pour le `batch_id` donné.
    3.  Si `remaining` atteint 0, cela signifie que toutes les tâches du lot sont terminées. Un message final est envoyé à la `response_queue` pour l'interface utilisateur, et le tracker de ce lot est supprimé.

### `execute_generer_documentation`

*   **Signature**: `def execute_generer_documentation(cible, mode, session, action_log_path, result_queue, task_queue, **kwargs)`
*   **Arguments**:
    *   `cible` (`str`): Le chemin (fichier ou répertoire) à documenter.
    *   `mode` (`str`): Le mode de documentation ("atomique" ou "résumé").
    *   `session` (`object`): L'objet de session IA.
    *   `action_log_path` (`str`): Chemin du fichier de journalisation des actions.
    *   `result_queue` (`queue.Queue` ou similaire): Queue pour envoyer les résultats et mises à jour à l'interface utilisateur.
    *   `task_queue` (`queue.Queue` ou similaire): Queue pour envoyer les tâches de documentation atomique à un pool de workers.
    *   `**kwargs` (`dict`): Arguments supplémentaires non utilisés directement ici.
*   **Retours**: `str`. Un message de statut général sur le lancement du processus de documentation.
*   **Logique interne**:
    Cette fonction est le point d'entrée principal pour la génération de documentation, gérant différents modes.

    **Mode "atomique"**:
    1.  Liste les fichiers cibles en utilisant `_lister_fichiers_cibles`.
    2.  Charge la carte d'architecture (`config/architecture_map.json`) comme contexte pour l'IA.
    3.  Charge les patterns d'exclusion de fichiers définis dans les paramètres de l'application (`APP_SETTINGS.code_analysis.ignored_folders`).
    4.  Charge les hashs de fichiers précédemment calculés depuis `doc_hashes.json`.
    5.  Initialise un `batch_id` unique pour le suivi de la progression.
    6.  Itère sur chaque fichier cible:
        *   Convertit le chemin en relatif.
        *   **Filtre d'Exclusion Utilisateur**: Vérifie si le fichier doit être ignoré en fonction des patterns définis dans `ignored_folders`. La vérification est stricte sur les segments de chemin.
        *   Calcule le hash SHA256 actuel du fichier.
        *   Vérifie l'existence physique d'une documentation Markdown correspondante (`Documentation/Reference/`).
        *   **Condition de Saut**: Si le fichier n'a pas été modifié (hash identique) ET que le fichier de documentation existe, le fichier est ignoré.
        *   Si le fichier nécessite une nouvelle documentation (modifié ou doc manquante), une tâche est ajoutée à la `task_queue` pour `task_documenter_fichier_atomique`.
        *   Le hash du fichier est mis à jour dans le dictionnaire `hashes` (marqué comme `dirty`).
    7.  Après avoir parcouru tous les fichiers, si des tâches ont été ajoutées, le tracker de progression pour ce `batch_id` est initialisé avec le nombre total de tâches.
    8.  Si le dictionnaire `hashes` a été modifié (`dirty`), il est sauvegardé dans `doc_hashes.json`.
    9.  Renvoie un message de statut indiquant combien de fichiers sont en cours de traitement ou si aucun fichier n'avait besoin d'être documenté.

    **Mode "résumé"**:
    1.  Construit un prompt simple pour générer un README pour le dossier cible.
    2.  Appelle l'IA via `call_ai_robust` en mode "writer" pour obtenir le résumé.
    3.  Renvoie le contenu généré par l'IA.

## 3. Exemple d'usage

Le module `Documentation.py` est principalement conçu pour être appelé via la fonction `execute_generer_documentation` dans un cadre plus large, tel qu'un système d'interface utilisateur ou un pipeline CI/CD. Les tâches atomiques sont ensuite gérées de manière asynchrone par un pool de threads.

```python
import queue
import threading
from config.settings import APP_SETTINGS
from features.ai_helper import create_session # Supposons cette fonction pour créer une session IA
from config import get_path, get_logger
from .Documentation import execute_generer_documentation, task_documenter_fichier_atomique # Importer les fonctions nécessaires

log = get_logger("example_documentation_usage")

# 1. Préparation de l'environnement (simulé)
session_ia = create_session(APP_SETTINGS) # Crée une session IA
action_log_path = get_path("action_log.json")
result_queue = queue.Queue() # Pour les messages vers l'UI
task_queue = queue.Queue() # Pour les tâches de documentation atomique

# Un pool de workers pour exécuter les tâches atomiques en arrière-plan
def worker(task_queue, result_queue, doc_session):
    while True:
        task = task_queue.get()
        if task is None: # Signal de fin
            break
        if task['type'] == 'doc_atomic_task':
            log.info(f"Worker démarré : {task['file_rel']}")
            task_documenter_fichier_atomique(
                task['file_rel'],
                doc_session,
                result_queue,
                task['context_map'],
                task['batch_id']
            )
        task_queue.task_done()

num_workers = 2 # Exemple: 2 threads de documentation simultanés
workers = []
for _ in range(num_workers):
    t = threading.Thread(target=worker, args=(task_queue, result_queue, session_ia))
    t.start()
    workers.append(t)

# 2. Exécution de la génération de documentation
# Mode "atomique" pour documenter un répertoire entier
target_directory = "features" # Exemple: documenter le dossier 'features'
log.info(f"Lancement de la documentation atomique pour le dossier : {target_directory}")
status_message = execute_generer_documentation(
    cible=target_directory,
    mode="atomique",
    session=session_ia,
    action_log_path=action_log_path,
    result_queue=result_queue,
    task_queue=task_queue
)
log.info(f"Statut initial: {status_message}")

# Simuler la lecture des messages de la queue pour l'UI
while True:
    try:
        message = result_queue.get(timeout=1) # Attendre 1 seconde pour un message
        log.info(f"Message UI/Progress: {message}")
        if message.get("type") == "ui_update" and "Documentation atomique terminée" in message.get("text", ""):
            break # La documentation est terminée
    except queue.Empty:
        # Vérifier si toutes les tâches sont terminées dans la task_queue si le batch est censé être fini
        # Cela pourrait être géré plus robustement avec un événement ou un signal de fin de batch
        if task_queue.empty() and threading.active_count() <= num_workers + 1: # Plus le thread principal
            break
        pass # Continue d'attendre

log.info("Processus de documentation atomique terminé ou toutes les tâches envoyées.")

# Envoyer le signal de fin aux workers et les joindre
for _ in range(num_workers):
    task_queue.put(None)
for t in workers:
    t.join()

# 3. Exemple de mode "résumé" (génère un README simple)
log.info(f"\nLancement de la documentation en mode 'résumé' pour le dossier : {target_directory}")
readme_content = execute_generer_documentation(
    cible=target_directory,
    mode="resume",
    session=session_ia,
    action_log_path=action_log_path,
    result_queue=None, # Pas de queue de résultat pour ce mode simple
    task_queue=None
)
log.info(f"Contenu README généré (extrait):\n{readme_content[:500]}...")

# Pour une application réelle, la 'result_queue' serait lue en continu par le thread de l'interface utilisateur.
# La 'task_queue' serait gérée par un gestionnaire de pool de threads qui démarre les workers.
# Documentation Technique : GitActions

## 1. En-tête

*   **Titre :** GitActions
*   **Description concise :** Ce module fournit des fonctionnalités liées à l'interaction avec les dépôts Git, notamment le clonage, l'analyse de contenu via l'IA et la simulation de création de Pull Requests.
*   **Dépendances :**
    *   `os`
    *   `logging`
    *   `config` (modules `get_path`, `get_logger`)
    *   `features.Shared` (module `log_action`)
    *   `ai_core.sessions` (module `call_ai_robust`)
    *   `features.Decorators` (module `trace_action`)
    *   `features.github` (module technique optionnel pour les interactions bas niveau avec GitHub)

## 2. Classes & Fonctions

### `execute_analyser_depot_github(url, session, action_log_path, result_queue, **kwargs)`

*   **Description :** Clone un dépôt GitHub à partir d'une URL, analyse son contenu en utilisant l'IA pour générer un rapport synthétique, et sauvegarde ce rapport localement. Le module `features.github` est utilisé pour la récupération des données du dépôt.
*   **Arguments :**
    *   `url` (str) : L'URL HTTPS du dépôt GitHub à analyser. Peut également être passé via `kwargs['url']`.
    *   `session` : L'objet de session à passer à l'appel IA.
    *   `action_log_path` (str) : Chemin vers le fichier journal des actions à mettre à jour.
    *   `result_queue` (Queue) : Une file d'attente pour envoyer des mises à jour d'interface utilisateur et le contenu du rapport.
    *   `**kwargs` : Arguments supplémentaires, peut contenir `url`.
*   **Retour :**
    *   (str) : Un message indiquant le succès (avec le nom du fichier de rapport) ou une chaîne d'erreur descriptive en cas d'échec.
*   **Logique interne :**
    1.  **Vérification des prérequis :** S'assure que le module `github_manager` est importé et que l'URL du dépôt est fournie.
    2.  **Feedback UI (Démarrage) :** Envoie des mises à jour à la `result_queue` pour indiquer le début du clonage et de l'analyse.
    3.  **Récupération du Contenu :** Appelle `github_manager.get_repo_contents_for_analysis` pour cloner le dépôt et en récupérer le contenu sous forme de dictionnaire `{chemin: contenu}`. Gère les erreurs et les cas de dépôt vide.
    4.  **Préparation du Prompt :**
        *   Construit une chaîne `full_content` en concaténant le contenu des fichiers (avec une limite par fichier et une limite globale).
        *   Crée un prompt détaillé pour l'IA, lui demandant d'agir en tant que Lead Developer pour analyser le dépôt, identifier l'objectif probable, la stack technique, la qualité du code et les points d'intérêt.
    5.  **Appel IA :** Utilise `call_ai_robust` en mode "pro" et "disposable" pour générer la réponse de l'IA.
    6.  **Sauvegarde et Retour :**
        *   Détermine un nom de fichier pour le rapport basé sur le nom du dépôt.
        *   Sauvegarde le contenu généré par l'IA dans un fichier Markdown (`.md`) dans le chemin spécifié par `get_path()`.
        *   Envoie le contenu du fichier et un message de succès à la `result_queue`.
        *   Journalise l'action via `log_action`.
        *   Retourne un message de succès ou un message d'erreur en cas de problème de sauvegarde.
    7.  **Gestion des Exceptions :** Capture les exceptions lors de l'appel IA ou de la récupération des données, et retourne un message d'erreur détaillé. Log l'erreur critique.

### `create_pr_simulation(branch, session=None, action_log_path=None, result_queue=None, **kwargs)`

*   **Description :** Fonction placeholder simulant la création d'une Pull Request. Destinée à des évolutions futures.
*   **Arguments :**
    *   `branch` (str) : Le nom de la branche (utilisé potentiellement dans une future implémentation).
    *   `session` (obj, optional) : L'objet de session (par défaut `None`).
    *   `action_log_path` (str, optional) : Chemin vers le fichier journal des actions (par défaut `None`).
    *   `result_queue` (Queue, optional) : File d'attente pour les résultats (par défaut `None`).
    *   `**kwargs` : Arguments supplémentaires (non utilisés actuellement).
*   **Retour :**
    *   (str) : Un message indiquant que la fonctionnalité est en cours de développement ("🚧 Fonctionnalité 'Créer PR' en cours de développement (V25).") ou une erreur si le module GitHub est manquant.
*   **Logique interne :**
    1.  **Vérification du module GitHub :** Vérifie si `github_manager` est disponible. Si non, retourne un message d'erreur.
    2.  **Message placeholder :** Retourne un message indiquant que la fonctionnalité n'est pas encore implémentée.

## 3. Exemple d'usage

```python
# Exemple d'appel pour analyser un dépôt GitHub
from queue import Queue

# Supposons que 'session', 'action_log_path' et 'result_queue' sont initialisés
session = ... # Votre objet de session AI
action_log_path = "path/to/action.log"
result_queue = Queue()

github_url = "https://github.com/utilisateur/depot-exemple.git"

# Lancement de l'analyse
result_message = execute_analyser_depot_github(
    url=github_url,
    session=session,
    action_log_path=action_log_path,
    result_queue=result_queue
)

print(result_message)

# Traitement des mises à jour de l'UI depuis la result_queue
while not result_queue.empty():
    update = result_queue.get()
    if update['type'] == 'ui_update':
        print(f"UI Update ({update['widget']}): {update['text']}")
    elif update['type'] == 'file_content':
        print(f"Contenu du rapport reçu : {update['path']}")
        # Ici, vous pourriez afficher le contenu ou l'ouvrir dans une interface
        # print(update['content'])

# Exemple d'appel pour la fonction placeholder PR
pr_result = create_pr_simulation(branch="main", action_log_path=action_log_path)
print(pr_result)
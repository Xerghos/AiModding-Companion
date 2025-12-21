# Documentation Technique - `worker/core.py`

## 1. En-tête

*   **Titre**: `core.py` - Thread Worker Principal (V24 - Architecture Modulaire & Stabilisée)
*   **Description concise**: Ce module définit la classe `Worker`, un thread Python qui sert de cœur logique à l'application. Il gère l'interaction avec l'utilisateur via une interface de file d'attente, orchestrant les conversations avec les modèles d'IA, la gestion de la mémoire, l'exécution d'outils, les agents spécialisés (Swarm), et les tâches de maintenance et d'audit. Il implémente des mécanismes de *hot-reload* de configuration, de RAG (Retrieval Augmented Generation) hybride, et de gestion robuste des flux et des erreurs.
*   **Dépendances**:
    *   **Standard Python**: `threading`, `queue`, `time`, `traceback`, `os`, `json`, `re`, `concurrent.futures.ThreadPoolExecutor`.
    *   **Internes (Configuration)**:
        *   `config.settings`: Pour les paramètres de l'application.
        *   `config.paths`: Pour la gestion des chemins de fichiers.
        *   `config.logs`: Pour la configuration du logger.
        *   `features.UnifiedLogger`: Système de log unifié.
        *   `features.Documentation.task_documenter_fichier_atomique`: Fonction pour les tâches de documentation atomique.
    *   **Internes (AI Core)**:
        *   `ai_core.factory.SessionFactory`: Pour la création de sessions d'IA.
        *   `ai_core.sessions.call_ai_robust`: Pour les appels robustes aux modèles d'IA.
        *   `features.Decorators.trace_action`: Décorateur pour le traçage d'actions.
    *   **Internes (Features / Optionnels)**:
        *   `features.audio` (aliased as `audio_manager`): Gestionnaire audio (ASR/TTS).
        *   `features.CacheManager.GlobalCacheManager`: Gestionnaire global de cache (optionnel).
        *   `features.context.database`: Base de données RAG (optionnel).
        *   `features.SemanticMemory.GlobalMemoryManager`: Gestionnaire de mémoire sémantique (optionnel).
        *   `agents.agent_personas.META_INSTRUCTIONS`: Instructions système par défaut pour l'IA.
        *   `agents.agent_personas.SWARM_AGENTS`: Définitions des agents du Swarm.
        *   `agents.swarm_manager.create_agent`: Fonction pour créer des agents du Swarm (optionnel).
        *   `features.CodeQuality`: Module d'audit de code (optionnel).
        *   `features.Documentation`: Module de documentation (optionnel).
        *   `features.Refactoring`: Module de refactoring (optionnel).
        *   `features.ProjectManager`: Module de gestion de projet (optionnel).
        *   `features.GitActions`: Module d'actions Git (optionnel).
        *   `features.BackupManager`: Module de gestion de sauvegardes (optionnel).
        *   `features.core_backup`: Module de backup du cœur (optionnel).
        *   `features.ai_helper.analyze_request_and_dispatch`: Dispatcheur de requêtes (optionnel).

## 2. Classes & Fonctions

### Classe `Worker`

```python
class Worker(threading.Thread):
    """
    Worker Thread Principal (V24 - Architecture Modulaire & Stabilisée).
    Gère le Chat, la Mémoire, et les Agents Persistants.
    """
    # ... (méthodes ci-dessous)
```

**Description**:
Cette classe étend `threading.Thread` et implémente la logique principale pour le traitement asynchrone des tâches. Elle agit comme un contrôleur central pour toutes les interactions IA, la gestion des outils, la mémoire, le RAG et les agents spécialisés. Sa conception vise la modularité et la robustesse, en s'appuyant sur des files d'attente pour la communication inter-threads et un `ThreadPoolExecutor` pour les opérations en arrière-plan.

#### Attributs (initialisés dans `__init__`)

*   `task_queue` (queue.Queue): File d'attente pour recevoir les tâches à exécuter.
*   `response_queue` (queue.Queue): File d'attente pour envoyer les résultats et les mises à jour à l'UI.
*   `stop_event` (threading.Event): Événement utilisé pour signaler l'arrêt du thread Worker.
*   `daemon` (bool): Indique si le thread est un daemon (True).
*   `main_session` (ai_core.sessions.BaseSession): La session principale de conversation IA. Initialisée en *lazy loading*.
*   `agent_sessions` (dict): Dictionnaire pour stocker les sessions persistantes d'agents (swarm).
*   `abort_current_stream` (bool): Drapeau pour interrompre un flux de génération d'IA en cours.
*   `bg_task_desc` (str | None): Description de la tâche de fond en cours pour l'affichage UI.
*   `current_task_desc` (str | None): Description de la tâche principale en cours pour l'affichage UI.
*   `reasoning_active` (bool): Indique si le mode de raisonnement avancé est activé.
*   `bg_executor` (concurrent.futures.ThreadPoolExecutor): Exécuteur pour les tâches en arrière-plan (agents, maintenance).
*   `last_arch_update` (float): Horodatage de la dernière mise à jour de l'architecture pour l'automaintenance.
*   `autonomy_mode` (str): Niveau d'autonomie configuré pour le worker/agents.
*   `max_react_depth` (int): Profondeur maximale des étapes de réaction pour les agents.
*   `rag_enabled` (bool): Indique si le RAG est activé.

#### Méthodes

##### `__init__(self, task_queue, response_queue, stop_event)`

*   **Signature**: `__init__(self, task_queue, response_queue, stop_event)`
*   **Arguments**:
    *   `task_queue` (queue.Queue): La file d'attente pour les tâches entrantes.
    *   `response_queue` (queue.Queue): La file d'attente pour les réponses sortantes vers l'UI.
    *   `stop_event` (threading.Event): Un événement qui, lorsqu'il est défini, signale au worker de s'arrêter.
*   **Retourne**: `None`
*   **Logique interne**:
    *   Appelle le constructeur de la classe parente `threading.Thread`.
    *   Initialise les files d'attente et l'événement d'arrêt.
    *   Définit le thread comme un daemon.
    *   Initialise les attributs de session (`main_session`, `agent_sessions`) et de contrôle de flux/tâche.
    *   Configure un `ThreadPoolExecutor` pour les tâches en arrière-plan non bloquantes.
    *   Initialise le timer pour l'automaintenance.
    *   Appelle `_refresh_config()` pour charger les paramètres initiaux.

##### `_refresh_config(self)`

*   **Signature**: `_refresh_config(self)`
*   **Arguments**: `self`
*   **Retourne**: `None`
*   **Logique interne**:
    *   Recharge les paramètres de l'application via `reload_app_settings()` de `config.settings`.
    *   Met à jour les attributs internes du worker (`autonomy_mode`, `max_react_depth`, `rag_enabled`) à partir des nouveaux paramètres.
    *   Log un message d'information sur le rechargement.

##### `get_main_session(self)`

*   **Signature**: `get_main_session(self)`
*   **Arguments**: `self`
*   **Retourne**: `ai_core.sessions.BaseSession`: La session principale d'IA.
*   **Logique interne**:
    *   Implémente un chargement paresseux (`lazy loading`) pour la session principale d'IA.
    *   Si `self.main_session` n'est pas initialisée, elle est créée via `SessionFactory.create_session()` avec le modèle "fast" et `META_INSTRUCTIONS`.
    *   Tente de charger l'historique de la session depuis `GlobalMemoryManager` si disponible, sinon un mécanisme de *fallback* manuel depuis un fichier JSON est envisagé (bien que minimal).
    *   Retourne la session principale d'IA.

##### `_warmup_caches(self)`

*   **Signature**: `_warmup_caches(self)`
*   **Arguments**: `self`
*   **Retourne**: `None`
*   **Logique interne**:
    *   Si `GlobalCacheManager` est disponible, tente de préchauffer les caches pour les modèles d'IA configurés (ex: `gemini-1.5-flash`) en utilisant la clé API appropriée. Permet d'améliorer la latence initiale des appels IA.

##### `_perform_startup_audit(self)`

*   **Signature**: `_perform_startup_audit(self)`
*   **Arguments**: `self`
*   **Retourne**: `None`
*   **Logique interne**:
    *   Si la `SessionFactory` a une méthode `audit_all_providers`, elle l'appelle pour vérifier la configuration des fournisseurs d'IA au démarrage.

##### `_retrieve_rag_context(self, query)`

*   **Signature**: `_retrieve_rag_context(self, query)`
*   **Arguments**:
    *   `query` (str): La requête de l'utilisateur pour laquelle récupérer le contexte RAG.
*   **Retourne**: `dict`: Un dictionnaire contenant les composants de contexte RAG:
    *   `"repo_map"` (str | None): Contexte structurel du dépôt de code.
    *   `"docs"` (str | None): Contexte pertinent extrait de documents via RAG hybride.
    *   `"ltm"` (str | None): Contexte pertinent de la mémoire à long terme (LTM).
*   **Logique interne**:
    *   Récupère le contexte du "Repo Map" (structure du projet) via `features.context.repo_map.get_repo_map_for_context`.
    *   Effectue une recherche hybride (FAISS + FTS5 avec RRF) dans la base de données RAG (`database`).
    *   Filtre et tronque intelligemment les résultats des documents:
        *   Applique un seuil de pertinence RRF (e.g., `RRF_THRESHOLD = 0.01`).
        *   Limite le budget total de caractères (`MAX_TOTAL_CHARS = 3000`).
        *   Déduplique les résultats par source.
        *   Trunque le contenu des documents à des frontières sémantiques naturelles pour préserver la cohérence.
        *   Construit un en-tête enrichi pour chaque document (nom de fichier, lignes, type AST, contexte parent, score).
        *   Implémente un *fallback* pour inclure quelques résultats même si les filtres sont stricts, afin d'éviter un contexte RAG vide.
    *   Récupère le contexte pertinent de la mémoire à long terme (`GlobalMemoryManager.retrieve_relevant_context`).
    *   Retourne les composants RAG structurés.

##### `_handle_agent_task(self, payload)`

*   **Signature**: `_handle_agent_task(self, payload)`
*   **Arguments**:
    *   `payload` (dict): Un dictionnaire contenant `agent_role` (ou `agent_type`), `prompt`, et `task_id`.
*   **Retourne**: `None`
*   **Logique interne**:
    *   Vérifie la disponibilité de `create_agent` (Swarm Manager).
    *   Construit un contexte intelligent pour l'agent en combinant:
        *   Le contexte RAG obtenu via `_retrieve_rag_context()`.
        *   Le contexte STM (Short-Term Memory) constitué des derniers messages de la session principale.
    *   Crée un agent spécialisé via `create_agent()`, en lui passant le contexte intelligent et le mode de raisonnement (`self.reasoning_active`).
    *   Exécute la tâche de l'agent avec le `prompt`.
    *   Envoie la réponse de l'agent à la `response_queue`.
    *   Gère les erreurs d'exécution de l'agent.

##### `_save_and_display(self, text, role="assistant")`

*   **Signature**: `_save_and_display(self, text, role="assistant")`
*   **Arguments**:
    *   `text` (str): Le texte à sauvegarder et afficher.
    *   `role` (str, optionnel): Le rôle de l'émetteur (par défaut "assistant").
*   **Retourne**: `None`
*   **Logique interne**:
    *   Si `GlobalMemoryManager` et `main_session` sont disponibles, sauvegarde l'historique de la session.
    *   Envoie le texte à la `response_queue` pour affichage dans l'UI.

##### `_execute_tool(self, tool_function, args, kwargs)`

*   **Signature**: `_execute_tool(self, tool_function, args, kwargs)`
*   **Arguments**:
    *   `tool_function` (callable): La fonction de l'outil à exécuter.
    *   `args` (list | tuple): Les arguments positionnels à passer à l'outil.
    *   `kwargs` (dict): Les arguments nommés à passer à l'outil.
*   **Retourne**: Le résultat de `tool_function` ou `None` en cas d'erreur.
*   **Logique interne**:
    *   Log le début et la fin de l'exécution de l'outil.
    *   Effectue une validation sommaire des arguments.
    *   Exécute la `tool_function` avec les arguments fournis.
    *   Gère les exceptions, log les erreurs et envoie un message d'erreur à la `response_queue`.

##### `_handle_analyze_file(self, payload)`

*   **Signature**: `_handle_analyze_file(self, payload)`
*   **Arguments**:
    *   `payload` (dict): Contient `file_path` et `prompt`.
*   **Retourne**: `None`
*   **Logique interne**:
    *   Si `CodeQuality` est chargé, exécute `CodeQuality.execute_verifier_code` via `_execute_tool`.
    *   Affiche le résultat ou un message d'erreur si le module n'est pas disponible.

##### `_handle_refactor(self, payload)`

*   **Signature**: `_handle_refactor(self, payload)`
*   **Arguments**:
    *   `payload` (dict): Contient `file_path` et `prompt`.
*   **Retourne**: `None`
*   **Logique interne**:
    *   Si `Refactoring` est chargé, exécute `Refactoring.execute_refactoriser_code` via `_execute_tool` (avec `auto_apply=False` par sécurité).
    *   Affiche le résultat ou un message d'erreur si le module n'est pas disponible.

##### `_handle_gen_doc(self, payload)`

*   **Signature**: `_handle_gen_doc(self, payload)`
*   **Arguments**:
    *   `payload` (dict): Contient `file_path`.
*   **Retourne**: `None`
*   **Logique interne**:
    *   Si `Documentation` est chargé, exécute `Documentation.execute_generer_documentation` via `_execute_tool`.
    *   Affiche le résultat ou un message d'erreur si le module n'est pas disponible.

##### `_handle_chat_stream(self, payload)`

*   **Signature**: `_handle_chat_stream(self, payload)`
*   **Arguments**:
    *   `payload` (dict): Contient `message` (le prompt de l'utilisateur).
*   **Retourne**: `None`
*   **Logique interne**:
    *   Initialise l'état du flux (`abort_current_stream`, `bg_task_desc`, signal `ui_stream_start`).
    *   Récupère le contexte RAG via `_retrieve_rag_context()`.
    *   Appelle `call_ai_robust()` en mode streaming, en passant le contexte RAG séparément.
    *   Parcourt les `chunk` de la réponse, les envoie à la `response_queue` et construit la réponse complète.
    *   Détecte et analyse les commandes d'outils (`!native_tool` ou `[TOOL_CALL:...]`) dans la réponse complète de l'IA.
    *   Si une commande d'outil est détectée, la place dans la `task_queue` pour exécution ultérieure.
    *   Gère l'interruption du flux et les erreurs.

##### `run(self)`

*   **Signature**: `run(self)`
*   **Arguments**: `self`
*   **Retourne**: `None`
*   **Logique interne**:
    *   C'est la méthode principale exécutée lorsque le thread Worker démarre.
    *   Initialise la base de données RAG, préchauffe les caches, et effectue un audit de démarrage.
    *   Contient une boucle `while` infinie qui s'exécute tant que `stop_event` n'est pas défini.
    *   **Automaintenance**: Déclenche périodiquement des tâches de fond comme la mise à jour de l'architecture (`Documentation.execute_update_architecture`).
    *   **Gestion des tâches**: Récupère les tâches de `task_queue` avec un court timeout pour permettre une interruption rapide.
    *   **Mise à jour UI**: Met à jour `current_task_desc` et `bg_task_desc` pour informer l'UI de l'activité.
    *   **Dispatching des messages**: Traite les tâches en fonction de leur `msg_type` et `action`:
        *   `stop_generation`: Interrompt le flux de génération d'IA.
        *   `set_reasoning_mode`: Active/désactive le mode de raisonnement et bascule dynamiquement le modèle d'IA de la session principale.
        *   `get_queue_status`: Fournit l'état des tâches en cours et en attente pour l'UI.
        *   `reload_system`: Recharge la configuration du worker et du gestionnaire de mémoire.
        *   `reset_memory`: Réinitialise l'historique de la session et supprime le fichier d'historique.
        *   `backup_now`, `get_backup_list`, `restore_backup`: Gère les opérations de sauvegarde.
        *   `reindex_db`, `delete_db`: Gère la base de données RAG.
        *   `start_asr`, `start_tts`: Gère les fonctionnalités audio.
        *   `analyze_file`, `refactor_file`, `gen_doc`: Appels directs aux modules de features.
        *   `agent_task`: Délègue la tâche à un agent spécialisé.
        *   `user_prompt`, `secondary_user_prompt`: Déclenche la discussion IA ou l'exécution de commande si le prompt commence par `!`.
        *   `action == 'chat'`: Appelle `_handle_chat_stream` en arrière-plan.
        *   `action == 'command'`:
            *   Contient une **correction majeure**: Intercepte la commande `lire_fichier` pour `config/architecture_map.json` et la remplace par une réponse d'optimisation (cache hit) pour éviter les relectures inutiles et les boucles.
            *   Dispatche la commande via `analyze_request_and_dispatch`.
            *   Implémente une **boucle de feedback structurée** pour injecter le résultat de l'outil dans la session IA, puis force l'IA à confirmer la fin de l'opération, en nettoyant les données pour éviter les hallucinations.
        *   `doc_atomic_task`:
            *   Crée une session IA dédiée ('writer') avec les **outils désactivés (`enable_tools=False`)** pour éviter les hallucinations et les boucles infinies de génération de commandes lors de la documentation atomique.
            *   Lance `task_documenter_fichier_atomique` en arrière-plan avec l'ID du batch.
    *   Gère les exceptions globales de la boucle `run`, log les erreurs et les renvoie à la `response_queue`.

## 3. Exemple d'usage

Pour utiliser le `Worker`, vous devez d'abord créer les files d'attente de tâches et de réponses, ainsi qu'un événement d'arrêt. Ensuite, instanciez le `Worker` et démarrez-le. Des tâches peuvent alors être placées dans la `task_queue`.

```python
import queue
import threading
import time
from worker.core import Worker # Assurez-vous que le chemin est correct

def main():
    # 1. Créer les files d'attente et l'événement d'arrêt
    task_queue = queue.Queue()
    response_queue = queue.Queue()
    stop_event = threading.Event()

    # 2. Instancier le Worker
    worker_thread = Worker(task_queue, response_queue, stop_event)

    # 3. Démarrer le Worker
    worker_thread.start()
    print("Worker démarré.")

    # 4. Envoyer des tâches au Worker
    # Exemple 1: Un message utilisateur
    print("\nEnvoi d'une tâche 'user_prompt'...")
    task_queue.put({
        'type': 'user_prompt',
        'prompt': "Quel est le design pattern le plus approprié pour gérer des états complexes dans une application Python ?"
    })

    # Exemple 2: Une commande directe
    print("Envoi d'une tâche 'command' pour recharger le système...")
    task_queue.put({
        'action': 'command',
        'payload': {'command': '!reload_system'}
    })

    # Exemple 3: Demander un audit de fichier
    print("Envoi d'une tâche 'analyze_file'...")
    task_queue.put({
        'type': 'analyze_file',
        'payload': {'file_path': 'my_project/my_module.py', 'prompt': 'Analyse ce fichier pour des problèmes de qualité de code.'}
    })

    # 5. Récupérer les réponses du Worker (simulé)
    print("\nRécupération des réponses du Worker (simulé)...")
    response_count = 0
    while response_count < 5: # Récupérer quelques réponses
        try:
            response = response_queue.get(timeout=10) # Attendre jusqu'à 10 secondes pour une réponse
            print(f"Réponse reçue: {response['type']} - {response.get('text', '')[:100]}...")
            response_count += 1
            if response['type'] == 'ui_stream_end' and 'action' in task_queue.queue[0] and task_queue.queue[0]['action'] == 'chat':
                # Si le stream est fini et la prochaine tâche est le chat, on a potentiellement la réponse complète
                pass # Ne pas incrémenter response_count pour ne pas manquer d'autres types de réponses

        except queue.Empty:
            print("Pas de réponse dans la file...")
            # Si le worker a fini ses tâches, on pourrait vouloir arrêter ici
            if task_queue.empty() and response_queue.empty() and response_count > 0:
                break
        except Exception as e:
            print(f"Erreur lors de la récupération de la réponse: {e}")
            break

    # 6. Envoyer le signal d'arrêt et attendre la fin du Worker
    print("\nEnvoi du signal d'arrêt au Worker...")
    stop_event.set()
    worker_thread.join(timeout=10) # Attendre que le thread se termine, avec un timeout
    if worker_thread.is_alive():
        print("Le Worker n'a pas pu s'arrêter correctement.")
    else:
        print("Worker arrêté.")

if __name__ == "__main__":
    main()
```
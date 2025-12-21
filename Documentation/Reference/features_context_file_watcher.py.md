# Documentation Technique: `features\context\file_watcher.py`

## En-tête

*   **Titre**: Module de surveillance de fichiers réactif
*   **Description concise**: Ce module fournit des outils pour surveiller les systèmes de fichiers en temps réel à l'aide de la bibliothèque `watchdog`. Il détecte les modifications, créations et suppressions de fichiers avec des extensions spécifiques et place ces événements dans une file d'attente pour un traitement asynchrone, ou les envoie à une fonction de rappel définie. Il inclut des mécanismes de dédoublonnage pour gérer les rafales d'événements.
*   **Dépendances**:
    *   **Internes**: `os`, `logging`, `threading`, `queue`, `time`, `typing` (Callable, Optional, List, Dict).
    *   **Projet**: `config.get_logger` (pour la configuration du logger), `features.Decorators.trace_action` (pour le traçage des actions).
    *   **Externes (Optionnel)**: `watchdog` (`watchdog.observers.Observer`, `watchdog.events.FileSystemEventHandler`, `watchdog.events.FileSystemEvent`). Ce module gère l'absence de `watchdog` en définissant `WATCHDOG_AVAILABLE` à `False` et en levant une `ImportError` lors de l'instanciation de `FileWatcher` si `watchdog` n'est pas installé.

## Classes & Fonctions

### Variable `log`

*   **Description**: Instance de logger configurée pour le module `features.context.file_watcher`, utilisée pour l'enregistrement des informations de débogage, d'information, d'avertissement et d'erreur.
*   **Type**: `logging.Logger`

### Variable `WATCHDOG_AVAILABLE`

*   **Description**: Indicateur booléen global qui est `True` si la bibliothèque `watchdog` a été importée avec succès, et `False` sinon. Permet une vérification conditionnelle de la disponibilité de la fonctionnalité.
*   **Type**: `bool`

### Classe `CodeFileHandler(FileSystemEventHandler)`

*   **Description**: Un gestionnaire d'événements personnalisé qui hérite de `watchdog.events.FileSystemEventHandler`. Il est responsable de filtrer les événements du système de fichiers (modification, création, suppression) en fonction des extensions de fichiers spécifiées et d'appliquer une logique de dédoublonnage pour éviter le traitement d'événements multiples très rapprochés pour le même fichier. Les événements traités sont placés dans une file d'attente.

*   #### `__init__(self, dirty_queue: queue.Queue, file_extensions: tuple = ('.py', '.js', '.ts', '.java', '.cpp', '.h'))`
    *   **Description**: Initialise une nouvelle instance du `CodeFileHandler`.
    *   **Arguments**:
        *   `dirty_queue` (`queue.Queue`): La file d'attente thread-safe où les événements de fichiers traités seront placés. Chaque élément de la file sera un tuple `(action: str, file_path: str)`.
        *   `file_extensions` (`tuple`): Un tuple de chaînes de caractères représentant les extensions de fichiers (ex: `('.py', '.txt')`) que le gestionnaire doit surveiller. Seuls les fichiers dont l'extension correspond seront pris en compte pour les modifications et créations.
    *   **Logique interne**:
        *   Appelle le constructeur de la classe parente `FileSystemEventHandler`.
        *   Stocke la file d'attente et les extensions de fichiers.
        *   Initialise `self.last_events` comme un dictionnaire vide (`Dict[str, float]`) pour enregistrer le dernier timestamp de traitement pour chaque fichier, utilisé pour le dédoublonnage.
        *   Définit `self.debounce_seconds` à `0.5` secondes, la période pendant laquelle les événements successifs pour un même fichier seront ignorés.

*   #### `_should_process(self, file_path: str) -> bool`
    *   **Description**: Méthode interne qui détermine si un événement pour un chemin de fichier donné doit être traité, en fonction de son extension et du délai de dédoublonnage.
    *   **Arguments**:
        *   `file_path` (`str`): Le chemin absolu du fichier à évaluer.
    *   **Retours**:
        *   `bool`: `True` si le fichier doit être traité, `False` sinon.
    *   **Logique interne**:
        *   Vérifie si l'extension du `file_path` (en minuscule) se termine par l'une des `self.file_extensions`.
        *   Applique une logique de dédoublonnage: calcule le temps écoulé depuis le dernier événement traité pour ce `file_path`. Si ce temps est inférieur à `self.debounce_seconds`, l'événement est ignoré.
        *   Met à jour le timestamp de `file_path` dans `self.last_events` si l'événement est considéré comme valide.

*   #### `on_modified(self, event: FileSystemEvent)`
    *   **Description**: Méthode de rappel appelée par `watchdog` lorsqu'un fichier est modifié.
    *   **Arguments**:
        *   `event` (`FileSystemEvent`): L'objet événement `watchdog` contenant les détails de la modification.
    *   **Logique interne**:
        *   Ignore les événements si `event.is_directory` est `True`.
        *   Normalise `event.src_path` en chemin absolu.
        *   Si `_should_process` retourne `True`, un message de débogage est enregistré et le tuple `('modified', file_path)` est ajouté à `self.dirty_queue`.

*   #### `on_created(self, event: FileSystemEvent)`
    *   **Description**: Méthode de rappel appelée par `watchdog` lorsqu'un fichier est créé.
    *   **Arguments**:
        *   `event` (`FileSystemEvent`): L'objet événement `watchdog` contenant les détails de la création.
    *   **Logique interne**:
        *   Ignore les événements si `event.is_directory` est `True`.
        *   Normalise `event.src_path` en chemin absolu.
        *   Si `_should_process` retourne `True`, un message de débogage est enregistré et le tuple `('created', file_path)` est ajouté à `self.dirty_queue`.

*   #### `on_deleted(self, event: FileSystemEvent)`
    *   **Description**: Méthode de rappel appelée par `watchdog` lorsqu'un fichier est supprimé.
    *   **Arguments**:
        *   `event` (`FileSystemEvent`): L'objet événement `watchdog` contenant les détails de la suppression.
    *   **Logique interne**:
        *   Ignore les événements si `event.is_directory` est `True`.
        *   Normalise `event.src_path` en chemin absolu.
        *   Un message de débogage est enregistré et le tuple `('deleted', file_path)` est ajouté à `self.dirty_queue`. La méthode `_should_process` n'est pas utilisée pour les suppressions, car l'extension et le dédoublonnage sont généralement moins critiques pour ce type d'événement.

### Classe `FileWatcher`

*   **Description**: Classe principale pour configurer, démarrer et arrêter la surveillance de fichiers. Elle encapsule la logique de `watchdog`, le `CodeFileHandler` et un thread séparé pour le traitement asynchrone des événements de la file d'attente.

*   #### `__init__(self, root_path: str, callback: Optional[Callable] = None, file_extensions: tuple = ('.py', '.js', '.ts', '.java', '.cpp', '.h'))`
    *   **Description**: Initialise une nouvelle instance du `FileWatcher`.
    *   **Arguments**:
        *   `root_path` (`str`): Le chemin racine du répertoire à surveiller. Sera converti en chemin absolu.
        *   `callback` (`Optional[Callable]`): Une fonction de rappel optionnelle qui sera invoquée pour chaque événement de fichier traité par le thread interne. La signature de la fonction doit être `callback(action: str, file_path: str)`.
        *   `file_extensions` (`tuple`): Un tuple d'extensions de fichiers à passer au `CodeFileHandler` pour filtrer les événements.
    *   **Logique interne**:
        *   Vérifie la disponibilité de `watchdog` via `WATCHDOG_AVAILABLE` et lève une `ImportError` si la bibliothèque n'est pas installée.
        *   Convertit `root_path` en chemin absolu et stocke les arguments fournis.
        *   Initialise `self.dirty_queue` (une `queue.Queue`).
        *   Initialise `self.observer`, `self.handler`, `self.processing_thread` à `None` et `self.running` à `False`.

*   #### `@trace_action(source="file_watcher")`
    #### `start(self)`
    *   **Description**: Démarre la surveillance des fichiers. Crée et lance l'observateur `watchdog` et le thread de traitement interne.
    *   **Logique interne**:
        *   Vérifie si le watcher est déjà en cours d'exécution et émet un avertissement.
        *   Vérifie l'existence de `self.root_path` et lève une `ValueError` si le chemin est introuvable.
        *   Crée une instance de `CodeFileHandler` en lui passant la `dirty_queue` et les `file_extensions`.
        *   Crée un `watchdog.observers.Observer` et programme le `handler` pour surveiller `self.root_path` de manière récursive.
        *   Démarre l'observateur `watchdog`.
        *   Définit `self.running` à `True`.
        *   Crée et démarre un `threading.Thread` (`daemon=True`) dont la cible est `self._process_queue`, responsable du traitement des événements en arrière-plan.
        *   Enregistre un message d'information confirmant le démarrage.

*   #### `stop(self)`
    *   **Description**: Arrête la surveillance des fichiers. Arrête l'observateur `watchdog` et attend la terminaison du thread de traitement interne.
    *   **Logique interne**:
        *   Définit `self.running` à `False`, signalant au thread `_process_queue` de s'arrêter.
        *   Si `self.observer` existe, l'arrête (`observer.stop()`) et attend sa terminaison (`observer.join(timeout=5)`).
        *   Si `self.processing_thread` existe, attend sa terminaison (`processing_thread.join(timeout=5)`).
        *   Enregistre un message d'information confirmant l'arrêt.

*   #### `_process_queue(self)`
    *   **Description**: Méthode interne exécutée dans un thread séparé. Elle récupère les événements de fichiers de la `dirty_queue` et invoque la fonction de rappel (`self.callback`) si elle est définie.
    *   **Logique interne**:
        *   Boucle tant que `self.running` est `True`.
        *   Tente de récupérer un événement de la `dirty_queue` avec un `timeout` de 1.0 seconde. Cela permet au thread de vérifier régulièrement `self.running` et de s'arrêter proprement.
        *   Si un événement `(action, file_path)` est récupéré, et si `self.callback` est défini, la fonction de rappel est appelée avec l'action et le chemin du fichier. Les exceptions lors de l'exécution du callback sont journalisées.
        *   `self.dirty_queue.task_done()` est appelée pour marquer la tâche comme terminée dans la file.
        *   Gère les exceptions génériques pouvant survenir pendant le traitement de la file.

*   #### `get_dirty_files(self, timeout: float = 0.1) -> List[tuple]`
    *   **Description**: Récupère tous les événements de fichiers actuellement présents dans la file d'attente du watcher. Cette méthode est utile si aucun `callback` n'a été fourni lors de l'initialisation du `FileWatcher`, ou si le traitement des événements doit être effectué de manière synchrone à un autre endroit.
    *   **Arguments**:
        *   `timeout` (`float`): Le temps maximal à attendre pour le premier élément si la file est vide. Si la file est vide après ce délai, la méthode retourne une liste vide. Par défaut à 0.1 secondes.
    *   **Retours**:
        *   `List[tuple]`: Une liste de tuples, où chaque tuple est de la forme `(action: str, file_path: str)`.
    *   **Logique interne**:
        *   Boucle pour extraire tous les éléments disponibles de la `dirty_queue` jusqu'à ce que la file soit vide ou que le `timeout` soit atteint pour le prochain élément.
        *   Chaque événement est ajouté à la liste `dirty_files` qui est retournée.

*   #### `is_running(self) -> bool`
    *   **Description**: Vérifie si le `FileWatcher` est actuellement en cours d'exécution et si son observateur `watchdog` est actif.
    *   **Retours**:
        *   `bool`: `True` si le watcher est actif et fonctionne, `False` sinon.
    *   **Logique interne**:
        *   Retourne `True` si `self.running` est `True`, si `self.observer` n'est pas `None`, et si `self.observer.is_alive()` retourne `True`.

### Fonction `get_global_watcher(root_path: str, callback: Optional[Callable] = None) -> FileWatcher`

*   **Description**: Fournit un mécanisme pour récupérer ou créer une instance singleton d'un `FileWatcher`. Si aucune instance globale n'existe ou si l'instance existante n'est pas en cours d'exécution, une nouvelle instance est créée avec les paramètres fournis (`root_path`, `callback`) et démarrée.
*   **Arguments**:
    *   `root_path` (`str`): Le chemin racine à surveiller. Utilisé uniquement si une nouvelle instance de `FileWatcher` doit être créée.
    *   `callback` (`Optional[Callable]`): La fonction de rappel à assigner. Utilisée uniquement si une nouvelle instance est créée.
*   **Retours**:
    *   `FileWatcher`: L'instance globale (existante ou nouvellement créée) du `FileWatcher`.
*   **Logique interne**:
    *   Utilise la variable globale `_global_watcher`.
    *   Si `_global_watcher` est `None` ou si `_global_watcher.is_running()` retourne `False`, une nouvelle instance de `FileWatcher` est créée avec `root_path` et `callback`, puis démarrée.
    *   L'instance `_global_watcher` est ensuite retournée.

## Exemple d'usage

```python
import time
import os
import tempfile
import shutil
from features.context.file_watcher import FileWatcher, get_global_watcher, WATCHDOG_AVAILABLE

if WATCHDOG_AVAILABLE:
    print("--- Démarrage de l'exemple FileWatcher direct ---")
    
    # Crée un répertoire temporaire pour la surveillance
    temp_dir = tempfile.mkdtemp()
    print(f"Surveillance du répertoire temporaire: {temp_dir}")

    # Fonction de callback pour les événements
    def my_callback(action: str, file_path: str):
        print(f"  [CALLBACK] Action '{action}' sur le fichier: {os.path.basename(file_path)}")

    # Initialisation du FileWatcher pour surveiller les fichiers .txt et .py
    watcher = FileWatcher(root_path=temp_dir, callback=my_callback, file_extensions=('.txt', '.py'))
    watcher.start()

    try:
        # Création d'un fichier .txt
        file_path_create_txt = os.path.join(temp_dir, "test_create.txt")
        with open(file_path_create_txt, 'w') as f:
            f.write("Premier contenu textuel.\n")
        print(f"1. Fichier créé: {os.path.basename(file_path_create_txt)}")
        time.sleep(1) # Laisser le temps à watchdog de détecter

        # Création et modification d'un fichier .py
        file_path_modify_py = os.path.join(temp_dir, "my_script.py")
        with open(file_path_modify_py, 'w') as f:
            f.write("print('Hello from Python!')\n")
        print(f"2. Fichier créé pour modification: {os.path.basename(file_path_modify_py)}")
        time.sleep(1)
        with open(file_path_modify_py, 'a') as f:
            f.write("print('Content added!')\n")
        print(f"3. Fichier modifié: {os.path.basename(file_path_modify_py)}")
        time.sleep(1)

        # Création d'un fichier non surveillé (extension .log)
        file_path_ignored = os.path.join(temp_dir, "ignore_me.log")
        with open(file_path_ignored, 'w') as f:
            f.write("Contenu ignoré.\n")
        print(f"4. Fichier créé (ignoré par l'extension .log): {os.path.basename(file_path_ignored)}")
        time.sleep(1)

        # Suppression d'un fichier
        os.remove(file_path_create_txt)
        print(f"5. Fichier supprimé: {os.path.basename(file_path_create_txt)}")
        time.sleep(1)

        # Récupération des fichiers sales directement si le callback n'avait pas été défini
        # (simulons en ayant un callback pour montrer la flexibilité)
        print("6. Récupération des événements restants via get_dirty_files (si existants):")
        dirty_files = watcher.get_dirty_files(timeout=0.5)
        if dirty_files:
            for action, path in dirty_files:
                print(f"  [QUEUE] Action '{action}' sur le fichier: {os.path.basename(path)}")
        else:
            print("  Aucun événement restant dans la file d'attente.")
        
    except Exception as e:
        print(f"Une erreur est survenue pendant l'exécution de l'exemple FileWatcher direct: {e}")
    finally:
        watcher.stop()
        print("7. FileWatcher arrêté.")
        shutil.rmtree(temp_dir)
        print(f"8. Répertoire temporaire supprimé: {temp_dir}")
    
    print("\n--- Fin de l'exemple FileWatcher direct ---\n")

    # --- Exemple avec get_global_watcher ---
    print("--- Démarrage de l'exemple get_global_watcher ---")
    
    temp_dir_global = tempfile.mkdtemp()
    print(f"Surveillance globale du répertoire temporaire: {temp_dir_global}")

    def global_callback(action: str, file_path: str):
        print(f"  [GLOBAL CALLBACK] Action '{action}' sur le fichier: {os.path.basename(file_path)}")

    # Obtient l'instance globale du watcher (la crée et la démarre si nécessaire)
    global_watcher_instance = get_global_watcher(temp_dir_global, global_callback)
    print(f"1. Watcher global est en cours d'exécution: {global_watcher_instance.is_running()}")
    
    try:
        # Création d'un fichier via le watcher global
        file_path_global = os.path.join(temp_dir_global, "global_doc.txt")
        with open(file_path_global, 'w') as f:
            f.write("Contenu pour le watcher global.\n")
        print(f"2. Fichier global créé: {os.path.basename(file_path_global)}")
        time.sleep(1)

        # Tenter d'obtenir une nouvelle instance du watcher global avec un chemin/callback différent
        # Il retournera la même instance déjà démarrée, ignorant les nouveaux paramètres (sauf si l'instance précédente n'était pas active)
        another_ref = get_global_watcher(temp_dir_global, lambda a, p: print("Ce callback ne sera pas appelé")) 
        print(f"3. Une autre référence au watcher global est la même instance: {another_ref is global_watcher_instance}")
        print(f"4. La nouvelle référence est en cours d'exécution: {another_ref.is_running()}")
        
        # Modification et suppression
        with open(file_path_global, 'a') as f:
            f.write("\nContenu additionnel global.\n")
        print(f"5. Fichier global modifié: {os.path.basename(file_path_global)}")
        time.sleep(1)
        os.remove(file_path_global)
        print(f"6. Fichier global supprimé: {os.path.basename(file_path_global)}")
        time.sleep(1)

    except Exception as e:
        print(f"Une erreur est survenue pendant l'exécution de l'exemple global: {e}")
    finally:
        # Arrêter le watcher global via sa référence
        global_watcher_instance.stop()
        print("7. Watcher global arrêté.")
        shutil.rmtree(temp_dir_global)
        print(f"8. Répertoire temporaire global supprimé: {temp_dir_global}")

    print("\n--- Fin de l'exemple get_global_watcher ---")

else:
    print("La bibliothèque 'watchdog' n'est pas installée. L'exemple ne peut pas s'exécuter.")
    print("Veuillez l'installer avec: `pip install watchdog`")
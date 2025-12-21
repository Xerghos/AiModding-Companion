# Documentation Technique : `ui\windows\tools.py`

## Description concise

Ce module contient les définitions des différentes fenêtres d'outils (`customtkinter`) utilisées dans l'application. Ces fenêtres fournissent des interfaces pour gérer des tâches en arrière-plan, comme le suivi d'une file d'attente, la gestion d'une base de données RAG (Retrieval-Augmented Generation) et la gestion des sauvegardes.

## Dépendances

*   `customtkinter` : Pour la création de widgets d'interface graphique stylisés.
*   `tkinter.messagebox` : Pour afficher des boîtes de dialogue d'information et de confirmation.
*   `tkinter.ttk` : Pour les widgets d'arbre (`Treeview`) qui nécessitent une gestion de style avancée.
*   `ui.widgets.COLORS` : Un dictionnaire contenant les codes couleurs utilisés dans l'application.
*   `ui.windows.base.BaseWindow` : La classe de base pour toutes les fenêtres de l'application, fournissant une structure et des fonctionnalités communes.
*   `features.Decorators.trace_action` : Un décorateur pour tracer les actions utilisateur, probablement pour le logging ou l'analyse.

---

## Classes & Fonctions

### 1. Classe `WaitingListWindow`

Affiche la liste des tâches en attente dans le Worker.

#### `__init__(self, master, task_queue)`

Initialise la fenêtre `WaitingListWindow`.

*   **Arguments**:
    *   `master` : Le widget parent.
    *   `task_queue` : Une file d'attente (`queue.Queue`) pour communiquer avec le Worker.

*   **Logique interne**:
    *   Appelle le constructeur de la classe parente (`BaseWindow`) avec le titre et les dimensions de la fenêtre.
    *   Stocke la `task_queue`.
    *   Configure le style `ttk.Treeview` pour qu'il corresponde aux couleurs de l'application.
    *   Crée un widget `ttk.Treeview` pour afficher les colonnes "ID", "Type" (Action) et "Status" (État).
    *   Configure les en-têtes du `Treeview`.
    *   Place le `Treeview` de manière à ce qu'il remplisse toute la fenêtre.
    *   Ajoute un bouton "Rafraîchir" qui appelle la méthode `_refresh`.
    *   Appelle `_refresh` une première fois pour charger le contenu initial.

#### `_refresh(self)`

Demande l'état actuel de la file d'attente au Worker et planifie un rafraîchissement périodique.

*   **Arguments**: Aucun.
*   **Retour**: Aucun.
*   **Logique interne**:
    *   Utilise le décorateur `@trace_action` pour tracer cette action.
    *   Envoie un message `{'type': 'get_queue_status'}` à la `task_queue` pour demander l'état de la file d'attente.
    *   Planifie l'appel à `self._refresh` après 2000 millisecondes (2 secondes) pour actualiser la liste périodiquement.

#### `update_list(self, tasks)`

Met à jour le contenu du `Treeview` avec la liste des tâches reçue.

*   **Arguments**:
    *   `tasks` : Une liste ou un dictionnaire contenant les informations des tâches. Le format attendu est un dictionnaire avec les clés `"current"` et `"waiting"`, ou une liste d'anciens formats.

*   **Retour**: Aucun.
*   **Logique interne**:
    *   Supprime tous les éléments existants du `Treeview`.
    *   Traite les tâches si le format est un dictionnaire :
        *   Extrait la tâche "actuelle" et la liste des tâches "en attente".
        *   Insère une ligne pour la tâche en cours (ID="NOW", Statut="Running").
        *   Insère des lignes pour chaque tâche en attente (ID=index+1, Statut="Pending").
    *   Gère un format de réponse plus ancien (liste) comme fallback.
    *   Gère les erreurs potentielles lors de la mise à jour de la liste.

### 2. Classe `DbManagerWindow`

Fenêtre pour la gestion du gestionnaire RAG (mémoire), permettant de reconstruire l'index, d'effacer le chat et de supprimer la base de données locale.

#### `__init__(self, master, task_queue, on_clear_chat=None)`

Initialise la fenêtre `DbManagerWindow`.

*   **Arguments**:
    *   `master` : Le widget parent.
    *   `task_queue` : Une file d'attente (`queue.Queue`) pour communiquer avec le Worker.
    *   `on_clear_chat` : Une fonction optionnelle à appeler pour effacer l'historique du chat.

*   **Logique interne**:
    *   Appelle le constructeur de `BaseWindow` avec le titre et les dimensions.
    *   Stocke `task_queue` et `on_clear_chat`.
    *   Appelle la méthode `_build` pour construire l'interface utilisateur.

#### `_build(self)`

Construit l'interface utilisateur de la fenêtre `DbManagerWindow`.

*   **Arguments**: Aucun.
*   **Retour**: Aucun.
*   **Logique interne**:
    *   Utilise le décorateur `@trace_action` pour tracer cette action.
    *   Crée un `CTkFrame` principal transparent.
    *   Ajoute des boutons pour :
        *   "Reconstruire l'Index (RAG)" : Appelle `_reindex_direct`.
        *   "Effacer Chat" : Appelle la fonction `on_clear_chat` si elle est fournie.
        *   "Supprimer Base Locale" : Appelle `_delete_db_direct`.
    *   Ajoute un `CTkLabel` pour afficher le statut.
    *   Gère les erreurs lors de la construction de l'UI.

#### `_reindex_direct(self)`

Lance directement la reconstruction de la base de données RAG via la `task_queue`.

*   **Arguments**: Aucun.
*   **Retour**: Aucun.
*   **Logique interne**:
    *   Envoie un message `{'type': 'reindex_db'}` à la `task_queue`.
    *   Ferme la fenêtre actuelle (`self.destroy()`).

#### `_delete_db_direct(self)`

Demande confirmation et lance la suppression de la base de données locale via la `task_queue`.

*   **Arguments**: Aucun.
*   **Retour**: Aucun.
*   **Logique interne**:
    *   Affiche une boîte de dialogue de confirmation (`messagebox.askyesno`).
    *   Si l'utilisateur confirme :
        *   Envoie un message `{'type': 'delete_db'}` à la `task_queue`.
        *   Ferme la fenêtre actuelle (`self.destroy()`).

### 3. Classe `BackupManagerWindow`

Fenêtre pour gérer les sauvegardes de l'application, permettant de créer, consulter et restaurer des sauvegardes.

#### `__init__(self, master, task_queue)`

Initialise la fenêtre `BackupManagerWindow`.

*   **Arguments**:
    *   `master` : Le widget parent.
    *   `task_queue` : Une file d'attente (`queue.Queue`) pour communiquer avec le Worker.

*   **Logique interne**:
    *   Appelle le constructeur de `BaseWindow` avec le titre et les dimensions.
    *   Stocke `task_queue`.
    *   Si le master a un attribut `windows`, enregistre cette fenêtre dedans.
    *   Appelle `_build_ui` pour créer l'interface.
    *   Appelle `_refresh` pour charger la liste des sauvegardes initiale.

#### `_build_ui(self)`

Construit l'interface utilisateur de la fenêtre `BackupManagerWindow`.

*   **Arguments**: Aucun.
*   **Retour**: Aucun.
*   **Logique interne**:
    *   Utilise le décorateur `@trace_action` pour tracer cette action.
    *   Crée une barre d'outils (`toolbar`) avec un titre et des boutons.
    *   Ajoute un bouton "📸 Créer Backup" qui appelle `_create_backup`.
    *   Ajoute un bouton "🔄 Actualiser" qui appelle `_refresh`.
    *   Crée un `CTkFrame` (`tree_frame`) pour contenir le `Treeview`.
    *   Configure le style `ttk.Treeview` et crée le widget `Treeview` avec les colonnes : "Date", "Fichier Original", "Taille", "Nom de Backup".
    *   Configure la largeur des colonnes.
    *   Place le `Treeview` et une barre de défilement verticale.
    *   Crée une section d'actions en bas avec un label et un bouton "🔙 Restaurer la version sélectionnée" qui appelle `_restore_selected`.
    *   Gère les erreurs lors de la construction de l'UI.

#### `_create_backup(self)`

Lance la création d'une sauvegarde via la `task_queue`.

*   **Arguments**: Aucun.
*   **Retour**: Aucun.
*   **Logique interne**:
    *   Utilise le décorateur `@trace_action` pour tracer cette action.
    *   Envoie un message `{'type': 'backup_now'}` à la `task_queue`.
    *   Affiche une boîte d'information pour indiquer que la sauvegarde a été lancée.

#### `_refresh(self)`

Demande la liste des sauvegardes au Worker.

*   **Arguments**: Aucun.
*   **Retour**: Aucun.
*   **Logique interne**:
    *   Utilise le décorateur `@trace_action` pour tracer cette action.
    *   Envoie un message `{'type': 'get_backup_list'}` à la `task_queue`.

#### `update_list(self, backups_data)`

Met à jour le `Treeview` avec les données des sauvegardes reçues.

*   **Arguments**:
    *   `backups_data` : Une liste de dictionnaires, où chaque dictionnaire représente une sauvegarde avec des clés comme `"date"`, `"original"`, `"size"`, `"filename"`.

*   **Retour**: Aucun.
*   **Logique interne**:
    *   Supprime tous les éléments existants du `Treeview`.
    *   Itère sur chaque sauvegarde dans `backups_data` et insère une ligne correspondante dans le `Treeview`.
    *   Gère les erreurs potentielles lors de la mise à jour de la liste.

#### `_restore_selected(self)`

Lance la restauration de la sauvegarde sélectionnée dans le `Treeview`.

*   **Arguments**: Aucun.
*   **Retour**: Aucun.
*   **Logique interne**:
    *   Utilise le décorateur `@trace_action` pour tracer cette action.
    *   Vérifie si une ligne est sélectionnée dans le `Treeview`. Si non, affiche un avertissement.
    *   Récupère le nom du fichier de backup de la ligne sélectionnée.
    *   Demande une confirmation à l'utilisateur (`messagebox.askyesno`).
    *   Si l'utilisateur confirme :
        *   Envoie un message `{'type': 'restore_backup', 'filename': backup_filename}` à la `task_queue`.
        *   Ferme la fenêtre actuelle (`self.destroy()`).

---

## Exemple d'usage

Il n'y a pas d'exemple d'usage direct du fichier `tools.py` car ces classes sont destinées à être instanciées et utilisées par la logique principale de l'application (probablement dans le module `ui.windows.main` ou similaire) lorsqu'une fonctionnalité d'outil est appelée. Par exemple, pour ouvrir la fenêtre de gestion de base de données :

```python
# Dans une autre partie du code où 'root' est l'instance principale de l'application
# et 'task_queue' est une instance de queue.Queue
from ui.windows.tools import DbManagerWindow

def open_db_manager():
    db_manager = DbManagerWindow(master=root, task_queue=task_queue, on_clear_chat=clear_chat_history)
    db_manager.pack() # Ou .grid(), .place() selon le layout de l'application principale

# Supposons que clear_chat_history est une fonction définie ailleurs
def clear_chat_history():
    print("Clearing chat history...")
    # Logique pour effacer l'historique du chat
# Fichier: ui\windows\queue.py

## Description concise

Ce module implémente la fenêtre `WaitingListWindow` qui est responsable de l'affichage de l'état de la file d'attente des tâches. Elle présente la tâche actuellement en cours d'exécution ainsi que la liste des tâches en attente. La fenêtre se rafraîchit périodiquement pour afficher les mises à jour.

## Dépendances

*   `customtkinter as ctk`: Pour la création de l'interface utilisateur graphique.
*   `ui.windows.base.BaseWindow`: Classe de base pour les fenêtres de l'application.
*   `features.Decorators.trace_action`: Décorateur pour tracer les actions.

## Classes & Fonctions

### Classe: `WaitingListWindow`

Hérite de `ui.windows.base.BaseWindow`.

#### Méthode: `__init__(self, master, task_queue)`

*   **Description:** Constructeur de la fenêtre `WaitingListWindow`. Initialise l'interface utilisateur pour afficher la file d'attente.
*   **Arguments:**
    *   `master`: Le widget parent.
    *   `task_queue`: Une instance de `queue.Queue` ou similaire, utilisée pour communiquer avec le processus worker.
*   **Logique interne:**
    *   Appelle le constructeur de la classe parente `BaseWindow` avec un titre et des dimensions spécifiés.
    *   Stocke la `task_queue` pour une communication ultérieure.
    *   Crée et configure les widgets pour afficher la tâche en cours (`CTkLabel`, `CTkTextbox`). Le `CTkTextbox` est désactivé pour éviter l'édition par l'utilisateur.
    *   Crée et configure les widgets pour afficher la liste des tâches en attente (`CTkLabel`, `CTkTextbox`). Le `CTkTextbox` est également désactivé.
    *   Crée un cadre pour les boutons d'action (`Rafraîchir`, `Vider la file`).
    *   Configure le bouton "Rafraîchir" pour appeler la méthode `_refresh`.
    *   Configure le bouton "Vider la file" pour appeler la méthode `_clear_queue`. Ce bouton est stylisé en rouge.
    *   Déclenche un rafraîchissement automatique initial après 500ms.

#### Méthode: `_refresh(self)`

*   **Description:** Lance une demande de mise à jour de l'état de la file d'attente et planifie le prochain rafraîchissement.
*   **Arguments:** Aucun.
*   **Retours:** Aucun.
*   **Logique interne:**
    *   Vérifie si la fenêtre existe toujours (`self.winfo_exists()`). Si ce n'est pas le cas, la méthode se termine pour éviter des erreurs.
    *   Si une `task_queue` est disponible, un dictionnaire `{"type": "get_queue_status"}` est mis dans la queue. Cela indique au processus worker de renvoyer l'état actuel de la file.
    *   Planifie l'appel de `_refresh` à nouveau après 1000ms (1 seconde) en utilisant `self.after()`.

#### Méthode: `_clear_queue(self)`

*   **Description:** Méthode placeholder pour vider la file d'attente. L'implémentation réelle dépend de la logique du worker.
*   **Arguments:** Aucun.
*   **Retours:** Aucun.
*   **Logique interne:**
    *   La méthode est actuellement vide (`pass`). Un commentaire indique qu'une commande `{"type": "clear_queue"}` pourrait être envoyée au worker si cette fonctionnalité est implémentée de ce côté.

#### Méthode: `update_list(self, data)`

*   **Description:** Met à jour l'interface utilisateur avec les données actuelles de la file d'attente. Cette méthode est décorée avec `@trace_action` pour enregistrer l'événement.
*   **Arguments:**
    *   `data` (dict): Un dictionnaire contenant les informations sur la file d'attente. Attend un format comme `{"current": str, "waiting": list}`.
*   **Retours:** Aucun.
*   **Logique interne:**
    *   Récupère la tâche actuelle (`current`) et la liste des tâches en attente (`waiting`) à partir du dictionnaire `data`. Des valeurs par défaut ("Inactif" et une liste vide) sont utilisées si les clés sont absentes.
    *   **Mise à jour de la section "En Cours":**
        *   Active le `CTkTextbox` (`txt_current`) pour permettre la modification.
        *   Supprime tout le contenu existant.
        *   Insère le texte de la tâche actuelle.
        *   Désactive le `CTkTextbox` à nouveau.
    *   **Mise à jour de la section "En Attente":**
        *   Active le `CTkTextbox` (`list_waiting`).
        *   Supprime tout le contenu existant.
        *   Si la liste `waiting` est vide, insère le message "La file est vide.".
        *   Sinon, itère sur la liste `waiting` et insère chaque tâche avec son numéro d'ordre (commençant à 1).
        *   Désactive le `CTkTextbox` à nouveau.

## Exemple d'usage

Il est supposé que `WaitingListWindow` est instanciée et gérée par une autre partie de l'application, qui lui fournit une instance de `queue.Queue` pour la communication.

```python
import customtkinter as ctk
from ui.windows.queue import WaitingListWindow
import queue

# Création de la fenêtre principale de l'application
app = ctk.CTk()
app.geometry("700x750")
app.title("Application Principale")

# Création d'une file pour la communication avec le worker (simulée ici)
task_queue = queue.Queue()

# Instanciation de la fenêtre de file d'attente
queue_window = WaitingListWindow(master=app, task_queue=task_queue)
queue_window.pack(pady=20, padx=20, fill="both", expand=True)

# Simuler des données de mise à jour (ceci serait fait par le processus worker)
def simulate_updates():
    # Simulation de la première mise à jour
    task_queue.put({"type": "queue_status", "data": {"current": "Traitement du fichier A...", "waiting": ["Envoi du rapport B", "Mise à jour de la base de données C"]}})
    app.after(3000, simulate_second_update)

def simulate_second_update():
    # Simulation d'une deuxième mise à jour
    task_queue.put({"type": "queue_status", "data": {"current": "Envoi du rapport B", "waiting": ["Mise à jour de la base de données C", "Génération du PDF D"]}})
    app.after(3000, simulate_third_update)

def simulate_third_update():
    # Simulation d'une troisième mise à jour (file presque vide)
    task_queue.put({"type": "queue_status", "data": {"current": "Mise à jour de la base de données C", "waiting": []}})
    app.after(3000, simulate_fourth_update)

def simulate_fourth_update():
    # Simulation d'une quatrième mise à jour (inactif)
    task_queue.put({"type": "queue_status", "data": {"current": "Inactif", "waiting": []}})

# Pour recevoir les mises à jour de la queue (à placer dans la boucle principale du worker ou un thread séparé)
def process_queue_updates():
    try:
        message = task_queue.get_nowait()
        if message.get("type") == "get_queue_status":
            # Le worker devrait répondre ici avec l'état réel.
            # Pour la démo, on simule la réponse ici.
            # Dans une vraie application, cette logique serait dans le worker.
            pass 
        elif message.get("type") == "queue_status":
            queue_window.update_list(message.get("data", {}))
    except queue.Empty:
        pass
    app.after(100, process_queue_updates) # Vérifier fréquemment

# Lancer les simulations et le traitement des updates
app.after(1000, simulate_updates)
app.after(100, process_queue_updates)

app.mainloop()
```
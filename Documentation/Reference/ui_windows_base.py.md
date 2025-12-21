# Documentation Technique : `ui\windows\base.py`

## Description

Ce module fournit des classes de base pour la création de fenêtres d'interface utilisateur (UI) dans une application utilisant `customtkinter` et `tkinter`. Il inclut des utilitaires pour les info-bulles, une classe de fenêtre de base pour les fenêtres secondaires, ainsi que des implémentations spécifiques pour la capture de touches et l'édition JSON.

## Dépendances

*   `customtkinter`
*   `tkinter`
*   `tkinter.messagebox`
*   `traceback`
*   `logging`
*   `ui.widgets` (spécifiquement `COLORS`)
*   `features.Decorators` (spécifiquement `trace_action`)

---

## Classes & Fonctions

### Classe `Tooltip`

Petit utilitaire pour afficher des info-bulles au survol (Ergonomie V16).

#### `__init__(self, widget, text)`

*   **Description**: Initialise l'utilitaire d'info-bulle. Lie les événements d'entrée et de sortie de souris au widget spécifié pour afficher/masquer l'info-bulle.
*   **Arguments**:
    *   `widget`: Le widget `tkinter` auquel l'info-bulle sera attachée.
    *   `text` (str): Le texte à afficher dans l'info-bulle.
*   **Logique interne**:
    *   Stocke le widget et le texte.
    *   Initialise `tooltip_window` à `None`.
    *   Lie `<Enter>` (souris sur le widget) à `show_tooltip`.
    *   Lie `<Leave>` (souris quitte le widget) à `hide_tooltip`.

#### `show_tooltip(self, event=None)`

*   **Description**: Affiche l'info-bulle à une position calculée par rapport au widget.
*   **Arguments**:
    *   `event` (optional): L'objet événement, utilisé pour obtenir les coordonnées si nécessaire.
*   **Logique interne**:
    *   Calcule les coordonnées `x`, `y` pour positionner l'info-bulle légèrement décalée par rapport à la position du curseur dans le widget.
    *   Crée une fenêtre `tk.Toplevel` (sans bordure) pour l'info-bulle.
    *   Configure la géométrie de la fenêtre `Toplevel` pour qu'elle apparaisse à la position calculée.
    *   Crée un `tk.Label` avec le texte de l'info-bulle, configuré avec une couleur de fond jaune pâle, un bord, et une police spécifique.
    *   Place le label dans la fenêtre `Toplevel`.
    *   Gère les exceptions silencieusement (`pass`) pour éviter de planter l'application si l'affichage de l'info-bulle échoue.
*   **Décorateur**: `@trace_action(source="base")`

#### `hide_tooltip(self, event=None)`

*   **Description**: Masque et détruit l'info-bulle si elle est actuellement affichée.
*   **Arguments**:
    *   `event` (optional): L'objet événement.
*   **Logique interne**:
    *   Vérifie si `self.tooltip_window` existe.
    *   Si oui, détruit la fenêtre de l'info-bulle.
    *   Réinitialise `self.tooltip_window` à `None`.
*   **Décorateur**: `@trace_action(source="base")`

---

### Classe `BaseWindow`

Classe de base pour toutes les fenêtres secondaires.

#### `__init__(self, master, title, width, height)`

*   **Description**: Constructeur de la fenêtre de base. Configure la fenêtre comme une fenêtre `CTkToplevel` avec des propriétés communes aux fenêtres secondaires.
*   **Arguments**:
    *   `master`: Le widget parent.
    *   `title` (str): Le titre de la fenêtre.
    *   `width` (int): La largeur initiale de la fenêtre.
    *   `height` (int): La hauteur initiale de la fenêtre.
*   **Logique interne**:
    *   Appelle le constructeur de la classe parente (`ctk.CTkToplevel`).
    *   Configure le titre de la fenêtre.
    *   Définit la géométrie initiale de la fenêtre.
    *   Configure la couleur de fond (`fg_color`) en utilisant `COLORS["BG_MAIN"]`.
    *   Définit la fenêtre comme transitoire par rapport à son maître (`transient(master)`).
    *   Place la fenêtre au premier plan (`lift()`).
    *   Utilise `self.after(200, lambda: self.focus_force())` pour forcer le focus sur la fenêtre après un court délai (pour s'assurer qu'elle est bien visible et interactive).
    *   Lie la touche `Escape` à la fermeture de la fenêtre (`self.destroy`).
    *   Configure le gestionnaire de protocole `WM_DELETE_WINDOW` (clic sur le bouton de fermeture) pour appeler `self.destroy`.

#### `report_error(self, context, e)`

*   **Description**: Affiche une erreur bloquante à l'utilisateur de manière claire et enregistre les détails dans le journal.
*   **Arguments**:
    *   `context` (str): Une chaîne décrivant le contexte dans lequel l'erreur s'est produite.
    *   `e`: L'objet exception levé.
*   **Logique interne**:
    *   Construit un message d'erreur incluant le contexte et la description de l'exception.
    *   Enregistre l'erreur et son traceback complet dans le logger `log`.
    *   Affiche une boîte de message d'erreur (`messagebox.showerror`) à l'utilisateur, informant du problème et l'invitant à consulter les logs pour plus de détails. La fenêtre de message est modale par rapport à la fenêtre courante (`parent=self`).
*   **Décorateur**: `@trace_action(source="base")`

---

### Classe `KeyCaptureDialog`

Fenêtre modale pour capturer une combinaison de touches.

#### `__init__(self, master, title, callback)`

*   **Description**: Initialise la boîte de dialogue de capture de touches.
*   **Arguments**:
    *   `master`: Le widget parent.
    *   `title` (str): Le titre de la fenêtre.
    *   `callback` (function): La fonction à appeler avec la combinaison de touches capturée en argument.
*   **Logique interne**:
    *   Appelle le constructeur de `BaseWindow` pour configurer la fenêtre (taille 400x200).
    *   Stocke la fonction de rappel (`callback`).
    *   Désactive la touche `Escape` (car elle est gérée différemment dans le `BaseWindow`).
    *   Crée et place un `CTkLabel` pour l'instruction principale.
    *   Crée et place un `CTkLabel` (`lbl_current`) pour afficher la combinaison de touches détectée en temps réel.
    *   Crée et place un `CTkButton` "Annuler" qui détruit la fenêtre.
    *   Lie l'événement `<KeyPress>` à la méthode `_on_key_press`.
    *   Lie l'événement `<Button-1>` (clic gauche) à la méthode `_check_click_outside` pour permettre la fermeture en cliquant à l'extérieur.
    *   Force le focus sur cette fenêtre et la rend modale (`grab_set`).

#### `_check_click_outside(self, event)`

*   **Description**: Ferme la fenêtre si l'utilisateur clique à l'extérieur de sa zone visible.
*   **Arguments**:
    *   `event`: L'objet événement du clic de souris.
*   **Logique interne**:
    *   Récupère les coordonnées `x`, `y` du clic par rapport à la fenêtre.
    *   Récupère la largeur (`w`) et la hauteur (`h`) de la fenêtre.
    *   Si les coordonnées du clic sont en dehors des limites de la fenêtre, appelle `self.destroy()`.
*   **Décorateur**: `@trace_action(source="base")`

#### `_on_key_press(self, event)`

*   **Description**: Gère la détection des touches pressées pour construire la combinaison.
*   **Arguments**:
    *   `event`: L'objet événement de la touche pressée.
*   **Logique interne**:
    *   Ignore les touches modificateurs seules (Ctrl, Alt, Shift, Caps Lock, Num Lock).
    *   Construit une liste `parts` contenant les modificateurs (Control, Alt, Shift) s'ils sont actifs, suivi du nom de la touche pressée (`event.keysym`).
    *   Formate la combinaison de touches en une chaîne lisible (ex: `<Control-Alt-A>`).
    *   Met à jour le texte du label `lbl_current` pour afficher la combinaison en cours.
    *   Après un délai de 300 ms, appelle `_confirm` pour finaliser la capture.
*   **Décorateur**: `@trace_action(source="base")`

#### `_confirm(self, key_str)`

*   **Description**: Appelle la fonction de rappel avec la combinaison de touches capturée et ferme la fenêtre.
*   **Arguments**:
    *   `key_str` (str): La chaîne représentant la combinaison de touches capturée.
*   **Logique interne**:
    *   Si une fonction de rappel (`self.callback`) a été fournie, l'appelle avec `key_str` comme argument.
    *   Détruit la fenêtre de dialogue.
*   **Décorateur**: `@trace_action(source="base")`

---

### Classe `ModelEditorWindow`

Fenêtre pour l'édition brute de données (probablement au format JSON).

#### `__init__(self, master, current_data, on_save)`

*   **Description**: Initialise la fenêtre d'édition de modèle.
*   **Arguments**:
    *   `master`: Le widget parent.
    *   `current_data`: Les données actuelles à éditer (attendu sous forme de dictionnaire/liste JSON).
    *   `on_save` (function): La fonction à appeler lorsque l'utilisateur sauvegarde les modifications. Elle recevra les données modifiées (après désérialisation JSON) en argument.
*   **Logique interne**:
    *   Appelle le constructeur de `BaseWindow` (titre "Éditeur JSON", taille 700x600).
    *   Stocke la fonction de rappel `on_save`.
    *   Utilise un bloc `try...except` pour gérer les erreurs d'initialisation et appeler `report_error`.
    *   Crée et place un `CTkLabel` d'information.
    *   Crée et place un `CTkTextbox` (`self.txt`) pour l'édition du contenu.
        *   Configure la police comme "Consolas" 12pt pour une meilleure lisibilité du code.
        *   Définit `wrap="none"` pour désactiver le retour à la ligne automatique.
    *   Insère les `current_data` formatées en JSON (avec indentation) dans le `CTkTextbox`.
    *   Crée un `CTkFrame` pour contenir les boutons.
    *   Crée et place un `CTkButton` "Annuler" qui ferme la fenêtre.
    *   Crée et place un `CTkButton` "Sauvegarder" qui appelle la méthode `_save`.

#### `_save(self)`

*   **Description**: Tente de sauvegarder les données éditées.
*   **Logique interne**:
    *   Importe le module `json` (peut-être redondant si déjà importé globalement, mais assure la disponibilité locale).
    *   Utilise un bloc `try...except` pour gérer les erreurs de parsing JSON ou de sauvegarde.
    *   Récupère le texte du `CTkTextbox`, supprime les espaces blancs au début et à la fin (`strip()`).
    *   Tente de désérialiser le texte en objet Python (`json.loads`).
    *   Si la désérialisation réussit, appelle la fonction `self.on_save` avec les données parsées.
    *   Ferme la fenêtre (`self.destroy()`).
    *   En cas d'exception (par exemple, JSON invalide), appelle `self.report_error` pour informer l'utilisateur et enregistrer l'erreur.
*   **Décorateur**: `@trace_action(source="base")`

---

## Exemple d'usage

### Afficher une info-bulle

```python
import tkinter as tk
from ui.windows.base import Tooltip
from ui.widgets import COLORS

root = tk.Tk()
button = tk.Button(root, text="Survolez-moi")
button.pack()

# Créer une info-bulle pour le bouton
tooltip = Tooltip(button, "Ceci est une description utile.")

root.mainloop()
```

### Ouvrir une fenêtre de base

```python
import tkinter as tk
from ui.windows.base import BaseWindow
from ui.widgets import COLORS

root = tk.Tk()
root.title("Fenêtre Principale")
root.geometry("800x600")

def open_secondary_window():
    secondary_win = BaseWindow(root, "Fenêtre Secondaire", 400, 300)
    # Ajoutez ici d'autres widgets à la fenêtre secondaire
    tk.Label(secondary_win, text="Contenu de la fenêtre secondaire", bg=COLORS["BG_MAIN"]).pack(pady=50)

button = tk.Button(root, text="Ouvrir Fenêtre Secondaire", command=open_secondary_window)
button.pack(pady=20)

root.mainloop()
```

### Utiliser le dialogue de capture de touches

```python
import tkinter as tk
from ui.windows.base import KeyCaptureDialog
from ui.widgets import COLORS

def handle_key_capture(key_string):
    print(f"Combinaison capturée : {key_string}")

root = tk.Tk()
root.title("Fenêtre Principale")
root.geometry("400x300")

def open_key_capture():
    dialog = KeyCaptureDialog(root, "Capture de Raccourci", handle_key_capture)

button = tk.Button(root, text="Capturer Touche", command=open_key_capture)
button.pack(pady=20)

root.mainloop()
```

### Utiliser l'éditeur JSON

```python
import tkinter as tk
from ui.windows.base import ModelEditorWindow
from ui.widgets import COLORS
import json

def save_config(new_data):
    print("Configuration sauvegardée :", json.dumps(new_data, indent=2))
    # Ici, vous intégreriez la logique pour réellement sauvegarder les données

root = tk.Tk()
root.title("Fenêtre Principale")
root.geometry("500x200")

initial_config = {
    "setting1": "value1",
    "nested": {
        "key": 123
    }
}

def open_editor():
    editor = ModelEditorWindow(root, initial_config, save_config)

button = tk.Button(root, text="Ouvrir Éditeur JSON", command=open_editor)
button.pack(pady=20)

root.mainloop()
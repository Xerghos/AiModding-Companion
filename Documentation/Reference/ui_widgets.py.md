# Documentation Technique: ui\widgets.py

## Description concise

Ce module contient des widgets personnalisés pour l'interface utilisateur graphique, développés avec `customtkinter`. Il inclut un éditeur de texte avancé avec numérotation de lignes et barre de recherche/remplacement, ainsi qu'un bouton d'état de clé API qui affiche un menu déroulant détaillé.

## Dépendances

*   `customtkinter`
*   `tkinter`
*   `logging`
*   `time`
*   `re`

---

## Classes & Fonctions

### Classe `TextEditorWithLineNumbers`

Hérite de `ctk.CTkFrame`.

**Description:** Un widget éditeur de texte enrichi qui affiche les numéros de ligne et intègre une barre de recherche/remplacement accessible via `Ctrl+F`.

**`__init__(self, master, **kwargs)`**

*   **Description:** Initialise le widget `TextEditorWithLineNumbers`. Configure les sous-composants tels que la zone de texte, les numéros de ligne, les barres de défilement et la barre de recherche.
*   **Arguments:**
    *   `master`: Le widget parent.
    *   `**kwargs`: Arguments supplémentaires passés au constructeur `ctk.CTkFrame`.
*   **Logique interne:**
    *   Configure la propagation de la géométrie (`pack_propagate(False)`).
    *   Initialise l'index de dernière recherche (`last_search_index`).
    *   Définit la police pour l'éditeur (`editor_font`) et la largeur pour la zone des numéros de ligne.
    *   Crée un `CTkFrame` principal (`main_editor_frame`).
    *   Crée un widget `tk.Text` pour les numéros de ligne (`line_numbers`), configuré pour être désactivé et stylisé.
    *   Crée une barre de défilement verticale (`vsb`) liée à la zone de texte.
    *   Crée la zone de texte principale (`text_area`) avec `CTkTextbox`, activant l'historique (`undo=True`) et appliquant les couleurs et polices.
    *   Configure la synchronisation du défilement vertical entre `text_area` et `line_numbers`.
    *   Tente de configurer un tag `found_match` pour surligner les résultats de recherche.
    *   Crée un `CTkFrame` pour la barre de recherche (`find_bar_frame`) et appelle `_setup_find_bar`.
    *   Lie les événements clavier et `<<Change>>` à la méthode `_on_content_changed`.
    *   Lie `Ctrl+F` à `open_find_bar`.
    *   Appelle `_update_line_numbers` pour l'initialisation.

**`_setup_find_bar(self)`**

*   **Description:** Configure les widgets internes de la barre de recherche et de remplacement.
*   **Arguments:** Aucun.
*   **Logique interne:**
    *   Crée un `CTkEntry` pour le champ de recherche (`find_entry`) et le lie à `find_next` sur `"<Return>"`.
    *   Ajoute un bouton "▼" pour déclencher `find_next`.
    *   Crée un `CTkEntry` pour le champ de remplacement (`replace_entry`).
    *   Ajoute un bouton "Remplacer Tout" pour déclencher `replace_all`.
    *   Ajoute un bouton "X" pour fermer la barre via `close_find_bar`.

**`open_find_bar(self, event=None)`**

*   **Description:** Affiche la barre de recherche et de remplacement en bas du widget éditeur.
*   **Arguments:**
    *   `event`: L'objet événementiel (peut être `None`).
*   **Logique interne:**
    *   Utilise `pack` pour afficher `find_bar_frame` sous le frame principal de l'éditeur.
    *   Donne le focus à `find_entry`.
    *   Retourne `"break"` pour empêcher la propagation de l'événement clavier `Ctrl+F`.

**`close_find_bar(self, event=None)`**

*   **Description:** Cache la barre de recherche et de remplacement et nettoie le surlignage des résultats précédents.
*   **Arguments:**
    *   `event`: L'objet événementiel (peut être `None`).
*   **Logique interne:**
    *   Utilise `pack_forget` pour cacher `find_bar_frame`.
    *   Redonne le focus à `text_area`.
    *   Tente de supprimer le tag `found_match` du widget `tk.Text` sous-jacent.

**`find_next(self, event=None)`**

*   **Description:** Recherche la prochaine occurrence du terme spécifié dans la barre de recherche. Surligne le résultat et défile la vue si nécessaire. Boucle au début si la fin est atteinte.
*   **Arguments:**
    *   `event`: L'objet événementiel (peut être `None`).
*   **Logique interne:**
    *   Récupère le terme de recherche depuis `find_entry`.
    *   Accède au widget `tk.Text` sous-jacent via `self.text_area._textbox`.
    *   Supprime les anciens surlignages (`tag_remove`).
    *   Effectue la recherche à partir de `self.last_search_index` ou du début si rien n'est trouvé.
    *   Si trouvé, ajoute le tag `found_match`, rend le résultat visible (`see`) et met à jour `self.last_search_index`.
    *   Si non trouvé, réinitialise `self.last_search_index` au début.
    *   Logue les erreurs potentielles.

**`replace_all(self, event=None)`**

*   **Description:** Remplace toutes les occurrences du terme de recherche par le terme de remplacement dans toute la zone de texte.
*   **Arguments:**
    *   `event`: L'objet événementiel (peut être `None`).
*   **Logique interne:**
    *   Récupère les termes de recherche et de remplacement.
    *   Récupère tout le contenu du `text_area`.
    *   Utilise la méthode `replace` de Python pour effectuer les remplacements.
    *   Efface le contenu actuel du `text_area` et insère le nouveau contenu.
    *   Appelle `_update_line_numbers` pour rafraîchir la numérotation.

**`_on_scroll_y(self, *args)`**

*   **Description:** Gère le défilement vertical synchronisé entre la zone de texte et les numéros de ligne.
*   **Arguments:** `*args`: Arguments passés par le mécanisme de défilement.
*   **Logique interne:**
    *   Appelle `yview` sur `self.text_area` et `self.line_numbers`.

**`_on_scroll_text_y(self, *args)`**

*   **Description:** Gère la mise à jour de la barre de défilement et des numéros de ligne lors du défilement de la zone de texte.
*   **Arguments:** `*args`: Arguments passés par le mécanisme de défilement.
*   **Logique interne:**
    *   Met à jour la position de la poignée de la barre de défilement (`self.vsb.set`).
    *   Déplace la vue des numéros de ligne pour correspondre au défilement de la zone de texte (`self.line_numbers.yview_moveto`).

**`_on_content_changed(self, event=None)`**

*   **Description:** Callback appelé lors de modifications du contenu de la zone de texte pour mettre à jour les numéros de ligne.
*   **Arguments:**
    *   `event`: L'objet événementiel (peut être `None`).
*   **Logique interne:**
    *   Appelle `_update_line_numbers`.

**`_update_line_numbers(self)`**

*   **Description:** Met à jour la zone des numéros de ligne pour refléter le nombre actuel de lignes dans la zone de texte.
*   **Arguments:** Aucun.
*   **Logique interne:**
    *   Calcule le nombre total de lignes.
    *   Génère une chaîne de caractères contenant tous les numéros de ligne.
    *   Active temporairement la zone `line_numbers`, efface son contenu, insère les nouveaux numéros, puis la désactive à nouveau.

**Méthodes Proxy:**

Les méthodes suivantes sont des proxys directs vers les méthodes correspondantes de `self.text_area` pour permettre l'utilisation de `TextEditorWithLineNumbers` comme un `CTkTextbox` standard tout en conservant la logique de mise à jour des numéros de ligne.

*   **`get(self, *args, **kwargs)`**: Appelle `self.text_area.get`.
*   **`insert(self, *args, **kwargs)`**: Appelle `self.text_area.insert` puis `_update_line_numbers`.
*   **`delete(self, *args, **kwargs)`**: Appelle `self.text_area.delete` puis `_update_line_numbers`.
*   **`see(self, *args, **kwargs)`**: Appelle `self.text_area.see`.
*   **`configure(self, **kwargs)`**: Appelle `self.text_area.configure`.
*   **`focus(self)`**: Appelle `self.text_area.focus`.
*   **`tag_config` (propriété)**: Renvoie l'accesseur `tag_config` de `self.text_area`.

---

### Classe `ApiKeyStatusMenu`

Hérite de `ctk.CTkButton`.

**Description:** Un bouton personnalisable qui affiche un menu contextuel (`CTkToplevel`) pour montrer l'état des clés API. Il met à jour son apparence en fonction des statuts et gère un timer pour les mises à jour locales.

**`__init__(self, master, task_queue=None, **kwargs)`**

*   **Description:** Initialise le widget `ApiKeyStatusMenu`.
*   **Arguments:**
    *   `master`: Le widget parent.
    *   `task_queue`: Une file d'attente (`queue.Queue`) pour envoyer des commandes au thread de fond (worker).
    *   `**kwargs`: Arguments supplémentaires passés au constructeur `ctk.CTkButton`.
*   **Logique interne:**
    *   Appelle le constructeur parent.
    *   Stocke `task_queue`.
    *   Initialise `menu` à `None`, `is_visible` à `False`, et `last_statuses` à un dictionnaire vide.
    *   Configure un timer (`after`) pour appeler `_local_tick` toutes les secondes.

**`toggle_menu(self)`**

*   **Description:** Inverse l'état de visibilité du menu (affiche s'il est caché, cache s'il est visible).
*   **Arguments:** Aucun.

**`show(self)`**

*   **Description:** Affiche le menu contextuel (`CTkToplevel`) d'état des clés API.
*   **Arguments:** Aucun.
*   **Logique interne:**
    *   Si un menu existe déjà, il est caché d'abord.
    *   Crée une nouvelle fenêtre `CTkToplevel`.
    *   Configure la fenêtre pour qu'elle soit sans bordure (`wm_overrideredirect(True)`).
    *   Positionne la fenêtre sous le bouton.
    *   Configure la couleur de fond du menu.
    *   Crée un `CTkFrame` pour l'en-tête du menu avec un titre et un bouton de rafraîchissement (`_request_audit`).
    *   Crée un `CTkScrollableFrame` (`self.scroll`) pour le contenu du menu.
    *   Lie l'événement `<FocusOut>` pour cacher le menu lorsque le focus est perdu.
    *   Donne le focus à la fenêtre du menu.
    *   Met `is_visible` à `True`.
    *   Appelle `_refresh_menu_content` pour remplir le menu.

**`hide(self)`**

*   **Description:** Cache et détruit le menu contextuel s'il est visible.
*   **Arguments:** Aucun.
*   **Logique interne:**
    *   Si `self.menu` existe, il est détruit et mis à `None`.
    *   Met `is_visible` à `False`.

**`update_statuses(self, statuses)`**

*   **Description:** Met à jour les données internes de l'état des clés et rafraîchit l'interface si le menu est visible.
*   **Arguments:**
    *   `statuses`: Un dictionnaire contenant les informations d'état des clés API fournies par le worker.
*   **Logique interne:**
    *   Stocke le dictionnaire `statuses` dans `self.last_statuses`.
    *   Appelle `_update_button_label` pour changer l'apparence du bouton principal.
    *   Si le menu est visible (`self.is_visible`), appelle `_refresh_menu_content`.

**`_update_button_label(self)`**

*   **Description:** Met à jour le texte et la couleur du bouton principal (`ApiKeyStatusMenu`) en fonction du résumé des statuts des clés API.
*   **Arguments:** Aucun.
*   **Logique interne:**
    *   Calcule les totaux, les clés valides, brûlées et en attente (quota).
    *   Définit le texte et la couleur du bouton en fonction de ces calculs:
        *   Erreur (rouge) si des clés sont brûlées et aucune valide.
        *   Attention (jaune) si des clés sont en quota et aucune valide.
        *   Succès (vert) s'il y a des clés valides.
        *   Neutre (gris) sinon.

**`_refresh_menu_content(self)`**

*   **Description:** Met à jour le contenu du menu déroulant avec les informations d'état des clés les plus récentes.
*   **Arguments:** Aucun.
*   **Logique interne:**
    *   Si le menu n'est pas visible, ne fait rien.
    *   Détruit tous les widgets enfants actuels dans le frame de défilement (`self.scroll`).
    *   Itère sur les `last_statuses` pour chaque fournisseur d'API.
    *   Pour chaque fournisseur, crée un frame contenant le nom du fournisseur et des frames pour chaque clé individuelle.
    *   Pour chaque clé, affiche un libellé avec l'icône correspondante (✅, 💀, ⏳), le masque de la clé, le statut, et le temps restant en cooldown si applicable.
    *   Applique les couleurs correspondantes aux statuts.

**`_local_tick(self)`**

*   **Description:** Méthode appelée périodiquement par le timer. Rafraîchit le contenu du menu si celui-ci est ouvert pour mettre à jour les compteurs de cooldown.
*   **Arguments:** Aucun.
*   **Logique interne:**
    *   Si `self.is_visible` est `True`, appelle `_refresh_menu_content`.
    *   Se replanifie pour s'exécuter à nouveau après 1000 ms.

**`_request_audit(self)`**

*   **Description:** Envoie une commande au worker via `task_queue` pour déclencher un audit des clés API.
*   **Arguments:** Aucun.
*   **Logique interne:**
    *   Si `self.task_queue` existe, met un message dans la file d'attente avec le type "command" et la commande native pour auditer les clés.

---

### Classe `ReasoningModeSwitch`

Hérite de `ctk.CTkFrame`.

**Description:** Un widget frame contenant un `CTkSwitch` pour activer ou désactiver un "mode Raisonnement". Il exécute une commande callback lorsque son état change.

**`__init__(self, master, command=None, **kwargs)`**

*   **Description:** Initialise le widget `ReasoningModeSwitch`.
*   **Arguments:**
    *   `master`: Le widget parent.
    *   `command`: Une fonction callback à exécuter lorsque le switch est activé/désactivé.
    *   `**kwargs`: Arguments supplémentaires passés au constructeur `ctk.CTkFrame`.
*   **Logique interne:**
    *   Appelle le constructeur parent.
    *   Stocke la commande callback.
    *   Crée une variable `ctk.BooleanVar` (`self.var_reasoning`) pour stocker l'état du switch, initialisée à `False`.
    *   Crée le `CTkSwitch`, le lie à `self.var_reasoning` et à la méthode `_on_toggle`.

**`_on_toggle(self)`**

*   **Description:** Callback exécuté lorsque l'état du switch change. Journalise l'état et appelle la commande callback fournie.
*   **Arguments:** Aucun.
*   **Logique interne:**
    *   Détermine le message d'état ("Activé" ou "Désactivé").
    *   Journalise l'état du mode Raisonnement.
    *   Si une commande callback existe (`self.command`), elle est appelée.

**`get_mode(self)`**

*   **Description:** Renvoie l'état actuel du switch (Raisonnement activé ou désactivé).
*   **Arguments:** Aucun.
*   **Retourne:** `True` si le mode Raisonnement est activé, `False` sinon.
*   **Logique interne:**
    *   Récupère la valeur de `self.var_reasoning`. La documentation mentionne explicitement que cela renvoie un booléen pur, corrigeant un ancien bug où des chaînes de caractères étaient retournées.

---

## Exemple d'usage

```python
import customtkinter as ctk
from ui.widgets import TextEditorWithLineNumbers, ApiKeyStatusMenu, ReasoningModeSwitch
import queue

# Configuration de base de customtkinter
app = ctk.CTk()
app.geometry("800x600")
app.configure(fg_color="#1E1E1E")

# File d'attente pour les communications Worker <-> UI
task_queue = queue.Queue()

# 1. Utilisation de TextEditorWithLineNumbers
editor_frame = ctk.CTkFrame(app, fg_color="#252526")
editor_frame.pack(pady=20, padx=20, fill="both", expand=True)

text_editor = TextEditorWithLineNumbers(editor_frame)
text_editor.pack(fill="both", expand=True, padx=10, pady=10)
text_editor.insert("1.0", "Ceci est un exemple de texte.\nLigne 2.\nLigne 3.\n" * 50)
text_editor.focus()

# 2. Utilisation de ApiKeyStatusMenu
api_status_button = ApiKeyStatusMenu(app, task_queue=task_queue)
api_status_button.pack(pady=10, padx=10, anchor="ne")

# Simulation de mise à jour des statuts API (à exécuter dans un thread séparé normalement)
# Ceci est juste pour démonstration
app.after(2000, lambda: api_status_button.update_statuses({
    "openai": {"total": 5, "valid": 3, "details": [
        {"key": "sk-...", "status": "OK", "cooldown_end": 0},
        {"key": "sk-...", "status": "OK", "cooldown_end": 0},
        {"key": "sk-...", "status": "BURNED", "cooldown_end": 0},
        {"key": "sk-...", "status": "QUOTA", "cooldown_end": time.time() + 60},
        {"key": "sk-...", "status": "OK", "cooldown_end": 0},
    ]},
    "anthropic": {"total": 2, "valid": 1, "details": [
        {"key": "sk-...", "status": "OK", "cooldown_end": 0},
        {"key": "sk-...", "status": "QUOTA", "cooldown_end": time.time() + 120},
    ]}
}))

# 3. Utilisation de ReasoningModeSwitch
def on_reasoning_mode_change():
    is_thinking = reasoning_switch.get_mode()
    print(f"Le mode raisonnement est maintenant : {is_thinking}")
    # Ici, on pourrait envoyer une commande au worker via task_queue
    # if is_thinking:
    #     task_queue.put({"type": "command", "command": "set_reasoning_mode(True)"})
    # else:
    #     task_queue.put({"type": "command", "command": "set_reasoning_mode(False)"})

reasoning_switch = ReasoningModeSwitch(app, command=on_reasoning_mode_change)
reasoning_switch.pack(pady=10, padx=10, anchor="nw")

app.mainloop()
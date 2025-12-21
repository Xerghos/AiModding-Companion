# Documentation Technique : `ui\panels.py`

## Description Concise

Ce fichier définit les composants de l'interface utilisateur de type "panneau" pour l'application. Il gère la disposition des éléments principaux, y compris la barre d'outils, les onglets de chat et la zone de saisie, ainsi que des fonctionnalités telles que la coloration syntaxique pour les éditeurs de code, la gestion de l'historique des prompts et l'affichage des messages dans les zones de chat.

## Dépendances

*   `customtkinter as ctk`: Bibliothèque d'interface graphique basée sur Tkinter.
*   `tkinter as tk`: Bibliothèque graphique standard de Python.
*   `os`: Module pour interagir avec le système d'exploitation (utilisé pour extraire les noms de fichiers).
*   `ui.syntax as syntax_highlighter`: Module personnalisé pour la coloration syntaxique du code.
*   `ui.widgets`: Module personnalisé contenant des widgets spécifiques comme `TextEditorWithLineNumbers`, `COLORS`, `ApiKeyStatusMenu`, `ReasoningModeSwitch`.
*   `ui.icons`: Module personnalisé pour la gestion des icônes (non utilisé directement dans les signatures mais potentiellement en interne par les widgets).
*   `features.Decorators.trace_action`: Décorateur pour le traçage des actions (probablement pour le logging ou le débogage).

---

## Classes & Fonctions

### Classe `MainPanel(ctk.CTkFrame)`

Contient toute la zone droite de l'interface utilisateur : Toolbar, Onglets (Chat/Code), et la zone d'Input.

#### `__init__(self, master, task_queue, callbacks, prompt_history_ref, **kwargs)`

*   **Description** : Initialise le panneau principal. Configure la mise en page et crée les sous-composants : barre d'outils, onglets et zone de saisie.
*   **Arguments** :
    *   `master`: Le widget parent.
    *   `task_queue`: Une file d'attente (`queue.Queue` ou similaire) pour envoyer des tâches au backend.
    *   `callbacks`: Un dictionnaire de fonctions de rappel pour les interactions utilisateur (ex: `send_message`, `open_settings`).
    *   `prompt_history_ref`: Une référence (probablement une liste) à l'historique des prompts pour la navigation.
    *   `**kwargs`: Arguments supplémentaires pour le widget `CTkFrame`.
*   **Retours** : Aucun.
*   **Logique Interne** :
    *   Appelle le constructeur de la classe parente (`ctk.CTkFrame`).
    *   Stocke les références `task_queue`, `callbacks`, et `prompt_history_ref`.
    *   Initialise `history_index` à -1.
    *   Configure la grille pour que la ligne 1 (onglets) s'étende verticalement et la colonne 0 horizontalement.
    *   Appelle les méthodes privées pour configurer la barre d'outils (`_setup_toolbar`), les onglets (`_setup_tabs`), et la zone de saisie (`_setup_input_area`).
    *   Crée et positionne une barre de statut (`CTkLabel`) en bas du panneau.

#### `_setup_toolbar(self)`

*   **Description** : Crée et positionne les widgets de la barre d'outils en haut du panneau.
*   **Arguments** : Aucun.
*   **Retours** : Aucun.
*   **Logique Interne** :
    *   Crée un `CTkFrame` pour la barre d'outils.
    *   Ajoute des boutons pour "Paramètres", "Clés API", "Backups", "RAG", "Queue", "Fermer". Les commandes de ces boutons sont récupérées du dictionnaire `self.cb`.
    *   Tente de créer une instance de `ApiKeyStatusMenu`. Si une erreur survient (ex: `ApiKeyStatusMenu` non disponible ou mal configuré), elle est ignorée (`try...except`).
    *   Crée un `CTkOptionMenu` pour les "Prompts Rapides", dont les valeurs sont définies par la clé `QUICK_PROMPTS`. La sélection d'une option appelle `_on_quick_prompt`.

#### `_setup_tabs(self)`

*   **Description** : Crée le widget d'onglets (`CTkTabview`) et initialise les zones de texte pour le chat.
*   **Arguments** : Aucun.
*   **Retours** : Aucun.
*   **Logique Interne** :
    *   Crée un `CTkTabview`.
    *   Ajoute un onglet nommé "Chat Principal" et y place un `CTkTextbox` (`chat1_txt`) configuré pour être désactivé, avec un retour à la ligne "word" et une police "Consolas".
    *   Ajoute un onglet nommé "Chat Secondaire" et y place un autre `CTkTextbox` (`chat2_txt`) avec les mêmes configurations.
    *   Appelle `_configure_chat_tags` pour configurer les styles de texte dans les deux zones de chat.

#### `_setup_input_area(self)`

*   **Description** : Crée et positionne les widgets de la zone de saisie en bas du panneau.
*   **Arguments** : Aucun.
*   **Retours** : Aucun.
*   **Logique Interne** :
    *   Crée un `CTkFrame` pour la zone de saisie.
    *   Tente de créer une instance de `ReasoningModeSwitch`. Si une erreur survient, elle est ignorée.
    *   Crée un bouton "Envoyer" dont la commande est `_on_send_press`.
    *   Crée des boutons pour l'activation de la reconnaissance vocale (ASR) et de la synthèse vocale (TTS), qui ajoutent des tâches à `self.task_queue`.
    *   Crée un `CTkTextbox` (`input_txt`) pour la saisie de texte de l'utilisateur.
    *   Configure des liaisons clavier pour `input_txt`:
        *   `<Return>` (Entrée) : Appelle `_on_send_press`.
        *   `<Shift-Return>` : Ne fait rien (permet le saut de ligne sans envoyer).
        *   `<Control-l>` : Donne le focus à la zone de saisie.
        *   `<Up>` / `<Down>` : Gère la navigation dans l'historique des prompts via `_history_up` et `_history_down`.

#### `_on_quick_prompt(self, choice)`

*   **Description** : Gère la sélection d'un prompt rapide dans le menu déroulant.
*   **Arguments** :
    *   `choice` (str): Le texte du prompt rapide sélectionné.
*   **Retours** : Aucun.
*   **Logique Interne** :
    *   Si le `choice` correspond à une clé dans `QUICK_PROMPTS`:
        *   Efface le contenu actuel de `self.input_txt`.
        *   Insère le texte du prompt rapide correspondant dans `self.input_txt`.
        *   Donne le focus à `self.input_txt`.
    *   Réinitialise le texte du menu déroulant à "✨ Prompts Rapides".

#### `_on_send_press(self)`

*   **Description** : Gère l'action d'envoi d'un message par l'utilisateur (via le bouton "Envoyer" ou la touche Entrée).
*   **Arguments** : Aucun.
*   **Retours** : Aucun.
*   **Logique Interne** :
    *   Récupère le texte de `self.input_txt`, le nettoie des espaces blancs au début et à la fin.
    *   Si le message n'est pas vide et que la fonction de rappel `send_message` existe dans `self.cb`:
        *   Appelle `self.cb['send_message']` avec le message.
        *   Efface le contenu de `self.input_txt`.
        *   Réinitialise `self.history_index` à -1 pour indiquer que l'on est sorti de l'historique.

#### `_on_enter(self, event)`

*   **Description** : Gestionnaire d'événement pour la touche Entrée, appelé lorsque l'utilisateur appuie sur Entrée dans la zone de saisie.
*   **Arguments** :
    *   `event`: L'objet événement Tkinter.
*   **Retours** : `"break"` pour empêcher le comportement par défaut de Tkinter pour la touche Entrée.
*   **Logique Interne** :
    *   Appelle `_on_send_press()` pour traiter l'envoi du message.

#### `_history_up(self, event)`

*   **Description** : Navigue vers l'entrée précédente dans l'historique des prompts lorsque la touche Haut est pressée.
*   **Arguments** :
    *   `event`: L'objet événement Tkinter.
*   **Retours** : `"break"` pour empêcher le comportement par défaut de Tkinter.
*   **Logique Interne** :
    *   Si `self.prompt_history` est vide, ne fait rien.
    *   Incrémente `self.history_index` si possible.
    *   Récupère l'entrée de l'historique à l'index actuel.
    *   Efface `self.input_txt` et y insère le prompt de l'historique.

#### `_history_down(self, event)`

*   **Description** : Navigue vers l'entrée suivante dans l'historique des prompts lorsque la touche Bas est pressée.
*   **Arguments** :
    *   `event`: L'objet événement Tkinter.
*   **Retours** : `"break"` pour empêcher le comportement par défaut de Tkinter.
*   **Logique Interne** :
    *   Si `self.history_index` est supérieur à 0:
        *   Décrémente `self.history_index`.
        *   Récupère l'entrée de l'historique à l'index actuel.
        *   Efface `self.input_txt` et y insère le prompt de l'historique.
    *   Si `self.history_index` est 0:
        *   Réinitialise `self.history_index` à -1 (pour sortir de l'historique).
        *   Efface `self.input_txt`.

#### `_close_current_tab(self)`

*   **Description** : Ferme l'onglet actuellement sélectionné s'il ne s'agit pas d'un onglet principal prédéfini.
*   **Arguments** : Aucun.
*   **Retours** : Aucun.
*   **Logique Interne** :
    *   Récupère le nom de l'onglet actuel.
    *   Si le nom de l'onglet n'est ni "Chat Principal" ni "Chat Secondaire":
        *   Supprime l'onglet du `tab_view`.
    *   Utilise un bloc `try...except` pour gérer les erreurs potentielles (ex: aucun onglet sélectionné).

#### `open_editor_tab(self, filepath, content=None)`

*   **Description** : Ouvre un nouvel onglet pour éditer un fichier spécifié, ou sélectionne l'onglet existant s'il a déjà été ouvert. Applique la coloration syntaxique.
*   **Arguments** :
    *   `filepath` (str): Le chemin complet du fichier à ouvrir.
    *   `content` (str, optionnel): Le contenu initial du fichier. Si `None`, le contenu est lu depuis le `filepath`.
*   **Retours** : Aucun.
*   **Logique Interne** :
    *   Extrait le nom du fichier du `filepath`.
    *   Vérifie si un onglet avec ce nom existe déjà. Si oui, sélectionne cet onglet et retourne.
    *   Ajoute un nouvel onglet avec le nom du fichier.
    *   Si `content` est `None`, tente de lire le contenu du fichier. En cas d'erreur, le contenu sera un message d'erreur.
    *   Crée une instance de `TextEditorWithLineNumbers` dans le nouvel onglet.
    *   Obtient le lexer approprié pour le nom de fichier en utilisant `syntax_highlighter.get_lexer`.
    *   Applique la coloration syntaxique au contenu du fichier dans l'éditeur en utilisant `syntax_highlighter.apply_highlighting_to_editor`.
    *   Sélectionne le nouvel onglet.

#### `log_chat(self, text, tag, target="Chat Principal")`

*   **Description** : Ajoute un message textuel avec un style spécifique (`tag`) à l'une des zones de chat.
*   **Arguments** :
    *   `text` (str): Le message à afficher.
    *   `tag` (str): Le nom de la balise de style à appliquer (ex: "user", "gemini", "info", "error").
    *   `target` (str, optionnel): Le nom de l'onglet cible ("Chat Principal" ou "Chat Secondaire"). Par défaut, "Chat Principal".
*   **Retours** : Aucun.
*   **Logique Interne** :
    *   Sélectionne le widget de zone de chat approprié (`widget`) en fonction de `target`.
    *   Active temporairement le widget (`state="normal"`).
    *   Insère le `text` suivi de deux sauts de ligne, et applique la `tag`.
    *   Désactive à nouveau le widget (`state="disabled"`).
    *   Fait défiler la zone de texte pour afficher le dernier message (`widget.see("end")`).

#### `_configure_chat_tags(self, widget)`

*   **Description** : Configure les balises de style pour les zones de texte de chat.
*   **Arguments** :
    *   `widget`: Le widget `CTkTextbox` auquel appliquer les configurations de tags.
*   **Retours** : Aucun.
*   **Logique Interne** :
    *   Définit les couleurs pour différentes balises (`user`, `gemini`, `info`, `error`) en utilisant le dictionnaire `COLORS`.
    *   Appelle `syntax_highlighter.configure_tags(widget)` pour appliquer également les tags de coloration syntaxique du code si nécessaire.

---

## Exemple d'usage

```python
# Cet exemple suppose que vous avez une instance de MainPanel déjà créée
# et que les callbacks et task_queue sont correctement initialisés.

# Créer une instance de MainPanel (dans le contexte d'une application Tkinter/CustomTkinter)
# root = ctk.CTk()
# task_queue = queue.Queue()
# callbacks = {
#     'send_message': lambda msg: print(f"Message envoyé : {msg}"),
#     'open_settings': lambda: print("Ouverture des paramètres..."),
#     'toggle_api': lambda: print("Toggle API..."),
#     'open_backups': lambda: print("Ouverture des backups..."),
#     'open_rag': lambda: print("Ouverture RAG..."),
#     'open_queue': lambda: print("Ouverture Queue...")
# }
# prompt_history = [] # Ou une liste pré-remplie
# main_panel = MainPanel(root, task_queue, callbacks, prompt_history)
# main_panel.pack(fill="both", expand=True)

# Exemple d'utilisation des méthodes de MainPanel :

# Afficher un message de l'utilisateur dans le chat principal
main_panel.log_chat("Bonjour, comment puis-je vous aider ?", "user")

# Afficher une réponse de l'IA dans le chat secondaire
main_panel.log_chat("Je suis prêt à traiter votre demande.", "gemini", target="Chat Secondaire")

# Afficher un message d'information
main_panel.log_chat("Traitement en cours...", "info")

# Simuler l'ouverture d'un fichier dans un nouvel onglet éditeur
# Assurez-vous que le fichier 'mon_script.py' existe ou adaptez le chemin
# try:
#     with open("mon_script.py", "w") as f:
#         f.write("print('Hello World')\ndef ma_fonction():\n    pass\n")
#     main_panel.open_editor_tab("mon_script.py")
# except Exception as e:
#     print(f"Erreur lors de la création du fichier d'exemple : {e}")

# Utiliser un prompt rapide (simulé par la sélection du menu)
# main_panel._on_quick_prompt("Générer Tests") 
# Le contenu "Génère des tests unitaires pour ce fichier : " sera inséré dans l'input_txt

# Ajouter des éléments à l'historique des prompts pour tester la navigation
# prompt_history.append({"prompt": "Premier prompt"})
# prompt_history.append({"prompt": "Deuxième prompt"})
# print("Utilisez les flèches Haut/Bas dans la zone de saisie pour naviguer dans l'historique.")
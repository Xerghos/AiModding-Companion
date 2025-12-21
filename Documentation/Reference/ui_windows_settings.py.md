# Documentation du module `ui\windows\settings.py`

## 1. En-tête

### Titre
Module de gestion des paramètres et du centre de contrôle de l'application.

### Description
Ce module implémente la fenêtre des paramètres de l'application, permettant aux utilisateurs de configurer divers aspects tels que les préférences de l'interface utilisateur, les clés d'API des moteurs d'IA, les réglages du "swarm" (essaim d'agents), les options du pont CLI, les paramètres système et de code, et les raccourcis clavier. Il inclut également des utilitaires pour les info-bulles, la capture de touches et un éditeur JSON avancé.

### Dépendances
*   `tkinter`, `customtkinter` (ctk), `tkinter.messagebox`, `tkinter.ttk`: Composants d'interface utilisateur graphique.
*   `json`: Manipulation de données JSON pour la configuration.
*   `os`: Opérations sur le système de fichiers.
*   `logging`: Gestion des logs d'application.
*   `threading`: Exécution de tâches en arrière-plan.
*   `traceback`: Récupération des informations d'erreur.
*   `time`: Fonctionnalités liées au temps.
*   `config.settings`: Pour charger, sauvegarder et accéder aux paramètres de l'application (`APP_SETTINGS`, `save_app_settings`, `load_app_settings`).
*   `config.logs`: Pour obtenir une instance de logger (`get_logger`).
*   `ui.windows.base`: Classe de base pour les fenêtres de l'interface utilisateur (`BaseWindow`).
*   `ai_core.factory`: Pour l'audit des fournisseurs d'IA (`SessionFactory`).
*   `ai_core.keys`: Pour la découverte des modèles d'IA (`discover_models`).
*   `features.Decorators`: Pour le décorateur `trace_action` (non directement utilisé dans ce fichier mais importé).

## 2. Classes & Fonctions

### Variables Globales

*   `log`: Instance de logger configurée pour le module `ui.windows.settings`.
*   `COLORS`: Dictionnaire de constantes définissant les couleurs utilisées dans l'interface utilisateur.

### Classes

#### `Tooltip`
Petit utilitaire pour afficher des info-bulles au survol d'un widget.

##### Méthodes

*   `__init__(self, widget, text)`
    *   **Description**: Initialise une instance de Tooltip.
    *   **Arguments**:
        *   `widget` (`tk.Widget`): Le widget auquel l'info-bulle sera attachée.
        *   `text` (`str`): Le texte à afficher dans l'info-bulle.
    *   **Logique interne**: Lie les événements `<Enter>` et `<Leave>` du widget aux méthodes `show_tooltip` et `hide_tooltip` respectivement.

*   `show_tooltip(self, event=None)`
    *   **Description**: Affiche l'info-bulle.
    *   **Arguments**:
        *   `event` (`tk.Event`, optionnel): L'événement qui a déclenché l'appel.
    *   **Logique interne**: Crée une fenêtre `tk.Toplevel` sans bordure (`wm_overrideredirect`), la positionne près du widget, et y ajoute un `tk.Label` avec le texte de l'info-bulle.

*   `hide_tooltip(self, event=None)`
    *   **Description**: Cache et détruit l'info-bulle.
    *   **Arguments**:
        *   `event` (`tk.Event`, optionnel): L'événement qui a déclenché l'appel.
    *   **Logique interne**: Détruit la fenêtre `tk.Toplevel` si elle existe.

#### `KeyCaptureDialog(BaseWindow)`
Dialogue modal pour capturer une combinaison de touches.

##### Méthodes

*   `__init__(self, master, title, callback)`
    *   **Description**: Initialise le dialogue de capture de touches.
    *   **Arguments**:
        *   `master` (`tk.Widget`): Le widget parent.
        *   `title` (`str`): Le titre de la fenêtre du dialogue.
        *   `callback` (`callable`): La fonction à appeler avec la combinaison de touches capturée.
    *   **Logique interne**: Crée une fenêtre modale, affiche des instructions et un label pour la touche actuelle. Lie l'événement `<KeyPress>` à la méthode `_on_key_press`. Force le focus et "grab" le dialogue pour empêcher l'interaction avec la fenêtre parente.

*   `_on_key_press(self, event)`
    *   **Description**: Gère l'événement d'appui sur une touche pour construire la combinaison.
    *   **Arguments**:
        *   `event` (`tk.Event`): L'événement de la touche pressée.
    *   **Logique interne**: Filtre les touches modificatrices seules. Construit une chaîne représentant la combinaison de touches (ex: `<Control-Alt-Shift-a>`). Met à jour le label affichant la combinaison et appelle `_confirm` après un court délai.

*   `_confirm(self, key)`
    *   **Description**: Appelle la fonction de rappel avec la combinaison de touches et ferme le dialogue.
    *   **Arguments**:
        *   `key` (`str`): La combinaison de touches capturée (ex: `<Control-Shift-a>`).
    *   **Logique interne**: Exécute `self.callback(key)` si `callback` est défini, puis détruit le dialogue.

#### `ModelEditorWindow(BaseWindow)`
Éditeur JSON brut pour la configuration avancée.

##### Méthodes

*   `__init__(self, master, current_data, on_save)`
    *   **Description**: Initialise l'éditeur JSON.
    *   **Arguments**:
        *   `master` (`tk.Widget`): Le widget parent.
        *   `current_data` (`dict`): Les données de configuration actuelles à afficher en JSON.
        *   `on_save` (`callable`): La fonction à appeler avec les données JSON parsées après validation.
    *   **Logique interne**: Affiche une zone de texte `ctk.CTkTextbox` pré-remplie avec le `current_data` formaté en JSON. Inclut des boutons "Annuler" et "Valider & Sauvegarder" qui appellent `_save`.

*   `_save(self)`
    *   **Description**: Tente de parser le contenu du champ de texte comme JSON et appelle `on_save`.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Récupère le texte de la zone de texte, tente de le parser avec `json.loads()`. Si réussi, appelle `self.on_save()` avec les données et détruit la fenêtre. Affiche une `messagebox` en cas d'erreur de parsing JSON.

#### `SettingsWindow(BaseWindow)`
Fenêtre principale des paramètres et du centre de contrôle de l'application.

##### Méthodes

*   `__init__(self, master, task_queue=None)`
    *   **Description**: Initialise la fenêtre des paramètres.
    *   **Arguments**:
        *   `master` (`tk.Widget`): Le widget parent.
        *   `task_queue` (`queue.Queue`, optionnel): Une file d'attente pour communiquer des tâches au système principal (ex: recharger la configuration).
    *   **Logique interne**:
        1.  Charge les paramètres de l'application.
        2.  Initialise les listes de modèles disponibles et les clés de registre des profils abstraits.
        3.  Configure la disposition de la fenêtre avec un `ctk.CTkTabview` pour organiser les paramètres par catégories (Général, API, Swarm, CLI, Système, UI).
        4.  Appelle les méthodes de construction de chaque onglet (`_build_general_tab`, etc.).
        5.  Ajoute une barre d'actions en bas avec des boutons "JSON Brut", "Annuler" et "Sauvegarder & Appliquer".
        6.  Démarre un thread pour les vérifications initiales (`_startup_checks`) après un court délai.

*   `_refresh_combo_values(self)`
    *   **Description**: Met à jour les listes déroulantes de sélection de modèles avec les modèles découverts.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Parcourt les profils abstraits (`registry_keys`) et met à jour les `ctk.CTkComboBox` correspondants avec la liste `self.available_models`, en conservant la valeur actuelle si elle n'est plus dans la nouvelle liste.

*   `destroy(self)`
    *   **Description**: Surcharge la méthode `destroy` pour appeler la version de la classe parente.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Appelle `super().destroy()`.

*   `_startup_checks(self)`
    *   **Description**: Lance les processus d'audit des clés d'API et de découverte des modèles d'IA.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Appelle `_update_available_models` (découverte) puis `_perform_update_cycle` (audit de santé des clés).

*   `_update_available_models(self)`
    *   **Description**: Scanne les clés d'API configurées pour découvrir les modèles d'IA disponibles chez les différents fournisseurs.
    *   **Arguments**: Aucun.
    *   **Logique interne**:
        1.  Initialise un ensemble de modèles déjà connus pour éviter les doublons.
        2.  Appelle `ai_core.keys.discover_models()` pour obtenir les modèles de tous les fournisseurs configurés via le `KeyManager`.
        3.  Ajoute les nouveaux modèles découverts à `self.available_models`.
        4.  Sauvegarde la liste des modèles disponibles dans `self.settings["ai_engine"]["available_models"]`.
        5.  Planifie un appel à `_refresh_combo_values` sur le thread principal pour mettre à jour l'UI.

*   `_add_header(self, parent, text)`
    *   **Description**: Ajoute un titre stylisé à un frame parent.
    *   **Arguments**:
        *   `parent` (`ctk.CTkFrame`): Le frame parent.
        *   `text` (`str`): Le texte du titre.
    *   **Logique interne**: Crée un `ctk.CTkLabel` avec une police et une couleur spécifiques, et le packe.

*   `_add_scroll_frame(self, parent)`
    *   **Description**: Ajoute un frame déroulant à un parent.
    *   **Arguments**:
        *   `parent` (`ctk.CTkFrame`): Le frame parent.
    *   **Retours**: `ctk.CTkScrollableFrame`
    *   **Logique interne**: Crée et packe un `ctk.CTkScrollableFrame`.

*   `_add_combo(self, parent, key, label, options, default)`
    *   **Description**: Ajoute un widget `ctk.CTkComboBox` pour sélectionner une valeur.
    *   **Arguments**:
        *   `parent` (`ctk.CTkFrame`): Le frame parent.
        *   `key` (`str`): La clé de configuration dans le dictionnaire `self.settings`.
        *   `label` (`str`): Le label à afficher pour le contrôle.
        *   `options` (`list`): La liste des options disponibles.
        *   `default` (`any`): La valeur par défaut si non trouvée dans les settings.
    *   **Logique interne**: Crée un `ctk.CTkLabel` et un `ctk.CTkComboBox`. Stocke la variable `ctk.StringVar` et le widget du combobox dans `self.vars`. Nettoie et trie les options, en insérant la valeur actuelle si elle n'est pas déjà présente.

*   `_add_slider(self, parent, key, label, min_val, max_val, default, is_float=False)`
    *   **Description**: Ajoute un widget `ctk.CTkSlider` pour choisir une valeur numérique.
    *   **Arguments**:
        *   `parent` (`ctk.CTkFrame`): Le frame parent.
        *   `key` (`str`): La clé de configuration.
        *   `label` (`str`): Le label.
        *   `min_val` (`int` ou `float`): Valeur minimale du slider.
        *   `max_val` (`int` ou `float`): Valeur maximale du slider.
        *   `default` (`int` ou `float`): Valeur par défaut.
        *   `is_float` (`bool`): Indique si la valeur est un flottant.
    *   **Logique interne**: Crée un `ctk.CTkLabel` (dont le texte se met à jour avec la valeur du slider) et un `ctk.CTkSlider`. Stocke la `tk.DoubleVar` dans `self.vars`.

*   `_add_switch(self, parent, key, label, default)`
    *   **Description**: Ajoute un widget `ctk.CTkSwitch` pour une option binaire.
    *   **Arguments**:
        *   `parent` (`ctk.CTkFrame`): Le frame parent.
        *   `key` (`str`): La clé de configuration.
        *   `label` (`str`): Le label.
        *   `default` (`bool`): Valeur par défaut.
    *   **Logique interne**: Crée et packe un `ctk.CTkSwitch`. Stocke la `ctk.BooleanVar` dans `self.vars`.

*   `_add_entry(self, parent, key, label, default)`
    *   **Description**: Ajoute un widget `ctk.CTkEntry` pour une entrée de texte.
    *   **Arguments**:
        *   `parent` (`ctk.CTkFrame`): Le frame parent.
        *   `key` (`str`): La clé de configuration.
        *   `label` (`str`): Le label.
        *   `default` (`str`): Valeur par défaut.
    *   **Logique interne**: Crée un `ctk.CTkLabel` et un `ctk.CTkEntry`. Stocke la `tk.StringVar` dans `self.vars`.

*   `_build_general_tab(self)`
    *   **Description**: Construit l'interface utilisateur pour l'onglet "Général".
    *   **Arguments**: Aucun.
    *   **Logique interne**: Ajoute des contrôles pour le thème UI, la langue, la taille de police, l'effet de machine à écrire, la visibilité de la barre latérale, et les paramètres des pools de threads.

*   `_build_api_tab_dynamic(self)`
    *   **Description**: Construit l'interface utilisateur pour l'onglet "Moteurs & API".
    *   **Arguments**: Aucun.
    *   **Logique interne**:
        1.  Ajoute des contrôles pour le fournisseur principal et le fallback.
        2.  Crée un `ttk.Treeview` pour la gestion des clés API (nom, provider, clé masquée, statut).
        3.  Fournit des boutons pour ajouter, supprimer et auditer les clés.
        4.  Ajoute des sélecteurs de modèles pour chaque rôle (`registry_keys`) en utilisant les modèles disponibles.

*   `_build_swarm_tab(self)`
    *   **Description**: Construit l'interface utilisateur pour l'onglet "Swarm & Rôles".
    *   **Arguments**: Aucun.
    *   **Logique interne**: Ajoute des contrôles pour le mode swarm, le niveau d'autonomie, la température, le nombre maximal de tokens de sortie, les étapes maximales ReAct, et le mappage des agents vers des profils de modèles.

*   `_build_cli_tab(self)`
    *   **Description**: Construit l'interface utilisateur pour l'onglet "Hybride / CLI".
    *   **Arguments**: Aucun.
    *   **Logique interne**:
        1.  Ajoute un interrupteur pour activer/désactiver le pont CLI.
        2.  Affiche des informations sur l'installation et l'utilisation du CLI.
        3.  Permet de lister les modèles à router via le CLI.
        4.  Inclut un bouton "Vérifier Installation CLI" et un label pour afficher son statut.

*   `_check_cli_installation(self)`
    *   **Description**: Vérifie la présence de l'exécutable `gemini` CLI dans le PATH du système.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Utilise `shutil.which` et des chemins fallback spécifiques à Windows pour localiser le CLI. Met à jour le `cli_status_label` avec le résultat (installé ou non trouvé).

*   `_build_system_code_tab(self)`
    *   **Description**: Construit l'interface utilisateur pour l'onglet "Système & Code".
    *   **Arguments**: Aucun.
    *   **Logique interne**: Ajoute des contrôles pour la sauvegarde avant refactoring, le niveau de scan de sécurité, la configuration des dossiers et fichiers à ignorer, le mode debug, le niveau de logs, les mises à jour au démarrage, la rétention de l'historique, le chemin de la base de données RAG, et les paramètres de compression sémantique.

*   `_build_ui_keys_tab(self)`
    *   **Description**: Construit l'interface utilisateur pour l'onglet "UI & Clés" (raccourcis clavier).
    *   **Arguments**: Aucun.
    *   **Logique interne**: Pour chaque raccourci clavier défini, affiche un label, un champ d'entrée en lecture seule et un bouton "Modifier" qui déclenche la capture d'une nouvelle touche.

*   `_get_val(self, key, default)`
    *   **Description**: Récupère une valeur de paramètre à partir du dictionnaire `self.settings` en utilisant une clé en notation pointée (ex: "ui_settings.theme").
    *   **Arguments**:
        *   `key` (`str`): La clé en notation pointée.
        *   `default` (`any`): La valeur à retourner si la clé n'est pas trouvée.
    *   **Retours**: `any`: La valeur du paramètre ou la valeur par défaut.
    *   **Logique interne**: Parcours le dictionnaire `self.settings` en suivant les parties de la clé.

*   `_refresh_key_tree(self)`
    *   **Description**: Recharge et met à jour le `ttk.Treeview` des clés API.
    *   **Arguments**: Aucun.
    *   **Logique interne**:
        1.  Vide le treeview.
        2.  Migre automatiquement les clés API depuis l'ancienne structure (`api_keys`) si `api_keys_list` est vide.
        3.  Insère chaque clé API de `self.settings["api_keys_list"]` dans le treeview avec un masque pour la clé elle-même et un statut initial "Inconnu".

*   `_add_key_dialog(self)`
    *   **Description**: Ouvre un dialogue modal pour ajouter une nouvelle clé API.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Crée une fenêtre `ctk.CTkToplevel` avec des champs pour le nom, le fournisseur (liste déroulante incluant deepseek, google_gemini, openai, mistral, groq), et la clé API. Le bouton "Sauvegarder" valide les entrées, ajoute la nouvelle clé à `self.settings["api_keys_list"]`, et rafraîchit le treeview.

*   `_delete_key(self)`
    *   **Description**: Supprime la ou les clés API sélectionnées dans le treeview.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Demande une confirmation à l'utilisateur. Si confirmé, filtre `self.settings["api_keys_list"]` pour retirer les clés correspondantes aux éléments sélectionnés du treeview, puis rafraîchit le treeview.

*   `_manual_refresh(self)`
    *   **Description**: Déclenche manuellement un cycle d'audit des connexions et de découverte des modèles.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Met à jour le titre de la fenêtre et lance `_startup_checks` dans un thread séparé.

*   `_perform_update_cycle(self)`
    *   **Description**: Exécute l'audit de santé de tous les fournisseurs d'API configurés.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Appelle `SessionFactory.audit_all_providers()` pour obtenir les rapports de santé des API, puis planifie `_update_tree_status` sur le thread principal pour mettre à jour l'UI.

*   `_update_tree_status(self, reports)`
    *   **Description**: Met à jour la colonne "Statut" du treeview des clés API avec les résultats de l'audit.
    *   **Arguments**:
        *   `reports` (`dict`): Un dictionnaire contenant les rapports de santé des fournisseurs, typiquement le retour de `SessionFactory.audit_all_providers()`.
    *   **Logique interne**: Parcourt les éléments du treeview. Pour chaque clé, retrouve l'entrée complète dans `self.settings["api_keys_list"]` et cherche son rapport correspondant dans `reports` (en utilisant le suffixe de la clé pour l'identification). Met à jour le statut avec un icône et un pourcentage de santé.

*   `_capture_key(self, name, var)`
    *   **Description**: Ouvre le dialogue de capture de touches pour un raccourci spécifique.
    *   **Arguments**:
        *   `name` (`str`): Le nom du raccourci (pour le titre du dialogue).
        *   `var` (`tk.StringVar`): La variable Tkinter associée à l'entrée du raccourci, qui sera mise à jour avec la touche capturée.
    *   **Logique interne**: Crée une instance de `KeyCaptureDialog`.

*   `_open_json_editor(self)`
    *   **Description**: Ouvre l'éditeur JSON avancé.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Crée une instance de `ModelEditorWindow`, lui passant les paramètres actuels et la méthode `save_all_settings` comme callback.

*   `save_all_settings(self, new_data=None)`
    *   **Description**: Sauvegarde tous les paramètres configurés, soit depuis l'interface utilisateur, soit depuis un dictionnaire de données brutes (éditeur JSON).
    *   **Arguments**:
        *   `new_data` (`dict`, optionnel): Un dictionnaire de données JSON si la sauvegarde provient de l'éditeur JSON.
    *   **Logique interne**:
        1.  Si `new_data` est fourni, l'utilise directement.
        2.  Sinon, itère sur `self.vars` pour collecter les valeurs des widgets. Gère spécifiquement les formats de liste pour `ignored_folders` et `cli_bridge.models`.
        3.  Reconstruit le dictionnaire `self.settings["api_keys"]` (pour la compatibilité arrière) à partir de `self.settings["api_keys_list"]`.
        4.  Appelle `save_app_settings(self.settings)` pour écrire les paramètres sur disque.
        5.  Tente d'appliquer le thème UI si modifié.
        6.  Si `task_queue` est présent, y ajoute une tâche "reload_system" pour que le système principal prenne en compte les changements.
        7.  Affiche une `messagebox` de succès ou d'erreur. Détruit la fenêtre en cas de succès.

*   `_show_exclusion_menu(self)`
    *   **Description**: Affiche un menu contextuel pour choisir entre ajouter des fichiers ou un dossier à la liste d'exclusion.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Crée un `tk.Menu` avec les options "Ajouter Fichier(s)..." et "Ajouter Dossier...", puis l'affiche à la position de la souris.

*   `_add_ignore_files(self)`
    *   **Description**: Ouvre une boîte de dialogue pour sélectionner un ou plusieurs fichiers à exclure.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Utilise `filedialog.askopenfilenames`. Si des fichiers sont sélectionnés, appelle `_append_ignore_paths`.

*   `_add_ignore_folder(self)`
    *   **Description**: Ouvre une boîte de dialogue pour sélectionner un dossier à exclure.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Utilise `filedialog.askdirectory`. Si un dossier est sélectionné, appelle `_append_ignore_paths`.

*   `_append_ignore_paths(self, abs_paths)`
    *   **Description**: Convertit les chemins absolus en chemins relatifs (si possible) et les ajoute au champ de texte des exclusions.
    *   **Arguments**:
        *   `abs_paths` (`list`): Une liste de chemins absolus de fichiers ou dossiers.
    *   **Logique interne**:
        1.  Détermine la racine du projet (si configurée, sinon le répertoire de travail actuel).
        2.  Pour chaque chemin absolu, tente de le convertir en chemin relatif par rapport à la racine du projet.
        3.  Normalise les séparateurs de chemin (remplace `\` par `/`).
        4.  Ajoute les chemins (uniques) à la liste existante dans le champ `self.ignore_entry`.
        5.  Met à jour l'affichage du champ de texte.

#### `ApiKeyManager(BaseWindow)`
Classe wrapper obsolète pour la gestion des clés API, désormais intégrée dans `SettingsWindow`.

##### Méthodes

*   `__init__(self, master, task_queue=None)`
    *   **Description**: Initialise le wrapper.
    *   **Arguments**:
        *   `master` (`tk.Widget`): Le widget parent.
        *   `task_queue` (`queue.Queue`, optionnel): Non utilisé directement ici.
    *   **Logique interne**: Affiche un message indiquant que la fonctionnalité a été déplacée et fournit un bouton pour ouvrir la fenêtre `SettingsWindow`.

*   `_open_settings(self)`
    *   **Description**: Ouvre la fenêtre `SettingsWindow`.
    *   **Arguments**: Aucun.
    *   **Logique interne**: Crée une instance de `SettingsWindow` et détruit la fenêtre actuelle.

## 3. Exemple d'usage

```python
import customtkinter as ctk
from ui.windows.settings import SettingsWindow
import queue

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.geometry("400x300")
    root.title("Application Principale")

    # Simuler une file d'attente pour les tâches système
    app_task_queue = queue.Queue()

    def open_settings():
        settings_win = SettingsWindow(root, app_task_queue)
        settings_win.grab_set() # Rendre la fenêtre des settings modale

    ctk.CTkButton(root, text="Ouvrir les Paramètres", command=open_settings).pack(pady=50)

    # Exemple de traitement d'une tâche de la queue (en arrière-plan dans une vraie app)
    def process_tasks():
        try:
            while not app_task_queue.empty():
                task = app_task_queue.get_nowait()
                print(f"Traitement de la tâche: {task}")
                if task.get("type") == "reload_system":
                    print("Rechargement du système demandé par les paramètres...")
                    # Ici, vous déclencheriez la logique de rechargement des services ou de l'UI
        finally:
            root.after(1000, process_tasks) # Vérifier les tâches toutes les secondes

    root.after(100, process_tasks) # Démarrer le traitement des tâches

    root.mainloop()
# Documentation Technique du fichier `ui\explorer.py`

## Description concise

Le module `ui\explorer.py` implémente un widget `FileExplorer` utilisant `customtkinter`. Ce widget sert d'explorateur de fichiers latéral, présentant la structure du projet dans un affichage en arbre (Treeview). Il permet la navigation, l'ouverture de fichiers, et l'exécution d'actions contextuelles sur les fichiers sélectionnés via un menu clic droit. Les actions peuvent être des requêtes à une IA pour analyser, auditer, tester ou refactoriser le code, ainsi que copier les chemins des fichiers.

## Dépendances

*   `customtkinter` (alias `ctk`): Pour la création d'une interface utilisateur moderne.
*   `tkinter` (alias `tk`): Bibliothèque GUI standard de Python, utilisée ici notamment pour le menu contextuel.
*   `tkinter.ttk`: Pour l'utilisation du widget `Treeview` avec un style personnalisé.
*   `os`: Pour les opérations sur le système de fichiers (listing de répertoires, vérification de type de fichier, chemins).
*   `config`: Module local contenant :
    *   `get_path()`: Fonction pour obtenir le chemin racine du projet.
    *   `SUPPORTED_FILE_EXTENSIONS`: Liste des extensions de fichiers supportées pour l'affichage.
*   `ui.widgets.COLORS`: Dictionnaire contenant les couleurs utilisées dans l'interface utilisateur.
*   `ui.icons.IconProvider`: Fournisseur d'icônes pour les dossiers et fichiers.
*   `features.Decorators.trace_action`: Décorateur pour tracer les actions utilisateur.

---

## Classes & Fonctions

### Classe `FileExplorer`

Hérite de `ctk.CTkFrame`.

#### `__init__(self, master, on_file_open, on_context_action, **kwargs)`

*   **Description :** Constructeur de la classe `FileExplorer`. Initialise le widget, configure sa disposition et ses éléments (header, treeview, footer), et charge le contenu initial.
*   **Arguments :**
    *   `master`: Widget parent dans lequel `FileExplorer` sera placé.
    *   `on_file_open` (callable): Fonction de rappel exécutée lorsqu'un fichier est double-cliqué. Reçoit le chemin absolu du fichier en argument.
    *   `on_context_action` (callable): Fonction de rappel exécutée lorsqu'une action contextuelle est sélectionnée. Reçoit une chaîne de caractères formatée (ex: "Analyse de chemin/fichier.py") en argument.
    *   `**kwargs`: Arguments supplémentaires passés au constructeur de `ctk.CTkFrame`.
*   **Logique interne :**
    1.  Appelle le constructeur de la classe parente.
    2.  Stocke les fonctions de rappel `on_file_open` et `on_context_action`.
    3.  Configure le `grid_rowconfigure` et `grid_columnconfigure` pour permettre au widget de s'étendre.
    4.  Appelle `_setup_header()` pour créer l'en-tête du widget.
    5.  Appelle `_setup_treeview()` pour créer et configurer l'arbre de fichiers.
    6.  Crée un bouton "Actualiser" qui appelle la méthode `refresh`.
    7.  Appelle `refresh()` pour charger le contenu initial de l'explorateur.

#### `_setup_header(self)`

*   **Description :** Crée la section d'en-tête du widget `FileExplorer`, affichant le titre "EXPLORATEUR".
*   **Arguments :** Aucun.
*   **Retours :** Aucun.
*   **Logique interne :**
    1.  Crée un `ctk.CTkFrame` pour contenir les éléments de l'en-tête, avec une couleur de fond transparente.
    2.  Positionne ce frame en haut du widget (`row=0`).
    3.  Ajoute un `ctk.CTkLabel` avec le texte "EXPLORATEUR" et une police mise en évidence.
    4.  Utilise `pack(side="left")` pour aligner le label à gauche.
*   **Décorateur :** `@trace_action(source="explorer")`

#### `_setup_treeview(self)`

*   **Description :** Crée et configure le widget `ttk.Treeview` utilisé pour afficher l'arborescence des fichiers.
*   **Arguments :** Aucun.
*   **Retours :** Aucun.
*   **Logique interne :**
    1.  Crée un `ctk.CTkFrame` (`self.tree_frame`) pour contenir le `Treeview` et sa barre de défilement, avec une couleur de fond définie dans `COLORS`.
    2.  Positionne ce frame pour qu'il occupe la majeure partie de l'espace disponible (`row=1`, `sticky="nsew"`).
    3.  Configure le style du `ttk.Treeview` (couleurs de fond, premier plan, sélection).
    4.  Instancie le `ttk.Treeview` (`self.tree`) avec `show="tree"` pour afficher uniquement la hiérarchie et `selectmode="extended"` pour permettre la sélection multiple.
    5.  Associe des événements (`<Double-1>`, `<Button-3>`, `<<TreeviewOpen>>`) à des méthodes de rappel (`_on_double_click`, `_on_right_click`, `_on_expand`).
    6.  Crée une `ctk.CTkScrollbar` et la lie au `Treeview` pour permettre le défilement vertical.
*   **Décorateur :** `@trace_action(source="explorer")`

#### `refresh(self)`

*   **Description :** Recharge le contenu de l'explorateur de fichiers à partir de la racine du projet.
*   **Arguments :** Aucun.
*   **Retours :** Aucun.
*   **Logique interne :**
    1.  Appelle `_populate_tree` avec une chaîne vide comme parent et le chemin racine du projet (obtenu via `get_path('.')`).
*   **Décorateur :** `@trace_action(source="explorer")`

#### `_populate_tree(self, parent, path)`

*   **Description :** Remplit le `Treeview` avec le contenu d'un répertoire donné.
*   **Arguments :**
    *   `parent` (str): L'identifiant de l'élément parent dans le `Treeview` où les nouveaux éléments doivent être insérés. Si vide, les enfants de la racine sont supprimés et remplis.
    *   `path` (str): Le chemin absolu du répertoire à lister.
*   **Retours :** Aucun.
*   **Logique interne :**
    1.  Supprime les enfants existants de `parent` (soit tous les enfants si `parent` est vide, soit les enfants d'un répertoire spécifique).
    2.  Tente de lister le contenu du répertoire `path`.
    3.  Trie les éléments : les répertoires en premier, puis les fichiers, le tout par ordre alphabétique insensible à la casse.
    4.  Itère sur chaque `item` du répertoire :
        *   Ignore les éléments commençant par `.` (fichiers cachés) et le répertoire `__pycache__`.
        *   Construit le chemin absolu `abspath`.
        *   Détermine si l'élément est un répertoire (`is_dir`).
        *   Si ce n'est pas un répertoire et que son extension n'est pas supportée (`SUPPORTED_FILE_EXTENSIONS`), ignore l'élément.
        *   Récupère l'icône appropriée (dossier ou fichier) via `IconProvider`.
        *   Insère l'élément dans le `Treeview` (`self.tree.insert`). Les valeurs stockées incluent le chemin absolu et le type ("dir" ou "file").
        *   Si c'est un répertoire, insère un élément "dummy" ("loading...") pour permettre l'extension/rétraction et indiquer que le contenu n'a pas encore été chargé.
    5.  Gère les exceptions (par exemple, permissions refusées) en passant simplement.
*   **Décorateur :** `@trace_action(source="explorer")`

#### `_on_expand(self, event)`

*   **Description :** Gère l'événement `<<TreeviewOpen>>`, qui est déclenché lorsqu'un nœud de répertoire est ouvert (agrandi). Recharge le contenu du répertoire concerné.
*   **Arguments :**
    *   `event`: L'objet événement tkinter.
*   **Retours :** Aucun.
*   **Logique interne :**
    1.  Obtient l'identifiant de l'élément actuellement mis en avant (`self.tree.focus()`).
    2.  Récupère les valeurs associées à cet élément.
    3.  Si l'élément est un répertoire (`values[1] == "dir"`), appelle `_populate_tree` pour charger son contenu, en utilisant l'identifiant de l'élément comme parent et son chemin absolu comme chemin à lister.
*   **Décorateur :** `@trace_action(source="explorer")`

#### `_on_double_click(self, event)`

*   **Description :** Gère l'événement de double-clic sur un élément du `Treeview`. Si l'élément est un fichier, appelle la fonction de rappel `on_file_open`.
*   **Arguments :**
    *   `event`: L'objet événement tkinter.
*   **Retours :** Aucun.
*   **Logique interne :**
    1.  Identifie la ligne (`item`) sous le curseur de la souris. Si aucun élément n'est trouvé, retourne.
    2.  Récupère les valeurs de l'élément sélectionné.
    3.  Si l'élément est un fichier (`values[1] == "file"`) et que la fonction `on_file_open` a été fournie, appelle `self.on_file_open` avec le chemin absolu du fichier (`values[0]`).
*   **Décorateur :** `@trace_action(source="explorer")`

#### `_on_right_click(self, event)`

*   **Description :** Gère l'événement de clic droit sur un élément du `Treeview`. Affiche un menu contextuel offrant diverses actions sur les fichiers sélectionnés.
*   **Arguments :**
    *   `event`: L'objet événement tkinter.
*   **Retours :** Aucun.
*   **Logique interne :**
    1.  Identifie la ligne (`item`) sous le curseur. Si aucun élément n'est trouvé, retourne.
    2.  Gère la sélection : si l'élément cliqué n'est pas déjà sélectionné, il est ajouté à la sélection actuelle.
    3.  Collecte tous les chemins absolus des éléments actuellement sélectionnés. Si aucun chemin n'est trouvé, retourne.
    4.  Convertit les chemins absolus en chemins relatifs au répertoire racine du projet (`get_path('.')`).
    5.  Formate les chemins relatifs en une chaîne de caractères (`paths_str`).
    6.  Crée un menu contextuel `tk.Menu`.
    7.  Définit une fonction interne `trigger_action(prefix)` qui appelle `self.on_context_action` avec un préfixe donné et la chaîne des chemins de fichiers. Cette fonction est décorée avec `@trace_action`.
    8.  Ajoute des commandes au menu contextuel :
        *   "🔍 Analyser / Expliquer"
        *   "🛡️ Audit Qualité & Sécurité"
        *   "🧪 Générer Tests"
        *   "🔨 Refactoriser"
        Chacune de ces commandes appelle `trigger_action` avec le préfixe approprié.
        *   "📝 Copier chemin(s)" qui copie `paths_str` dans le presse-papiers système.
    9.  Affiche le menu contextuel à la position du clic droit (`event.x_root`, `event.y_root`).
*   **Décorateur :** `@trace_action(source="explorer")`

---

## Exemple d'usage

```python
import customtkinter as ctk
import tkinter as tk
from ui.explorer import FileExplorer

# Fonctions de rappel pour les actions
def open_file_in_editor(filepath):
    print(f"Ouvrir le fichier : {filepath}")
    # Ici, vous intégreriez la logique pour ouvrir le fichier dans votre éditeur

def send_to_ai(prompt):
    print(f"Envoyer à l'IA : {prompt}")
    # Ici, vous intégreriez la logique pour envoyer le prompt à un modèle IA

if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Exemple FileExplorer")
    root.geometry("600x400")

    # Création du FileExplorer
    explorer = FileExplorer(root, on_file_open=open_file_in_editor, on_context_action=send_to_ai)
    explorer.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    # Ajouter un espace pour d'autres widgets si nécessaire
    main_frame = ctk.CTkFrame(root)
    main_frame.pack(side="right", fill="both", expand=True)
    ctk.CTkLabel(main_frame, text="Contenu principal").pack(pady=20)

    # Assurez-vous que le chemin courant est un répertoire de projet valide
    # ou que get_path('.') retourne un chemin approprié.

    root.mainloop()
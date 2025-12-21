# Documentation Technique : ui\syntax.py

## Description concise

Ce module gère la coloration syntaxique pour l'éditeur de code et les blocs de code dans le chat. Il utilise la bibliothèque `pygments` pour analyser le code source et appliquer des styles prédéfinis basés sur les types de tokens. Il définit également une palette de couleurs personnalisée pour un thème sombre.

## Dépendances

*   `tkinter` : Pour les widgets d'interface utilisateur.
*   `logging` : Pour la journalisation.
*   `pygments`:
    *   `lex` : Fonction pour générer des tokens à partir du code.
    *   `get_lexer_by_name` : Pour obtenir un lexer par son nom.
    *   `get_lexer_for_filename` : Pour obtenir un lexer en fonction du nom du fichier.
    *   `guess_lexer` : Pour deviner le lexer approprié si le nom du fichier ou le nom du langage ne sont pas spécifiés.
    *   `Token` : Types de tokens génériques.
    *   `Comment`, `Keyword`, `Name`, `String`, `Error`, `Number`, `Operator`, `Generic`, `Literal`, `Punctuation` : Types de tokens spécifiques.
    *   `NotFound` : Exception levée si un lexer n'est pas trouvé.
*   `features.Decorators.trace_action` : Un décorateur pour tracer les actions.

---

## Classes & Fonctions

### Constantes globales

#### `SYNTAX_COLORS`

*   **Type:** Dictionnaire
*   **Description:** Définit la palette de couleurs pour chaque type de token `pygments`. Le thème est inspiré de "Monokai" avec une dominante sombre.
*   **Structure:**
    ```python
    {
        Token: '#F8F8F2',
        Keyword: '#F92672',
        # ... autres mappings Token -> couleur hexadécimale
    }
    ```

#### `DEFAULT_COLOR`

*   **Type:** Chaîne de caractères
*   **Description:** Couleur par défaut utilisée si une couleur spécifique n'est pas trouvée dans `SYNTAX_COLORS`. C'est une couleur blanc cassé (#F8F8F2).

### Fonctions

#### `get_lexer(filename=None, lang_name=None, code_content=None)`

*   **Description:** Obtient le 'lexer' Pygments approprié en fonction des arguments fournis. Tente d'abord par le nom du langage, puis par le nom du fichier, et enfin devine le lexer à partir du contenu du code. Si aucun lexer n'est trouvé, il retourne le lexer pour le type de fichier 'text'.
*   **Arguments:**
    *   `filename` (str, optionnel): Le nom du fichier pour lequel obtenir le lexer.
    *   `lang_name` (str, optionnel): Le nom du langage de programmation (par exemple, 'python', 'javascript').
    *   `code_content` (str, optionnel): Le contenu du code source à analyser pour deviner le lexer.
*   **Retour:**
    *   Un objet lexer Pygments correspondant au langage du code, ou le lexer 'text' par défaut.
*   **Logique interne:**
    1.  Essaie d'obtenir le lexer en utilisant `get_lexer_by_name(lang_name)` si `lang_name` est fourni. Intercepte `ClassNotFound`.
    2.  Si le premier essai échoue ou n'est pas effectué, essaie d'obtenir le lexer en utilisant `get_lexer_for_filename(filename)` si `filename` est fourni. Intercepte `ClassNotFound`.
    3.  Si les deux tentatives précédentes échouent, utilise `guess_lexer()` avec le contenu du code (`code_content`), puis le nom du fichier (`filename`) si `code_content` est vide. Intercepte `ClassNotFound`.
    4.  En cas d'échec de toutes les tentatives, retourne `get_lexer_by_name("text")`.
*   **Décorateur:** `@trace_action(source="syntax")`

#### `configure_tags(textbox)`

*   **Description:** Applique la configuration de couleur (foreground) à chaque tag dans un widget `tk.Text`. Les noms des tags sont dérivés des types de tokens `pygments`.
*   **Arguments:**
    *   `textbox` (tk.Text): Le widget de texte Tkinter dont les tags doivent être configurés.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Itère sur chaque paire `(token, color)` dans `SYNTAX_COLORS`.
    2.  Convertit le type de token en chaîne de caractères pour l'utiliser comme nom de tag.
    3.  Applique la couleur de premier plan (`foreground`) spécifiée au tag correspondant dans le `textbox` à l'aide de `textbox.tag_config()`.
    4.  Applique des configurations spécifiques pour `Token.Literal` et `Token.Name`, en utilisant les couleurs définies pour `String` et `Name` respectivement dans `SYNTAX_COLORS`, ou la `DEFAULT_COLOR` si elles ne sont pas trouvées.
*   **Décorateur:** `@trace_action(source="syntax")`

#### `apply_highlighting_to_editor(textbox, code, lexer)`

*   **Description:** Efface le contenu actuel d'un widget `tk.Text` et applique la coloration syntaxique à tout le code fourni en utilisant le lexer spécifié.
*   **Arguments:**
    *   `textbox` (tk.Text): Le widget de texte Tkinter de l'éditeur.
    *   `code` (str): Le contenu du code source à colorer.
    *   `lexer`: L'objet lexer Pygments à utiliser pour l'analyse.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Appelle `configure_tags(textbox)` pour s'assurer que tous les styles de coloration sont appliqués.
    2.  Configure l'état du `textbox` à `tk.NORMAL` pour permettre les modifications.
    3.  Supprime tout le contenu existant du `textbox` avec `textbox.delete("1.0", tk.END)`.
    4.  Utilise `lex(code, lexer)` pour itérer sur les paires `(token_type, token_string)` du code.
    5.  Pour chaque token, convertit `token_type` en chaîne de caractères pour obtenir le `tag_name`.
    6.  Insère le `token_string` dans le `textbox` à la fin (`tk.END`) en lui associant le `tag_name` approprié.
    7.  Configure l'état du `textbox` à `tk.NORMAL` (cela semble redondant car il est déjà réglé sur NORMAL avant la boucle, mais est présent dans le code source).
*   **Décorateur:** `@trace_action(source="syntax")`

#### `highlight_code_block_in_chat(textbox, code_content, lexer)`

*   **Description:** Insère un bloc de code formaté avec coloration syntaxique dans un widget `tk.Text`, typiquement utilisé pour afficher du code dans une zone de chat. Le code est entouré de séparateurs (`-----`).
*   **Arguments:**
    *   `textbox` (tk.Text): Le widget de texte Tkinter de la zone de chat.
    *   `code_content` (str): Le contenu du bloc de code à colorer.
    *   `lexer`: L'objet lexer Pygments à utiliser pour l'analyse.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Appelle `configure_tags(textbox)` pour s'assurer que les styles de coloration sont disponibles.
    2.  Insère un saut de ligne suivi de 80 tirets (`\n` + `"-"*80` + `\n`) pour marquer le début du bloc de code.
    3.  Itère sur les paires `(token_type, token_string)` générées par `lex(code_content, lexer)`.
    4.  Pour chaque token, obtient le `tag_name` à partir de `token_type`.
    5.  Insère le `token_string` dans le `textbox` à la fin (`tk.END`) avec le `tag_name` associé.
    6.  Insère un saut de ligne suivi de 80 tirets (`\n` + `"-"*80` + `\n\n`) pour marquer la fin du bloc de code et ajouter des sauts de ligne supplémentaires.
*   **Décorateur:** `@trace_action(source="syntax")`

---

## Exemple d'usage

```python
import tkinter as tk
from ui.syntax import get_lexer, configure_tags, apply_highlighting_to_editor, highlight_code_block_in_chat

# Initialisation de Tkinter
root = tk.Tk()
root.title("Syntax Highlighting Demo")

# Création d'un widget Text pour l'éditeur
editor_textbox = tk.Text(root, wrap=tk.WORD, height=15, width=80)
editor_textbox.pack(pady=10)

# Contenu de code exemple
sample_code = """
def hello_world():
    # Ceci est un commentaire
    message = "Bonjour, le monde !"
    print(message)
    return 123

class MyClass:
    def __init__(self):
        self.value = "test"
"""

# Obtention du lexer pour Python
python_lexer = get_lexer(lang_name="python")

# Application de la coloration syntaxique à l'éditeur
apply_highlighting_to_editor(editor_textbox, sample_code, python_lexer)

# Création d'un widget Text pour simuler une zone de chat
chat_textbox = tk.Text(root, wrap=tk.WORD, height=10, width=80)
chat_textbox.pack(pady=10)

# Contenu de code à afficher dans le chat
chat_code_block = """
if __name__ == "__main__":
    print("Exécution du script.")
"""

# Obtention du lexer pour le bloc de chat (peut être le même ou deviné)
chat_lexer = get_lexer(code_content=chat_code_block, filename="script.py") # Utilisation du filename pour aider à deviner

# Affichage du bloc de code coloré dans le chat
highlight_code_block_in_chat(chat_textbox, chat_code_block, chat_lexer)

root.mainloop()
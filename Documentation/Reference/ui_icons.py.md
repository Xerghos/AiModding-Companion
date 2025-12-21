# Documentation Technique: `ui\icons.py`

## Description concise

Ce module stocke les icônes graphiques sous forme de données encodées en Base64. L'objectif est d'éviter toute dépendance à des fichiers externes (.png, .ico), rendant l'application plus autonome.

## Dépendances

*   `tkinter` (alias `tk`) : Bibliothèque standard de Python pour l'interface graphique.
*   `features.Decorators.trace_action` : Un décorateur personnalisé pour tracer les actions.

---

## Classes & Fonctions

### Classe `IconProvider`

**Description:**

Cette classe agit comme un singleton pour charger les objets `tk.PhotoImage` à partir des données Base64. Elle s'assure que chaque icône n'est chargée qu'une seule fois en mémoire, optimisant ainsi les performances. Elle nécessite qu'une instance de `tk.Tk()` ait déjà été créée avant son utilisation.

#### Méthode de classe `get_folder_icon(cls)`

*   **Signature:** `get_folder_icon(cls)`
*   **Arguments:**
    *   `cls` : La classe elle-même (`IconProvider`).
*   **Retourne:** Un objet `tk.PhotoImage` représentant l'icône du dossier.
*   **Logique interne:**
    1.  Vérifie si l'attribut de classe `_folder_icon` est déjà défini (c'est-à-dire, si l'icône a déjà été chargée).
    2.  Si `_folder_icon` est `None`, une nouvelle instance de `tk.PhotoImage` est créée en utilisant la chaîne de données `FOLDER_ICON_DATA` et assignée à `cls._folder_icon`.
    3.  L'objet `tk.PhotoImage` stocké dans `cls._folder_icon` est retourné.
    4.  Le décorateur `@trace_action(source="icons")` est appliqué, ce qui implique que l'appel à cette méthode sera probablement enregistré ou tracé.

#### Méthode de classe `get_file_icon(cls)`

*   **Signature:** `get_file_icon(cls)`
*   **Arguments:**
    *   `cls` : La classe elle-même (`IconProvider`).
*   **Retourne:** Un objet `tk.PhotoImage` représentant l'icône du fichier.
*   **Logique interne:**
    1.  Vérifie si l'attribut de classe `_file_icon` est déjà défini (c'est-à-dire, si l'icône a déjà été chargée).
    2.  Si `_file_icon` est `None`, une nouvelle instance de `tk.PhotoImage` est créée en utilisant la chaîne de données `FILE_ICON_DATA` et assignée à `cls._file_icon`.
    3.  L'objet `tk.PhotoImage` stocké dans `cls._file_icon` est retourné.
    4.  Le décorateur `@trace_action(source="icons")` est appliqué, ce qui implique que l'appel à cette méthode sera probablement enregistré ou tracé.

---

## Exemple d'usage

```python
import tkinter as tk
from ui.icons import IconProvider

# Assurez-vous qu'une instance Tkinter est créée
root = tk.Tk()

# Obtenir l'icône du dossier
folder_icon = IconProvider.get_folder_icon()

# Obtenir l'icône du fichier
file_icon = IconProvider.get_file_icon()

# Exemple d'utilisation avec un Label (pour illustration)
# Note: L'image doit rester référencée pour ne pas être garbage collectée
label_with_icon = tk.Label(root, image=folder_icon)
label_with_icon.pack()

# Maintenir l'application Tkinter en cours d'exécution
# root.mainloop()
# Documentation Technique : `config/paths.py`

## Description concise

Ce module fournit des utilitaires pour construire des chemins de fichiers absolus relatifs à la racine du projet. Il est essentiel pour assurer que le code peut accéder aux ressources (données, configurations, etc.) de manière indépendante de l'emplacement d'exécution du script.

## Dépendances

*   `os`
*   `sys`

---

## Classes & Fonctions

### `get_path(filename)`

*   **Signature :** `get_path(filename)`
*   **Arguments :**
    *   `filename` (str) : Le nom du fichier ou du sous-répertoire dont on souhaite obtenir le chemin absolu.
*   **Retours :**
    *   `str` : Le chemin absolu complet du fichier spécifié, basé sur la racine du projet.
*   **Logique interne :**
    1.  Détermine la racine du projet. Si le fichier est exécuté directement, il remonte deux niveaux à partir de son propre emplacement (`__file__`). Dans le cas où `__file__` n'est pas défini (par exemple, lors d'une exécution interactive ou si le script est lancé d'une manière qui masque cette variable), il utilise le premier argument de la ligne de commande (`sys.argv[0]`) ou le répertoire courant (`.`) comme référence pour déterminer la racine.
    2.  Utilise `os.path.join()` pour concaténer la racine du projet (`project_root`) avec le nom de fichier fourni (`filename`) afin de construire le chemin absolu.

---

## Exemple d'usage

```python
# Supposons que ce code soit exécuté depuis n'importe quel répertoire du projet.
# Le fichier 'config/paths.py' est accessible et importé.

import config.paths as paths

# Pour obtenir le chemin absolu du répertoire 'data'
data_dir_path = paths.get_path("data")
print(f"Chemin du répertoire data : {data_dir_path}")

# Pour obtenir le chemin absolu d'un fichier de configuration nommé 'settings.yaml'
settings_file_path = paths.get_path("config/settings.yaml")
print(f"Chemin du fichier de configuration : {settings_file_path}")

# Exemple concret où la racine du projet est '/home/user/mon_projet'
# et get_path("data") est appelé :
# Retourné sera : '/home/user/mon_projet/data'

# Exemple concret où la racine du projet est '/home/user/mon_projet'
# et get_path("config/settings.yaml") est appelé :
# Retourné sera : '/home/user/mon_projet/config/settings.yaml'
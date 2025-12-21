# Documentation Technique : tests\test_filesystem_resolver.py

## Description concise

Ce fichier contient les tests unitaires pour la fonctionnalité de résolution de fichiers potentiellement imprécise (fuzzy matching) du module `FileSystem`. Il vise à vérifier que le système peut localiser et lire des fichiers même lorsque le nom fourni n'est pas exact, en se basant sur des heuristiques ou des correspondances partielles.

## Dépendances

*   `unittest`: Framework de test Python standard.
*   `os`: Module pour interagir avec le système d'exploitation (chemins, etc.).
*   `sys`: Module pour accéder aux paramètres et fonctions spécifiques au système (gestion du chemin d'accès).
*   `shutil`: Module pour les opérations de haut niveau sur les fichiers et collections de fichiers.
*   `tempfile`: Module pour créer des fichiers et répertoires temporaires.
*   `unittest.mock.patch`: Outil pour patcher (remplacer temporairement) des objets lors des tests.
*   `features.FileSystem`: Module contenant les fonctions `lire_fichier` et `get_path` testées.
*   `features.SearchEngine`: Module dont le `get_path` est également patché car il est utilisé par le `FileSystem`.

---

## Classes & Fonctions

### Classe `TestFileSystemResolver`

Hérite de `unittest.TestCase`. Cette classe regroupe les tests pour la résolution de fichiers.

#### Méthode `setUp(self)`

*   **Signature:** `setUp(self)`
*   **Arguments:** Aucun.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Crée un répertoire temporaire (`self.test_dir`) pour isoler les tests du système de fichiers réel.
    2.  Crée un fichier de test nommé `secret_data.json` dans le répertoire temporaire avec un contenu factice ("TOP SECRET CONTENT").
    3.  Met en place un "patch" sur la fonction `features.FileSystem.get_path`. Ce patch fait en sorte que toute tentative d'appel à `get_path` renvoie un chemin combiné avec le répertoire temporaire (`self.test_dir`). Ceci est crucial pour que les tests fonctionnent dans un environnement contrôlé.
    4.  Met en place un deuxième patch sur la fonction `features.SearchEngine.get_path` pour la même raison que la précédente, car `FileSystem` peut potentiellement utiliser cette fonction via `SearchEngine`.
    5.  Stocke les objets de patch (`self.patcher`, `self.patcher_search`) pour pouvoir les arrêter plus tard.

#### Méthode `tearDown(self)`

*   **Signature:** `tearDown(self)`
*   **Arguments:** Aucun.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Arrête les patches (`self.patcher.stop()`, `self.patcher_search.stop()`) qui ont été démarrés dans `setUp`. Cela restaure les fonctions originales.
    2.  Supprime le répertoire temporaire créé (`self.test_dir`) et tout son contenu pour nettoyer l'environnement de test.

#### Méthode `test_lecture_avec_resolution_automatique(self)`

*   **Signature:** `test_lecture_avec_resolution_automatique(self)`
*   **Arguments:** Aucun.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Simule le scénario où l'utilisateur demande à lire un fichier avec un nom incomplet ou sans extension (`"secret_data"`).
    2.  Appelle `FS.lire_fichier` avec ce nom incomplet.
    3.  Vérifie que le contenu retourné par `lire_fichier` est bien le contenu attendu ("TOP SECRET CONTENT"), démontrant que la résolution automatique (probablement via une logique floue ou par ajout d'extensions courantes) a fonctionné.
    4.  Affiche un message de succès.

#### Méthode `test_echec_si_introuvable(self)`

*   **Signature:** `test_echec_si_introuvable(self)`
*   **Arguments:** Aucun.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Tente de lire un fichier avec un nom qui est certain de ne pas exister dans l'environnement de test (`"fichier_imaginaire_total"`).
    2.  Vérifie que la chaîne retournée par `FS.lire_fichier` contient le mot "Erreur", indiquant que l'échec de lecture a été géré correctement et qu'une indication d'erreur est remontée.
    3.  Affiche un message de succès.

---

## Exemple d'usage

Bien que ce fichier contienne des tests, l'utilisation typique de la fonctionnalité qu'il teste serait la suivante (depuis un autre module, par exemple) :

```python
# Supposons que FS est importé comme 'import features.FileSystem as FS'
# et que le système de fichiers a un fichier nommé 'config.json'

# Lecture directe si le nom est exact
contenu_exact = FS.lire_fichier("config.json")

# Lecture avec nom imprécis, la résolution automatique devrait trouver 'config.json'
contenu_imprecis = FS.lire_fichier("config")
```

Les tests dans `test_filesystem_resolver.py` valident que le `contenu_imprecis` sera correctement récupéré, même si le nom fourni à `lire_fichier` n'est pas complet.
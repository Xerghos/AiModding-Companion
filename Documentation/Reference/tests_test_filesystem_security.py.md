# Documentation technique du fichier `tests\test_filesystem_security.py`

## Description concise

Ce fichier contient des tests unitaires pour la classe `FileSystem` (présumée être importée depuis `features.FileSystem`) axés sur la sécurité, en particulier sur la manière dont les fichiers sont gérés lors de leur écriture. Les tests vérifient que le code Python invalide est rejeté et que le code valide est correctement traité et indexé.

## Dépendances

*   `unittest`: Bibliothèque standard Python pour l'écriture de tests unitaires.
*   `shutil`: Fournit des opérations de haut niveau sur les fichiers et les collections de fichiers.
*   `tempfile`: Génère des fichiers et des répertoires temporaires.
*   `os`: Interface pour interagir avec le système d'exploitation.
*   `sys`: Accès à certaines variables utilisées ou gérées par l'interpréteur Python.
*   `unittest.mock.MagicMock`, `unittest.mock.patch`: Outils pour simuler des objets et des fonctions pendant les tests.
*   `features.FileSystem`: Module contenant la logique à tester (`ecrire_fichier` et potentiellement `get_path`).

---

## Classes & Fonctions

### Classe `TestFileSystemSecurity`

Hérite de `unittest.TestCase`. Cette classe regroupe les tests pour la sécurité du système de fichiers.

#### Méthode `setUp(self)`

*   **Signature:** `setUp(self)`
*   **Arguments:** Aucun.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Crée un répertoire temporaire (`self.test_dir`) pour isoler les opérations de fichier pendant le test.
    2.  Met en place des *mocks* (simulations) pour les dépendances optionnelles :
        *   `features.FileSystem.database` (`self.patcher_db`, `self.mock_db`) : Permet de vérifier les interactions avec la base de données (comme l'indexation de fichiers).
        *   `features.FileSystem.backup_manager` (`self.patcher_backup`, `self.mock_backup`) : Permet de vérifier les interactions avec un gestionnaire de sauvegarde (bien que non utilisé dans les tests présents).
    3.  Redirige la fonction `features.FileSystem.get_path` pour qu'elle retourne des chemins absolus basés sur le répertoire temporaire (`self.test_dir`). Cela garantit que les tests n'écrivent pas dans des emplacements système sensibles.
    4.  Démarre les *mocks* et les *patches*.

#### Méthode `tearDown(self)`

*   **Signature:** `tearDown(self)`
*   **Arguments:** Aucun.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Arrête les *mocks* et les *patches* démarrés dans `setUp`.
    2.  Supprime le répertoire temporaire (`self.test_dir`) et tout son contenu pour nettoyer l'environnement de test.

#### Méthode `test_ecriture_python_valide(self)`

*   **Signature:** `test_ecriture_python_valide(self)`
*   **Arguments:** Aucun.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Définit un nom de fichier (`chemin`) et un code Python valide (`code`).
    2.  Appelle `FS.ecrire_fichier(chemin, code)`.
    3.  Vérifie que la réponse de `ecrire_fichier` indique un succès (insensible à la casse).
    4.  Vérifie que le fichier spécifié existe réellement dans le répertoire temporaire.
    5.  Vérifie que la méthode `add_file_to_db` du *mock* `self.mock_db` a été appelée avec le nom du fichier, indiquant que le fichier valide a été correctement indexé.

#### Méthode `test_ecriture_python_invalide(self)`

*   **Signature:** `test_ecriture_python_invalide(self)`
*   **Arguments:** Aucun.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Définit un nom de fichier (`chemin`) et un code Python intentionnellement invalide (`code_pourri`) (manque un deux-points).
    2.  Appelle `FS.ecrire_fichier(chemin, code_pourri)`.
    3.  Vérifie que la réponse de `ecrire_fichier` indique une erreur de syntaxe et un rejet (insensible à la casse).
    4.  Vérifie que le fichier spécifié N'EXISTE PAS dans le répertoire temporaire.
    5.  Vérifie que la méthode `add_file_to_db` du *mock* `self.mock_db` n'a PAS été appelée, confirmant que le fichier invalide n'a pas été indexé.

#### Méthode `test_ecriture_texte_standard(self)`

*   **Signature:** `test_ecriture_texte_standard(self)`
*   **Arguments:** Aucun.
*   **Retour:** Aucun.
*   **Logique interne:**
    1.  Définit un nom de fichier (`chemin`) et un contenu texte standard (`contenu`).
    2.  Appelle `FS.ecrire_fichier(chemin, contenu)`.
    3.  Vérifie que la réponse de `ecrire_fichier` indique un succès.
    4.  Vérifie que le fichier texte existe bien dans le répertoire temporaire, confirmant que les fichiers non-Python ne subissent pas la validation syntaxique du code.

---

## Exemple d'usage

Pour exécuter ces tests, assurez-vous d'avoir le répertoire `features` à la racine de votre projet, contenant `FileSystem.py`. Ensuite, exécutez le script Python depuis la racine du projet :

```bash
python -m unittest tests/test_filesystem_security.py
```

Ou si le script est exécuté directement :

```bash
python tests/test_filesystem_security.py
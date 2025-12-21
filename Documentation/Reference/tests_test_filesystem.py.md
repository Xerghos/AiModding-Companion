# Documentation Technique : `tests\test_filesystem.py`

## Description

Ce fichier contient les tests unitaires pour les fonctionnalités du module `features.FileSystem`. Il utilise le framework `unittest` de Python pour simuler des interactions avec le système de fichiers dans un environnement isolé (sandbox) afin de garantir que les fonctions de manipulation de fichiers (lecture, écriture, suppression, liste) se comportent comme prévu sans affecter le système de fichiers réel.

## Dépendances

*   `unittest` : Framework de tests unitaires de Python.
*   `shutil` : Fournit des opérations de haut niveau sur les fichiers et collections de fichiers.
*   `tempfile` : Génère des fichiers et dossiers temporaires.
*   `os` : Fournit un moyen d'utiliser des fonctionnalités dépendant du système d'exploitation.
*   `sys` : Permet de modifier le chemin de recherche des modules.
*   `pathlib.Path` : Interface orientée objet pour le système de fichiers.
*   `unittest.mock` : Outil pour créer des mocks, stubs et autres objets de test.
*   `features.FileSystem` : Le module dont les fonctionnalités sont testées.
*   `features.core_backup` : Utilisé pour le mock de la fonction `create_backup`.
*   `features.Shared` : Utilisé pour le mock de la fonction `log_action`.
*   `features.ai_helper` : Utilisé pour le mock de la fonction `_security_check`.

---

## Classes & Fonctions

### Classe `TestFileSystem`

Hérite de `unittest.TestCase`. Cette classe regroupe les tests pour le module `features.FileSystem`.

#### Méthode `setUp(self)`

**Description :**
Prépare l'environnement de test avant l'exécution de chaque méthode de test. Cela inclut la création d'un répertoire temporaire (sandbox), la configuration du répertoire de travail actuel, et la création de mocks pour les dépendances externes (session, file d'attente de résultats, file d'attente de tâches, chemin de log) ainsi que pour des fonctions du système de fichiers critiques (`get_path`, `_security_check`).

**Arguments :**
Aucun.

**Retours :**
Aucun.

**Logique interne :**
1.  Crée un répertoire temporaire à l'aide de `tempfile.mkdtemp()` et stocke son chemin dans `self.test_dir`.
2.  Sauvegarde le répertoire de travail actuel dans `self.original_cwd`.
3.  Crée des instances `MagicMock` pour `self.mock_session`, `self.mock_queue` (résultats) et `self.mock_task_queue` (tâches).
4.  Définit un chemin de log fictif `self.mock_log_path`.
5.  Prépare un dictionnaire `self.sys_args` contenant les mocks et le chemin de log, qui sera passé aux fonctions du module `FileSystem`.
6.  Utilise `unittest.mock.patch` pour :
    *   Remplacer `features.core_backup.create_backup` par un mock (`self.mock_backup`).
    *   Remplacer `features.Shared.log_action` par un mock (`self.mock_log`).
    *   Remplacer `features.FileSystem.get_path` par un mock (`self.mock_get_path`). La logique de ce mock est définie pour retourner le répertoire temporaire (`self.test_dir`) lorsque le chemin demandé est ".", et le chemin combiné (`os.path.join(self.test_dir, path_rel)`) dans les autres cas. Ceci assure que toutes les opérations de fichier ciblent la sandbox.
    *   Remplacer `features.ai_helper._security_check` par un mock qui ne fait rien (`return_value=None`), car le répertoire temporaire n'est pas un chemin de projet valide pour la vérification de sécurité.
7.  Démarre tous les patchs.

#### Méthode `tearDown(self)`

**Description :**
Nettoie l'environnement de test après l'exécution de chaque méthode de test. Cela inclut la suppression du répertoire temporaire créé et l'arrêt des patchs appliqués.

**Arguments :**
Aucun.

**Retours :**
Aucun.

**Logique interne :**
1.  Supprime récursivement le répertoire temporaire `self.test_dir` à l'aide de `shutil.rmtree()`.
2.  Arrête tous les patchs démarrés dans `setUp()` en appelant leur méthode `stop()`.

#### Méthode `test_ecrire_et_lire_fichier(self)`

**Description :**
Teste la fonctionnalité combinée d'écriture et de lecture d'un fichier simple.

**Arguments :**
Aucun.

**Retours :**
Aucun.

**Logique interne :**
1.  Définit un nom de fichier (`nom_fichier`) et un contenu (`contenu`).
2.  Appelle `FS.execute_ecrire_fichier()` avec le nom du fichier, le contenu et les arguments système préparés (`self.sys_args`).
3.  Vérifie que le résultat de l'écriture contient le mot "succès" (insensible à la casse).
4.  Vérifie que le fichier a été physiquement créé dans la sandbox à l'emplacement attendu (`os.path.join(self.test_dir, nom_fichier)`).
5.  Appelle `FS.execute_lire_fichier()` avec le nom du fichier et les arguments système.
6.  Vérifie que le contenu lu correspond exactement au contenu original écrit.

#### Méthode `test_ecrire_dans_sous_dossier_auto(self)`

**Description :**
Teste si la fonction d'écriture de fichier crée automatiquement les répertoires parents manquants.

**Arguments :**
Aucun.

**Retours :**
Aucun.

**Logique interne :**
1.  Définit un chemin de fichier imbriqué (`chemin`) et un contenu (`contenu`).
2.  Appelle `FS.execute_ecrire_fichier()` avec ce chemin et le contenu, en passant `self.sys_args`.
3.  Calcule le chemin complet attendu du fichier dans la sandbox.
4.  Vérifie que le fichier, ainsi que tous ses répertoires parents, ont été créés dans la sandbox.

#### Méthode `test_lister_arborescence(self)`

**Description :**
Teste la fonctionnalité de listage de l'arborescence des fichiers, en s'assurant qu'elle reflète le contenu de la sandbox et non le système de fichiers réel.

**Arguments :**
Aucun.

**Retours :**
Aucun.

**Logique interne :**
1.  Crée manuellement un sous-répertoire `src` et un fichier `src/main.py` dans la sandbox (`self.test_dir`).
2.  Appelle `FS.execute_lister_arborescence(".")` avec les arguments système. Le "." est interprété par le mock de `get_path` comme `self.test_dir`.
3.  Vérifie que la sortie contient les noms "src" et "main.py".
4.  Vérifie que la sortie *ne contient pas* de noms qui appartiendraient au répertoire du projet réel (ici, exemple avec "AiModding-Companion"), confirmant que le listage est bien confiné à la sandbox.

#### Méthode `test_supprimer_fichier(self)`

**Description :**
Teste la fonctionnalité de suppression d'un fichier.

**Arguments :**
Aucun.

**Retours :**
Aucun.

**Logique interne :**
1.  Définit un nom de fichier à supprimer (`f`) et crée physiquement ce fichier dans la sandbox.
2.  Appelle `FS.execute_supprimer_fichier()` avec le nom du fichier et les arguments système.
3.  Vérifie que le fichier n'existe plus dans la sandbox (`os.path.exists(p)` retourne `False`).

---

## Exemple d'usage

Ce fichier est conçu pour être exécuté par le système de test `unittest`. Il n'est pas destiné à être exécuté directement comme un script principal.

Pour exécuter ces tests, naviguez jusqu'au répertoire racine de votre projet dans le terminal et exécutez :

```bash
python -m unittest tests/test_filesystem.py
```

ou, si vous êtes déjà dans le répertoire `tests` :

```bash
python test_filesystem.py
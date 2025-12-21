# Documentation Technique du Fichier `tests\test_backup_manager.py`

## Description Concise

Ce fichier contient les tests unitaires pour la fonctionnalité de gestion des sauvegardes (BackupManager) de l'application. Il vise à vérifier le bon fonctionnement de la création de sauvegardes, de la rotation des anciens fichiers de sauvegarde et de la liste des sauvegardes disponibles.

## Dépendances

*   `unittest` : Framework de test unitaire standard de Python.
*   `shutil` : Opérations de haut niveau sur les fichiers et collections de fichiers.
*   `tempfile` : Génération de fichiers et répertoires temporaires.
*   `os` : Interaction avec le système d'exploitation (chemins, création de répertoires).
*   `sys` : Accès aux paramètres et fonctions spécifiques au système.
*   `time` : Fonctions relatives au temps.
*   `zipfile` : Manipulation des archives ZIP.
*   `unittest.mock` : Outils pour mocker les objets (MagicMock, patch).
*   `features.BackupManager` : Module à tester, contenant la logique de gestion des sauvegardes.
*   `features.core_backup` : Module utilisé par BackupManager pour les opérations de sauvegarde de base.
*   `config.settings` : Module de configuration de l'application.

---

## Classes & Fonctions

### Classe `TestBackupManager(unittest.TestCase)`

Cette classe hérite de `unittest.TestCase` et regroupe les différents tests unitaires pour `BackupManager`.

#### Méthode `setUp(self)`

**Signature :** `setUp(self)`

**Arguments :** Aucun

**Retours :** Aucun

**Logique interne :**
Cette méthode est exécutée avant chaque test unitaire de la classe. Elle initialise un environnement de test isolé :
1.  Crée un répertoire temporaire (`self.test_root`) pour servir de "sandbox".
2.  Crée un répertoire `MyProject` dans la sandbox pour simuler le projet à sauvegarder (`self.project_dir`).
3.  Crée un répertoire `Backups` dans la sandbox pour stocker les sauvegardes (`self.backup_dir`).
4.  Crée un fichier factice `data.txt` dans `self.project_dir`.
5.  Prépare un dictionnaire `self.mock_sys_args` contenant des mocks pour les arguments système attendus par les fonctions de `BackupManager` (`session`, `action_log_path`, `result_queue`, `task_queue`).
6.  Applique des "patches" (mocks) critiques pour isoler les tests :
    *   Patch de `features.core_backup.BACKUP_DIR` pour pointer vers `self.backup_dir`.
    *   Patch de `features.core_backup.APP_TO_BACKUP` pour pointer vers `self.project_dir`.
    *   Patch de `features.BackupManager.BACKUP_DIR` pour pointer vers `self.backup_dir`.
    *   Patch de `config.settings.APP_SETTINGS` pour s'assurer que le répertoire de sauvegarde configuré est bien `self.backup_dir`.
    Ces patches sont démarrés (`.start()`) ici et arrêtés dans `tearDown`.

#### Méthode `tearDown(self)`

**Signature :** `tearDown(self)`

**Arguments :** Aucun

**Retours :** Aucun

**Logique interne :**
Cette méthode est exécutée après chaque test unitaire de la classe. Elle nettoie l'environnement de test :
1.  Arrête tous les patches démarrés dans `setUp` (`.stop()`).
2.  Supprime récursivement le répertoire temporaire `self.test_root` et tout son contenu.

#### Méthode `test_creation_backup_zip(self)`

**Signature :** `test_creation_backup_zip(self)`

**Arguments :** Aucun

**Retours :** Aucun

**Logique interne :**
Ce test vérifie que la fonction `BM.execute_creer_backup` crée correctement un fichier ZIP contenant les données du projet.
1.  Appelle `BM.execute_creer_backup` avec un commentaire et les arguments mockés.
2.  Vérifie que le retour de la fonction indique un succès (contient "réussie" ou "Succès").
3.  Liste les fichiers dans le répertoire de sauvegarde et vérifie qu'exactement un fichier `.zip` a été créé.
4.  Ouvre le fichier ZIP créé et vérifie qu'il contient bien le fichier `data.txt`.

#### Méthode `test_rotation_backups(self)`

**Signature :** `test_rotation_backups(self)`

**Arguments :** Aucun

**Retours :** Aucun

**Logique interne :**
Ce test vérifie que la logique de rotation des sauvegardes (`CoreBackup._clean_old_backups`) supprime correctement les fichiers les plus anciens lorsque la limite `MAX_BACKUPS_TO_KEEP` est dépassée.
1.  Utilise un `patch` pour définir `features.core_backup.MAX_BACKUPS_TO_KEEP` à `2`.
2.  Crée manuellement trois fichiers ZIP factices (`backup_old.zip`, `backup_mid.zip`, `backup_new.zip`) dans le répertoire de sauvegarde, en simulant des dates de création différentes (plus anciennes pour `_old`, plus récentes pour `_new`).
3.  Appelle `CoreBackup._clean_old_backups()`.
4.  Liste les fichiers restants dans le répertoire de sauvegarde et vérifie qu'il n'y en a que `2`.
5.  Vérifie que `backup_new.zip` est présent et que `backup_old.zip` a été supprimé.

#### Méthode `test_lister_backups(self)`

**Signature :** `test_lister_backups(self)`

**Arguments :** Aucun

**Retours :** Aucun

**Logique interne :**
Ce test vérifie que la fonction `BM.execute_lister_backups` liste correctement les fichiers présents dans le répertoire de sauvegarde.
1.  Crée manuellement un fichier nommé `manuel.zip` dans le répertoire de sauvegarde.
2.  Appelle `BM.execute_lister_backups` avec les arguments mockés.
3.  Vérifie que le nom du fichier `manuel.zip` est présent dans la chaîne de caractères retournée par la fonction.

---

## Exemple d'usage

Les tests fournis dans ce fichier servent eux-mêmes d'exemples d'utilisation des fonctions `BM.execute_creer_backup`, `CoreBackup._clean_old_backups` et `BM.execute_lister_backups` dans un contexte de test.

Pour exécuter ces tests, vous pouvez utiliser la commande suivante depuis la racine du projet :

```bash
python -m unittest tests/test_backup_manager.py
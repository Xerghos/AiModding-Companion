# Documentation Technique : `tests\test_context_loader.py`

## Description

Ce fichier contient les tests unitaires pour le module `features.ContextLoader`. Il vise à vérifier la fonctionnalité de chargement de contexte pour différents domaines, en s'assurant que les fichiers spécifiés dans la `architecture_map.json` sont correctement chargés et que les cas d'erreur sont gérés.

## Dépendances

*   `unittest`: Framework de test unitaire de Python.
*   `shutil`: Opérations sur les fichiers et répertoires.
*   `tempfile`: Création de fichiers et répertoires temporaires.
*   `os`: Interactions avec le système d'exploitation.
*   `sys`: Paramètres et fonctions spécifiques au système.
*   `json`: Encodage et décodage de données JSON.
*   `unittest.mock.MagicMock`, `unittest.mock.patch`: Mocking pour isoler les tests.
*   `features.ContextLoader`: Le module à tester.

---

## Classes & Fonctions

### Classe `TestContextLoader`

Hérite de `unittest.TestCase`. Contient les méthodes de test pour `ContextLoader`.

#### Méthode `setUp(self)`

**Description :**
Configure l'environnement de test avant chaque méthode de test. Crée un répertoire temporaire, change le répertoire de travail actuel vers ce répertoire temporaire, initialise des mocks pour `sys` et crée un fichier `config/architecture_map.json` simulé. Applique des patchs aux fonctions externes pour contrôler leur comportement pendant les tests.

**Arguments :**
Aucun.

**Retours :**
Aucun.

**Logique interne :**
1.  Crée un répertoire temporaire (`self.test_dir`).
2.  Sauvegarde le répertoire de travail actuel (`self.original_cwd`).
3.  Change le répertoire de travail actuel vers `self.test_dir`.
4.  Définit un dictionnaire `self.mock_sys` avec des mocks pour les files d'attente et des chemins simulés.
5.  Crée le répertoire `config`.
6.  Crée un dictionnaire `self.fake_arch_map` représentant une configuration d'architecture.
7.  Écrit `self.fake_arch_map` dans `config/architecture_map.json`.
8.  Initialise une liste de patchs (`self.patchers`) pour :
    *   `features.Shared.log_action`
    *   `features.ContextLoader.get_path` (pour retourner des chemins absolus)
    *   `features.Shared.smart_resolve_path` (pour retourner des chemins absolus)
9.  Démarre chaque patch.

#### Méthode `tearDown(self)`

**Description :**
Nettoie l'environnement de test après chaque méthode de test. Arrête les patchs appliqués dans `setUp`, restaure le répertoire de travail original et supprime le répertoire temporaire créé.

**Arguments :**
Aucun.

**Retours :**
Aucun.

**Logique interne :**
1.  Arrête chaque patch dans `self.patchers`.
2.  Restaure le répertoire de travail original.
3.  Supprime le répertoire temporaire (`self.test_dir`) et son contenu.

#### Méthode `test_chargement_domaine(self)`

**Description :**
Teste la fonctionnalité principale de `charger_contexte_domaine`. Vérifie que les fichiers spécifiés dans `primary_files` de l'architecture map sont chargés et que leur contenu est inclus dans le résultat, tandis que les fichiers non spécifiés sont ignorés.

**Arguments :**
Aucun.

**Retours :**
Aucun.

**Logique interne :**
1.  Crée le répertoire `src`.
2.  Crée les fichiers `src/a.py` et `src/b.py` avec du contenu.
3.  Crée le fichier `src/c.py` (qui ne doit pas être chargé) avec du contenu.
4.  Appelle `CL.charger_contexte_domaine` avec `"test_domain"` et les mocks système.
5.  Vérifie que le contenu de `src/a.py` et `src/b.py` est présent dans le résultat retourné.
6.  Vérifie que le contenu de `src/c.py` n'est PAS présent dans le résultat.
7.  Vérifie que l'en-tête de contexte architectural est présent dans le résultat.

#### Méthode `test_domaine_inconnu(self)`

**Description :**
Teste la gestion d'erreur lorsque `charger_contexte_domaine` est appelé avec un nom de domaine qui n'existe pas dans l'architecture map.

**Arguments :**
Aucun.

**Retours :**
Aucun.

**Logique interne :**
1.  Appelle `CL.charger_contexte_domaine` avec un nom de domaine inexistant (`"inconnu_au_bataillon"`) et les mocks système.
2.  Vérifie que la chaîne retournée contient le mot `"inconnu"` (insensible à la casse).

---

## Exemple d'usage

Ce fichier est destiné à être exécuté par le framework de tests unitaires de Python (`unittest`). L'exécution typique se ferait depuis la racine du projet avec la commande :

```bash
python -m unittest tests/test_context_loader.py
```

Il n'y a pas d'exemple d'usage direct pour les utilisateurs de la bibliothèque, car il s'agit d'un fichier de test interne.
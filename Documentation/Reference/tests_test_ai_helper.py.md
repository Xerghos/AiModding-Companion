# Documentation technique : tests\test_ai_helper.py

## Description concise

Ce fichier contient les tests unitaires pour les fonctions du module `features.ai_helper`. Il vise à vérifier le bon fonctionnement de la gestion de la sécurité des requêtes, de l'extraction et du parsing intelligent des commandes, ainsi que du dispatch des requêtes vers les fonctions appropriées.

## Dépendances

*   `unittest` : Framework de test unitaire standard de Python.
*   `unittest.mock.MagicMock`, `unittest.mock.patch` : Outils pour simuler des objets et des fonctions lors des tests.
*   `sys`, `os` : Modules système pour la manipulation de chemins et l'ajout de répertoires au `sys.path`.
*   `features.ai_helper` : Module contenant les fonctions à tester (`_security_check`, `_smart_extract_and_parse`, `analyze_request_and_dispatch`).

---

## Classes & Fonctions

### Classe : `TestAiHelperSecurity`

Hérite de `unittest.TestCase`. Cette classe regroupe les tests unitaires pour la fonction `_security_check`.

#### Méthode : `setUp(self)`

*   **Description** : Méthode de configuration exécutée avant chaque test de cette classe. Elle initialise un dictionnaire de configuration de sécurité (`mock_settings`) simulant `APP_SETTINGS` et patch `APP_SETTINGS` pour que `_security_check` utilise cette configuration pendant les tests.
*   **Arguments** : Aucun.
*   **Retour** : Aucun.
*   **Logique interne** :
    *   Définit `self.mock_settings` avec des paramètres de sécurité activés et des répertoires/fichiers protégés.
    *   Utilise `patch` pour remplacer temporairement `features.ai_helper.APP_SETTINGS` par `self.mock_settings`.
    *   Démarre le patch.

#### Méthode : `tearDown(self)`

*   **Description** : Méthode de nettoyage exécutée après chaque test de cette classe. Elle arrête le patch appliqué dans `setUp`.
*   **Arguments** : Aucun.
*   **Retour** : Aucun.
*   **Logique interne** : Arrête le patch sur `APP_SETTINGS`.

#### Méthode : `test_security_access_legitime(self)`

*   **Description** : Teste si un accès légitime à un fichier non protégé est autorisé.
*   **Arguments** : Aucun.
*   **Retour** : Aucun.
*   **Logique interne** :
    *   Appelle `_security_check` avec l'action "lire_fichier" et un chemin "README.md".
    *   Vérifie que le retour est `None` (indiquant l'absence d'erreur).

#### Méthode : `test_security_confinement_jail(self)`

*   **Description** : Teste si la tentative d'accès à un fichier hors du répertoire projet est bloquée.
*   **Arguments** : Aucun.
*   **Retour** : Aucun.
*   **Logique interne** :
    *   Appelle `_security_check` avec l'action "lire_fichier" et un chemin "../secret.txt".
    *   Vérifie que le retour n'est pas `None` (une erreur est attendue).
    *   Vérifie que le message d'erreur contient "Accès interdit hors du projet".

#### Méthode : `test_security_protected_file_write(self)`

*   **Description** : Teste si l'écriture sur un fichier protégé est bloquée.
*   **Arguments** : Aucun.
*   **Retour** : Aucun.
*   **Logique interne** :
    *   Appelle `_security_check` avec l'action "ecrire_fichier" et un chemin "config/settings.py".
    *   Vérifie que le retour n'est pas `None`.
    *   Vérifie que le message d'erreur contient "protégé".

#### Méthode : `test_security_protected_file_read_allowed(self)`

*   **Description** : Teste si la LECTURE d'un fichier protégé est autorisée.
*   **Arguments** : Aucun.
*   **Retour** : Aucun.
*   **Logique interne** :
    *   Appelle `_security_check` avec l'action "lire_fichier" et un chemin "config/settings.py".
    *   Vérifie que le retour est `None` (la lecture est autorisée).

#### Méthode : `test_security_disabled(self)`

*   **Description** : Teste si toutes les vérifications de sécurité sont désactivées lorsque `enable_sanity_check` est `False`.
*   **Arguments** : Aucun.
*   **Retour** : Aucun.
*   **Logique interne** :
    *   Utilise un `with patch` pour remplacer temporairement `APP_SETTINGS` avec une configuration où `enable_sanity_check` est `False`.
    *   Appelle `_security_check` avec l'action "ecrire_fichier" et un chemin "config/settings.py".
    *   Vérifie que le retour est `None`.

---

### Classe : `TestAiHelperParsing`

Hérite de `unittest.TestCase`. Cette classe regroupe les tests unitaires pour la fonction `_smart_extract_and_parse`.

#### Méthode : `test_parse_valid_json(self)`

*   **Description** : Teste le parsing d'une chaîne JSON valide.
*   **Arguments** : Aucun.
*   **Retour** : Aucun.
*   **Logique interne** :
    *   Définit une chaîne `text` contenant `!native_tool` suivi d'un JSON valide.
    *   Appelle `_smart_extract_and_parse` avec la partie JSON de la chaîne.
    *   Vérifie que le champ "name" du résultat parsé est "test".

#### Méthode : `test_parse_python_dict(self)`

*   **Description** : Teste le parsing d'une chaîne formatée comme un dictionnaire Python, souvent généré par les LLM locaux.
*   **Arguments** : Aucun.
*   **Retour** : Aucun.
*   **Logique interne** :
    *   Définit une chaîne `text` contenant `!native_tool` suivi d'un dictionnaire Python.
    *   Appelle `_smart_extract_and_parse` avec la partie dictionnaire de la chaîne.
    *   Vérifie que le champ "val" dans "args" du résultat parsé est `True`.

#### Méthode : `test_repair_json_truncated(self)`

*   **Description** : Teste la capacité de `_smart_extract_and_parse` à réparer un JSON tronqué (manquant l'accolade fermante).
*   **Arguments** : Aucun.
*   **Retour** : Aucun.
*   **Logique interne** :
    *   Définit une chaîne `text` représentant un JSON tronqué.
    *   Appelle `_smart_extract_and_parse` avec cette chaîne tronquée.
    *   Vérifie que le champ "name" du résultat parsé est "test".
    *   Vérifie que le champ "a" dans "args" du résultat parsé est `1`.

---

### Classe : `TestAiHelperDispatch`

Hérite de `unittest.TestCase`. Cette classe regroupe les tests unitaires pour la fonction `analyze_request_and_dispatch`.

#### Méthode : `test_dispatch_routing(self, mock_exec)`

*   **Description** : Vérifie que `analyze_request_and_dispatch` route correctement la commande vers `execute_native_tool`.
*   **Arguments** : `mock_exec` (un `MagicMock` injecté par le décorateur `@patch`).
*   **Retour** : Aucun.
*   **Logique interne** :
    *   Configure le retour de `mock_exec` à "OK".
    *   Définit une commande `cmd` pour un outil natif.
    *   Appelle `analyze_request_and_dispatch` avec cette commande.
    *   Vérifie que `mock_exec` a été appelé exactement une fois.
    *   Récupère les arguments de l'appel à `mock_exec` et vérifie que le nom de l'outil passé est "my_tool".

#### Méthode : `test_introspection_call(self, mock_list)`

*   **Description** : Vérifie que la commande `!list_tools` déclenche correctement l'appel à `execute_lister_outils`.
*   **Arguments** : `mock_list` (un `MagicMock` injecté par le décorateur `@patch`).
*   **Retour** : Aucun.
*   **Logique interne** :
    *   Appelle `analyze_request_and_dispatch` avec la commande "!list_tools".
    *   Vérifie que `mock_list` a été appelé exactement une fois.

---

## Exemple d'usage

Ce fichier est destiné à être exécuté par un framework de test. Pour lancer tous les tests, on peut exécuter le fichier Python directement :

```bash
python tests/test_ai_helper.py
```

Si tous les tests passent, la sortie sera généralement silencieuse ou affichera un message de succès. En cas d'échec, `unittest` fournira des détails sur le test qui a échoué et pourquoi.
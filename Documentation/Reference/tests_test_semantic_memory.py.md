# Documentation Technique : `tests\test_semantic_memory.py`

## Description concise

Ce fichier contient les tests unitaires pour le module `features.SemanticMemory`. Il vise à vérifier la fonctionnalité de sauvegarde (`execute_sauvegarder_memoire`) et de recherche (`execute_rechercher_memoire`) de la mémoire sémantique, en s'assurant que les interactions avec la base de données sont correctement effectuées.

## Dépendances

*   `unittest` : Bibliothèque standard de Python pour les tests unitaires.
*   `sys` : Module système pour interagir avec l'interpréteur Python.
*   `os` : Module système pour interagir avec le système d'exploitation.
*   `unittest.mock` : Bibliothèque pour simuler des objets et des modules.
*   `features.SemanticMemory` : Module principal à tester.

---

## Classes & Fonctions

### Classe `TestSemanticMemory(unittest.TestCase)`

Classe principale pour les tests unitaires du module `SemanticMemory`.

#### Méthodes

*   `setUp(self)`

    *   **Description :** Méthode exécutée avant chaque test. Elle initialise les mocks nécessaires pour les tests.
    *   **Logique interne :**
        *   Crée un dictionnaire `self.mock_sys` simulant les paramètres système (session, chemins, queues).
        *   Utilise `unittest.mock.patch` pour remplacer le module `features.SemanticMemory.database` par un mock (`self.mock_db`).
        *   Configure des `MagicMock` pour les méthodes de `self.mock_db` (`store_memory`, `search_memories`, `search_vector_db`, `add_memory_fragment`).
        *   Force l'activation de la mémoire longue durée (`SemMem.GlobalMemoryManager.ltm_enabled = True`).

*   `tearDown(self)`

    *   **Description :** Méthode exécutée après chaque test. Elle nettoie les mocks.
    *   **Logique interne :**
        *   Arrête le patch de la base de données (`self.patcher_db.stop()`).

*   `test_sauvegarder_memoire(self)`

    *   **Description :** Vérifie que la fonction `execute_sauvegarder_memoire` appelle correctement les méthodes de la base de données pour sauvegarder une donnée.
    *   **Logique interne :**
        *   Définit une clé (`cle`) et une valeur (`valeur`) pour la mémoire.
        *   Appelle `SemMem.execute_sauvegarder_memoire` avec les mocks système.
        *   Vérifie que la réponse contient les mots "succès" et la valeur sauvegardée.
        *   Vérifie qu'une des méthodes de sauvegarde de la base de données (`store_memory` ou `add_memory_fragment`) a été appelée.

*   `test_rechercher_memoire(self)`

    *   **Description :** Vérifie que la fonction `execute_rechercher_memoire` interroge la base de données et formate correctement les résultats de recherche.
    *   **Logique interne :**
        *   Configure le mock `self.mock_db.search_memories` pour retourner une liste de résultats simulés, chacun étant un tuple `(Source, Contenu, Score)`.
        *   Appelle `SemMem.execute_rechercher_memoire` avec un terme de recherche et les mocks système.
        *   Vérifie que la réponse formatée contient des éléments des résultats simulés.
        *   Vérifie que la méthode `search_memories` de la base de données a été appelée.

*   `test_recherche_vide(self)`

    *   **Description :** Vérifie le comportement de `execute_rechercher_memoire` lorsqu'aucun résultat n'est trouvé dans la base de données.
    *   **Logique interne :**
        *   Configure le mock `self.mock_db.search_memories` pour retourner une liste vide.
        *   Appelle `SemMem.execute_rechercher_memoire` avec un terme de recherche peu probable et les mocks système.
        *   Vérifie que la réponse indique qu'aucun souvenir n'a été trouvé ("Aucun souvenir").

---

## Exemple d'usage

Ce fichier est conçu pour être exécuté dans un environnement de test unitaire. L'exécution se fait généralement via un outil comme `unittest` ou `pytest`.

Pour lancer les tests spécifiquement pour ce fichier :

```bash
python -m unittest tests/test_semantic_memory.py
```

L'exécution de ce script lance le découpage des tests dans la classe `TestSemanticMemory`, où chaque méthode commençant par `test_` est exécutée. Les mocks simulent les interactions avec le module `SemanticMemory` et sa dépendance à la base de données.
# Documentation Technique : `tests\test_worker_integration.py`

## Description Concise

Ce fichier contient des tests d'intégration pour la classe `Worker`. Il vise à vérifier le bon fonctionnement du `Worker` dans des scénarios réalistes impliquant ses dépendances externes (agents, bases de données, gestionnaires de mémoire) tout en les isolant via des `mocks` pour garantir la fiabilité des tests. Les tests couvrent la gestion des modes de raisonnement et l'injection de tâches d'agents avec contexte.

## Dépendances

*   `unittest`: Framework de test unitaire standard de Python.
*   `queue`: Pour la gestion des files d'attente utilisées par le `Worker`.
*   `sys`: Pour manipuler le chemin d'accès Python.
*   `os`: Pour manipuler les chemins d'accès.
*   `threading`: Potentiellement utilisé par le `Worker` (bien que désactivé dans les tests).
*   `unittest.mock`: Pour simuler les dépendances externes du `Worker` (`MagicMock`, `patch`, `ANY`).
*   `worker.core.Worker`: La classe principale à tester.

---

## Classes & Fonctions

### Classe `TestWorkerIntegration` (`unittest.TestCase`)

Cette classe hérite de `unittest.TestCase` et regroupe les tests d'intégration pour le `Worker`.

#### Méthode `setUp(self)`

*   **Description**: Méthode de préparation exécutée avant chaque test. Elle initialise les files d'attente, les événements d'arrêt et met en place les `mocks` pour les dépendances externes du `Worker`.
*   **Logique interne**:
    *   Initialise `self.task_queue` et `self.response_queue` comme des `queue.Queue()`.
    *   Crée un `MagicMock` pour `self.stop_event`.
    *   Met en place une liste de `patchers` pour les éléments suivants :
        *   `worker.core.SessionFactory`
        *   `worker.core.create_agent` (Factory Swarm)
        *   `worker.core.database` (RAG)
        *   `worker.core.GlobalMemoryManager` (Mémoire)
        *   `worker.core.APP_SETTINGS` (pour éviter les erreurs de clé, fournit une structure minimale).
    *   Démarre les `patchers` et stocke les `mocks` résultants dans `self.mocks`.
    *   Récupère les mocks spécifiques `SessionFactory` et `create_agent`.
    *   Configure le mock de l'instance d'agent retournée par `create_agent` pour simuler une réponse réussie (`execute_task` renvoie un objet avec un attribut `text`).
    *   Instancie le `Worker` avec les files d'attente et l'événement d'arrêt préparés.
    *   Remplace le `bg_executor` du `Worker` par un `MagicMock` et redéfinit sa méthode `submit` pour exécuter les fonctions immédiatement (mode synchrone pour faciliter les tests).

#### Méthode `tearDown(self)`

*   **Description**: Méthode de nettoyage exécutée après chaque test. Elle arrête tous les `patchers` actifs.
*   **Logique interne**:
    *   Itère sur `self.patchers` et appelle `p.stop()` pour chaque patch.

#### Méthode `test_switch_reasoning_mode(self)`

*   **Description**: Teste la capacité du `Worker` à activer le mode raisonnement en réponse à une tâche spécifique envoyée via l'interface utilisateur.
*   **Logique interne**:
    1.  **Configuration**:
        *   Configure `self.stop_event.is_set` pour qu'il renvoie `False` une fois, puis `True` pour arrêter la boucle `run()`.
        *   Crée un `MagicMock` pour `self.worker.main_session` et lui attribue un historique simulé.
    2.  **Action**:
        *   Crée une tâche de type `'set_reasoning_mode'` avec `enabled=True`.
        *   Met cette tâche dans `self.task_queue`.
    3.  **Exécution**:
        *   Imprime un message indiquant le début du test.
        *   Appelle `self.worker.run()`.
    4.  **Vérifications**:
        *   Vérifie que `self.worker.reasoning_active` est maintenant `True`.
        *   Vérifie que `self.mock_factory.create_session` a été appelée avec le bon `model_type` (`"reasoning"`) et `system_instruction=ANY`.
        *   Imprime un message de succès.

#### Méthode `test_agent_task_injection(self)`

*   **Description**: Teste le scénario où un agent est lancé, recevant à la fois un contexte (provenant du RAG) et l'activation du mode raisonnement.
*   **Logique interne**:
    1.  **Prerequis**:
        *   Définit `self.worker.reasoning_active` à `True` manuellement.
    2.  **Mock du RAG**:
        *   Crée un `MagicMock` pour `self.worker._retrieve_rag_context` et configure son retour pour simuler des documents RAG trouvés.
    3.  **Action**:
        *   Définit le `task_payload` pour une tâche d'agent, incluant le rôle (`'CODER'`), le prompt et un `task_id`.
        *   Appelle directement `self.worker._handle_agent_task()` avec ce payload pour isoler le test.
    4.  **Vérifications**:
        *   Vérifie que `self.mock_create_agent` a été appelée une fois.
        *   Récupère les arguments (`args`) et mots-clés (`kwargs`) de l'appel à `create_agent`.
        *   Vérifie que le premier argument (`args[0]`) est le rôle `'CODER'`.
        *   Vérifie que le mot-clé `'reasoning_mode'` dans `kwargs` est `True`.
        *   Vérifie que le contexte RAG simulé est inclus dans le `initial_context` passé via `kwargs`.
        *   Imprime un message de succès.

---

## Exemple d'Usage

Ce fichier est conçu pour être exécuté par le framework de test `unittest`. Il n'a pas d'usage direct en dehors de cet environnement. Pour exécuter les tests, utilisez la commande :

```bash
python -m unittest tests/test_worker_integration.py
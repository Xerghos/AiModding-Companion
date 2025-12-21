# Documentation Technique : `tests\test_worker_context.py`

## Description concise

Ce fichier contient un test unitaire pour la fonctionnalité d'injection de contexte dans le `Worker`. Il vise à vérifier que le `Worker` est capable de combiner l'historique de la conversation principale avec des informations récupérées via RAG (Retrieval Augmented Generation) avant de les passer à un agent pour traitement.

## Dépendances

*   `sys`
*   `os`
*   `queue`
*   `unittest.mock.MagicMock`
*   `config.settings.load_app_settings`
*   `worker.core.Worker`
*   `agents.swarm_manager.create_agent` (mocké)

## Classes & Fonctions

### Fonction : `test_context_injection`

#### Signatures

```python
def test_context_injection():
```

#### Arguments

Aucun.

#### Retours

Aucun.

#### Logique interne

1.  **Initialisation du Worker :**
    *   Crée des instances de `queue.Queue` pour simuler les files d'attente d'entrée et de sortie.
    *   Crée une instance de `Worker` en utilisant ces files d'attente et un `MagicMock` pour le gestionnaire d'API.

2.  **Injection de données simulées (Historique STM) :**
    *   Remplace la session principale du `Worker` par un `MagicMock`.
    *   Popule l'attribut `history` de cette session mockée avec une séquence de messages simulant un historique de conversation (`user` et `model`).

3.  **Mock du RAG :**
    *   Remplace la méthode `_retrieve_rag_context` du `Worker` par un `MagicMock`.
    *   Configure ce mock pour qu'il retourne une chaîne de caractères spécifique simulant un résultat de recherche RAG (`"[RAG] Fichier 'test.py' détecté."`).

4.  **Mock de `create_agent` :**
    *   Sauvegarde la référence originale de la fonction `create_agent` du module `agents.swarm_manager`.
    *   Crée un `MagicMock` (appelé `spy`) pour remplacer temporairement `create_agent`.
    *   Configure `spy` pour qu'il retourne un objet mocké qui a une méthode `execute_task` retournant `"OK"`. Cette étape est cruciale pour vérifier les arguments passés à `create_agent`.

5.  **Exécution de la tâche :**
    *   Définit un dictionnaire `payload` simulant les données d'une tâche à traiter par un agent (`agent_type`, `prompt`, `task_id`).
    *   Appelle la méthode `_handle_agent_task` du `Worker` avec ce `payload`.

6.  **Vérification :**
    *   Vérifie si le `spy` (le mock de `create_agent`) a été appelé.
    *   Si appelé, récupère les arguments (`args`) et les mots-clés (`kwargs`) avec lesquels `create_agent` a été appelé.
    *   Extrait la valeur de l'argument `initial_context` passé à `create_agent`.
    *   **Analyse du contexte :**
        *   Vérifie la présence du marqueur `"[RAG]"` dans le contexte pour confirmer l'injection RAG.
        *   Vérifie la présence d'un fragment de l'historique de conversation (`"Analyse ce fichier"`) pour confirmer l'injection de l'historique STM.
        *   Affiche des messages indiquant si le RAG et l'historique STM sont présents dans le contexte transmis à l'agent.
        *   Affiche un message de succès total ou d'avertissement si la transmission est partielle.
    *   Si `create_agent` n'a pas été appelé, affiche un message d'échec.
    *   Un bloc `try...except` capture et affiche toute exception survenant pendant le test.
    *   Le bloc `finally` assure la restauration de la fonction `create_agent` originale, quel que soit le résultat du test.

### Bloc `if __name__ == "__main__":`

Ce bloc standard Python permet d'exécuter la fonction `test_context_injection` directement lorsque le script est lancé comme programme principal.

## Exemple d'usage

Ce script est conçu pour être exécuté en tant que test unitaire, généralement via un framework de test comme `pytest` ou en le lançant directement :

```bash
python tests/test_worker_context.py
```

L'exécution affichera des messages indiquant les étapes du test et le résultat de la vérification de l'injection du contexte.

Exemple de sortie attendue en cas de succès :

```
--- 🧠 TEST MEMOIRE PARTAGEE (WORKER -> AGENT) ---
🔹 Init Worker...
🔹 Injection Historique (STM)...
🔹 Lancement Tâche Agent...

🔍 ANALYSE DU CONTEXTE REÇU PAR L'AGENT :
✅ RAG présent.
✅ Historique STM présent.

🎉 SUCCÈS TOTAL : Le Worker transmet bien la mémoire hybride !
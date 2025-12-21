# Documentation Technique: `tests\test_swarm_manager.py`

## Description concise

Ce fichier contient des tests unitaires pour la classe `SwarmAgent` et la fonction `create_agent` du module `agents.swarm_manager`. Il vise à vérifier le comportement de l'agent lors de son initialisation (configuration des tiers, injection de contexte, whitelisting d'outils), de son passage en mode raisonnement, et de sa boucle d'exécution autonome. Les tests s'appuient sur `unittest` et `unittest.mock` pour isoler l'unité testée et simuler les dépendances externes.

## Dépendances

*   `unittest`
*   `unittest.mock` (pour `MagicMock`, `patch`, `ANY`)
*   `sys`
*   `os`
*   `agents.swarm_manager` (pour `SwarmAgent`, `create_agent`)
*   `features.ai_helper` (pour `analyze_request_and_dispatch` - utilisé dans un des tests)

---

## Classes & Fonctions

### Classe `TestSwarmManager(unittest.TestCase)`

Classe de test pour `SwarmAgent`.

#### Méthode `setUp(self)`

**Logique interne:**
Configure les mocks pour les dépendances externes avant chaque test.
1.  Met en place un patch pour `agents.swarm_manager.SessionFactory`, remplaçant l'instance réelle par un `MagicMock`.
2.  Met en place un patch pour `agents.swarm_manager.APP_SETTINGS`, fournissant une configuration spécifique pour les tests, notamment `max_auto_loop`.

#### Méthode `tearDown(self)`

**Logique interne:**
Nettoie les mocks après chaque test pour éviter toute interférence entre les tests.
1.  Arrête le patch de `SessionFactory`.
2.  Arrête le patch de `APP_SETTINGS`.

#### Méthode `test_init_coder_properties(self)`

**Description:** Vérifie que lorsqu'un agent de type "CODER" est instancié, il est correctement configuré avec le tier approprié et un prompt système incluant les outils autorisés pour ce persona.

**Logique interne:**
1.  Instancie `SwarmAgent` avec le rôle "CODER".
2.  Vérifie que l'attribut `tier` de l'agent est bien `"coder"`.
3.  Vérifie que la méthode `create_session` de `SessionFactory` (mockée) a été appelée une fois.
4.  Vérifie que le `system_instruction` de l'agent contient les chaînes "MANUEL DES OUTILS AUTORISÉS" et "lire_fichier" (outil autorisé pour le CODER).
5.  Vérifie que le `system_instruction` ne contient pas la chaîne "web_search" (outil interdit pour le CODER selon la configuration par défaut supposée).

#### Méthode `test_init_router_properties(self)`

**Description:** Vérifie que lorsqu'un agent de type "ROUTER" est instancié, il est léger, configuré avec le tier "fast" et n'a pas d'outils dans son prompt système.

**Logique interne:**
1.  Instancie `SwarmAgent` avec le rôle "ROUTER".
2.  Vérifie que l'attribut `tier` de l'agent est bien `"fast"`.
3.  Vérifie que le `system_instruction` de l'agent ne contient pas la chaîne "MANUEL DES OUTILS AUTORISÉS", indiquant l'absence d'outils.

#### Méthode `test_context_injection(self)`

**Description:** Vérifie que le contexte initial fourni lors de l'instanciation d'un agent est correctement injecté dans son `system_instruction`.

**Logique interne:**
1.  Définit une chaîne de `contexte`.
2.  Instancie `SwarmAgent` avec le rôle "ARCHITECT" et le `contexte` initial.
3.  Vérifie que le `system_instruction` de l'agent contient les chaînes "CONTEXTE DE MISSION" et la chaîne de `contexte` fournie.

#### Méthode `test_reasoning_mode_upgrade(self)`

**Description:** Teste le comportement de mise à niveau automatique du tier d'un agent lorsqu'il est démarré en mode raisonnement (`reasoning_mode=True`).

**Logique interne:**
1.  **Cas 1 (ARCHITECT):**
    *   Instancie `SwarmAgent` avec le rôle "ARCHITECT" et `reasoning_mode=True`.
    *   Vérifie que le `tier` de l'agent a été mis à jour à `"reasoning"`.
2.  **Cas 2 (WRITER):**
    *   Instancie `SwarmAgent` avec le rôle "WRITER" (supposé être de tier "fast") et `reasoning_mode=True`.
    *   Vérifie que le `tier` de l'agent reste `"fast"` car ce persona n'est pas éligible à l'upgrade en mode raisonnement.

#### Méthode `test_retry_loop_logic(self, mock_dispatch)`

**Description:** Simule un scénario de boucle d'exécution où l'agent rencontre une erreur lors de l'utilisation d'un outil, est corrigé, puis réussit finalement la tâche. Cela teste la logique de retry et l'interaction avec les outils.

**Logique interne:**
1.  Instancie `SwarmAgent` avec le rôle "CODER".
2.  Simule la conversation avec l'IA:
    *   La première réponse attendue de `agent.session.send_message` est une invocation d'outil (`!native_tool`).
    *   La deuxième réponse attendue est la conclusion finale de la tâche.
3.  Configure le mock `agent.session.send_message` pour qu'il retourne ces réponses simulées séquentiellement via `side_effect`.
4.  Définit le retour simulé de l'outil (`mock_dispatch`) qui serait appelé par l'agent suite à l'invocation de l'outil.
5.  Appelle `agent.execute_task` pour déclencher la boucle.
6.  **Vérifications:**
    *   Vérifie que `agent.session.send_message` a été appelée 2 fois (une pour demander l'outil, une pour la réponse finale).
    *   Vérifie que `mock_dispatch` (représentant l'exécution de l'outil) a été appelé une fois.
    *   Vérifie que le résultat final contient le texte de conclusion attendu.

---

## Exemple d'usage

Bien que ce fichier contienne principalement des tests, il illustre comment `SwarmAgent` peut être instancié et utilisé :

```python
# Instanciation d'un agent CODER avec contexte initial
contexte_mission = "Analyser le fichier de configuration principal."
agent_coder = SwarmAgent("CODER", initial_context=contexte_mission)

# Instanciation d'un agent ROUTER en mode raisonnement
agent_router = SwarmAgent("ROUTER", reasoning_mode=True)

# Exécution d'une tâche (cette méthode gère la boucle d'autonomie)
# Le résultat sera un objet similaire à une réponse LLM, avec un attribut 'text'
try:
    resultat_analyse = agent_coder.execute_task("Vérifier la présence de clés sensibles dans config.yaml")
    print(f"Résultat de l'analyse: {resultat_analyse.text}")
except Exception as e:
    print(f"Erreur lors de l'exécution de la tâche: {e}")

# La fonction create_agent peut être utilisée pour une création plus simple
# agent_create = create_agent(role="CODER", ...)
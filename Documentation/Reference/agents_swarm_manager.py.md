# Documentation Technique - `agents\swarm_manager.py`

## 1. En-tête

### Titre
`swarm_manager.py` - Gestionnaire d'Agents Swarm V2

### Description concise
Ce module implémente la logique des `SwarmAgent` (V2), des agents autonomes spécialisés. Chaque `SwarmAgent` est doté de sa propre session LLM isolée (tiering), d'un contexte d'outils whitelisté (filtrage), d'une mémoire de mission (injection de contexte) et d'une capacité d'autonomie en boucle (retry loop) pour exécuter des tâches complexes, incluant l'utilisation d'outils et le mode raisonnement.

### Dépendances
*   `logging`: Pour la journalisation des informations et erreurs.
*   `json`: Pour la manipulation des données JSON.
*   `re`: Pour les opérations d'expressions régulières (non utilisé directement, mais peut être une dépendance implicite des outils).
*   `queue`: Pour la gestion des files de messages (pour les outils).
*   `features.Decorators.trace_action`: Décorateur pour le traçage des actions.
*   `ai_core.factory.SessionFactory`: Fabrique pour créer des sessions LLM.
*   `config.tools_schema.TOOLS_SCHEMA`: Schéma global des outils disponibles.
*   `config.settings.APP_SETTINGS`: Paramètres globaux de l'application.
*   `agents.agent_personas.SWARM_AGENTS` ou `agent_personas.SWARM_AGENTS`: Import dynamique des définitions de personas d'agents.
*   `features.ai_helper.analyze_request_and_dispatch` (importé localement dans `execute_task`): Pour le dispatch des appels d'outils.

## 2. Classes & Fonctions

### Classe : `SwarmAgent`

**Description**
Représente un agent autonome au sein d'un "essaim" (Swarm V2). Chaque agent possède les caractéristiques suivantes :
*   **Session dédiée (Tiering)**: Chaque `SwarmAgent` gère sa propre session avec le modèle de langage, permettant d'adapter le tier du modèle (ex: `fast`, `reasoning`) à sa tâche spécifique.
*   **Contexte d'outils (Whitelisting)**: Accès contrôlé à un sous-ensemble d'outils définis dans son persona, évitant l'hallucination d'outils non pertinents ou non autorisés.
*   **Mémoire de mission (Context Injection)**: Peut recevoir un contexte initial (historique, résumé) pour démarrer sa tâche avec une compréhension préalable.
*   **Boucle autonome (Retry Loop)**: Capable d'exécuter une série d'actions, incluant des appels d'outils, et de se corriger en fonction des résultats jusqu'à atteindre un objectif ou une limite.
*   **Support du mode Raisonnement (Reasoning Mode)**: Peut être configuré pour utiliser des modèles plus puissants (tier `reasoning`) pour des tâches nécessitant une analyse approfondie.

#### `__init__(self, agent_type, parent_session=None, initial_context=None, reasoning_mode=False)`

*   **Signature**: `__init__(self, agent_type, parent_session=None, initial_context=None, reasoning_mode=False)`
*   **Arguments**:
    *   `agent_type` (`str`): La clé correspondant à la définition de l'agent dans `SWARM_AGENTS` (ex: `'CODER'`, `'ARCHITECT'`).
    *   `parent_session` (`object`, optionnel): (Obsolète) Ancienne session du worker, ignorée car chaque `SwarmAgent` crée sa propre session dédiée.
    *   `initial_context` (`str` ou `dict`, optionnel): Un historique, un résumé ou toute information pertinente à injecter dans le prompt système de l'agent dès son démarrage.
    *   `reasoning_mode` (`bool`, optionnel, défaut `False`): Si `True`, et que l'agent n'est pas déjà configuré avec le tier `'fast'`, le modèle de l'agent est mis à niveau vers le tier `'reasoning'`.
*   **Logique interne**:
    1.  Convertit `agent_type` en majuscules.
    2.  Charge le profil (`persona`) de l'agent depuis `SWARM_AGENTS`. En cas d'agent inconnu, utilise un profil `ROUTER` par défaut.
    3.  Détermine le `model_tier` initial à partir du persona.
    4.  **Applique le mode raisonnement**: Si `reasoning_mode` est `True` et que le tier n'est pas `'fast'`, le tier est mis à jour en `'reasoning'`.
    5.  Construit l'instruction système complète via `_build_system_instruction`, intégrant l'identité, le manuel des outils et le contexte initial.
    6.  Crée une session LLM dédiée à l'agent en utilisant `SessionFactory.create_session`, en spécifiant le `model_type`, l'activation des outils, l'instruction système et un nom d'affichage pour l'agent.

#### `_get_tool_definitions(self)`

*   **Signature**: `_get_tool_definitions(self)`
*   **Arguments**: Aucun.
*   **Retours**: `list` de `dict`. Une liste des schémas JSON des outils autorisés pour cet agent, filtrés depuis `TOOLS_SCHEMA`.
*   **Logique interne**:
    1.  Récupère la liste des noms d'outils autorisés (`allowed_tools`) depuis le `persona` de l'agent.
    2.  Si aucun outil n'est autorisé, retourne une liste vide.
    3.  Parcourt `TOOLS_SCHEMA` pour collecter toutes les définitions de fonctions, gérant deux formats possibles :
        *   Le format Google GenAI avec `{"function_declarations": [...]}`.
        *   Le format plat avec une liste d'objets `function_declaration`.
    4.  Filtre les fonctions collectées pour ne retenir que celles dont le `name` figure dans la liste `allowed_tools`.

#### `_build_system_instruction(self)`

*   **Signature**: `_build_system_instruction(self)`
*   **Arguments**: Aucun.
*   **Retours**: `str`. Le prompt système complet (identité de l'agent, manuel des outils autorisés, bloc de contexte de mission).
*   **Logique interne**:
    1.  Récupère le prompt de base (`persona.get("prompt")`).
    2.  **A. Injection des Outils (Whitelisting)**:
        *   Appelle `_get_tool_definitions` pour obtenir la liste des outils autorisés.
        *   Construit un bloc de texte descriptif listant les noms et descriptions de ces outils, formant un "manuel" que l'agent doit suivre strictement.
    3.  **B. Injection du Contexte (Context Sharing)**:
        *   Si `initial_context` a été fourni lors de l'initialisation, il est formaté dans un bloc `--- CONTEXTE DE MISSION ---` et ajouté au prompt.
    4.  Assemble et retourne la chaîne de caractères finale qui servira d'instruction système pour la session LLM de l'agent.

#### `@trace_action(source="swarm_manager")`
#### `execute_task(self, task_prompt, result_queue=None, task_queue=None)`

*   **Signature**: `execute_task(self, task_prompt, result_queue=None, task_queue=None)`
*   **Arguments**:
    *   `task_prompt` (`str`): La tâche ou la question principale à exécuter par l'agent.
    *   `result_queue` (`queue.Queue`, optionnel): Une file d'attente pour communiquer les résultats des outils (utilisée pour le logging/UI). Crée une queue factice si non fournie.
    *   `task_queue` (`queue.Queue`, optionnel): Une file d'attente pour communiquer les sous-tâches ou actions à d'autres composants. Crée une queue factice si non fournie.
*   **Retours**: Un objet de type `obj` (`type('obj', (object,), {'text': final_response_text})`) compatible avec l'interface attendue par d'autres modules (ex: `Worker`), contenant la réponse finale de l'agent dans son attribut `.text`.
*   **Logique interne**:
    1.  Importe `analyze_request_and_dispatch` localement pour éviter les problèmes d'importation cyclique.
    2.  Configure la boucle d'autonomie avec un nombre maximal d'itérations (`max_auto_loop` depuis `APP_SETTINGS`).
    3.  Initialise l'input courant avec `task_prompt` et une instruction pour le raisonnement (`<thought>`).
    4.  Entre dans une boucle qui s'exécute jusqu'à `max_loops` fois ou jusqu'à ce que l'agent fournisse une réponse finale sans appel d'outil.
    5.  **Appel IA**: Envoie `current_input` à la session LLM de l'agent (`self.session.send_message`).
    6.  **Détection Outil**: Vérifie si la réponse de l'IA contient `"!native_tool"`, indiquant une intention d'utiliser un outil.
        *   Si un outil est détecté, `analyze_request_and_dispatch` est appelé pour exécuter l'outil.
        *   Le résultat de l'outil est ensuite formaté comme `--- RÉSULTAT OUTIL (SYSTÈME) ---` et devient le `current_input` pour la prochaine itération, créant une boucle de feedback.
    7.  Si aucun outil n'est détecté, la boucle se termine, la réponse de l'IA est considérée comme finale.
    8.  Gère les exceptions pendant la boucle en injectant un message d'erreur à l'IA.
    9.  Si la limite de `max_loops` est atteinte, un avertissement est ajouté à la réponse finale.
    10. Retourne un objet simple avec la réponse finale dans son attribut `.text`.

### Fonction : `create_agent`

#### `@trace_action(source="swarm_manager")`
#### `create_agent(agent_type, worker_session=None, initial_context=None, reasoning_mode=False)`

*   **Signature**: `create_agent(agent_type, worker_session=None, initial_context=None, reasoning_mode=False)`
*   **Arguments**:
    *   `agent_type` (`str`): Le type de l'agent à créer (ex: `'CODER'`).
    *   `worker_session` (`object`, optionnel): (Transmis à `SwarmAgent`, mais obsolète pour la logique interne de `SwarmAgent`).
    *   `initial_context` (`str` ou `dict`, optionnel): Contexte initial pour l'agent.
    *   `reasoning_mode` (`bool`, optionnel, défaut `False`): Active le mode raisonnement pour l'agent.
*   **Retours**: Une instance de `SwarmAgent`.
*   **Logique interne**: C'est une fonction "usine" (factory wrapper) qui instancie simplement et retourne un objet `SwarmAgent` avec les paramètres fournis, facilitant la création d'agents.

## 3. Exemple d'usage

```python
import queue
from agents.swarm_manager import create_agent

# Supposons que SWARM_AGENTS contient une entrée 'WRITER' :
# SWARM_AGENTS = {
#     "WRITER": {
#         "prompt": "Tu es un écrivain créatif spécialisé dans la rédaction de contenu marketing.",
#         "allowed_tools": ["search_web"], # Supposons que 'search_web' est défini dans TOOLS_SCHEMA
#         "model_tier": "balanced"
#     }
# }

# 1. Création d'un agent de type "WRITER" avec un contexte initial
#    et le mode raisonnement activé pour une meilleure qualité.
print("Création de l'agent WRITER...")
writer_agent = create_agent(
    agent_type='WRITER',
    initial_context="Le client souhaite un texte promotionnel pour un nouveau produit AI nommé 'MindFlow'.",
    reasoning_mode=True
)
print(f"Agent {writer_agent.agent_type} créé avec le tier : {writer_agent.tier}")


# 2. Préparation des files pour l'exécution des tâches (même si factices ici)
result_q = queue.Queue()
task_q = queue.Queue()

# 3. Exécution d'une tâche par l'agent
print("\nExécution de la tâche par l'agent WRITER...")
task = "Rédige un paragraphe de présentation captivant pour 'MindFlow'. Recherche des informations clés si nécessaire."
response = writer_agent.execute_task(task, result_queue=result_q, task_queue=task_q)

# 4. Affichage de la réponse finale de l'agent
print("\n--- Réponse de l'agent WRITER ---")
print(response.text)

# Exemple de création d'un agent plus simple sans mode raisonnement ni contexte
print("\nCréation de l'agent ROUTER...")
router_agent = create_agent(agent_type='ROUTER')
print(f"Agent {router_agent.agent_type} créé avec le tier : {router_agent.tier}")
task_router = "Classifie la demande suivante: 'J'ai besoin d'aide pour débugger mon code Python.'"
response_router = router_agent.execute_task(task_router)
print("\n--- Réponse de l'agent ROUTER ---")
print(response_router.text)
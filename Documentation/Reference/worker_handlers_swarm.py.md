# `worker/handlers/swarm.py` - Gestion des Agents Swarm AI

## 1. En-tête

### Description concise
Ce module est responsable de la gestion des agents AI spécialisés, basés sur un concept de "Swarm AI". Il permet de créer, récupérer et maintenir des sessions AI persistantes pour différents rôles (ex: Architecte, Développeur), et d'exécuter des tâches spécifiques via ces agents. Le module met en cache les sessions pour optimiser les performances et conserver le contexte des conversations avec les agents.

### Dépendances
*   `logging`: Utilisé pour la journalisation des événements et des informations de débogage.
*   `ai_core.SessionFactory`: Service essentiel pour la création et l'initialisation de nouvelles sessions AI.
*   `ai_core.call_ai_robust`: Fonction utilitaire pour effectuer des appels robustes aux modèles AI, gérant potentiellement les erreurs ou les tentatives.
*   `features.Decorators.trace_action`: Décorateur utilisé pour tracer l'exécution des fonctions à des fins de monitoring et de débogage.

## 2. Classes & Fonctions

### Fonctions

#### `get_agent_session(role)`

```python
def get_agent_session(role)
```

**Description**
Cette fonction récupère une session AI existante pour un rôle spécifique ou en crée une nouvelle si aucune session n'est actuellement mise en cache pour ce rôle. Les sessions sont stockées de manière persistante au niveau du module (`_agent_sessions`) pour maintenir la mémoire et le contexte de l'agent entre les appels.

**Arguments**
*   `role` (str): Le rôle de l'agent souhaité (ex: "ARCHITECT", "DEVELOPER", "ASSISTANT"). Ce rôle est utilisé pour déterminer le type de modèle AI à instancier et pour définir l'identité de l'agent via l'instruction système.

**Retourne**
*   `ai_core.Session`: Une instance de session AI configurée pour le rôle donné, prête à interagir avec le modèle de langage.

**Logique interne**
1.  Vérifie si une session correspondant au `role` est déjà présente dans le dictionnaire de cache `_agent_sessions`.
2.  Si aucune session n'est trouvée pour le `role` :
    *   Crée une clé de modèle (`m_key`) en convertissant le `role` en minuscules (ex: "ARCHITECT" -> "architect"), ce qui correspond aux types de modèles configurés dans `ai_engine`.
    *   Génère un nom d'affichage propre (`display_name`) en capitalisant le `role` (ex: "ARCHITECT" -> "Architect").
    *   Utilise `SessionFactory.create_session` pour instancier une nouvelle session AI. Cette session est configurée avec :
        *   `model_type`: Basé sur `m_key`.
        *   `system_instruction`: Une instruction forte ("Tu es un expert {role}. Agis strictement selon ce rôle.") pour définir le comportement de l'agent.
        *   `agent_name`: Le `display_name` pour identifier l'agent.
    *   Stocke la nouvelle session dans le cache `_agent_sessions` en utilisant le `role` comme clé.
3.  Retourne la session (qu'elle ait été récupérée du cache ou nouvellement créée).

**Décorateurs**
*   `@trace_action(source="swarm")`: Indique que l'exécution de cette fonction doit être tracée, avec "swarm" comme source de l'action.

#### `handle_agent_task(payload)`

```python
def handle_agent_task(payload)
```

**Description**
Cette fonction est le point d'entrée principal pour l'exécution d'une tâche AI via un agent spécialisé. Elle reçoit un `payload` contenant le rôle de l'agent et le prompt à traiter, puis utilise `get_agent_session` pour obtenir la session de l'agent et soumet le prompt via `call_ai_robust`.

**Arguments**
*   `payload` (dict): Un dictionnaire contenant les informations nécessaires à l'exécution de la tâche de l'agent.
    *   `'agent_role'` (str, optionnel): Le rôle de l'agent à utiliser pour cette tâche (ex: "DEVELOPER"). Si non spécifié, il est par défaut à "ASSISTANT". La valeur est convertie en majuscules.
    *   `'prompt'` (str, requis): La question ou l'instruction à soumettre à l'agent AI.

**Retourne**
*   `str`: La réponse générée par l'agent AI suite à l'exécution du `prompt`.
*   `str`: Un message d'erreur si le `prompt` est manquant dans le `payload`.

**Logique interne**
1.  Extrait `'agent_role'` du `payload`, en lui attribuant "ASSISTANT" par défaut s'il est absent et en le convertissant en majuscules.
2.  Extrait `'prompt'` du `payload`.
3.  Vérifie si le `prompt` est vide ou manquant. Si c'est le cas, retourne une chaîne d'erreur.
4.  Appelle `get_agent_session(agent_role)` pour récupérer la session AI associée au rôle spécifié. Cela garantit que l'agent utilise son contexte et sa mémoire précédents.
5.  Appelle `call_ai_robust(session, prompt)` pour soumettre le `prompt` à la session AI et obtenir une réponse. Cette fonction est conçue pour gérer les interactions avec le modèle de manière fiable.
6.  Retourne la réponse obtenue de l'agent AI.

**Décorateurs**
*   `@trace_action(source="swarm")`: Indique que l'exécution de cette fonction doit être tracée, avec "swarm" comme source de l'action.

## 3. Exemple d'usage

```python
from worker.handlers.swarm import handle_agent_task

# Exemple de payload pour une tâche d'architecte
architect_payload = {
    'agent_role': 'ARCHITECT',
    'prompt': 'Propose un modèle d\'architecture microservices pour une application de e-commerce à forte charge.'
}

# Exemple de payload pour une tâche de développeur
developer_payload = {
    'agent_role': 'DEVELOPER',
    'prompt': 'Écris un extrait de code Python pour une fonction qui calcule la suite de Fibonacci de manière récursive.'
}

# Exemple de payload pour une tâche d'assistant générique
assistant_payload = {
    'prompt': 'Quelle est la capitale de la France ?'
}

# Exécuter les tâches
architect_response = handle_agent_task(architect_payload)
print(f"Réponse de l'architecte : \n{architect_response}\n")

developer_response = handle_agent_task(developer_payload)
print(f"Réponse du développeur : \n{developer_response}\n")

assistant_response = handle_agent_task(assistant_payload)
print(f"Réponse de l'assistant : \n{assistant_response}\n")

# Exemple de gestion d'erreur (prompt manquant)
error_payload = {
    'agent_role': 'TESTER'
    # 'prompt' est volontairement manquant ici
}
error_response = handle_agent_task(error_payload)
print(f"Réponse en cas d'erreur : \n{error_response}\n")
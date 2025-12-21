```json
[
  {
    "name": "AiMode",
    "type": "enum",
    "description": "Représente les différents modes de fonctionnement de l'IA.\n\n*   **STANDARD**: Mode de fonctionnement par défaut de l'IA.\n*   **ROUTER_STRICT**: Mode où l'IA agit comme un routeur strict, dirigeant les tâches sans interprétation supplémentaire.\n*   **CREATIVE**: Mode qui encourage une pensée plus créative et imaginative de l'IA.\n*   **REASONING**: Mode où l'IA se concentre sur des processus de raisonnement et de logique.",
    "members": [
      {"name": "STANDARD", "value": "standard"},
      {"name": "ROUTER_STRICT", "value": "router_strict"},
      {"name": "CREATIVE", "value": "creative"},
      {"name": "REASONING", "value": "reasoning"}
    ]
  },
  {
    "name": "SwarmAgent",
    "type": "enum",
    "description": "Définit les différents types d'agents qui composent le 'swarm' (essaim) de l'IA. Chaque agent a un rôle spécialisé.\n\n*   **ROUTER**: Agent responsable du routage et de la distribution des tâches.\n*   **ARCHITECT**: Agent chargé de la conception et de la planification des solutions.\n*   **CODER**: Agent spécialisé dans l'écriture de code.\n*   **REVIEWER**: Agent dont le rôle est de réviser et d'évaluer le travail effectué.\n*   **WRITER**: Agent dédié à la production de contenu écrit.\n*   **GUARDIAN**: Agent responsable de la sécurité et du respect des directives.",
    "members": [
      {"name": "ROUTER", "value": "ROUTER"},
      {"name": "ARCHITECT", "value": "ARCHITECT"},
      {"name": "CODER", "value": "CODER"},
      {"name": "REVIEWER", "value": "REVIEWER"},
      {"name": "WRITER", "value": "WRITER"},
      {"name": "GUARDIAN", "value": "GUARDIAN"}
    ]
  },
  {
    "name": "QuotaExceededException",
    "type": "class",
    "description": "Exception levée lorsque l'utilisation des ressources ou le nombre de requêtes dépasse le quota alloué."
  },
  {
    "name": "SafetyBlockedException",
    "type": "class",
    "description": "Exception levée lorsqu'une action ou une requête est bloquée par les mécanismes de sécurité de l'IA."
  },
  {
    "name": "ProviderError",
    "type": "class",
    "description": "Exception générique pour signaler une erreur survenue lors de l'interaction avec un fournisseur de services externe (par exemple, une API tierce)."
  }
]
```
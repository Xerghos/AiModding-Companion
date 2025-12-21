```json
[
  {
    "type": "function",
    "name": "__init__",
    "filename": "features/quality.py",
    "docstring": "Initialise le gestionnaire de qualité.\n:param worker_session: Session Gemini active (passée par le Worker).",
    "line_start": 23,
    "line_end": 30,
    "parameters": [
      {"name": "self", "type": "QualityManager"},
      {"name": "worker_session", "type": "Any"}
    ],
    "return_type": "None",
    "metrics": {
      "loc": 8,
      "complexity": 0,
      "todo_count": 0,
      "fixme_count": 0
    },
    "technical_debt": {
      "todos": [],
      "fixmes": []
    }
  },
  {
    "type": "function",
    "name": "_parse_critique",
    "filename": "features/quality.py",
    "docstring": "Extrait le score (0-100) de la réponse textuelle du critique.\nCherche des patterns comme \"Score: 85/100\", \"85/100\" ou juste \"85\".",
    "line_start": 32,
    "line_end": 57,
    "parameters": [
      {"name": "self", "type": "QualityManager"},
      {"name": "critique_text", "type": "str"}
    ],
    "return_type": "int",
    "metrics": {
      "loc": 26,
      "complexity": 1,
      "todo_count": 0,
      "fixme_count": 0
    },
    "technical_debt": {
      "todos": [],
      "fixmes": []
    }
  },
  {
    "type": "function",
    "name": "validate_and_refine",
    "filename": "features/quality.py",
    "docstring": "Exécute la boucle de qualité (Quality Loop).\n\n:param initial_content: Le brouillon initial (str) ou None si doit être généré from scratch.\n:param context_instruction: L'instruction précise de la tâche (ex: \"Documente ce fichier\").\n:param generator_role: Le Persona Swarm qui produit/corrige (ex: WRITER, REFACTORER).\n:param validator_role: Le Persona Swarm qui note (ex: GUARDIAN).\n:return: Le contenu final optimisé (str).",
    "line_start": 60,
    "line_end": 134,
    "parameters": [
      {"name": "self", "type": "QualityManager"},
      {"name": "initial_content", "type": "Optional[str]"},
      {"name": "context_instruction", "type": "str"},
      {"name": "generator_role", "type": "str", "default": "TECHNICAL_WRITER"},
      {"name": "validator_role", "type": "str", "default": "GUARDIAN"}
    ],
    "return_type": "str",
    "metrics": {
      "loc": 75,
      "complexity": 4,
      "todo_count": 0,
      "fixme_count": 0
    },
    "technical_debt": {
      "todos": [],
      "fixmes": []
    }
  },
  {
    "type": "function",
    "name": "run_quality_process",
    "filename": "features/quality.py",
    "docstring": "Helper pour instancier et lancer le process rapidement depuis le Worker.",
    "line_start": 136,
    "line_end": 139,
    "parameters": [
      {"name": "worker_session", "type": "Any"},
      {"name": "instruction", "type": "str"},
      {"name": "initial_draft", "type": "Optional[str]", "default": "None"},
      {"name": "gen_role", "type": "str", "default": "ARCHITECT"},
      {"name": "val_role", "type": "str", "default": "GUARDIAN"}
    ],
    "return_type": "str",
    "metrics": {
      "loc": 4,
      "complexity": 0,
      "todo_count": 0,
      "fixme_count": 0
    },
    "technical_debt": {
      "todos": [],
      "fixmes": []
    }
  },
  {
    "type": "class",
    "name": "QualityManager",
    "filename": "features/quality.py",
    "docstring": "Moteur autonome de validation et d'amélioration continue (Feedback Loop).\nUtilise l'architecture Swarm pour alterner entre un Générateur et un Critique.",
    "line_start": 21,
    "line_end": 134,
    "metrics": {
      "loc": 113,
      "complexity": 0,
      "todo_count": 0,
      "fixme_count": 0
    },
    "technical_debt": {
      "todos": [],
      "fixmes": []
    },
    "definitions": {
      "methods": ["__init__", "_parse_critique", "validate_and_refine"]
    }
  }
]
```
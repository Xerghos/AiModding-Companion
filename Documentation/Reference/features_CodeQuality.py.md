```json
{
  "file_path": "features/CodeQuality.py",
  "module_name": "CodeQuality",
  "functions": [
    {
      "name": "_lister_fichiers_pertinents",
      "description": "Retourne une liste nettoyée de fichiers à analyser (exclut les dossiers techniques).",
      "parameters": [
        {
          "name": "abs_path",
          "type": "str",
          "description": "Le chemin absolu du fichier ou du dossier à parcourir."
        }
      ],
      "return_value": {
        "type": "list",
        "description": "Une liste de chemins absolus vers les fichiers éligibles pour l'analyse."
      },
      "dependencies": [
        "os",
        "config.constants.SUPPORTED_FILE_EXTENSIONS"
      ],
      "complexity": 0,
      "loc": 23,
      "docstring": "Retourne une liste nettoyée de fichiers à analyser (exclut les dossiers techniques)."
    },
    {
      "name": "execute_verifier_code",
      "description": "Audit statique (Linting & Sécurité) sur un fichier ou un dossier.",
      "parameters": [
        {
          "name": "chemin",
          "type": "str",
          "description": "Le chemin du fichier ou du dossier à auditer."
        },
        {
          "name": "session",
          "type": "object",
          "description": "L'objet de session de l'IA."
        },
        {
          "name": "action_log_path",
          "type": "str",
          "description": "Le chemin vers le fichier de log des actions."
        },
        {
          "name": "result_queue",
          "type": "queue.Queue",
          "description": "Une file d'attente pour les mises à jour de l'interface utilisateur.",
          "optional": true
        },
        {
          "name": "kwargs",
          "type": "dict",
          "description": "Arguments supplémentaires, notamment 'consigne'."
        }
      ],
      "return_value": {
        "type": "str",
        "description": "Le rapport d'audit ou un message d'erreur."
      },
      "dependencies": [
        "config.paths.get_path",
        "features.Shared.smart_resolve_path",
        "features.Shared.log_action",
        "ai_core.sessions.call_ai_robust",
        "features.Decorators.trace_action",
        "_lister_fichiers_pertinents"
      ],
      "complexity": 4,
      "loc": 76,
      "docstring": "Audit statique (Linting & Sécurité) sur un fichier ou un dossier.\nCommande : audit_qualite, verifier_code"
    },
    {
      "name": "execute_analyser_code",
      "description": "Analyse structurelle et sémantique (Architecture, Dépendances, Logique).",
      "parameters": [
        {
          "name": "chemin",
          "type": "str",
          "description": "Le chemin du fichier ou du dossier à analyser."
        },
        {
          "name": "session",
          "type": "object",
          "description": "L'objet de session de l'IA."
        },
        {
          "name": "action_log_path",
          "type": "str",
          "description": "Le chemin vers le fichier de log des actions."
        },
        {
          "name": "result_queue",
          "type": "queue.Queue",
          "description": "Une file d'attente pour les mises à jour de l'interface utilisateur.",
          "optional": true
        },
        {
          "name": "kwargs",
          "type": "dict",
          "description": "Arguments supplémentaires."
        }
      ],
      "return_value": {
        "type": "str",
        "description": "Le rapport d'analyse structurelle ou un message d'erreur."
      },
      "dependencies": [
        "config.paths.get_path",
        "features.Shared.smart_resolve_path",
        "features.Shared.log_action",
        "ai_core.sessions.call_ai_robust",
        "features.Decorators.trace_action",
        "_lister_fichiers_pertinents"
      ],
      "complexity": 5,
      "loc": 66,
      "docstring": "Analyse structurelle et sémantique (Architecture, Dépendances, Logique).\nCommande : analyser_code"
    },
    {
      "name": "execute_generer_tests",
      "description": "Génère des tests unitaires pour un fichier donné.",
      "parameters": [
        {
          "name": "chemin_source",
          "type": "str",
          "description": "Le chemin absolu du fichier source pour lequel générer des tests."
        },
        {
          "name": "session",
          "type": "object",
          "description": "L'objet de session de l'IA."
        },
        {
          "name": "action_log_path",
          "type": "str",
          "description": "Le chemin vers le fichier de log des actions."
        },
        {
          "name": "result_queue",
          "type": "queue.Queue",
          "description": "Une file d'attente pour les mises à jour de l'interface utilisateur.",
          "optional": true
        },
        {
          "name": "kwargs",
          "type": "dict",
          "description": "Arguments supplémentaires."
        }
      ],
      "return_value": {
        "type": "str",
        "description": "Un message de succès avec le chemin du fichier de tests et un extrait du code généré, ou un message d'erreur."
      },
      "dependencies": [
        "os",
        "logging",
        "json",
        "traceback",
        "config.paths.get_path",
        "features.Shared.smart_resolve_path",
        "features.Shared.log_action",
        "ai_core.sessions.call_ai_robust",
        "features.Decorators.trace_action",
        "features.core_backup",
        "logging.error"
      ],
      "complexity": 3,
      "loc": 70,
      "docstring": "Génère des tests unitaires pour un fichier donné.\nCommande : generer_tests"
    }
  ],
  "globals": [
    {
      "name": "log",
      "type": "Logger",
      "description": "Logger pour le module CodeQuality."
    },
    {
      "name": "ALWAYS_IGNORE_FILES",
      "type": "list",
      "description": "Liste des noms de fichiers à ignorer systématiquement lors de l'audit."
    },
    {
      "name": "backup_manager",
      "type": "module | None",
      "description": "Module pour la gestion des sauvegardes, ou None si l'importation échoue."
    }
  ],
  "imports": [
    {"name": "os", "module": null},
    {"name": "logging", "module": null},
    {"name": "json", "module": null},
    {"name": "traceback", "module": null},
    {"name": "get_path", "module": "config.paths"},
    {"name": "get_logger", "module": "config.logs"},
    {"name": "SUPPORTED_FILE_EXTENSIONS", "module": "config.constants"},
    {"name": "smart_resolve_path", "module": "features.Shared"},
    {"name": "log_action", "module": "features.Shared"},
    {"name": "call_ai_robust", "module": "ai_core.sessions"},
    {"name": "trace_action", "module": "features.Decorators"},
    {"name": "backup_manager", "module": "features.core_backup", "optional": true}
  ],
  "metrics": {
    "loc": 287,
    "complexity": 12,
    "todo_count": 0,
    "fixme_count": 0
  },
  "technical_debt": {
    "todos": [],
    "fixmes": []
  }
}
```
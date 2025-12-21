```json
{
  "file_path": "features/Refactoring.py",
  "id": "d2c21142-c94d-49d6-8354-e2991504e966",
  "name": "Refactoring",
  "description": "Ce module fournit des fonctions pour la modification, le refactoring et le formatage du code source. Il interagit avec l'IA pour proposer et appliquer des changements, tout en assurant la sécurité via des sauvegardes et des vérifications syntaxiques.",
  "functions": [
    {
      "name": "_verifier_syntaxe_python",
      "description": "Vérifie si un bloc de code Python est syntaxiquement valide en utilisant le module `ast`.",
      "parameters": [
        {
          "name": "code_content",
          "type": "str",
          "description": "Le contenu du code Python à vérifier."
        },
        {
          "name": "filename",
          "type": "str",
          "description": "Nom du fichier (utilisé dans les messages d'erreur). Par défaut 'temp.py'.",
          "default": "temp.py"
        }
      ],
      "returns": [
        {
          "type": "tuple",
          "description": "Un tuple contenant un booléen indiquant la validité et un message d'erreur ou None si valide."
        }
      ],
      "dependencies": [
        "ast"
      ],
      "metrics": {
        "loc": 16,
        "complexity": 2,
        "todo_count": 0,
        "fixme_count": 0
      }
    },
    {
      "name": "_extraire_code_python",
      "description": "Extrait proprement le code Python d'une réponse texte brute d'une IA. Gère les blocs Markdown, le texte brut et les phrases de politesse.",
      "parameters": [
        {
          "name": "texte_brut",
          "type": "str",
          "description": "Le texte brut reçu de l'IA."
        }
      ],
      "returns": [
        {
          "type": "str",
          "description": "Le code Python extrait et nettoyé."
        }
      ],
      "dependencies": [
        "re"
      ],
      "metrics": {
        "loc": 45,
        "complexity": 6,
        "todo_count": 0,
        "fixme_count": 0
      }
    },
    {
      "name": "execute_modifier_fichier",
      "description": "Applique une modification ciblée sur un fichier existant. Gère la sauvegarde, la lecture, l'appel IA pour la modification, la vérification syntaxique et l'écriture du fichier.",
      "parameters": [
        {
          "name": "chemin",
          "type": "str",
          "description": "Chemin relatif du fichier à modifier."
        },
        {
          "name": "instruction",
          "type": "str",
          "description": "Consigne de modification à appliquer."
        },
        {
          "name": "session",
          "type": "object",
          "description": "Objet de session pour l'appel IA."
        },
        {
          "name": "action_log_path",
          "type": "str",
          "description": "Chemin vers le fichier de log des actions."
        },
        {
          "name": "result_queue",
          "type": "object",
          "description": "File d'attente pour renvoyer des résultats à l'interface utilisateur."
        },
        {
          "name": "kwargs",
          "type": "dict",
          "description": "Arguments supplémentaires (pour compatibilité)."
        }
      ],
      "returns": [
        {
          "type": "str",
          "description": "Message de succès ou d'erreur décrivant le résultat de l'opération."
        }
      ],
      "decorators": [
        {
          "name": "trace_action",
          "args": ["source=\"Refactoring\""]
        }
      ],
      "dependencies": [
        "os",
        "config.paths.get_path",
        "config.logs.get_logger",
        "features.Shared.log_action",
        "ai_core.sessions.call_ai_robust",
        "features.core_backup.create_backup",
        "features.context.database.add_file_to_db",
        "_verifier_syntaxe_python",
        "_extraire_code_python"
      ],
      "metrics": {
        "loc": 103,
        "complexity": 8,
        "todo_count": 0,
        "fixme_count": 0
      }
    },
    {
      "name": "execute_refactoriser_code",
      "description": "Analyse et propose un plan de refactoring pour une cible donnée (fichier ou dossier). Peut appliquer directement les modifications si `auto_apply` est True.",
      "parameters": [
        {
          "name": "cible",
          "type": "str",
          "description": "Chemin du fichier ou dossier à refactoriser."
        },
        {
          "name": "consigne",
          "type": "str",
          "description": "Instruction décrivant l'objectif du refactoring."
        },
        {
          "name": "session",
          "type": "object",
          "description": "Objet de session pour l'appel IA."
        },
        {
          "name": "action_log_path",
          "type": "str",
          "description": "Chemin vers le fichier de log des actions."
        },
        {
          "name": "result_queue",
          "type": "object",
          "description": "File d'attente pour renvoyer des résultats à l'interface utilisateur."
        },
        {
          "name": "auto_apply",
          "type": "bool",
          "description": "Si True, applique directement les modifications (si la cible est un fichier). Sinon, propose un plan.",
          "default": false
        },
        {
          "name": "kwargs",
          "type": "dict",
          "description": "Arguments supplémentaires (pour compatibilité)."
        }
      ],
      "returns": [
        {
          "type": "str",
          "description": "Un plan de refactoring détaillé ou le résultat de l'application directe."
        }
      ],
      "decorators": [
        {
          "name": "trace_action",
          "args": ["source=\"Refactoring\""]
        }
      ],
      "dependencies": [
        "os",
        "config.paths.get_path",
        "config.constants.SUPPORTED_FILE_EXTENSIONS",
        "config.logs.get_logger",
        "features.Shared.log_action",
        "ai_core.sessions.call_ai_robust",
        "execute_modifier_fichier"
      ],
      "metrics": {
        "loc": 90,
        "complexity": 10,
        "todo_count": 0,
        "fixme_count": 0
      }
    },
    {
      "name": "execute_formater_code",
      "description": "Formate le code d'un fichier spécifié en utilisant l'IA. Agit comme un wrapper pour `execute_modifier_fichier` avec une instruction de formatage prédéfinie.",
      "parameters": [
        {
          "name": "fichier",
          "type": "str",
          "description": "Chemin du fichier à formater."
        },
        {
          "name": "session",
          "type": "object",
          "description": "Objet de session pour l'appel IA."
        },
        {
          "name": "action_log_path",
          "type": "str",
          "description": "Chemin vers le fichier de log des actions."
        },
        {
          "name": "result_queue",
          "type": "object",
          "description": "File d'attente pour renvoyer des résultats à l'interface utilisateur."
        },
        {
          "name": "kwargs",
          "type": "dict",
          "description": "Arguments supplémentaires (pour compatibilité)."
        }
      ],
      "returns": [
        {
          "type": "str",
          "description": "Message de succès ou d'erreur de l'opération de modification."
        }
      ],
      "decorators": [
        {
          "name": "trace_action",
          "args": ["source=\"Refactoring\""]
        }
      ],
      "dependencies": [
        "execute_modifier_fichier"
      ],
      "metrics": {
        "loc": 10,
        "complexity": 1,
        "todo_count": 0,
        "fixme_count": 0
      }
    }
  ],
  "imports": [
    {
      "module": "os",
      "from": null
    },
    {
      "module": "logging",
      "from": null
    },
    {
      "module": "re",
      "from": null
    },
    {
      "module": "ast",
      "from": null
    },
    {
      "module": "config.paths",
      "from": "get_path"
    },
    {
      "module": "config.logs",
      "from": "get_logger"
    },
    {
      "module": "config.constants",
      "from": "SUPPORTED_FILE_EXTENSIONS"
    },
    {
      "module": "features.Shared",
      "from": "log_action"
    },
    {
      "module": "ai_core.sessions",
      "from": "call_ai_robust"
    },
    {
      "module": "features.Decorators",
      "from": "trace_action"
    },
    {
      "module": "features.core_backup",
      "from": null,
      "optional": true
    },
    {
      "module": "core_backup",
      "from": null,
      "optional": true
    },
    {
      "module": "features.context",
      "from": "database",
      "optional": true
    }
  ],
  "metrics": {
    "loc": 258,
    "complexity": 28,
    "todo_count": 0,
    "fixme_count": 0,
    "file_count": 1
  },
  "technical_debt": {
    "todos": [],
    "fixmes": []
  },
  "constants": [],
  "classes": []
}
```
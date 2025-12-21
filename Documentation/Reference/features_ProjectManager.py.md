```json
{
  "file_path": "features/ProjectManager.py",
  "name": "ProjectManager",
  "description": "Ce module gère la gestion et la mise à jour des artefacts de projet tels que la roadmap, le plan technique et le changelog. Il utilise des appels aux modèles d'IA pour générer et synthétiser des informations, tout en intégrant des mécanismes de sauvegarde et de journalisation des actions.",
  "functions": [
    {
      "name": "execute_mettre_a_jour_roadmap",
      "description": "Wrapper de compatibilité pour `execute_generer_roadmap_synthetique`. Assure la rétrocompatibilité avec d'anciennes appels ou configurations.",
      "parameters": [
        {"name": "instruction", "type": "str", "description": "Instruction textuelle pour guider la mise à jour de la roadmap."},
        {"name": "session", "type": "object", "description": "Session AI à utiliser (si différente de celle par défaut)."},
        {"name": "action_log_path", "type": "str", "description": "Chemin vers le fichier de log des actions pour enregistrer l'opération."},
        {"name": "result_queue", "type": "object", "description": "Queue pour envoyer des mises à jour UI (ex: statut, contenu de fichier)."},
        {"name": "**kwargs", "type": "dict", "description": "Arguments supplémentaires."}
      ],
      "returns": "str",
      "dependencies": [
        "features.ProjectManager.execute_generer_roadmap_synthetique"
      ],
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
      "name": "execute_generer_roadmap_synthetique",
      "description": "Génère ou met à jour le fichier `roadmap.md` en se basant sur les actions récentes enregistrées dans `action_log.json`. La génération est effectuée par un modèle IA spécialisé dans l'écriture, et le contenu est ajouté en mode append.",
      "parameters": [
        {"name": "instruction", "type": "str", "description": "Instruction spécifique pour la génération de la roadmap. Par défaut, une mise à jour standard."},
        {"name": "session", "type": "object", "description": "Session AI à utiliser (si différente de celle par défaut)."},
        {"name": "action_log_path", "type": "str", "description": "Chemin vers le fichier de log des actions. Utilise `get_path('action_log.json')` par défaut."},
        {"name": "result_queue", "type": "object", "description": "Queue pour envoyer des mises à jour UI (ex: statut, contenu de fichier)."},
        {"name": "**kwargs", "type": "dict", "description": "Arguments supplémentaires, notamment pour l'instruction."}
      ],
      "returns": "str",
      "dependencies": [
        "config.paths.get_path",
        "config.logs.get_logger",
        "config.settings.ROADMAP_FILE",
        "config.settings.charger_json_robuste",
        "features.Shared.log_action",
        "ai_core.sessions.SessionFactory",
        "ai_core.sessions.call_ai_robust",
        "features.Decorators.trace_action",
        "features.core_backup",
        "datetime.datetime.now",
        "os.path.exists",
        "open",
        "os.path.join"
      ],
      "metrics": {
        "loc": 68,
        "complexity": 3,
        "todo_count": 0,
        "fixme_count": 0
      },
      "technical_debt": {
        "todos": [],
        "fixmes": []
      }
    },
    {
      "name": "execute_synthese_historique",
      "description": "Crée une synthèse concise de l'activité récente du projet (historique des conversations et actions techniques). La synthèse est enregistrée dans `synthese_activite.json` et retournée sous forme de texte formaté.",
      "parameters": [
        {"name": "filtre", "type": "str", "description": "Un filtre optionnel pour orienter la synthèse vers des aspects spécifiques."},
        {"name": "session", "type": "object", "description": "Session AI à utiliser (par défaut, type 'router')."},
        {"name": "action_log_path", "type": "str", "description": "Chemin vers le fichier de log des actions. Utilise `get_path('action_log.json')` par défaut."},
        {"name": "result_queue", "type": "object", "description": "Queue pour envoyer des mises à jour UI (ex: message d'état)."},
        {"name": "**kwargs", "type": "dict", "description": "Arguments supplémentaires, notamment pour le filtre."}
      ],
      "returns": "str",
      "dependencies": [
        "config.paths.get_path",
        "config.logs.get_logger",
        "config.settings.charger_json_robuste",
        "config.settings.sauvegarder_json",
        "ai_core.sessions.SessionFactory",
        "ai_core.sessions.call_ai_robust",
        "features.Decorators.trace_action",
        "datetime.datetime.now",
        "re"
      ],
      "metrics": {
        "loc": 43,
        "complexity": 2,
        "todo_count": 0,
        "fixme_count": 0
      },
      "technical_debt": {
        "todos": [],
        "fixmes": []
      }
    },
    {
      "name": "regenerer_plan_technique_atomique",
      "description": "Génère ou met à jour le fichier `PLAN_TECHNIQUE_ATOMIQUE.md`. Ce processus implique l'analyse de l'architecture globale du projet et la liste des fichiers, puis l'utilisation d'un modèle IA 'architecte' pour produire le contenu du plan.",
      "parameters": [
        {"name": "instruction", "type": "str", "description": "Instruction pour guider la régénération du plan. Par défaut, 'Mise à jour standard.'."},
        {"name": "session", "type": "object", "description": "Session AI à utiliser (par défaut, type 'architect')."},
        {"name": "action_log_path", "type": "str", "description": "Chemin vers le fichier de log des actions."},
        {"name": "result_queue", "type": "object", "description": "Queue pour envoyer des mises à jour UI (ex: message d'état)."},
        {"name": "**kwargs", "type": "dict", "description": "Arguments supplémentaires."}
      ],
      "returns": "str",
      "dependencies": [
        "config.paths.get_path",
        "config.logs.get_logger",
        "features.Shared.log_action",
        "ai_core.sessions.SessionFactory",
        "ai_core.sessions.call_ai_robust",
        "features.Decorators.trace_action",
        "features.core_backup",
        "features.Documentation._analyse_globale_architecture",
        "features.Documentation._lister_fichiers_cibles",
        "os.path.exists",
        "open",
        "os.path.join",
        "os.makedirs",
        "os.path.relpath"
      ],
      "metrics": {
        "loc": 64,
        "complexity": 3,
        "todo_count": 0,
        "fixme_count": 0
      },
      "technical_debt": {
        "todos": [],
        "fixmes": []
      }
    },
    {
      "name": "execute_generer_changelog_append_only",
      "description": "Met à jour le fichier `changelogs.md` en ajoutant les phases terminées du `PLAN_TECHNIQUE_ATOMIQUE.md` qui n'y figurent pas encore. Le mode est 'append-only' pour conserver l'historique.",
      "parameters": [
        {"name": "session", "type": "object", "description": "Session AI à utiliser (si nécessaire pour des contextes plus larges)."},
        {"name": "action_log_path", "type": "str", "description": "Chemin vers le fichier de log des actions."},
        {"name": "result_queue", "type": "object", "description": "Queue pour envoyer des mises à jour UI (ex: contenu de fichier mis à jour)."},
        {"name": "**kwargs", "type": "dict", "description": "Arguments supplémentaires."}
      ],
      "returns": "str",
      "dependencies": [
        "config.paths.get_path",
        "config.logs.get_logger",
        "features.Shared.log_action",
        "features.Decorators.trace_action",
        "features.core_backup",
        "datetime.datetime.now",
        "os.path.exists",
        "open",
        "re"
      ],
      "metrics": {
        "loc": 68,
        "complexity": 4,
        "todo_count": 0,
        "fixme_count": 0
      },
      "technical_debt": {
        "todos": [],
        "fixmes": []
      }
    }
  ],
  "metrics": {
    "loc": 290,
    "complexity": 12,
    "todo_count": 0,
    "fixme_count": 0
  },
  "technical_debt": {
    "todos": [],
    "fixmes": []
  },
  "dependencies": [
    "os",
    "json",
    "datetime",
    "logging",
    "re",
    "config.paths.get_path",
    "config.logs.get_logger",
    "config.settings.ROADMAP_FILE",
    "config.settings.FULL_ROADMAP_FILE",
    "config.settings.ROADMAP_BACKUP_DIR",
    "config.settings.charger_json_robuste",
    "config.settings.sauvegarder_json",
    "features.Shared.log_action",
    "ai_core.sessions.call_ai_robust",
    "ai_core.factory.SessionFactory",
    "features.Decorators.trace_action",
    "features.core_backup",
    "features.Documentation"
  ],
  "used_by": []
}
```
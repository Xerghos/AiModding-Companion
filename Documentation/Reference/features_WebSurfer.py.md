```json
{
  "file_path": "features\\WebSurfer.py",
  "module_name": "WebSurfer",
  "description": "Module gérant les interactions avec un navigateur web via Playwright pour effectuer des recherches, naviguer vers des URLs, et capturer des écrans. Il implémente un modèle Singleton pour la gestion du navigateur et des pages afin d'optimiser les ressources. Le nettoyage du HTML extrait est effectué pour le rendre plus facile à traiter par des modèles linguistiques.",
  "functions": [
    {
      "name": "_ensure_playwright",
      "description": "Charge Playwright et initialise le navigateur et la page s'ils ne sont pas déjà actifs. Crée une nouvelle page si la précédente est fermée. Configure un user-agent générique pour éviter les blocages simples.",
      "parameters": [],
      "return_type": "Page",
      "dependencies": [
        "playwright.sync_api"
      ],
      "metrics": {
        "loc": 35,
        "complexity": 2
      },
      "technical_debt": {
        "todos": [],
        "fixmes": []
      }
    },
    {
      "name": "_clean_html_text",
      "description": "Nettoie le contenu HTML brut pour extraire uniquement le texte pertinent. Supprime les balises script, style, nav, footer, header, svg, et noscript. Normalise les espaces et les lignes vides pour un texte plus propre et facile à utiliser.",
      "parameters": [
        {
          "name": "html_content",
          "type": "str",
          "description": "Le contenu HTML brut à nettoyer."
        }
      ],
      "return_type": "str",
      "dependencies": [
        "bs4"
      ],
      "metrics": {
        "loc": 22,
        "complexity": 3
      },
      "technical_debt": {
        "todos": [],
        "fixmes": []
      }
    },
    {
      "name": "handle_web_search",
      "description": "Effectue une recherche sur Google avec une requête donnée. Navigue vers la page de résultats, tente de refuser les cookies, et extrait les 6 premiers résultats (titre, lien, extrait). Retourne une chaîne formatée des résultats ou un message d'erreur.",
      "decorators": [
        {
          "name": "trace_action",
          "args": ["source=\"WebSurfer\""]
        }
      ],
      "parameters": [
        {
          "name": "query",
          "type": "str",
          "description": "Les mots-clés pour la recherche Google."
        },
        {
          "name": "session",
          "type": "any",
          "description": "Session de l'IA (peut être utilisé pour des appels futurs)."
        },
        {
          "name": "result_queue",
          "type": "Queue",
          "description": "File d'attente pour envoyer des mises à jour à l'UI."
        },
        {
          "name": "action_log_path",
          "type": "str",
          "description": "Chemin du fichier de log d'action."
        },
        {
          "name": "task_queue",
          "type": "Queue",
          "description": "File d'attente des tâches."
        }
      ],
      "return_type": "str",
      "dependencies": [
        "config.logs.get_logger",
        "features.UnifiedLogger.UnifiedLogger",
        "features.Decorators.trace_action",
        "features.WebSurfer._ensure_playwright"
      ],
      "metrics": {
        "loc": 52,
        "complexity": 4
      },
      "technical_debt": {
        "todos": [],
        "fixmes": []
      }
    },
    {
      "name": "handle_web_navigate",
      "description": "Navigue vers une URL spécifiée. Extrait le titre, le contenu HTML brut, le nettoie, et génère un résumé via une IA si le contenu est trop long. Retourne le titre, l'URL, le résumé (si applicable) et un extrait du contenu nettoyé.",
      "decorators": [
        {
          "name": "trace_action",
          "args": ["source=\"WebSurfer\""]
        }
      ],
      "parameters": [
        {
          "name": "url",
          "type": "str",
          "description": "L'URL vers laquelle naviguer."
        },
        {
          "name": "session",
          "type": "any",
          "description": "Session de l'IA pour les appels au modèle."
        },
        {
          "name": "result_queue",
          "type": "Queue",
          "description": "File d'attente pour envoyer des mises à jour à l'UI."
        },
        {
          "name": "action_log_path",
          "type": "str",
          "description": "Chemin du fichier de log d'action."
        },
        {
          "name": "task_queue",
          "type": "Queue",
          "description": "File d'attente des tâches."
        }
      ],
      "return_type": "str",
      "dependencies": [
        "ai_core.sessions.call_ai_robust",
        "config.logs.get_logger",
        "features.UnifiedLogger.UnifiedLogger",
        "features.Decorators.trace_action",
        "features.WebSurfer._ensure_playwright",
        "features.WebSurfer._clean_html_text"
      ],
      "metrics": {
        "loc": 63,
        "complexity": 5
      },
      "technical_debt": {
        "todos": [],
        "fixmes": []
      }
    },
    {
      "name": "handle_web_screenshot",
      "description": "Prend une capture d'écran de la page web actuelle et la sauvegarde dans le répertoire 'screenshots' avec un nom basé sur le temps ou un nom fourni. Retourne le chemin du fichier sauvegardé ou un message d'erreur.",
      "decorators": [
        {
          "name": "trace_action",
          "args": ["source=\"WebSurfer\""]
        }
      ],
      "parameters": [
        {
          "name": "filename",
          "type": "str",
          "description": "Nom optionnel pour le fichier de capture d'écran."
        },
        {
          "name": "session",
          "type": "any",
          "description": "Session de l'IA."
        },
        {
          "name": "result_queue",
          "type": "Queue",
          "description": "File d'attente pour envoyer des mises à jour à l'UI."
        },
        {
          "name": "action_log_path",
          "type": "str",
          "description": "Chemin du fichier de log d'action."
        },
        {
          "name": "task_queue",
          "type": "Queue",
          "description": "File d'attente des tâches."
        }
      ],
      "return_type": "str",
      "dependencies": [
        "os",
        "time",
        "config.paths.get_path",
        "config.logs.get_logger",
        "features.UnifiedLogger.UnifiedLogger",
        "features.Decorators.trace_action",
        "features.WebSurfer._ensure_playwright"
      ],
      "metrics": {
        "loc": 27,
        "complexity": 2
      },
      "technical_debt": {
        "todos": [],
        "fixmes": []
      }
    },
    {
      "name": "close",
      "description": "Ferme proprement le navigateur Playwright et arrête le processus Playwright. Doit être appelée lors de la fermeture de l'application pour libérer les ressources.",
      "parameters": [],
      "return_type": "None",
      "dependencies": [
        "config.logs.get_logger",
        "features.UnifiedLogger.UnifiedLogger"
      ],
      "metrics": {
        "loc": 9,
        "complexity": 1
      },
      "technical_debt": {
        "todos": [],
        "fixmes": []
      }
    }
  ],
  "globals": [
    {
      "name": "_PLAYWRIGHT",
      "type": "object",
      "description": "Instance globale de Playwright (Singleton)."
    },
    {
      "name": "_BROWSER",
      "type": "object",
      "description": "Instance globale du navigateur Playwright (Singleton)."
    },
    {
      "name": "_PAGE",
      "type": "object",
      "description": "Instance globale de la page Playwright (Singleton)."
    },
    {
      "name": "log",
      "type": "Logger",
      "description": "Objet logger configuré pour le module WebSurfer."
    }
  ],
  "dependencies": [
    "os",
    "time",
    "logging",
    "bs4",
    "playwright.sync_api",
    "config.paths",
    "config.logs",
    "features.UnifiedLogger",
    "features.Decorators",
    "ai_core.sessions"
  ],
  "metrics": {
    "loc": 208,
    "complexity": 17,
    "todo_count": 0,
    "fixme_count": 0
  },
  "technical_debt": {
    "todos": [],
    "fixmes": []
  }
}
```
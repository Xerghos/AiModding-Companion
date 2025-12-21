```json
{
  "file_path": "config/tools_schema.py",
  "description": "Définit les schémas des outils disponibles pour l'IA, servant de contrat d'interface pour les modèles Gemini/Groq. Ce fichier catalogue les commandes utilisables par l'IA et leurs paramètres associés, organisées par catégories fonctionnelles.",
  "definitions": {
    "globals": [
      {
        "name": "TOOLS_SCHEMA",
        "type": "list",
        "description": "Liste de dictionnaires, où chaque dictionnaire représente un outil avec son nom, sa description, et les paramètres attendus.",
        "schema": {
          "type": "OBJECT",
          "properties": {
            "name": {
              "type": "STRING",
              "description": "Nom unique de l'outil (correspondant à la fonction à appeler)."
            },
            "description": {
              "type": "STRING",
              "description": "Description textuelle de ce que fait l'outil, et dans quels cas l'utiliser."
            },
            "parameters": {
              "type": "OBJECT",
              "description": "Structure décrivant les paramètres que l'outil accepte.",
              "properties": {
                "type": {
                  "type": "STRING",
                  "description": "Type de données des paramètres (généralement 'OBJECT')."
                },
                "properties": {
                  "type": "OBJECT",
                  "description": "Dictionnaire des propriétés (paramètres) attendues, avec leur type et description.",
                  "additionalProperties": {
                    "type": "OBJECT",
                    "properties": {
                      "type": {"type": "STRING"},
                      "description": {"type": "STRING"},
                      "enum": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                      }
                    }
                  }
                },
                "required": {
                  "type": "ARRAY",
                  "items": {"type": "STRING"},
                  "description": "Liste des noms des paramètres qui sont obligatoires."
                }
              }
            }
          },
          "required": ["name", "description", "parameters"]
        }
      }
    ],
    "functions": [],
    "classes": []
  },
  "dependencies": [],
  "used_by": [],
  "metrics": {
    "loc": 393,
    "complexity": 0,
    "todo_count": 0,
    "fixme_count": 0
  },
  "technical_debt": {
    "todos": [],
    "fixmes": []
  }
}
```
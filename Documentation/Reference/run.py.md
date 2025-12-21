```json
{
  "file": "run.py",
  "description": "Ce script est le point d'entrée principal de l'application. Il gère l'initialisation, la configuration de l'apparence de l'interface utilisateur, et le lancement de la boucle principale de l'application.",
  "functions": [
    {
      "name": "main",
      "description": "Fonction principale qui initialise l'application, configure l'apparence, crée la fenêtre principale et démarre la boucle d'événements.",
      "parameters": [],
      "return_type": "None",
      "code_snippet": "def main():\n    try:\n        # --- CONFIGURATION DE L'APPARENCE ---\n        # On définit le thème AVANT de créer la fenêtre\n        ctk.set_appearance_mode(\"Dark\")  # ou \"System\"\n        ctk.set_default_color_theme(\"blue\")\n        \n        # Options de mise à l'échelle (Si l'interface est trop grosse/petite)\n        ctk.set_widget_scaling(1.0)  # 1.0 = 100% (Standard)\n        ctk.set_window_scaling(1.0)  # 1.0 = 100% (Standard)\n\n        # Création de la fenêtre racine\n        root = ctk.CTk()\n        root.title(\"AiModding-Companion\")\n        \n        # Taille par défaut (ajustable)\n        root.geometry(\"1400x900\")\n\n        # Instanciation de l'App\n        app = GeminiApp(root)\n        \n        if 'UnifiedLogger' in locals():\n            UnifiedLogger.write(\"run\", \"SUCCESS\", \"--- APPLICATION DÉMARRÉE ---\")\n        \n        root.mainloop()\n\n    except Exception as e:\n        print(f\"\\n❌ CRASH : {e}\")\n        traceback.print_exc()\n        input(\"Appuyez sur Entrée...\")",
      "dependencies": [
        "customtkinter",
        "ui.main_window.GeminiApp",
        "config.logs.UnifiedLogger",
        "features.UnifiedLogger.UnifiedLogger"
      ],
      "exceptions": [
        "ImportError",
        "Exception"
      ]
    }
  ],
  "dependencies": [
    {
      "name": "os",
      "description": "Module pour interagir avec le système d'exploitation, utilisé ici pour manipuler les chemins de fichiers."
    },
    {
      "name": "sys",
      "description": "Module fournissant l'accès à des variables et fonctions propres à l'interpréteur Python, utilisé pour modifier le path et quitter le script."
    },
    {
      "name": "customtkinter",
      "description": "Bibliothèque pour créer des interfaces utilisateur modernes et personnalisées."
    },
    {
      "name": "traceback",
      "description": "Module pour afficher ou enregistrer les informations de traceback en cas d'erreur."
    },
    {
      "name": "ctypes",
      "description": "Module pour appeler des fonctions dans des bibliothèques partagées (DLLs), utilisé ici pour gérer la mise à l'échelle de la résolution sur Windows."
    },
    {
      "name": "config.logs",
      "description": "Module de configuration pour la gestion des logs."
    },
    {
      "name": "features.UnifiedLogger",
      "description": "Module pour un système de journalisation unifié."
    },
    {
      "name": "ui.main_window.GeminiApp",
      "description": "Classe représentant l'application principale de l'interface utilisateur."
    }
  ],
  "usage": {
    "entry_point": true,
    "script_execution": "Ce script est exécuté directement lorsque l'application est lancée."
  },
  "code_metrics": {
    "loc": 64,
    "complexity": 4,
    "todo_count": 0,
    "fixme_count": 0
  },
  "technical_debt": {
    "todos": [],
    "fixmes": []
  }
}
```
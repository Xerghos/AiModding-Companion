```json
[
  {
    "name": "OmniscientResolver",
    "type": "class",
    "description": "Moteur de résolution de chemin intelligent (Portage Legacy V2).\nStratégie : Exact -> Fuzzy -> RAG -> IA Sémantique.",
    "file": "features/SearchEngine.py",
    "line": 44,
    "methods": [
      {
        "name": "_get_recency_score",
        "type": "method",
        "description": "Calcule un score de récence basé sur la date de modification du fichier.",
        "file": "features/SearchEngine.py",
        "line": 51,
        "parameters": [
          {"name": "filepath", "type": "str", "description": "Le chemin complet du fichier."}
        ],
        "returns": {"type": "int", "description": "Score de récence (plus le chiffre est élevé, plus le fichier est récent)."}
      },
      {
        "name": "_get_project_structure_light",
        "type": "method",
        "description": "Génère une liste légère de la structure du projet racine pour l'IA.",
        "file": "features/SearchEngine.py",
        "line": 65,
        "parameters": [],
        "returns": {"type": "str", "description": "Chaîne de caractères représentant les dossiers de premier niveau du projet."}
      },
      {
        "name": "_semantic_resolve",
        "type": "method",
        "description": "Demande au Router (IA) de deviner le chemin le plus probable pour une requête donnée.",
        "file": "features/SearchEngine.py",
        "line": 78,
        "parameters": [
          {"name": "query", "type": "str", "description": "La requête de l'utilisateur pour trouver un chemin."}
        ],
        "returns": {"type": "str|None", "description": "Le chemin résolu par l'IA, ou None si aucune correspondance n'est trouvée."}
      },
      {
        "name": "resolve",
        "type": "method",
        "description": "Point d'entrée principal pour trouver un fichier en utilisant une stratégie multi-niveaux (Exact, Fuzzy, RAG, IA Sémantique).",
        "file": "features/SearchEngine.py",
        "line": 111,
        "parameters": [
          {"name": "query", "type": "str", "description": "La requête de l'utilisateur pour trouver un chemin."}
        ],
        "returns": {"type": "str|None", "description": "Le chemin résolu le plus probable, ou None si aucun chemin n'est trouvé."}
      }
    ]
  },
  {
    "name": "execute_recherche_texte",
    "type": "function",
    "description": "Recherche une chaîne de caractères dans le contenu des fichiers (fonctionnalité similaire à `grep`).\n\nArgs:\n    query (str): Le texte à chercher.\n    path (str): Le dossier racine de la recherche (par défaut '.').\n    session: Objet de session pour l'IA (peut être None).\n    action_log_path (str): Chemin vers le fichier de log d'actions.\n    result_queue (Queue): File d'attente pour envoyer des mises à jour UI.",
    "file": "features/SearchEngine.py",
    "line": 178,
    "parameters": [
      {"name": "query", "type": "str", "description": "Le texte à chercher."},
      {"name": "path", "type": "str", "description": "Le dossier racine de la recherche (par défaut '.')."},
      {"name": "session", "type": "object|None", "description": "Objet de session pour l'IA (peut être None)."},
      {"name": "action_log_path", "type": "str|None", "description": "Chemin vers le fichier de log d'actions."},
      {"name": "result_queue", "type": "Queue|None", "description": "File d'attente pour envoyer des mises à jour UI."},
      {"name": "**kwargs", "type": "dict", "description": "Arguments supplémentaires, notamment 'query' et 'path'."}
    ],
    "returns": {"type": "str", "description": "Un rapport des résultats de la recherche ou un message d'erreur."}
  },
  {
    "name": "execute_rechercher_fichiers",
    "type": "function",
    "description": "Recherche des fichiers par nom en utilisant un motif Glob.\n\nArgs:\n    pattern (str): Motif de recherche (ex: *.py, test_*).\n    chemin_racine (str): Dossier de départ pour la recherche (par défaut '.').\n    session: Objet de session pour l'IA (peut être None).\n    action_log_path (str): Chemin vers le fichier de log d'actions.\n    result_queue (Queue): File d'attente pour envoyer des mises à jour UI.",
    "file": "features/SearchEngine.py",
    "line": 253,
    "parameters": [
      {"name": "pattern", "type": "str", "description": "Motif de recherche (ex: *.py, test_*)."},
      {"name": "chemin_racine", "type": "str", "description": "Dossier de départ pour la recherche (par défaut '.')."},
      {"name": "session", "type": "object|None", "description": "Objet de session pour l'IA (peut être None)."},
      {"name": "action_log_path", "type": "str|None", "description": "Chemin vers le fichier de log d'actions."},
      {"name": "result_queue", "type": "Queue|None", "description": "File d'attente pour envoyer des mises à jour UI."},
      {"name": "**kwargs", "type": "dict", "description": "Arguments supplémentaires, notamment 'pattern' et 'chemin_racine'."}
    ],
    "returns": {"type": "str", "description": "Une liste des fichiers trouvés ou un message d'erreur."}
  },
  {
    "name": "omniscient_resolve_path",
    "type": "function",
    "description": "Wrapper pour appeler la méthode `resolve` de la classe `OmniscientResolver`.",
    "file": "features/SearchEngine.py",
    "line": 275,
    "parameters": [
      {"name": "query", "type": "str", "description": "La requête de l'utilisateur pour trouver un chemin."}
    ],
    "returns": {"type": "str|None", "description": "Le chemin résolu par OmniscientResolver."}
  }
]
```
```json
{
  "file_path": "scripts/rag_cli.py",
  "type": "module",
  "docstring": null,
  "metrics": {
    "loc": 41,
    "complexity": 2,
    "todo_count": 0,
    "fixme_count": 0
  },
  "technical_debt": {
    "todos": [],
    "fixmes": []
  },
  "definitions": {
    "classes": [],
    "functions": [
      "main"
    ],
    "globals": []
  },
  "dependencies": [
    "database.search_vector_db",
    "config.get_path"
  ],
  "used_by": [],
  "description": "Ce script Python fournit une interface en ligne de commande (CLI) pour effectuer des recherches de type Retrieval-Augmented Generation (RAG) sur une base de données vectorielle.\nIl prend une requête de recherche en argument, interroge la base de données vectorielle spécifiée et affiche les résultats pertinents.",
  "usage": [
    {
      "command": "python scripts/rag_cli.py \"<votre requête de recherche>\"",
      "description": "Exécute une recherche RAG avec la requête fournie et affiche les résultats."
    }
  ],
  "functions": {
    "main": {
      "name": "main",
      "description": "Fonction principale qui gère l'exécution de la recherche RAG via la CLI.",
      "args": [],
      "returns": null,
      "exceptions": [],
      "dependencies": [
        "sys.argv",
        "sys.exit",
        "config.get_path",
        "database.search_vector_db"
      ],
      "logic": [
        "Vérifie si au moins un argument (la requête) est fourni.",
        "Si aucun argument n'est fourni, affiche un message d'utilisation et quitte le programme.",
        "Récupère la requête de recherche à partir des arguments de la ligne de commande.",
        "Tente de récupérer le chemin de la base de données vectorielle en utilisant `config.get_path('database')`.",
        "En cas d'erreur lors de la récupération du chemin de la base de données, affiche un message d'erreur et quitte.",
        "Affiche un message indiquant que la recherche est en cours et le chemin de la base de données utilisée.",
        "Appelle la fonction `search_vector_db` du module `database` avec la requête et le chemin de la base de données.",
        "Si la fonction `search_vector_db` retourne une erreur, affiche le message d'erreur et quitte.",
        "Si aucun résultat n'est retourné par la recherche, affiche un message indiquant 'AUCUN RÉSULTAT'.",
        "Si des résultats sont retournés, affiche un titre indiquant le nombre de résultats et itère sur chaque résultat pour afficher le score, la source et le contenu."
      ]
    }
  }
}
```
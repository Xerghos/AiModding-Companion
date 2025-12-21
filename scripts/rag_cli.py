import sys
import os
from database import search_vector_db
from config import get_path # Nécessite l'accès à la fonction get_path

def main():
    if len(sys.argv) < 2:
        print("Usage: python rag_cli.py \"<votre requête de recherche>\"")
        sys.exit(1)

    query = sys.argv[1]
    
    # Assurez-vous d'utiliser le chemin de la DB approprié
    # Je vais supposer que 'get_path("database")' retourne le préfixe du chemin (ex: 'data/project_db')
    try:
        db_path = get_path("database")
    except Exception:
        # Fallback si 'get_path' n'est pas implémenté comme attendu ou la config est absente
        print("Erreur: Impossible de déterminer le chemin de la base de données via config.get_path('database').")
        sys.exit(1)

    print(f"Recherche RAG pour : '{query}' dans {db_path}...")
    
    # Utilisation de la fonction du module database
    results, error = search_vector_db(query, db_path, max_results=3)

    if error:
        print(f"\n--- ERREUR RAG ---")
        print(error)
        sys.exit(1)
        
    if not results:
        print("\n--- AUCUN RÉSULTAT ---")
        return

    print(f"\n--- RÉSULTATS (Top {len(results)}) ---")
    for source, content, score in results:
        print(f"\n[Score: {score}] Source: {source}")
        print("-" * 50)
        print(content)

if __name__ == "__main__":
    main()
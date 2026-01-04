#!/usr/bin/env python3
"""
Script de test pour la fonction calculate_indexing_stats.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import load_app_settings
from features.context.database import calculate_indexing_stats

def test_calculate_indexing_stats():
    """Teste la fonction calculate_indexing_stats."""
    print("Test de calculate_indexing_stats")
    print("=" * 50)
    
    # Charger les paramètres
    settings = load_app_settings()
    
    # Chemin racine (dossier courant)
    root_path = os.getcwd()
    
    print(f"Chemin racine: {root_path}")
    print(f"Dossiers exclus configurés: {settings.get('code_analysis', {}).get('ignored_folders', [])}")
    print(f"Fichiers watchlist: {settings.get('repo_map_cache', {}).get('watch_files', [])}")
    print()
    
    # Calculer les statistiques
    print("Calcul des statistiques...")
    stats = calculate_indexing_stats(root_path, settings)
    
    # Afficher les résultats
    print("Resultats:")
    print(f"  Fichiers à indexer: {stats['included']}")
    print(f"  Fichiers ignorés: {stats['excluded']}")
    print(f"  Exceptions (watchlist): {stats['bypassed']}")
    print()
    
    total = stats['included'] + stats['excluded'] + stats['bypassed']
    print(f"Total fichiers analysés: {total}")
    
    # Vérifications de base
    assert isinstance(stats, dict), "Le résultat doit être un dictionnaire"
    assert 'included' in stats, "Le dictionnaire doit contenir 'included'"
    assert 'excluded' in stats, "Le dictionnaire doit contenir 'excluded'"
    assert 'bypassed' in stats, "Le dictionnaire doit contenir 'bypassed'"
    
    print("Test réussi!")

if __name__ == "__main__":
    try:
        test_calculate_indexing_stats()
    except Exception as e:
        print(f"Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
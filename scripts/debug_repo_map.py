"""
Script de diagnostic pour analyser la génération de la Repo Map.
Permet d'identifier les problèmes de performance et d'exclusion.
"""

from features.context.repo_map import RepoMapGenerator, get_repo_map_generator
from features.context.symbol_graph import get_symbol_graph
from config.paths import get_path
from config.settings import APP_SETTINGS
import os
import fnmatch


def analyze_symbol_graph(symbol_graph):
    """Analyse le SymbolGraph pour identifier les fichiers top."""
    print("=== Analyse SymbolGraph ===")
    top_files = symbol_graph.get_top_files(top_n=20)
    
    if not top_files:
        print("⚠️ Aucun fichier trouvé dans le SymbolGraph!")
        return
    
    print(f"✅ {len(top_files)} fichiers trouvés:")
    for file_path, score in top_files:
        print(f"  - {file_path} (PageRank: {score:.4f})")


def analyze_exclusions():
    """Analyse les fichiers exclus par les patterns d'exclusion."""
    print("\n=== Analyse Exclusions ===")
    
    ignored_folders = APP_SETTINGS.get("code_analysis", {}).get("ignored_folders", [])
    ignored_files = APP_SETTINGS.get("system_settings", {}).get("ignored_files", [])
    
    print(f"Dossiers ignorés: {ignored_folders}")
    print(f"Fichiers ignorés: {ignored_files}")
    
    # Lister tous les fichiers Python dans les dossiers surveillés
    watch_dirs = ["features/", "ai_core/", "worker/"]
    all_py_files = []
    
    for dir_path in watch_dirs:
        abs_dir = get_path(dir_path) if not os.path.isabs(dir_path) else dir_path
        if os.path.exists(abs_dir):
            for root, dirs, files in os.walk(abs_dir):
                # Filtrer les dossiers ignorés
                dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'venv', 'env', 'node_modules']]
                
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, get_path("."))
                        all_py_files.append(rel_path)
    
    print(f"\nTotal fichiers Python trouvés: {len(all_py_files)}")
    
    # Vérifier les exclusions
    excluded_count = 0
    for file_path in all_py_files:
        is_excluded = False
        exclusion_reason = None
        
        # Vérifier les patterns de dossiers
        for pattern in ignored_folders:
            if fnmatch.fnmatch(file_path, pattern) or pattern in file_path:
                is_excluded = True
                exclusion_reason = f"Pattern dossier: {pattern}"
                break
        
        # Vérifier les patterns de fichiers
        if not is_excluded:
            for pattern in ignored_files:
                if fnmatch.fnmatch(file_path, pattern) or pattern in file_path:
                    is_excluded = True
                    exclusion_reason = f"Pattern fichier: {pattern}"
                    break
        
        if is_excluded:
            excluded_count += 1
            print(f"  ❌ EXCLU: {file_path} ({exclusion_reason})")
    
    print(f"\nFichiers exclus: {excluded_count}/{len(all_py_files)}")


def test_signature_extraction(repo_map_gen, symbol_graph):
    """Teste l'extraction de signatures pour chaque fichier top."""
    print("\n=== Test Extraction Signatures ===")
    
    top_files = symbol_graph.get_top_files(top_n=20)
    if not top_files:
        print("⚠️ Aucun fichier à tester")
        return
    
    empty_signatures = []
    for file_path, score in top_files:
        abs_path = get_path(file_path) if not os.path.isabs(file_path) else file_path
        if os.path.exists(abs_path):
            try:
                signatures = repo_map_gen._extract_signatures(abs_path)
                if signatures:
                    print(f"  ✅ {file_path}: {len(signatures)} signatures")
                else:
                    print(f"  ⚠️ {file_path}: Aucune signature extraite")
                    empty_signatures.append(file_path)
            except Exception as e:
                print(f"  ❌ {file_path}: Erreur - {e}")
        else:
            print(f"  ❌ {file_path}: Fichier introuvable")
    
    if empty_signatures:
        print(f"\n⚠️ {len(empty_signatures)} fichiers avec signatures vides:")
        for f in empty_signatures:
            print(f"  - {f}")


def main():
    """Fonction principale."""
    db_path = get_path(APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid"))
    repo_map_gen = get_repo_map_generator(db_path)
    symbol_graph = get_symbol_graph(db_path)
    
    print("=== Analyse SymbolGraph ===")
    analyze_symbol_graph(symbol_graph)
    
    print("\n=== Analyse Exclusions ===")
    analyze_exclusions()
    
    print("\n=== Test Extraction Signatures ===")
    test_signature_extraction(repo_map_gen, symbol_graph)


if __name__ == "__main__":
    main()

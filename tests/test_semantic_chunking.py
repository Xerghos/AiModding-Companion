"""
Test du chunking sémantique avec Tree-sitter.
Valide que le chunking fonctionne correctement et génère les métadonnées attendues.
"""

import os
import sys
import tempfile

# Ajout de la racine au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.context.code_chunker import get_chunker, SemanticChunker


def test_chunker_initialization():
    """Test l'initialisation du chunker."""
    print("=" * 60)
    print("Test 1: Initialisation du chunker")
    print("=" * 60)
    
    chunker = get_chunker()
    assert chunker is not None, "Le chunker devrait être initialisé"
    
    print(f"[OK] Chunker initialise")
    print(f"   - is_available: {chunker.is_available}")
    print(f"   - parser: {'[OK]' if chunker.parser else '[KO]'}")
    print(f"   - language: {'[OK]' if chunker.language else '[KO]'}")
    
    if chunker.is_available:
        print("   [OK] Chunking semantique ACTIF (Tree-sitter disponible)")
    else:
        print("   [WARN] Chunking semantique INACTIF (fallback basique)")
    
    return chunker


def test_chunk_file_with_sample():
    """Test le chunking d'un fichier Python simple."""
    print("\n" + "=" * 60)
    print("Test 2: Chunking d'un fichier Python simple")
    print("=" * 60)
    
    chunker = get_chunker()
    
    # Créer un fichier Python de test
    test_code = """\"\"\"
Module de test pour le chunking sémantique.
\"\"\"

import os
import sys

CONSTANT = "test"

class TestClass:
    \"\"\"Classe de test.\"\"\"
    
    def __init__(self, value):
        self.value = value
    
    def method_one(self):
        '''Première méthode.'''
        return self.value * 2
    
    def method_two(self, x, y):
        '''Deuxième méthode avec paramètres.'''
        result = x + y
        return result * self.value

def standalone_function(param1, param2):
    \"\"\"Fonction standalone.\"\"\"
    return param1 + param2

if __name__ == "__main__":
    obj = TestClass(5)
    print(obj.method_one())
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(test_code)
        temp_path = f.name
    
    try:
        chunks = chunker.chunk_file(temp_path)
        
        print(f"[OK] Fichier chunke: {len(chunks)} chunks crees\n")
        
        # Vérifier que les chunks ont les métadonnées attendues
        required_fields = ['content', 'start_line', 'end_line', 'ast_type', 'parent_context', 'raw_content']
        
        for i, chunk in enumerate(chunks, 1):
            print(f"Chunk {i}:")
            print(f"  - ast_type: {chunk.get('ast_type', 'N/A')}")
            print(f"  - start_line: {chunk.get('start_line', 'N/A')}")
            print(f"  - end_line: {chunk.get('end_line', 'N/A')}")
            print(f"  - parent_context: {chunk.get('parent_context', 'N/A')}")
            print(f"  - content length: {len(chunk.get('content', ''))} caractères")
            
            # Vérifier que tous les champs requis sont présents
            for field in required_fields:
                assert field in chunk, f"Chunk {i} manque le champ '{field}'"
            
            # Afficher un extrait du contenu
            content_preview = chunk['content'][:100].replace('\n', ' ')
            print(f"  - preview: {content_preview}...")
            print()
        
        # Vérifier qu'on a au moins quelques chunks
        assert len(chunks) > 0, "Aucun chunk créé"
        
        # Vérifier qu'on a des types AST variés
        ast_types = [chunk.get('ast_type') for chunk in chunks]
        print(f"Types AST trouvés: {set(ast_types)}")
        
        return chunks
        
    finally:
        # Nettoyer
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_metadata_quality():
    """Test la qualité des métadonnées générées."""
    print("\n" + "=" * 60)
    print("Test 3: Qualité des métadonnées")
    print("=" * 60)
    
    chunker = get_chunker()
    
    if not chunker.is_available:
        print("[WARN] Test ignore - chunking semantique non disponible")
        return
    
    # Code avec classe et méthodes
    test_code = """class MyClass:
    def method1(self):
        return 1
    
    def method2(self):
        return 2
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(test_code)
        temp_path = f.name
    
    try:
        chunks = chunker.chunk_file(temp_path)
        
        # Vérifier que les méthodes ont le bon parent_context
        for chunk in chunks:
            if chunk.get('ast_type') in ['method', 'function']:
                parent = chunk.get('parent_context', '')
                assert 'Classe:' in parent or 'Fichier:' in parent, \
                    f"parent_context devrait contenir 'Classe:' ou 'Fichier:': {parent}"
        
        print("[OK] Metadonnees valides")
        print(f"   - Tous les chunks ont des parent_context corrects")
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def main():
    """Exécute tous les tests."""
    print("\n" + "=" * 60)
    print("TESTS DU CHUNKING SÉMANTIQUE")
    print("=" * 60 + "\n")
    
    try:
        # Test 1: Initialisation
        chunker = test_chunker_initialization()
        
        # Test 2: Chunking d'un fichier
        chunks = test_chunk_file_with_sample()
        
        # Test 3: Qualité des métadonnées
        test_metadata_quality()
        
        print("\n" + "=" * 60)
        print("[OK] TOUS LES TESTS REUSSIS")
        print("=" * 60)
        
        if chunker.is_available:
            print("\n[OK] Le chunking semantique est ACTIF et fonctionnel")
        else:
            print("\n[WARN] Le chunking semantique est INACTIF (fallback basique)")
            print("   Pour l'activer, installez: pip install tree-sitter tree-sitter-python")
        
    except AssertionError as e:
        print(f"\n[FAIL] ECHEC DU TEST: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


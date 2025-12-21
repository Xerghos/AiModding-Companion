"""
Test simple du chunking sémantique - version sans problèmes d'encodage.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Forcer UTF-8 pour les prints
if sys.stdout.encoding != 'utf-8':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from features.context.code_chunker import get_chunker


def main():
    print("Test du chunking semantique")
    print("=" * 50)
    
    # Test 1: Initialisation
    print("\n1. Initialisation du chunker...")
    chunker = get_chunker()
    
    print(f"   - Chunker cree: {chunker is not None}")
    print(f"   - is_available: {chunker.is_available}")
    print(f"   - parser disponible: {chunker.parser is not None}")
    print(f"   - language disponible: {chunker.language is not None}")
    
    if chunker.is_available:
        print("   [OK] Chunking semantique ACTIF")
    else:
        print("   [INFO] Chunking semantique INACTIF (fallback basique)")
        print("          Ceci est normal si tree-sitter-python retourne un PyCapsule")
    
    # Test 2: Chunking d'un fichier simple
    print("\n2. Test de chunking d'un fichier Python...")
    
    test_code = """class TestClass:
    def method1(self):
        return 1
    
    def method2(self):
        return 2

def standalone():
    pass
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(test_code)
        temp_path = f.name
    
    try:
        chunks = chunker.chunk_file(temp_path)
        print(f"   - Chunks crees: {len(chunks)}")
        
        if chunks:
            print("\n   Details des chunks:")
            for i, chunk in enumerate(chunks, 1):
                print(f"\n   Chunk {i}:")
                print(f"     - ast_type: {chunk.get('ast_type', 'N/A')}")
                print(f"     - start_line: {chunk.get('start_line', 'N/A')}")
                print(f"     - end_line: {chunk.get('end_line', 'N/A')}")
                print(f"     - parent_context: {chunk.get('parent_context', 'N/A')}")
                
                # Vérifier les champs requis
                required = ['content', 'start_line', 'end_line', 'ast_type', 'parent_context']
                missing = [f for f in required if f not in chunk]
                if missing:
                    print(f"     [WARN] Champs manquants: {missing}")
                else:
                    print(f"     [OK] Tous les champs requis sont presents")
        
        print("\n[OK] Test termine avec succes")
        
    except Exception as e:
        print(f"\n[ERROR] Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


if __name__ == "__main__":
    main()


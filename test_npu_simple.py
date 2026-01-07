"""
Test simple du NPU Manager sans dépendances du projet.
"""

import sys
import os
import numpy as np

# Ajouter le chemin du projet
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importer directement le NPU Manager
try:
    from ai_core.hardware.npu_manager import NPUManager
    print("✅ NPU Manager importé avec succès")
except ImportError as e:
    print(f"❌ Erreur d'import: {e}")
    sys.exit(1)

def test_basic_functionality():
    """Test les fonctionnalités de base du NPU Manager."""
    print("\n=== Test des fonctionnalités de base ===")
    
    # 1. Initialisation
    print("1. Initialisation du NPU Manager...")
    manager = NPUManager()
    print(f"   ✅ Singleton créé")
    
    # 2. Configuration VAIP
    print("\n2. Vérification configuration VAIP...")
    assert hasattr(manager, 'vaip_config'), "Configuration VAIP manquante"
    print(f"   ✅ Configuration chargée")
    print(f"   Cache dir: {manager.vaip_config.get('cache_dir', 'N/A')}")
    
    # 3. Buckets
    print("\n3. Vérification des buckets...")
    assert hasattr(manager, 'BUCKET_SIZES'), "Buckets manquants"
    print(f"   ✅ Buckets: {manager.BUCKET_SIZES}")
    
    # 4. Providers
    print("\n4. Vérification des providers...")
    assert hasattr(manager, 'providers'), "Providers manquants"
    print(f"   ✅ Providers: {manager.providers}")
    
    # 5. Test bucket selection
    print("\n5. Test sélection bucket...")
    test_cases = [(50, 128), (200, 256), (512, 512), (1000, 1024)]
    for seq_len, expected in test_cases:
        bucket = manager._get_bucket_for_length(seq_len)
        print(f"   seq_len={seq_len} -> bucket={bucket} (attendu: {expected})")
        assert bucket == expected, f"Bucket incorrect pour seq_len={seq_len}"
    
    # 6. Test padding
    print("\n6. Test padding...")
    tokens = [1, 2, 3, 4, 5]
    padded = manager._pad_sequence(tokens, 10)
    print(f"   Tokens: {tokens}")
    print(f"   Padded (len={len(padded)}): {padded}")
    assert len(padded) == 10, "Longueur incorrecte après padding"
    
    return True

def test_onnx_availability():
    """Test la disponibilité d'ONNX Runtime."""
    print("\n=== Test ONNX Runtime ===")
    
    try:
        import onnxruntime as ort
        print("✅ ONNX Runtime disponible")
        
        # Vérifier les providers
        providers = ort.get_available_providers()
        print(f"   Providers disponibles: {providers}")
        
        # Vérifier si VitisAI est disponible
        if 'VitisAIExecutionProvider' in providers:
            print("   ✅ VitisAIExecutionProvider disponible !")
            return True
        else:
            print("   ⚠️  VitisAIExecutionProvider non disponible")
            print("   Providers disponibles:", providers)
            return False
            
    except ImportError:
        print("❌ ONNX Runtime non disponible")
        return False

def main():
    """Fonction principale."""
    print("=" * 60)
    print("TEST NPU MANAGER - ENVIRONNEMENT RYZEN AI")
    print("=" * 60)
    
    # Vérifier l'environnement
    print(f"Python: {sys.version}")
    print(f"CWD: {os.getcwd()}")
    
    # Exécuter les tests
    tests = [
        ("Fonctionnalités de base", test_basic_functionality),
        ("ONNX Runtime", test_onnx_availability),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*40}")
        print(f"Test: {test_name}")
        print('='*40)
        
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Résumé
    print("\n" + "=" * 60)
    print("RÉSUMUM")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests réussis")
    
    if passed == total:
        print("\n🎉 Tous les tests sont réussis !")
        print("Le NPU Manager est prêt pour l'utilisation.")
        print("\nProchaines étapes:")
        print("1. Télécharger un modèle ONNX (ex: nomic-embed-text-v1.5)")
        print("2. Utiliser manager.load_model() pour le charger sur NPU")
        print("3. Utiliser manager.infer() pour l'inférence")
        return 0
    else:
        print(f"\n⚠️  {total - passed} tests ont échoué")
        return 1

if __name__ == "__main__":
    sys.exit(main())
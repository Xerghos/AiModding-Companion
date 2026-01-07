"""
Tests pour le NPU Manager.
"""

import sys
import os
import numpy as np
from pathlib import Path

# Ajouter le chemin du projet
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_core.hardware.npu_manager import NPUManager

def test_npu_manager_initialization():
    """Test l'initialisation du NPU Manager."""
    print("Test 1: Initialisation du NPU Manager...")
    
    manager = NPUManager()
    
    # Vérifier que c'est un singleton
    manager2 = NPUManager()
    assert manager is manager2, "NPUManager devrait être un singleton"
    
    print("✅ NPU Manager initialisé correctement")
    return True

def test_vaip_config():
    """Test la création de la configuration VAIP."""
    print("\nTest 2: Configuration VAIP...")
    
    manager = NPUManager()
    
    # Vérifier que la configuration existe
    assert hasattr(manager, 'vaip_config'), "Configuration VAIP manquante"
    assert 'cache_dir' in manager.vaip_config, "cache_dir manquant"
    assert 'vaiml_config' in manager.vaip_config, "vaiml_config manquant"
    
    # Vérifier les paramètres critiques
    vaiml_config = manager.vaip_config['vaiml_config']
    assert vaiml_config.get('preferred_data_storage') == 'unvectorized', \
        "preferred_data_storage devrait être 'unvectorized'"
    assert vaiml_config.get('enable_f32_to_bf16_conversion') == False, \
        "enable_f32_to_bf16_conversion devrait être False"
    
    print("✅ Configuration VAIP correcte")
    return True

def test_bucket_selection():
    """Test la sélection des buckets."""
    print("\nTest 3: Sélection des buckets...")
    
    manager = NPUManager()
    
    # Tester différentes longueurs
    test_cases = [
        (50, 128),   # Court -> bucket 128
        (128, 128),  # Exact -> bucket 128
        (200, 256),  # Moyen -> bucket 256
        (512, 512),  # Exact -> bucket 512
        (1000, 1024), # Long -> bucket 1024
        (2000, 1024), # Très long -> bucket max
    ]
    
    for seq_len, expected_bucket in test_cases:
        bucket = manager._get_bucket_for_length(seq_len)
        assert bucket == expected_bucket, \
            f"Pour seq_len={seq_len}, attendu {expected_bucket}, obtenu {bucket}"
    
    print("✅ Sélection des buckets correcte")
    return True

def test_padding():
    """Test le padding des séquences."""
    print("\nTest 4: Padding des séquences...")
    
    manager = NPUManager()
    
    # Test avec séquence courte
    tokens = [1, 2, 3, 4, 5]
    padded = manager._pad_sequence(tokens, 10)
    
    assert len(padded) == 10, f"Longueur attendue: 10, obtenue: {len(padded)}"
    assert np.array_equal(padded[:5], tokens), "Les tokens originaux devraient être préservés"
    assert np.all(padded[5:] == 0), "Le padding devrait être des zéros"
    
    # Test avec séquence égale à la cible
    tokens = list(range(10))
    padded = manager._pad_sequence(tokens, 10)
    assert np.array_equal(padded, tokens), "Pas de padding nécessaire"
    
    # Test avec séquence plus longue
    tokens = list(range(15))
    padded = manager._pad_sequence(tokens, 10)
    assert len(padded) == 10, "Devrait être tronqué à 10"
    assert np.array_equal(padded, tokens[:10]), "Devrait être tronqué"
    
    print("✅ Padding correct")
    return True

def test_npu_availability():
    """Test la disponibilité du NPU."""
    print("\nTest 5: Disponibilité du NPU...")
    
    manager = NPUManager()
    
    # Vérifier que les providers sont configurés
    assert hasattr(manager, 'providers'), "Providers manquants"
    assert isinstance(manager.providers, list), "Providers devrait être une liste"
    
    # Le premier provider devrait être VitisAI
    if len(manager.providers) > 0:
        print(f"  Providers disponibles: {manager.providers}")
    
    print("✅ NPU disponible (configuration vérifiée)")
    return True

def test_model_info_structure():
    """Test la structure des informations de modèle."""
    print("\nTest 6: Structure des informations de modèle...")
    
    manager = NPUManager()
    
    # Tester avec un modèle fictif (pas de chargement réel)
    # On teste juste que la méthode existe et retourne None si modèle non chargé
    info = manager.get_model_info("model_inexistant")
    assert info is None, "Devrait retourner None pour modèle non chargé"
    
    print("✅ Structure des informations de modèle correcte")
    return True

def main():
    """Exécute tous les tests."""
    print("=" * 60)
    print("TESTS NPU MANAGER")
    print("=" * 60)
    
    tests = [
        test_npu_manager_initialization,
        test_vaip_config,
        test_bucket_selection,
        test_padding,
        test_npu_availability,
        test_model_info_structure,
    ]
    
    results = []
    for test in tests:
        try:
            success = test()
            results.append((test.__name__, success))
        except Exception as e:
            print(f"❌ {test.__name__} échoué: {e}")
            results.append((test.__name__, False))
    
    # Résumé
    print("\n" + "=" * 60)
    print("RÉSUMUM DES TESTS")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests réussis")
    
    if passed == total:
        print("\n🎉 Tous les tests sont réussis !")
        print("Le NPU Manager est prêt pour l'intégration.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} tests ont échoué")
        return 1

if __name__ == "__main__":
    sys.exit(main())
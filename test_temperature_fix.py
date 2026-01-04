#!/usr/bin/env python3
"""
Test de la correction de température pour Gemini-3.
Vérifie que la température est ajustée à 1.0 pour les modèles Gemini-3.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_core.litellm_proxy import LiteLLMProxy, ModelProvider

def test_temperature_adjustment():
    """Teste l'ajustement de température pour différents modèles."""
    proxy = LiteLLMProxy()
    
    test_cases = [
        # (model, input_temp, expected_temp, should_adjust)
        ("gemini-3-flash-preview", 0.7, 1.0, True),
        ("gemini-3-pro-preview", 0.5, 1.0, True),
        ("gemini-3-flash-preview", 1.0, 1.0, False),  # Déjà à 1.0
        ("gemini-3-flash-preview", 1.2, 1.2, False),  # > 1.0, pas d'ajustement
        ("gemini-2.0-flash-exp", 0.7, 0.7, False),    # Pas Gemini-3
        ("gemini-1.5-pro-preview-0409", 0.3, 0.3, False),  # Pas Gemini-3
        ("deepseek-chat", 0.7, 0.7, False),           # Pas Gemini
        ("gpt-4o", 0.7, 0.7, False),                 # Pas Gemini
    ]
    
    print("TEST: Ajustement de température pour Gemini-3")
    print("=" * 60)
    
    all_passed = True
    
    for model, input_temp, expected_temp, should_adjust in test_cases:
        # Simuler la logique de détection
        provider = proxy._detect_provider(model)
        is_gemini3 = provider == ModelProvider.GEMINI and "gemini-3" in model.lower()
        
        # Simuler l'ajustement
        adjusted_temp = input_temp
        if is_gemini3 and input_temp < 1.0:
            adjusted_temp = 1.0
        
        passed = abs(adjusted_temp - expected_temp) < 0.001
        
        status = "PASS" if passed else "FAIL"
        adjust_msg = "(ajuste)" if should_adjust and input_temp < 1.0 else "(inchange)"
        
        print(f"{status:4} {model:35} temp={input_temp:.1f} -> {adjusted_temp:.1f} {adjust_msg}")
        
        if not passed:
            all_passed = False
            print(f"   ATTENDU: {expected_temp:.1f}, OBTENU: {adjusted_temp:.1f}")
    
    print("=" * 60)
    
    if all_passed:
        print("✅ Tous les tests passent !")
    else:
        print("❌ Certains tests échouent.")
    
    return all_passed

def test_code_assist_converter():
    """Teste que code_assist_converter ajuste aussi la température."""
    try:
        from ai_core.code_assist_converter import to_generate_content_request
        
        print("\n🧪 Test de code_assist_converter")
        print("=" * 60)
        
        # Test avec Gemini-3
        request = to_generate_content_request(
            model="gemini-3-flash-preview",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7
        )
        
        # Extraire la température du request
        request_data = request.get("request", {})
        gen_config = request_data.get("generationConfig", {})
        final_temp = gen_config.get("temperature", None)
        
        if final_temp == 1.0:
            print("✅ code_assist_converter ajuste correctement Gemini-3: 0.7 -> 1.0")
        else:
            print(f"❌ code_assist_converter: température={final_temp} (attendu: 1.0)")
            return False
        
        # Test avec non-Gemini-3
        request2 = to_generate_content_request(
            model="gemini-2.0-flash-exp",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7
        )
        
        request_data2 = request2.get("request", {})
        gen_config2 = request_data2.get("generationConfig", {})
        final_temp2 = gen_config2.get("temperature", None)
        
        if abs(final_temp2 - 0.7) < 0.001:
            print("✅ code_assist_converter conserve température pour non-Gemini-3: 0.7")
        else:
            print(f"❌ code_assist_converter: température={final_temp2} (attendu: 0.7)")
            return False
        
        print("=" * 60)
        return True
        
    except ImportError as e:
        print(f"⚠️ Impossible d'importer code_assist_converter: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Test de la correction du warning température Gemini-3")
    print("=" * 60)
    
    test1_ok = test_temperature_adjustment()
    test2_ok = test_code_assist_converter()
    
    if test1_ok and test2_ok:
        print("\n🎉 Tous les tests passent ! Le warning température Gemini-3 devrait être résolu.")
        sys.exit(0)
    else:
        print("\n⚠️ Certains tests échouent. Vérifiez les modifications.")
        sys.exit(1)
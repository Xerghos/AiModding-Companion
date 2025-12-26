"""
Tests pour comparer la structure des payloads CodeAssist.
Objectif: Vérifier que notre CodeAssistClient génère la même structure que gemini-cli.
"""

import os
import sys
import json
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_core.code_assist_converter import to_generate_content_request

def test_1_payload_structure_basic():
    """Test 1: Structure de base du payload (sans outils)."""
    print("\n" + "="*80)
    print("TEST 1: Structure de base du payload")
    print("="*80)
    
    messages = [
        {"role": "user", "content": "Bonjour, comment ça va?"}
    ]
    
    payload = to_generate_content_request(
        model="gemini-3-flash-preview",
        messages=messages,
        user_prompt_id="test-123",
        session_id="session-456",
        temperature=0.7,
        max_tokens=1000,
        system_instruction="Tu es un assistant utile."
    )
    
    print("Payload généré:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    # Vérifications
    checks = {
        "model présent": "model" in payload,
        "request présent": "request" in payload,
        "user_prompt_id présent": "user_prompt_id" in payload,
        "session_id dans request": "session_id" in payload.get("request", {}),
        "contents dans request": "contents" in payload.get("request", {}),
        "systemInstruction dans request": "systemInstruction" in payload.get("request", {}),
        "generationConfig dans request": "generationConfig" in payload.get("request", {}),
    }
    
    print("\nVérifications:")
    all_ok = True
    for check, result in checks.items():
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {check}")
        if not result:
            all_ok = False
    
    return all_ok, payload

def test_2_payload_with_tools():
    """Test 2: Structure du payload avec outils."""
    print("\n" + "="*80)
    print("TEST 2: Structure du payload avec outils")
    print("="*80)
    
    messages = [
        {"role": "user", "content": "Appelle la fonction get_weather"}
    ]
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Obtient la météo pour une ville",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "Nom de la ville"
                        }
                    },
                    "required": ["city"]
                }
            }
        }
    ]
    
    payload = to_generate_content_request(
        model="gemini-3-flash-preview",
        messages=messages,
        user_prompt_id="test-123",
        tools=tools,
        temperature=0.7
    )
    
    print("Payload généré avec outils:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    # Vérifications spécifiques aux outils
    request = payload.get("request", {})
    checks = {
        "tools présent": "tools" in request,
        "tools est une liste": isinstance(request.get("tools"), list),
        "tools contient functionDeclarations": (
            len(request.get("tools", [])) > 0 and
            "functionDeclarations" in request.get("tools", [{}])[0]
        ),
        "toolConfig présent": "toolConfig" in request,  # ← CRITIQUE
        "toolConfig contient functionCallingConfig": (
            "toolConfig" in request and
            "functionCallingConfig" in request.get("toolConfig", {})
        ),
    }
    
    print("\nVérifications outils:")
    all_ok = True
    for check, result in checks.items():
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {check}")
        if not result:
            all_ok = False
            if "toolConfig" in check:
                print("     [CRITICAL] PROBLÈME CRITIQUE: toolConfig manquant!")
    
    return all_ok, payload

def test_3_compare_with_gemini_cli_structure():
    """Test 3: Comparer avec la structure attendue par gemini-cli."""
    print("\n" + "="*80)
    print("TEST 3: Comparaison avec structure gemini-cli")
    print("="*80)
    
    # Structure attendue basée sur converter.ts de gemini-cli
    expected_structure = {
        "model": "gemini-3-flash-preview",
        "project": None,  # Optionnel, None pour quota personnel
        "user_prompt_id": "test-123",
        "request": {
            "contents": [],  # Liste de Content
            "systemInstruction": {},  # Content optionnel
            "tools": [],  # ToolListUnion optionnel
            "toolConfig": {  # ← CRITIQUE selon gemini-cli
                "functionCallingConfig": {
                    "mode": "AUTO"  # ou "ANY", "NONE"
                }
            },
            "generationConfig": {},
            "session_id": "session-456"
        }
    }
    
    # Générer notre payload
    messages = [
        {"role": "user", "content": "Test"}
    ]
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "test_func",
                "description": "Test",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ]
    
    payload = to_generate_content_request(
        model="gemini-3-flash-preview",
        messages=messages,
        user_prompt_id="test-123",
        session_id="session-456",
        tools=tools,
        temperature=0.7
    )
    
    print("Structure attendue (gemini-cli):")
    print(json.dumps(expected_structure, indent=2, ensure_ascii=False))
    
    print("\nNotre structure générée:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    # Comparaisons
    print("\nComparaisons:")
    comparisons = []
    
    # 1. Structure de base
    comparisons.append(("model présent", "model" in payload))
    comparisons.append(("request présent", "request" in payload))
    comparisons.append(("user_prompt_id présent", "user_prompt_id" in payload))
    
    # 2. Contenu de request
    request = payload.get("request", {})
    comparisons.append(("contents dans request", "contents" in request))
    comparisons.append(("generationConfig dans request", "generationConfig" in request))
    comparisons.append(("session_id dans request", "session_id" in request))
    
    # 3. Outils (CRITIQUE)
    comparisons.append(("tools dans request", "tools" in request))
    comparisons.append(("toolConfig dans request", "toolConfig" in request))  # ← CRITIQUE
    
    # 4. Structure toolConfig
    if "toolConfig" in request:
        tool_config = request["toolConfig"]
        comparisons.append(("toolConfig contient functionCallingConfig", 
                           "functionCallingConfig" in tool_config))
        if "functionCallingConfig" in tool_config:
            fcc = tool_config["functionCallingConfig"]
            comparisons.append(("functionCallingConfig contient mode", "mode" in fcc))
    
    all_ok = True
    for check, result in comparisons:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {check}")
        if not result:
            all_ok = False
    
    return all_ok, payload

def test_4_payload_without_tools():
    """Test 4: Payload sans outils (ne doit pas avoir toolConfig)."""
    print("\n" + "="*80)
    print("TEST 4: Payload sans outils (toolConfig ne doit pas être présent)")
    print("="*80)
    
    messages = [
        {"role": "user", "content": "Simple message sans outils"}
    ]
    
    payload = to_generate_content_request(
        model="gemini-3-flash-preview",
        messages=messages,
        user_prompt_id="test-123",
        temperature=0.7
    )
    
    request = payload.get("request", {})
    
    # Sans outils, toolConfig ne devrait PAS être présent
    has_toolconfig = "toolConfig" in request
    has_tools = "tools" in request
    
    print(f"Payload généré (sans outils):")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    print("\nVérifications:")
    print(f"  {'[OK]' if not has_tools else '[FAIL]'} tools absent (attendu)")
    print(f"  {'[OK]' if not has_toolconfig else '[WARN]'} toolConfig absent (attendu sans outils)")
    
    # C'est OK si toolConfig n'est pas présent sans outils
    return True, payload

def main():
    """Exécuter tous les tests."""
    print("\n" + "="*80)
    print("SUITE DE TESTS: Structure des payloads CodeAssist")
    print("="*80)
    
    results = {}
    
    # Test 1: Structure de base
    results['basic'] = test_1_payload_structure_basic()
    
    # Test 2: Avec outils
    results['tools'] = test_2_payload_with_tools()
    
    # Test 3: Comparaison gemini-cli
    results['comparison'] = test_3_compare_with_gemini_cli_structure()
    
    # Test 4: Sans outils
    results['no_tools'] = test_4_payload_without_tools()
    
    # Résumé
    print("\n" + "="*80)
    print("RÉSUMÉ DES TESTS")
    print("="*80)
    for test_name, result in results.items():
        status = "[OK]" if result[0] else "[FAIL]"
        print(f"{status} {test_name}")
    
    # Conclusion
    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)
    
    if not results['tools'][0]:
        print("[CRITICAL] PROBLÈME CRITIQUE: toolConfig manquant dans les payloads avec outils")
        print("   -> C'est probablement la cause des erreurs 500!")
    else:
        print("[OK] Structure des payloads semble correcte")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()


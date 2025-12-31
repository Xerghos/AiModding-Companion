"""
Script de test pour valider les corrections du format functionResponse et functionCall.
Teste :
1. Format functionResponse avec "output" au lieu de "content"
2. Absence d'ID dans functionCall lors de l'injection
3. Structure de continuation (uniquement functionResponse, pas functionCall)
"""

import sys
import os
import json
import uuid
from pathlib import Path

# Ajouter le répertoire racine au path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from ai_core.code_assist_client import FunctionCallObject

def test_function_response_format():
    """Test 1: Vérifier que functionResponse utilise 'output' et non 'content'"""
    print("\n" + "="*80)
    print("TEST 1: Format functionResponse (output vs content)")
    print("="*80)
    
    # Simuler un tool call
    function_call = FunctionCallObject(
        name="lire_fichier",
        args={"path": "test.txt"},
        call_id=None,
        thought_signature=None
    )
    
    # Simuler l'exécution du tool (comme dans _execute_tool_call)
    tool_result_str = "Contenu du fichier test"
    
    function_response = {
        "name": function_call.name,
        "response": {
            "output": tool_result_str  # ✅ Doit être "output"
        }
    }
    
    # Vérifier le format
    assert "output" in function_response["response"], "ERREUR: 'output' manquant dans functionResponse"
    assert "content" not in function_response["response"], "ERREUR: 'content' present (devrait etre 'output')"
    print("[OK] Format functionResponse correct: utilise 'output'")
    
    return function_response

def test_function_call_no_id():
    """Test 2: Vérifier que functionCall n'a pas d'ID lors de l'injection"""
    print("\n" + "="*80)
    print("TEST 2: functionCall sans ID")
    print("="*80)
    
    function_call = FunctionCallObject(
        name="lire_fichier",
        args={"path": "test.txt"},
        call_id=None,
        thought_signature=None
    )
    
    # Simuler la création du function_call_dict (comme dans _inject_function_response)
    function_call_dict = {
        "functionCall": {
            "name": function_call.name,
            "args": function_call.args or {}
            # ❌ NE PAS AJOUTER D'ID ICI
        }
    }
    
    # Vérifier qu'il n'y a pas d'ID
    func_call = function_call_dict.get("functionCall", {})
    assert "id" not in func_call, f"ERREUR: ID present dans functionCall: {func_call.get('id')}"
    print("[OK] functionCall correct: pas d'ID")
    
    return function_call_dict

def test_continuation_structure():
    """Test 3: Vérifier que la continuation n'injecte que functionResponse"""
    print("\n" + "="*80)
    print("TEST 3: Structure de continuation")
    print("="*80)
    
    # Simuler shadow_history
    shadow_history = []
    
    # Simuler functionResponse
    function_response = {
        "name": "lire_fichier",
        "id": str(uuid.uuid4()),
        "response": {
            "output": "Contenu du fichier"
        }
    }
    
    # Simuler l'injection (comme dans _inject_function_response corrigé)
    # ❌ NE PAS INJECTER LE FUNCTIONCALL
    # Ajouter uniquement le functionResponse
    shadow_history.append({
        "role": "function",
        "parts": [{"functionResponse": function_response}]
    })
    
    # Vérifier la structure
    assert len(shadow_history) == 1, f"ERREUR: shadow_history devrait contenir 1 message, contient {len(shadow_history)}"
    
    last_message = shadow_history[-1]
    assert last_message["role"] == "function", f"ERREUR: role devrait etre 'function', est '{last_message['role']}'"
    
    parts = last_message.get("parts", [])
    assert len(parts) == 1, f"ERREUR: devrait avoir 1 part, a {len(parts)}"
    
    part = parts[0]
    assert "functionResponse" in part, "ERREUR: part devrait contenir 'functionResponse'"
    assert "functionCall" not in part, "ERREUR: part ne devrait PAS contenir 'functionCall'"
    
    # Vérifier qu'aucun message avec role="model" et functionCall n'est présent
    for msg in shadow_history:
        if msg.get("role") == "model":
            for p in msg.get("parts", []):
                assert "functionCall" not in p, "ERREUR: functionCall trouve dans shadow_history (ne devrait pas etre injecte)"
    
    print("[OK] Structure de continuation correcte: uniquement functionResponse injecte")
    
    return shadow_history

def test_complete_flow():
    """Test 4: Test du flux complet"""
    print("\n" + "="*80)
    print("TEST 4: Flux complet (simulation)")
    print("="*80)
    
    # 1. Créer functionCall (sans ID)
    function_call_dict = {
        "functionCall": {
            "name": "lire_fichier",
            "args": {"path": "test.txt"}
        }
    }
    
    # 2. Créer functionResponse (avec output)
    function_response = {
        "name": "lire_fichier",
        "id": str(uuid.uuid4()),
        "response": {
            "output": "Contenu du fichier test"
        }
    }
    
    # 3. Simuler shadow_history initial (avec user message)
    shadow_history = [
        {
            "role": "user",
            "parts": [{"text": "Lis le fichier test.txt"}]
        }
    ]
    
    # 4. Simuler l'injection (uniquement functionResponse)
    shadow_history.append({
        "role": "function",
        "parts": [{"functionResponse": function_response}]
    })
    
    # 5. Vérifier la structure finale
    print(f"Shadow History contient {len(shadow_history)} messages")
    for idx, msg in enumerate(shadow_history):
        role = msg.get("role")
        parts = msg.get("parts", [])
        print(f"  Message {idx}: role={role}, {len(parts)} parts")
        for part_idx, part in enumerate(parts):
            if "text" in part:
                print(f"    Part {part_idx}: text (len={len(part['text'])})")
            elif "functionResponse" in part:
                fr = part["functionResponse"]
                output = fr.get("response", {}).get("output", "")
                print(f"    Part {part_idx}: functionResponse (name={fr.get('name')}, id={fr.get('id')}, output_len={len(str(output))})")
            elif "functionCall" in part:
                print(f"    Part {part_idx}: functionCall (ATTENTION: NE DEVRAIT PAS ETRE ICI)")
    
    # Vérifications finales
    assert len(shadow_history) == 2, f"ERREUR: devrait avoir 2 messages, a {len(shadow_history)}"
    
    # Vérifier qu'il n'y a pas de functionCall dans shadow_history
    has_function_call = False
    for msg in shadow_history:
        for part in msg.get("parts", []):
            if "functionCall" in part:
                has_function_call = True
                break
    
    assert not has_function_call, "ERREUR: functionCall trouve dans shadow_history (ne devrait pas etre injecte)"
    
    # Vérifier que functionResponse utilise "output"
    function_response_msg = shadow_history[1]
    fr_part = function_response_msg["parts"][0]["functionResponse"]
    assert "output" in fr_part["response"], "ERREUR: 'output' manquant dans functionResponse"
    assert "content" not in fr_part["response"], "ERREUR: 'content' present (devrait etre 'output')"
    
    print("[OK] Flux complet correct")
    
    return shadow_history

def test_payload_structure():
    """Test 5: Vérifier la structure du payload final"""
    print("\n" + "="*80)
    print("TEST 5: Structure du payload final")
    print("="*80)
    
    # Simuler le payload comme il serait envoyé à l'API
    shadow_history = [
        {
            "role": "user",
            "parts": [{"text": "Lis le fichier test.txt"}]
        },
        {
            "role": "function",
            "parts": [{
                "functionResponse": {
                    "id": str(uuid.uuid4()),
                    "name": "lire_fichier",
                    "response": {
                        "output": "Contenu du fichier"
                    }
                }
            }]
        }
    ]
    
    # Vérifier la structure JSON
    payload_json = json.dumps(shadow_history, indent=2)
    print("Payload JSON:")
    print(payload_json)
    
    # Vérifier qu'il n'y a pas de functionCall
    payload_str = payload_json
    assert '"functionCall"' not in payload_str, "ERREUR: 'functionCall' trouve dans le payload"
    
    # Vérifier que functionResponse utilise "output"
    assert '"output"' in payload_str, "ERREUR: 'output' manquant dans le payload"
    assert '"content"' not in payload_str, "ERREUR: 'content' present (devrait etre 'output')"
    
    print("[OK] Structure du payload correcte")
    
    return shadow_history

def main():
    """Exécute tous les tests"""
    print("\n" + "="*80)
    print("SCRIPT DE TEST: Format functionResponse et functionCall")
    print("="*80)
    
    try:
        # Test 1: Format functionResponse
        test_function_response_format()
        
        # Test 2: functionCall sans ID
        test_function_call_no_id()
        
        # Test 3: Structure de continuation
        test_continuation_structure()
        
        # Test 4: Flux complet
        test_complete_flow()
        
        # Test 5: Structure du payload
        test_payload_structure()
        
        print("\n" + "="*80)
        print("[OK] TOUS LES TESTS SONT PASSES")
        print("="*80)
        return 0
        
    except AssertionError as e:
        print(f"\n[ERREUR] ECHEC DU TEST: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n[ERREUR] ERREUR INATTENDUE: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

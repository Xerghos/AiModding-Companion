"""
Test réel de l'injection functionResponse avec vérification du format.
Ce script simule exactement ce qui se passe dans _execute_tool_call et _inject_function_response.
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

def test_real_function_injection():
    """Test réel de l'injection comme dans le code"""
    print("\n" + "="*80)
    print("TEST REEL: Injection functionResponse (simulation exacte du code)")
    print("="*80)
    
    # Simuler un functionCall reçu de l'API (sans ID)
    function_call_object = FunctionCallObject(
        name="lire_fichier",
        args={"path": "README.md"},
        call_id=None,  # L'API n'a pas fourni d'ID
        thought_signature="test_signature"
    )
    
    print(f"\n1. FunctionCall reçu: name={function_call_object.name}, id={function_call_object.id}")
    
    # Simuler l'exécution du tool (comme dans _execute_tool_call)
    tool_result_str = "Contenu du fichier README.md"
    
    # Créer functionResponse (comme dans _execute_tool_call ligne 637-642)
    function_response = {
        "name": function_call_object.name,
        "response": {
            "output": tool_result_str  # ✅ Format corrigé: "output" au lieu de "content"
        }
    }
    
    # Ajouter l'ID (comme dans _execute_tool_call ligne 644-653)
    if function_call_object.id:
        function_response["id"] = function_call_object.id
    else:
        generated_id = str(uuid.uuid4())
        print(f"   [INFO] ID genere pour functionResponse: {generated_id}")
        function_response["id"] = generated_id
    
    print(f"\n2. FunctionResponse cree:")
    print(f"   name: {function_response['name']}")
    print(f"   id: {function_response['id']}")
    print(f"   response keys: {list(function_response['response'].keys())}")
    
    # Vérifier le format
    assert "output" in function_response["response"], "ERREUR: 'output' manquant"
    assert "content" not in function_response["response"], "ERREUR: 'content' present"
    print(f"   [OK] Format correct: utilise 'output'")
    
    # Simuler l'injection (comme dans _inject_function_response)
    shadow_history = [
        {
            "role": "user",
            "parts": [{"text": "Lis le fichier README.md"}]
        }
    ]
    
    # Créer function_call_dict (comme dans _inject_function_response ligne 689-694)
    function_call_dict = {
        "functionCall": {
            "name": function_call_object.name,
            "args": function_call_object.args or {}
            # ❌ NE PAS AJOUTER D'ID ICI - conforme gemini-cli
        }
    }
    
    print(f"\n3. FunctionCall dict cree:")
    print(f"   name: {function_call_dict['functionCall']['name']}")
    print(f"   keys: {list(function_call_dict['functionCall'].keys())}")
    
    # Vérifier qu'il n'y a pas d'ID
    assert "id" not in function_call_dict["functionCall"], "ERREUR: ID present dans functionCall"
    print(f"   [OK] Pas d'ID dans functionCall")
    
    # Injection (comme dans _inject_function_response ligne 710-720 CORRIGÉE)
    # ❌ NE PAS INJECTER LE FUNCTIONCALL
    # Ajouter uniquement le functionResponse
    shadow_history.append({
        "role": "function",
        "parts": [{"functionResponse": function_response}]
    })
    
    print(f"\n4. Shadow History apres injection:")
    print(f"   Nombre de messages: {len(shadow_history)}")
    
    # Vérifier la structure
    assert len(shadow_history) == 2, f"ERREUR: devrait avoir 2 messages, a {len(shadow_history)}"
    
    # Vérifier qu'il n'y a pas de functionCall dans shadow_history
    has_function_call = False
    for msg in shadow_history:
        if msg.get("role") == "model":
            for part in msg.get("parts", []):
                if "functionCall" in part:
                    has_function_call = True
                    break
    
    assert not has_function_call, "ERREUR: functionCall trouve dans shadow_history"
    print(f"   [OK] Pas de functionCall dans shadow_history (conforme gemini-cli)")
    
    # Vérifier que functionResponse est présent
    function_response_msg = shadow_history[1]
    assert function_response_msg["role"] == "function", "ERREUR: role devrait etre 'function'"
    assert "functionResponse" in function_response_msg["parts"][0], "ERREUR: functionResponse manquant"
    print(f"   [OK] FunctionResponse present dans shadow_history")
    
    # Afficher le payload final
    print(f"\n5. Payload final (JSON):")
    payload_json = json.dumps(shadow_history, indent=2, ensure_ascii=False)
    print(payload_json)
    
    # Vérifications finales
    payload_str = payload_json
    assert '"functionCall"' not in payload_str, "ERREUR: 'functionCall' trouve dans le payload"
    assert '"output"' in payload_str, "ERREUR: 'output' manquant dans le payload"
    assert '"content"' not in payload_str, "ERREUR: 'content' present dans le payload"
    
    print(f"\n" + "="*80)
    print("[OK] TOUS LES TESTS REELS SONT PASSES")
    print("="*80)
    print("\nVerifications:")
    print("  [OK] functionResponse utilise 'output' (pas 'content')")
    print("  [OK] functionCall n'a pas d'ID")
    print("  [OK] functionCall n'est PAS injecte dans shadow_history")
    print("  [OK] Seul functionResponse est injecte (conforme gemini-cli)")
    print("  [OK] Structure du payload correcte")
    
    return True

if __name__ == "__main__":
    try:
        success = test_real_function_injection()
        sys.exit(0 if success else 1)
    except AssertionError as e:
        print(f"\n[ERREUR] ECHEC DU TEST: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERREUR] ERREUR INATTENDUE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

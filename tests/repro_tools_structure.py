
import json
import os
import sys
import uuid

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai_core.code_assist_converter import to_generate_content_request
from config.tools_schema import TOOLS_SCHEMA

def test_tools_structure():
    print("--- 🛠️ TEST STRUCTURE OUTILS (CodeAssist) ---")
    
    # Mock des messages
    messages = [{"role": "user", "content": "test"}]
    
    # Cas A : Outils Natifs (Ce que fait LiteLLMSession maintenant)
    print("\n[Cas A] Input: TOOLS_SCHEMA (Format Gemini Natif)")
    # TOOLS_SCHEMA est une liste de dicts : [{"name":..., "parameters":...}]
    
    request_a = to_generate_content_request(
        model="gemini-3-flash-preview",
        messages=messages,
        tools=TOOLS_SCHEMA,
        temperature=0.7
    )
    
    tools_a = request_a.get("request", {}).get("tools", [])
    print(json.dumps(tools_a, indent=2))
    
    # Vérification de la structure attendue par l'API
    # L'API attend: [{"functionDeclarations": [...]}] ou peut-être juste les déclarations si c'est déjà une liste ?
    # Regardons ce que _convert_tools_to_gemini_format a produit
    
    if isinstance(tools_a, list) and len(tools_a) > 0:
        first_item = tools_a[0]
        if "functionDeclarations" in first_item:
            print("✅ Structure OK: [{'functionDeclarations': [...]}]")
            # Vérifions le contenu des déclarations
            decls = first_item["functionDeclarations"]
            print(f"   Nombre de fonctions : {len(decls)}")
            if "name" in decls[0] and "parameters" in decls[0]:
                 print("   ✅ Format interne fonction OK")
            else:
                 print("   ❌ Format interne fonction SUSPECT")
        else:
            print("❌ Structure KO: Pas de 'functionDeclarations' trouvé à la racine de tools")
    else:
        print("❌ Structure KO: Tools vide ou invalide")

if __name__ == "__main__":
    test_tools_structure()

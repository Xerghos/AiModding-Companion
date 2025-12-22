
import json
import os
import sys
from typing import Optional, Dict

# Ajouter la racine du projet au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock des dépendances pour le test statique
from ai_core.factory import SessionFactory
from ai_core.code_assist_converter import to_generate_content_request
from features.UnifiedLogger import UnifiedLogger

def test_litellm_payload_quality():
    """
    Simule la création d'un payload via LiteLLMSession et valide sa structure finale.
    """
    print("--- 🛠️ TEST DE QUALITÉ DU PAYLOAD LITELLM ---")
    
    # 1. Configurer une session via la factory (en forçant LiteLLM si nécessaire)
    # Note: On utilise directement to_generate_content_request pour voir ce que CodeAssist recevra
    
    system_instruction = "IDENTITÉ : Tu es AiModding-Companion..."
    
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "system", "content": "--- REPO MAP ---\nFichier: features/Decorators.py..."},
        {"role": "system", "content": "--- ARBORESCENCE ---\nAiModding-Companion/..."},
        {"role": "user", "content": "--- CONTEXTE RAG ---\nDoc technique...\n\n--- MESSAGE ---\ndis hello"}
    ]
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lister_arborescence",
                "description": "Liste l'arborescence...",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}
            }
        }
    ]

    print("\n[Step 1] Conversion via code_assist_converter...")
    
    # Simuler l'appel final que fait CodeAssistClient
    ca_request = to_generate_content_request(
        model="gemini-3-flash-preview",
        messages=messages,
        tools=tools,
        system_instruction=None # Les instructions sont déjà dans 'messages' via LiteLLMSession
    )
    
    # 2. Analyse structurelle
    request = ca_request.get("request", {})
    contents = request.get("contents", [])
    system_instruction_field = request.get("systemInstruction", {})
    
    print("\n--- ANALYSE DU PAYLOAD GÉNÉRÉ ---")
    
    # Vérification System Instruction
    if system_instruction_field:
        text = system_instruction_field.get("parts", [{}])[0].get("text", "")
        print(f"✅ systemInstruction détecté ({len(text)} chars)")
        if "REPO MAP" in text and "ARBORESCENCE" in text:
            print("   ✅ Blocs statiques (Repo Map, Arbo) correctement déplacés dans systemInstruction")
        else:
            print("   ❌ Blocs statiques MANQUANTS dans systemInstruction")
    else:
        print("   ❌ systemInstruction est VIDE")

    # Vérification Messages
    user_msgs = [c for c in contents if c.get("role") == "user"]
    system_msgs_in_contents = [c for c in contents if c.get("role") == "system"]
    
    print(f"✅ Nombre de messages 'user' dans contents : {len(user_msgs)}")
    if system_msgs_in_contents:
        print(f"   ❌ Erreur : {len(system_msgs_in_contents)} messages 'system' sont restés dans contents")
    else:
        print("   ✅ Aucun message 'system' n'est resté dans la liste contents")

    # Vérification RAG
    if user_msgs and "CONTEXTE RAG" in user_msgs[-1]["parts"][0]["text"]:
        print("✅ Contexte RAG présent dans le message utilisateur")
    
    # 3. Dump pour comparaison manuelle
    output_path = os.path.join(os.path.dirname(__file__), "debug_output_payload.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ca_request, f, indent=2, ensure_ascii=False)
    
    print(f"\n📝 Payload complet sauvegardé dans : {output_path}")
    print("\n--- FIN DU TEST ---")

if __name__ == "__main__":
    test_litellm_payload_quality()

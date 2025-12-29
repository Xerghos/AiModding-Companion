"""
Script de diagnostic pour tester les variantes de payload CodeAssist.
Teste différentes combinaisons de session_id et generationConfig pour identifier
la cause du stream vide.
"""

import os
import sys
import uuid
import json
from typing import Optional, Dict, Any

# Ajouter le répertoire racine au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_core.code_assist_client import CodeAssistClient
from features.UnifiedLogger import UnifiedLogger


def test_codeassist_variant(
    model: str,
    session_id: Optional[str] = None,
    use_uuid_session: bool = False,
    use_minimal_config: bool = False,
    test_name: str = ""
):
    """
    Teste une variante de configuration CodeAssist.
    
    Args:
        model: Nom du modèle (ex: "gemini-3-flash-preview")
        session_id: ID de session personnalisé (optionnel)
        use_uuid_session: Si True, utilise un UUID standard au lieu de "aimodding_..."
        use_minimal_config: Si True, utilise une config minimale (seulement temperature)
        test_name: Nom du test pour le logging
    """
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    print(f"Modèle: {model}")
    print(f"Session ID: {session_id if session_id else 'None'}")
    print(f"Use UUID session: {use_uuid_session}")
    print(f"Use minimal config: {use_minimal_config}")
    print(f"{'='*80}\n")
    
    # Générer session_id selon le type demandé
    if use_uuid_session:
        final_session_id = str(uuid.uuid4())
        print(f"[OK] Utilisation UUID session: {final_session_id}")
    elif session_id:
        final_session_id = session_id
        print(f"[OK] Utilisation session_id fourni: {final_session_id}")
    else:
        # Format "aimodding_..." (format actuel)
        final_session_id = f"aimodding_{uuid.uuid4().hex[:8]}"
        print(f"[OK] Utilisation format aimodding_: {final_session_id}")
    
    # Créer le client
    try:
        client = CodeAssistClient(
            session_id=final_session_id,
            use_personal_quota=True
        )
        print("[OK] Client CodeAssist créé avec succès")
    except Exception as e:
        print(f"[ERREUR] Erreur création client: {e}")
        return None
    
    # Préparer les messages
    messages = [
        {"role": "user", "content": "Hello"}
    ]
    
    # Préparer les kwargs selon la configuration
    kwargs = {}
    if use_minimal_config:
        # Config minimale : seulement temperature
        print("[CONFIG] Utilisation generationConfig minimale (temperature seulement)")
        kwargs["temperature"] = 0.7
    else:
        # Config complète : topP, topK, thinkingConfig (sera ajouté automatiquement pour gemini-3)
        print("[CONFIG] Utilisation generationConfig complète (topP, topK, thinkingConfig)")
        kwargs["temperature"] = 1.0 if "gemini-3" in model.lower() else 0.7
        kwargs["top_p"] = 0.95
        kwargs["top_k"] = 64
        # thinkingConfig sera ajouté automatiquement pour gemini-3 dans le code
    
    # Faire l'appel API
    print(f"\n[API] Envoi requête à l'API CodeAssist...")
    print(f"   Modèle: {model}")
    print(f"   Messages: {messages}")
    print(f"   Stream: True")
    print(f"   Kwargs: {kwargs}\n")
    
    try:
        response = client.generate_content(
            model=model,
            messages=messages,
            stream=True,
            **kwargs
        )
        
        print("[OK] Réponse reçue, traitement du stream...\n")
        
        # Traiter le stream
        chunks_received = 0
        text_received = ""
        usage_metadata_found = False
        last_chunk_data = None
        
        for chunk in response:
            chunks_received += 1
            
            # Extraire le texte si présent
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'text') and delta.text:
                    text_received += delta.text
                    print(f"[CHUNK {chunks_received}] {delta.text[:100]}...")
            
            # Vérifier usageMetadata dans le chunk (si accessible)
            if hasattr(chunk, 'usageMetadata'):
                usage_metadata_found = True
                print(f"[METRICS] UsageMetadata trouvé dans chunk {chunks_received}")
            
            # Garder le dernier chunk pour inspection
            last_chunk_data = chunk
        
        print(f"\n{'='*80}")
        print(f"RÉSULTATS:")
        print(f"{'='*80}")
        print(f"Chunks reçus: {chunks_received}")
        print(f"Texte reçu: {len(text_received)} caractères")
        if text_received:
            print(f"Texte (premiers 200 chars): {text_received[:200]}")
        else:
            print(f"[WARNING] AUCUN TEXTE REÇU")
        print(f"UsageMetadata trouvé: {usage_metadata_found}")
        print(f"{'='*80}\n")
        
        # Log du dernier chunk pour inspection
        if last_chunk_data:
            try:
                chunk_str = str(last_chunk_data)
                print(f"Dernier chunk (str): {chunk_str[:500]}...")
            except:
                print("Impossible de convertir le dernier chunk en string")
        
        return {
            "chunks_received": chunks_received,
            "text_received": text_received,
            "usage_metadata_found": usage_metadata_found,
            "success": len(text_received) > 0
        }
        
    except Exception as e:
        print(f"[ERREUR] Erreur lors de l'appel API: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Exécute tous les tests de variantes."""
    print("\n" + "="*80)
    print("SCRIPT DE DIAGNOSTIC CODEASSIST - TEST DES VARIANTES")
    print("="*80)
    
    models = ["gemini-3-flash-preview", "gemini-3-pro-preview"]
    
    # Liste des tests à exécuter
    tests = [
        # Test 1: Format aimodding_ + Config minimale
        {
            "name": "Test 1: Format aimodding_ + Config minimale",
            "use_uuid_session": False,
            "use_minimal_config": True
        },
        # Test 2: Format aimodding_ + Config complète
        {
            "name": "Test 2: Format aimodding_ + Config complète",
            "use_uuid_session": False,
            "use_minimal_config": False
        },
        # Test 3: UUID standard + Config minimale
        {
            "name": "Test 3: UUID standard + Config minimale",
            "use_uuid_session": True,
            "use_minimal_config": True
        },
        # Test 4: UUID standard + Config complète
        {
            "name": "Test 4: UUID standard + Config complète",
            "use_uuid_session": True,
            "use_minimal_config": False
        },
        # Test 5: Pas de session_id + Config complète
        {
            "name": "Test 5: Pas de session_id + Config complète",
            "session_id": None,
            "use_uuid_session": False,
            "use_minimal_config": False
        },
    ]
    
    results = {}
    
    for model in models:
        print(f"\n\n{'#'*80}")
        print(f"# TEST AVEC MODÈLE: {model}")
        print(f"{'#'*80}\n")
        
        results[model] = {}
        
        for test in tests:
            result = test_codeassist_variant(
                model=model,
                session_id=test.get("session_id"),
                use_uuid_session=test["use_uuid_session"],
                use_minimal_config=test["use_minimal_config"],
                test_name=f"{model} - {test['name']}"
            )
            results[model][test["name"]] = result
            
            # Pause entre les tests pour éviter le rate limiting
            import time
            time.sleep(2)
    
    # Résumé final
    print("\n\n" + "="*80)
    print("RÉSUMÉ DES RÉSULTATS")
    print("="*80)
    
    for model in models:
        print(f"\n{model}:")
        for test_name, result in results[model].items():
            if result:
                status = "[SUCCES]" if result.get("success") else "[ECHEC]"
                print(f"  {status} - {test_name}")
                print(f"    Chunks: {result.get('chunks_received', 0)}, "
                      f"Texte: {len(result.get('text_received', ''))} chars, "
                      f"UsageMetadata: {result.get('usage_metadata_found', False)}")
            else:
                print(f"  [ERREUR] - {test_name}")
    
    print("\n" + "="*80)
    print("FIN DES TESTS")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

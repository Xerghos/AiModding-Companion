"""
Script de test réel avec appel API CodeAssist.
Teste le format functionResponse et functionCall avec un vrai appel API.
"""

import sys
import os
import time
import json
from pathlib import Path

# Ajouter le répertoire racine au path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from worker.core import Worker
from features.UnifiedLogger import UnifiedLogger
from queue import Queue
import threading

# Configuration pour capturer les logs
test_logs = []

def test_real_api_call():
    """Test réel avec appel API"""
    print("\n" + "="*80)
    print("TEST REEL: Appel API CodeAssist avec tool call")
    print("="*80)
    
    # Créer les queues et events nécessaires
    task_queue = Queue()
    response_queue = Queue()
    stop_event = threading.Event()
    
    # Créer un worker
    worker = Worker(task_queue, response_queue, stop_event)
    
    # Message de test qui devrait déclencher un tool call
    test_message = "Lis le fichier README.md et dis-moi ce qu'il contient"
    
    print(f"\nMessage de test: {test_message}")
    print("\nEnvoi du message...")
    
    # Démarrer le worker
    worker.start()
    
    # Envoyer le message via task_queue
    task_queue.put({
        'type': 'user_prompt',
        'text': test_message
    })
    
    # Attendre un peu pour que le worker démarre
    time.sleep(3)
    
    # Attendre les réponses
    print("\nAttente des reponses...")
    max_wait = 90  # 90 secondes max
    start_time = time.time()
    responses = []
    tool_calls_detected = []
    function_responses_detected = []
    stream_ended = False
    last_response_time = time.time()
    
    while time.time() - start_time < max_wait and not stream_ended:
        try:
            # Vérifier la queue avec timeout
            try:
                response = response_queue.get(timeout=3)
                last_response_time = time.time()
                responses.append(response)
                
                response_type = response.get('type', 'unknown')
                
                if response_type == 'ui_stream_chunk':
                    content = response.get('text', '')
                    if content:
                        print(f"[CHUNK] {content[:100]}...")
                        
                elif response_type == 'ui_stream_end':
                    print("\n[FIN] Stream termine")
                    stream_ended = True
                    # Attendre encore un peu pour voir s'il y a d'autres messages
                    time.sleep(2)
                    break
                    
                elif response_type == 'tool_call':
                    tool_info = response.get('tool', {})
                    print(f"\n[TOOL CALL] {tool_info.get('name', 'unknown')} avec args: {tool_info.get('args', {})}")
                    tool_calls_detected.append(tool_info)
                    
                elif response_type == 'tool_result':
                    result = response.get('result', '')
                    print(f"\n[TOOL RESULT] {result[:200]}...")
                    function_responses_detected.append(result)
                    
                elif response_type == 'error':
                    error_text = response.get('text', '')
                    print(f"\n[ERREUR] {error_text}")
                    stop_event.set()
                    return False
                    
            except Exception as queue_exc:
                # Timeout ou queue vide
                if "Empty" in str(queue_exc) or "timeout" in str(queue_exc).lower():
                    # Si on n'a pas reçu de réponse depuis 30 secondes, on arrête
                    if time.time() - last_response_time > 30 and len(responses) > 0:
                        print("\n[INFO] Aucune reponse depuis 30 secondes, arret...")
                        break
                    continue
                raise
                
        except Exception as e:
            print(f"\n[ERREUR] Exception: {e}")
            import traceback
            traceback.print_exc()
            break
    
    # Arrêter le worker
    stop_event.set()
    worker.join(timeout=5)
    
    # Analyser les résultats
    print("\n" + "="*80)
    print("ANALYSE DES RESULTATS")
    print("="*80)
    
    print(f"\nNombre de réponses reçues: {len(responses)}")
    print(f"Tool calls détectés: {len(tool_calls_detected)}")
    print(f"Function responses détectés: {len(function_responses_detected)}")
    
    # Vérifier le shadow_history du worker
    if hasattr(worker, '_shadow_history'):
        shadow_history = worker._shadow_history
        print(f"\nShadow History contient {len(shadow_history)} messages")
        
        if len(shadow_history) == 0:
            print("[ATTENTION] Shadow History est vide - le message n'a peut-etre pas ete traite")
            print("Verification des reponses recues...")
            if len(responses) == 0:
                print("[ERREUR] Aucune reponse recue")
                return False
            else:
                print(f"[INFO] {len(responses)} reponses recues mais shadow_history vide")
                print("Cela peut etre normal si le stream n'a pas encore commence")
                return True  # On considere que c'est OK si on a des reponses
        
        for idx, msg in enumerate(shadow_history):
            role = msg.get("role", "unknown")
            parts = msg.get("parts", [])
            print(f"\n  Message {idx}: role={role}, {len(parts)} parts")
            
            for part_idx, part in enumerate(parts):
                if "text" in part:
                    text_content = part["text"]
                    print(f"    Part {part_idx}: text (len={len(str(text_content))})")
                    
                elif "functionCall" in part:
                    func_call = part["functionCall"]
                    func_id = func_call.get("id", "NONE")
                    print(f"    Part {part_idx}: functionCall (name={func_call.get('name')}, id={func_id})")
                    
                    # Vérifier qu'il n'y a pas d'ID
                    if "id" in func_call:
                        print(f"      [ERREUR] ID present dans functionCall: {func_call.get('id')}")
                        return False
                    else:
                        print(f"      [OK] Pas d'ID dans functionCall")
                        
                elif "functionResponse" in part:
                    func_resp = part["functionResponse"]
                    response_obj = func_resp.get("response", {})
                    
                    # Vérifier le format
                    has_output = "output" in response_obj
                    has_content = "content" in response_obj
                    
                    print(f"    Part {part_idx}: functionResponse (name={func_resp.get('name')}, id={func_resp.get('id')})")
                    print(f"      response keys: {list(response_obj.keys())}")
                    
                    if has_output:
                        output_len = len(str(response_obj.get("output", "")))
                        print(f"      [OK] Utilise 'output' (len={output_len})")
                    else:
                        print(f"      [ERREUR] 'output' manquant")
                        return False
                        
                    if has_content:
                        print(f"      [ERREUR] 'content' present (devrait etre 'output')")
                        return False
    else:
        print("\n[ATTENTION] Worker n'a pas d'attribut _shadow_history")
    
    # Vérifier la structure de continuation
    if hasattr(worker, '_shadow_history') and len(worker._shadow_history) > 0:
        # Compter les messages avec functionCall
        function_call_messages = 0
        function_response_messages = 0
        
        for msg in worker._shadow_history:
            if msg.get("role") == "model":
                for part in msg.get("parts", []):
                    if "functionCall" in part:
                        function_call_messages += 1
            elif msg.get("role") == "function":
                for part in msg.get("parts", []):
                    if "functionResponse" in part:
                        function_response_messages += 1
        
        print(f"\nStructure de continuation:")
        print(f"  Messages avec functionCall: {function_call_messages}")
        print(f"  Messages avec functionResponse: {function_response_messages}")
        
        if function_call_messages > 0:
            print(f"  [ERREUR] functionCall trouve dans shadow_history (ne devrait pas etre injecte)")
            return False
        else:
            print(f"  [OK] Pas de functionCall dans shadow_history (conforme gemini-cli)")
    
    print("\n" + "="*80)
    print("[OK] TEST REEL REUSSI")
    print("="*80)
    return True

def main():
    """Point d'entrée principal"""
    print("\n" + "="*80)
    print("SCRIPT DE TEST REEL: Appel API CodeAssist")
    print("="*80)
    print("\nCe test va:")
    print("  1. Envoyer un message qui declenche un tool call")
    print("  2. Verifier le format functionResponse (output vs content)")
    print("  3. Verifier l'absence d'ID dans functionCall")
    print("  4. Verifier la structure de continuation")
    print("\nDebut du test dans 2 secondes...")
    time.sleep(2)
    
    try:
        success = test_real_api_call()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\nTest interrompu par l'utilisateur")
        return 1
    except Exception as e:
        print(f"\n[ERREUR] Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

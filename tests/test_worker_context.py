import sys
import os
import queue
from unittest.mock import MagicMock

# Ajout racine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from config.settings import load_app_settings
    load_app_settings()
    from worker.core import Worker
except ImportError as e:
    print(f"❌ Erreur Import Worker: {e}")
    sys.exit(1)

def test_context_injection():
    print("--- 🧠 TEST MEMOIRE PARTAGEE (WORKER -> AGENT) ---")
    
    # 1. Instanciation Worker (Avec Mocks)
    print("🔹 Init Worker...")
    mock_q = queue.Queue()
    worker = Worker(mock_q, mock_q, MagicMock())
    
    # 2. Injection Données Simulées (STM)
    print("🔹 Injection Historique (STM)...")
    worker.main_session = MagicMock()
    worker.main_session.history = [
        MagicMock(role='user', parts=[MagicMock(text="Bonjour")]),
        MagicMock(role='model', parts=[MagicMock(text="Salut")]),
        MagicMock(role='user', parts=[MagicMock(text="Analyse ce fichier.")])
    ]
    
    # 3. Mock du RAG (Simuler une réponse de la base de données)
    # On force la méthode _retrieve_rag_context à renvoyer du texte
    worker._retrieve_rag_context = MagicMock(return_value="[RAG] Fichier 'test.py' détecté.")
    
    # 4. Mock de create_agent pour intercepter les arguments
    # C'est ici qu'on vérifie si votre modification manuelle a fonctionné
    original_create_agent = sys.modules['agents.swarm_manager'].create_agent
    
    try:
        # On remplace temporairement la vraie fonction par un espion
        spy = MagicMock()
        spy.return_value.execute_task.return_value = "OK"
        sys.modules['agents.swarm_manager'].create_agent = spy
        
        # 5. Exécution de la tâche
        print("🔹 Lancement Tâche Agent...")
        payload = {"agent_type": "CODER", "prompt": "Refactor ça.", "task_id": "TEST_01"}
        worker._handle_agent_task(payload)
        
        # 6. Vérification
        if spy.called:
            args, kwargs = spy.call_args
            context_sent = kwargs.get('initial_context', '')
            
            print("\n🔍 ANALYSE DU CONTEXTE REÇU PAR L'AGENT :")
            if "[RAG]" in context_sent:
                print("✅ RAG présent.")
            else:
                print("❌ RAG manquant.")
                
            if "Analyse ce fichier" in context_sent:
                print("✅ Historique STM présent.")
            else:
                print("❌ Historique STM manquant.")
                
            if "[RAG]" in context_sent and "Analyse ce fichier" in context_sent:
                print("\n🎉 SUCCÈS TOTAL : Le Worker transmet bien la mémoire hybride !")
            else:
                print("\n⚠️ ATTENTION : Transmission partielle.")
                print(f"Contenu reçu : {context_sent[:200]}...")
        else:
            print("❌ ÉCHEC : create_agent n'a jamais été appelé. Vérifiez _handle_agent_task.")

    except Exception as e:
        print(f"❌ CRASH TEST : {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restauration
        sys.modules['agents.swarm_manager'].create_agent = original_create_agent

if __name__ == "__main__":
    test_context_injection()
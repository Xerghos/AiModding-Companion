import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# --- 🛠️ DIAGNOSTIC D'ENVIRONNEMENT ---
print("\n🔍 --- DIAGNOSTIC ENVIRONNEMENT ---")
current_script = os.path.abspath(__file__)
current_dir = os.path.dirname(current_script) # Dossier tests
project_root = os.path.dirname(current_dir)   # Dossier parent (Racine)

print(f"📂 Racine détectée : {project_root}")

# Vérification physique (Basé sur votre liste: 'worker' en minuscule)
worker_path = os.path.join(project_root, 'worker') # <-- MINUSCULE ICI
worker_init = os.path.join(worker_path, '__init__.py')

if not os.path.exists(worker_path):
    print(f"❌ CRITIQUE : Le dossier '{worker_path}' n'existe pas !")
    sys.exit(1)

# Création __init__.py si manquant
if not os.path.exists(worker_init):
    print(f"⚠️  Création de '{worker_init}' pour permettre l'import...")
    try:
        with open(worker_init, 'w') as f: pass
    except Exception as e:
        print(f"❌ Erreur création fichier: {e}")

# Injection du chemin racine
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- MOCKS ---
sys.modules['google.generativeai'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['groq'] = MagicMock()

# --- IMPORTS FONCTIONNELS (MINUSCULES) ---
try:
    # On utilise 'worker' et non 'Worker'
    from worker.handlers.swarm import get_agent_session 
    from ai_core.factory import SessionFactory
    from features.UnifiedLogger import UnifiedLogger
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")
    print("Astuce : Vérifiez que 'worker', 'handlers' et 'swarm.py' contiennent tous un fichier __init__.py (sauf swarm.py)")
    sys.exit(1)

class TestIdentityDataFlow(unittest.TestCase):
    def test_trace_identity_propagation(self):
        target_role = "CODER"
        expected_identity = "Coder" 
        
        print("\n" + "="*60)
        print(f"🚀 SCÉNARIO : L'utilisateur demande un agent '{target_role}'")
        print("="*60)

        # Reset cache (Notez l'import en minuscule)
        import worker.handlers.swarm
        worker.handlers.swarm._agent_sessions = {}

        passed_name = None
        
        # Espionnage de la Factory
        with patch.object(SessionFactory, 'create_session', side_effect=SessionFactory.create_session) as spy_create:
            session = get_agent_session(target_role)
            
            if spy_create.called:
                args, kwargs = spy_create.call_args
                passed_name = kwargs.get('agent_name')
                print(f"\n1️⃣  [WORKER -> FACTORY]")
                print(f"   Donnée transmise : agent_name='{passed_name}'")
                if passed_name == expected_identity:
                    print("   ✅ SUCCÈS : Le nom est bien passé.")
                else:
                    print(f"   ❌ ÉCHEC : Attendu '{expected_identity}', Reçu '{passed_name}'")
            else:
                print("❌ create_session non appelé.")

        # Vérification Session
        current_agent_name = getattr(session, 'agent_name', None)
        print(f"\n2️⃣  [FACTORY -> SESSION]")
        print(f"   Donnée stockée : self.agent_name='{current_agent_name}'")

        # Vérification Logs
        print(f"\n3️⃣  [SESSION -> LOGS]")
        found_log = False
        with patch('features.UnifiedLogger.UnifiedLogger.write') as mock_log_write:
            # Simulation log
            if hasattr(session, '_log_metrics'):
                mock_resp = MagicMock()
                mock_resp.usage_metadata.prompt_token_count = 10
                mock_resp.usage_metadata.candidates_token_count = 10
                session._log_metrics(0, mock_resp)
            
            for call in mock_log_write.call_args_list:
                args = call[0]
                if len(args) > 3 and args[1] == "METRICS":
                    data = args[3]
                    print(f"   Log intercepté : {data}")
                    if data.get("agent") == expected_identity:
                        found_log = True
                        print("   ✅ SUCCÈS : Le log contient le bon agent.")

        print("\n" + "-"*60)
        if passed_name == expected_identity and current_agent_name == expected_identity and found_log:
            print("🟢 SUCCÈS TOTAL : La chaîne est réparée.")
        else:
            print(f"🔴 ÉCHEC FINAL.")
        print("-"*60)

if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=0)
    runner.run(unittest.makeSuite(TestIdentityDataFlow)) 
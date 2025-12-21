import unittest
import queue
import sys
import os
import threading
from unittest.mock import MagicMock, patch, ANY

# Ajout racine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# On importe la classe Worker
from worker.core import Worker

class TestWorkerIntegration(unittest.TestCase):
    
    def setUp(self):
        """Préparation du banc d'essai."""
        self.task_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.stop_event = MagicMock()
        
        # Patchs des dépendances externes du Worker
        self.patchers = [
            patch('worker.core.SessionFactory'),
            patch('worker.core.create_agent'), # Le Factory Swarm
            patch('worker.core.database'),     # Le RAG
            patch('worker.core.GlobalMemoryManager'), # La Mémoire
            # On simule les Settings pour éviter les erreurs de clé
            patch('worker.core.APP_SETTINGS', {
                "swarm_settings": {"role_mapping": {}},
                "system_settings": {"rag_database_path": "db/test.sqlite"},
                "automation": {"arch_update_interval": 0}
            })
        ]
        
        # Démarrage des patchs
        self.mocks = [p.start() for p in self.patchers]
        self.mock_factory = self.mocks[0]
        self.mock_create_agent = self.mocks[1]
        
        # Configuration du Mock Agent (Ce que create_agent renvoie)
        self.mock_agent_instance = MagicMock()
        # Simulation d'une réponse d'agent réussie
        self.mock_agent_instance.execute_task.return_value = type('obj', (object,), {'text': "Mission Accomplished"})
        self.mock_create_agent.return_value = self.mock_agent_instance
        
        # Instanciation du Worker
        self.worker = Worker(self.task_queue, self.response_queue, self.stop_event)
        
        # Désactivation du background executor pour que tout soit synchrone (plus facile à tester)
        self.worker.bg_executor = MagicMock()
        self.worker.bg_executor.submit = lambda fn, *args, **kwargs: fn(*args, **kwargs)

    def tearDown(self):
        for p in self.patchers: p.stop()

    def test_switch_reasoning_mode(self):
        """SCÉNARIO 1 : Activation du mode Raisonnement via l'UI."""
        # 1. Configuration : On force le Worker à faire 1 tour de boucle puis s'arrêter
        self.stop_event.is_set.side_effect = [False, True]
        
        # On simule une session existante pour vérifier qu'elle est bien recréée
        self.worker.main_session = MagicMock()
        self.worker.main_session.chat.history = ["Ancien Historique"]
        
        # 2. Action : Envoi du signal UI
        task = {'type': 'set_reasoning_mode', 'payload': {'enabled': True}}
        self.task_queue.put(task)
        
        # 3. Exécution : On lance le run() qui va consommer la tâche
        print("\n🔹 Test: Bascule Mode Raisonnement...")
        self.worker.run()
        
        # 4. Vérifications
        # L'état interne doit être True
        self.assertTrue(self.worker.reasoning_active, "L'état reasoning_active devrait être True")
        
        # La session doit avoir été recréée avec le modèle 'reasoning'
        self.mock_factory.create_session.assert_called_with(
            model_type="reasoning", 
            system_instruction=ANY
        )
        print("✅ Session recréée avec modèle 'reasoning'.")

    def test_agent_task_injection(self):
        """SCÉNARIO 2 : Lancement d'un Agent avec Contexte et Mode Raisonnement."""
        # 1. Prerequis : Mode Raisonnement activé
        self.worker.reasoning_active = True
        
        # 2. Mock du RAG (Simuler des documents trouvés)
        self.worker._retrieve_rag_context = MagicMock(return_value="[CONTENU RAG CRITIQUE]")
        
        # 3. Action : Demande de tâche agent
        task_payload = {
            'agent_role': 'CODER', 
            'prompt': 'Refactorise ce code.',
            'task_id': 'TEST_001'
        }
        
        print("\n🔹 Test: Lancement Agent Coder...")
        # Appel direct du handler pour isoler ce test
        self.worker._handle_agent_task(task_payload)
        
        # 4. Vérifications
        # create_agent a-t-il été appelé ?
        self.mock_create_agent.assert_called_once()
        
        # A-t-il reçu les bons arguments ?
        args, kwargs = self.mock_create_agent.call_args
        
        # Vérif 1 : Le rôle
        self.assertEqual(args[0], 'CODER')
        
        # Vérif 2 : Le Mode Raisonnement (C'est le point clé !)
        self.assertEqual(kwargs['reasoning_mode'], True, "L'agent n'a pas reçu le reasoning_mode=True")
        
        # Vérif 3 : Le Contexte RAG
        context_sent = kwargs['initial_context']
        self.assertIn("[CONTENU RAG CRITIQUE]", context_sent, "Le contexte RAG n'a pas été transmis.")
        
        print("✅ Agent créé avec Contexte + Reasoning Mode.")

if __name__ == '__main__':
    unittest.main()
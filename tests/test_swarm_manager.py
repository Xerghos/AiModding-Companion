import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import os

# Ajout de la racine du projet au PATH pour les imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Imports du module à tester
from agents.swarm_manager import SwarmAgent, create_agent

class TestSwarmManager(unittest.TestCase):
    
    def setUp(self):
        """Préparation avant chaque test."""
        # On mocke les dépendances externes pour isoler le test
        self.mock_session_factory_patcher = patch('agents.swarm_manager.SessionFactory')
        self.MockSessionFactory = self.mock_session_factory_patcher.start()
        
        # On mocke la configuration pour avoir des tests déterministes
        self.mock_settings_patcher = patch('agents.swarm_manager.APP_SETTINGS', {
            "swarm_settings": {"max_auto_loop": 3}
        })
        self.mock_settings = self.mock_settings_patcher.start()

    def tearDown(self):
        """Nettoyage après chaque test."""
        self.mock_session_factory_patcher.stop()
        self.mock_settings_patcher.stop()

    # --- 1. TESTS D'INITIALISATION (Whitelisting & Tiering) ---

    def test_init_coder_properties(self):
        """Vérifie qu'un agent CODER est bien configuré (Tier + Outils)."""
        # Exécution
        agent = SwarmAgent("CODER")
        
        # Vérifications
        self.assertEqual(agent.tier, "coder", "Le Tier devrait être 'coder'")
        self.MockSessionFactory.create_session.assert_called_once()
        
        # Vérification du Whitelisting dans le prompt
        prompt_genere = agent.system_instruction
        self.assertIn("MANUEL DES OUTILS AUTORISÉS", prompt_genere)
        self.assertIn("lire_fichier", prompt_genere)  # Outil autorisé
        self.assertNotIn("web_search", prompt_genere) # Outil interdit pour le Coder (selon personas par défaut)

    def test_init_router_properties(self):
        """Vérifie qu'un agent ROUTER est léger et sans outils."""
        agent = SwarmAgent("ROUTER")
        
        self.assertEqual(agent.tier, "fast", "Le Tier devrait être 'fast'")
        
        prompt_genere = agent.system_instruction
        self.assertNotIn("MANUEL DES OUTILS AUTORISÉS", prompt_genere, "Le Router ne devrait pas avoir d'outils")

    def test_context_injection(self):
        """Vérifie que la mémoire partagée est bien injectée."""
        contexte = "Ceci est un souvenir important."
        agent = SwarmAgent("ARCHITECT", initial_context=contexte)
        
        self.assertIn("CONTEXTE DE MISSION", agent.system_instruction)
        self.assertIn(contexte, agent.system_instruction)

    # --- 2. TESTS DU MODE RAISONNEMENT ---

    def test_reasoning_mode_upgrade(self):
        """Vérifie l'upgrade automatique du modèle en mode raisonnement."""
        # Cas 1 : Agent 'ARCHITECT' (Eligible)
        agent = SwarmAgent("ARCHITECT", reasoning_mode=True)
        self.assertEqual(agent.tier, "reasoning", "L'Architecte aurait dû passer en 'reasoning'")
        
        # Cas 2 : Agent 'WRITER' (Fast -> Pas d'upgrade)
        # Note : Cela dépend de votre config dans agent_personas.py. Supposons Writer=fast.
        agent_fast = SwarmAgent("WRITER", reasoning_mode=True)
        self.assertEqual(agent_fast.tier, "fast", "Le Writer (Fast) ne devrait pas changer de tier")

    # --- 3. TESTS DE LA BOUCLE D'AUTONOMIE (Retry Loop) ---

    @patch('features.ai_helper.analyze_request_and_dispatch')
    def test_retry_loop_logic(self, mock_dispatch):
        """Simule une boucle : Erreur Outil -> Correction -> Succès."""
        agent = SwarmAgent("CODER")
        
        # Simulation de la conversation :
        # Tour 1 : L'IA demande un outil (!native_tool)
        # Tour 2 : L'IA reçoit le résultat et conclut (Texte)
        
        mock_response_tool = MagicMock()
        mock_response_tool.text = '!native_tool {"name": "lire_fichier", "args": {"chemin": "test.py"}}'
        
        mock_response_final = MagicMock()
        mock_response_final.text = "Analyse terminée."
        
        # On configure le Mock de session pour renvoyer ces réponses successivement
        agent.session.send_message.side_effect = [mock_response_tool, mock_response_final]
        
        # On configure le résultat simulé de l'outil
        mock_dispatch.return_value = "Contenu du fichier test.py..."
        
        # Exécution
        result = agent.execute_task("Analyse test.py")
        
        # Vérifications
        self.assertEqual(agent.session.send_message.call_count, 2, "L'IA aurait dû être appelée 2 fois")
        mock_dispatch.assert_called_once() # L'outil a bien été exécuté
        self.assertIn("Analyse terminée", result.text)

if __name__ == '__main__':
    unittest.main()
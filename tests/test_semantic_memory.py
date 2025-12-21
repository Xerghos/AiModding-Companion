import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Ajout racine au path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import du module à tester
import features.SemanticMemory as SemMem

class TestSemanticMemory(unittest.TestCase):
    
    def setUp(self):
        """Préparation de l'environnement de test."""
        self.mock_sys = {
            "session": MagicMock(),
            "action_log_path": "dummy_log.json",
            "result_queue": MagicMock(),
            "task_queue": MagicMock()
        }
        
        # --- PATCH BASE DE DONNÉES ---
        self.patcher_db = patch('features.SemanticMemory.database')
        self.mock_db = self.patcher_db.start()
        
        self.mock_db.store_memory = MagicMock(return_value=True)
        self.mock_db.search_memories = MagicMock()
        self.mock_db.search_vector_db = MagicMock()
        self.mock_db.add_memory_fragment = MagicMock()

        # Activation forcée
        SemMem.GlobalMemoryManager.ltm_enabled = True

    def tearDown(self):
        self.patcher_db.stop()

    def test_sauvegarder_memoire(self):
        """Vérifie que la sauvegarde appelle correctement la DB."""
        cle = "projet_actuel"
        valeur = "Refactoring du module Swarm"
        
        res = SemMem.execute_sauvegarder_memoire(cle, valeur, **self.mock_sys)
        
        self.assertIn("succès", str(res).lower())
        self.assertIn(valeur, str(res))
        
        # Vérification appel DB (Nouveau ou Ancien)
        called = self.mock_db.store_memory.called or self.mock_db.add_memory_fragment.called
        self.assertTrue(called, "La base de données n'a pas été appelée.")

    def test_rechercher_memoire(self):
        """Vérifie que la recherche interroge la DB et formate le résultat."""
        # CORRECTION MOCK : Format (Source, Contenu, Score)
        # C'est ce format que SemanticMemory.py attend (index 1 = contenu)
        self.mock_db.search_memories.return_value = [
            ("memory://1", "L'utilisateur préfère le mode sombre.", 0.95),
            ("memory://2", "Le projet utilise Python 3.10.", 0.88)
        ]
        
        res = SemMem.execute_rechercher_memoire("préférences", **self.mock_sys)
        
        self.assertIn("mode sombre", str(res))
        self.assertIn("Python 3.10", str(res))
        self.mock_db.search_memories.assert_called()

    def test_recherche_vide(self):
        """Vérifie le comportement si la DB ne trouve rien."""
        self.mock_db.search_memories.return_value = []
        
        res = SemMem.execute_rechercher_memoire("truc impossible", **self.mock_sys)
        
        self.assertIn("Aucun souvenir", str(res))

if __name__ == '__main__':
    unittest.main()
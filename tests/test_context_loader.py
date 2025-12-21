import unittest
import shutil
import tempfile
import os
import sys
import json
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import features.ContextLoader as CL

class TestContextLoader(unittest.TestCase):
    
    def setUp(self):
        """Sandbox Context."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        self.mock_sys = {
            "session": MagicMock(),
            "action_log_path": "dummy.json",
            "result_queue": MagicMock(),
            "task_queue": MagicMock()
        }
        
        os.makedirs("config", exist_ok=True)
        
        # CORRECTION : Utilisation des clés attendues par ContextLoader.py ('primary_files')
        self.fake_arch_map = {
            "test_domain": {
                "primary_files": ["src/a.py", "src/b.py"],
                "related_files": []
            }
        }
        with open("config/architecture_map.json", "w") as f:
            json.dump(self.fake_arch_map, f)
        
        # Patchs
        self.patchers = [
            patch('features.Shared.log_action'),
            # Patch 1: get_path (Config) - Force le chemin relatif
            patch('features.ContextLoader.get_path', side_effect=lambda p: os.path.abspath(p)),
            
            # Patch 2: Résolveur global (au cas où il est appelé)
            patch('features.Shared.smart_resolve_path', side_effect=lambda p: os.path.abspath(p))
        ]
        
        for p in self.patchers: p.start()

    def tearDown(self):
        for p in self.patchers: p.stop()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_chargement_domaine(self):
        """Vérifie le chargement de fichiers via Architecture Map."""
        # Setup arborescence
        os.makedirs("src")
        with open("src/a.py", "w", encoding="utf-8") as f: f.write("contenu code A")
        with open("src/b.py", "w", encoding="utf-8") as f: f.write("contenu code B")
        with open("src/c.py", "w", encoding="utf-8") as f: f.write("contenu code C") # Non inclus
        
        res = CL.charger_contexte_domaine(domaine="test_domain", **self.mock_sys)
        
        # Vérifications
        # On vérifie que le texte des fichiers est bien présent dans le rapport
        self.assertIn("contenu code A", str(res))
        self.assertIn("contenu code B", str(res))
        
        # On vérifie que le fichier non listé n'est pas chargé
        self.assertNotIn("contenu code C", str(res))
        
        # On vérifie la structure du rapport
        self.assertIn("CONTEXTE ARCHITECTURAL : TEST_DOMAIN", str(res))

    def test_domaine_inconnu(self):
        """Vérifie la gestion d'erreur."""
        res = CL.charger_contexte_domaine(domaine="inconnu_au_bataillon", **self.mock_sys)
        self.assertIn("inconnu", str(res).lower())

if __name__ == '__main__':
    unittest.main()
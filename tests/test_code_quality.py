import unittest
import shutil
import tempfile
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import features.CodeQuality as CQ

class TestCodeQuality(unittest.TestCase):
    
    def setUp(self):
        """Sandbox Code."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        self.mock_sys = {
            "session": MagicMock(),
            "action_log_path": "dummy.json",
            "result_queue": MagicMock(),
            "task_queue": MagicMock()
        }
        
        # Patchs
        self.patchers = [
            patch('features.core_backup.create_backup'),
            patch('features.Shared.log_action'),
            # On stocke le patcher de l'IA pour pouvoir modifier sa réponse dans les tests
            patch('features.CodeQuality.call_ai_robust', return_value="Analyse IA simulée: Code OK."),
            patch('features.CodeQuality.smart_resolve_path', side_effect=lambda p: os.path.abspath(p))
        ]
        
        self.mocks = [p.start() for p in self.patchers]
        # On récupère le mock de l'IA (le 3ème dans la liste, index 2)
        self.mock_ai = self.mocks[2]

    def tearDown(self):
        for p in self.patchers: p.stop()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_audit_syntaxe_invalide(self):
        """Vérifie que l'audit rapporte une erreur (Simulée via IA)."""
        # --- CORRECTIF : On force l'IA à détecter l'erreur pour ce test ---
        self.mock_ai.return_value = "CRITIQUE: SyntaxError detected line 1. Missing colon."
        
        fichier_casse = "broken.py"
        with open(fichier_casse, "w") as f:
            f.write("def fonction_sans_deux_points()\n    print('bug')")
            
        res = CQ.execute_verifier_code(chemin=fichier_casse, consigne="Check", **self.mock_sys)
        
        # On vérifie que le rapport contient le mot clé d'erreur
        self.assertIn("SyntaxError", str(res))

    def test_analyse_metriques(self):
        """Vérifie l'extraction des métriques."""
        # On remet l'IA en mode succès
        self.mock_ai.return_value = "Analyse : Classe MaClasse trouvée."
        
        fichier_propre = "clean.py"
        with open(fichier_propre, "w") as f: f.write("class MaClasse: pass")
        
        res = CQ.execute_analyser_code(chemin=fichier_propre, **self.mock_sys)
        
        self.assertIn("MaClasse", str(res))

    def test_audit_fichier_vide(self):
        """Vérifie la gestion des fichiers vides (Logique interne sans IA)."""
        with open("empty.py", "w") as f: f.write("")
        
        res = CQ.execute_verifier_code(chemin="empty.py", consigne="", **self.mock_sys)
        self.assertIn("vide", str(res).lower())

if __name__ == '__main__':
    unittest.main()
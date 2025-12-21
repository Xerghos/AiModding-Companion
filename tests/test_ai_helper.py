import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Ajout racine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Imports cibles
from features.ai_helper import (
    _security_check, 
    _smart_extract_and_parse, 
    analyze_request_and_dispatch
)

class TestAiHelperSecurity(unittest.TestCase):
    
    def setUp(self):
        """Configuration d'un environnement de sécurité strict."""
        self.mock_settings = {
            "security": {
                "enable_sanity_check": True,
                "block_outside_project": True,
                "protected_directories": [".git", "logs"],
                "protected_files": ["config/settings.py"]
            }
        }
        # On patch APP_SETTINGS pour contrôler la config de sécurité
        self.patcher = patch("features.ai_helper.APP_SETTINGS", self.mock_settings)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    # --- 1. TESTS MIDDLEWARE SÉCURITÉ ---

    def test_security_access_legitime(self):
        """Un accès à un fichier normal doit passer."""
        error = _security_check("lire_fichier", {"chemin": "README.md"})
        self.assertIsNone(error, "L'accès à README.md devrait être autorisé.")

    def test_security_confinement_jail(self):
        """La sortie du dossier projet doit être bloquée."""
        error = _security_check("lire_fichier", {"chemin": "../secret.txt"})
        self.assertIsNotNone(error)
        self.assertIn("Accès interdit hors du projet", error)

    def test_security_protected_file_write(self):
        """L'écriture sur un fichier protégé doit être bloquée."""
        error = _security_check("ecrire_fichier", {"chemin": "config/settings.py"})
        self.assertIsNotNone(error)
        self.assertIn("protégé", error)

    def test_security_protected_file_read_allowed(self):
        """La LECTURE d'un fichier protégé doit être AUTORISÉE (seule l'écriture est dangereuse)."""
        error = _security_check("lire_fichier", {"chemin": "config/settings.py"})
        self.assertIsNone(error, "La lecture des settings devrait être permise.")

    def test_security_disabled(self):
        """Si on désactive la sécu, tout doit passer."""
        with patch("features.ai_helper.APP_SETTINGS", {"security": {"enable_sanity_check": False}}):
            error = _security_check("ecrire_fichier", {"chemin": "config/settings.py"})
            self.assertIsNone(error, "La sécurité désactivée devrait tout laisser passer.")


class TestAiHelperParsing(unittest.TestCase):

    # --- 2. TESTS PARSING INTELLIGENT ---

    def test_parse_valid_json(self):
        """JSON valide standard."""
        text = '!native_tool {"name": "test", "args": {"a": 1}}'
        res = _smart_extract_and_parse(text.split('!native_tool')[1])
        self.assertEqual(res['name'], "test")

    def test_parse_python_dict(self):
        """Format Python (ast) souvent généré par les LLM locaux."""
        text = "!native_tool {'name': 'test', 'args': {'val': True}}"
        res = _smart_extract_and_parse(text.split('!native_tool')[1])
        self.assertEqual(res['args']['val'], True)

    def test_repair_json_truncated(self):
        """Réparation de JSON tronqué (manque l'accolade finale)."""
        text = '{"name": "test", "args": {"a": 1' # Il manque }}
        res = _smart_extract_and_parse(text)
        self.assertEqual(res['name'], "test")
        self.assertEqual(res['args']['a'], 1)


class TestAiHelperDispatch(unittest.TestCase):

    # --- 3. TESTS DISPATCHER ---

    @patch('features.ai_helper.execute_native_tool')
    def test_dispatch_routing(self, mock_exec):
        """Vérifie que la commande est bien routée vers l'exécuteur."""
        mock_exec.return_value = "OK"
        
        cmd = '!native_tool {"name": "my_tool", "args": {}}'
        analyze_request_and_dispatch(cmd, None, None)
        
        mock_exec.assert_called_once()
        args, _ = mock_exec.call_args
        self.assertEqual(args[0], "my_tool")

    @patch('features.ai_helper.execute_lister_outils')
    def test_introspection_call(self, mock_list):
        """Vérifie que '!list_tools' déclenche l'introspection."""
        analyze_request_and_dispatch("!list_tools", None, None)
        mock_list.assert_called_once()

if __name__ == '__main__':
    unittest.main()
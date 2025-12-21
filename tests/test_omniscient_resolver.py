import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Ajout racine projet
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from features.SearchEngine import OmniscientResolver, omniscient_resolve_path

class TestOmniscient(unittest.TestCase):
    
    def test_fuzzy_search(self):
        """Vérifie que 'config' trouve bien 'config/settings.py' ou similaire."""
        # On suppose que config/settings.py existe dans le projet
        result = OmniscientResolver.resolve("settings.py")
        print(f"Fuzzy 'settings.py' -> {result}")
        self.assertIsNotNone(result)
        self.assertIn("settings.py", result)

    def test_exact_search(self):
        """Vérifie la recherche exacte."""
        result = OmniscientResolver.resolve("requirements.txt")
        print(f"Exact 'requirements.txt' -> {result}")
        self.assertIsNotNone(result)

    def test_wrapper(self):
        """Vérifie le wrapper exposé."""
        res = omniscient_resolve_path("main.py")
        # Même si main.py n'existe pas, ça ne doit pas crasher
        print(f"Wrapper 'main.py' -> {res}")

if __name__ == '__main__':
    unittest.main()
import unittest
import shutil
import tempfile
import os
import sys
from unittest.mock import MagicMock, patch

# Ajout racine projet
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# On importe le module à tester
import features.FileSystem as FS

class TestFileSystemSecurity(unittest.TestCase):
    
    def setUp(self):
        """Configuration d'un environnement de test isolé (Sandbox)."""
        self.test_dir = tempfile.mkdtemp()
        
        # Mocks des dépendances optionnelles (RAG & Backup)
        self.patcher_db = patch('features.FileSystem.database')
        self.patcher_backup = patch('features.FileSystem.backup_manager')
        
        # On redirige get_path pour qu'il travaille dans le dossier temporaire
        self.patcher_path = patch('features.FileSystem.get_path', side_effect=lambda p: os.path.join(self.test_dir, p))
        
        self.mock_db = self.patcher_db.start()
        self.mock_backup = self.patcher_backup.start()
        self.mock_path = self.patcher_path.start()

    def tearDown(self):
        self.patcher_db.stop()
        self.patcher_backup.stop()
        self.patcher_path.stop()
        shutil.rmtree(self.test_dir)

    def test_ecriture_python_valide(self):
        """Vérifie qu'un code valide est écrit et indexé."""
        chemin = "valid.py"
        code = "def hello():\n    print('World')"
        
        res = FS.ecrire_fichier(chemin, code)
        
        # 1. Vérif succès
        self.assertIn("succès", res.lower())
        
        # 2. Vérif fichier sur disque
        full_path = os.path.join(self.test_dir, chemin)
        self.assertTrue(os.path.exists(full_path))
        
        # 3. Vérif Hook RAG activé
        self.mock_db.add_file_to_db.assert_called_with(chemin)

    def test_ecriture_python_invalide(self):
        """Vérifie que le code cassé est rejeté."""
        chemin = "broken.py"
        # Erreur de syntaxe (manque ':')
        code_pourri = "def fonction_sans_deux_points()\n    pass"
        
        res = FS.ecrire_fichier(chemin, code_pourri)
        
        # 1. Vérif rejet
        self.assertIn("erreur syntaxe", res.lower())
        self.assertIn("refusée", res.lower())
        
        # 2. Vérif fichier NON créé
        full_path = os.path.join(self.test_dir, chemin)
        self.assertFalse(os.path.exists(full_path))
        
        # 3. Vérif RAG NON appelé
        self.mock_db.add_file_to_db.assert_not_called()

    def test_ecriture_texte_standard(self):
        """Vérifie que les fichiers non-python ignorent le check syntaxique."""
        chemin = "note.txt"
        contenu = "Pas de syntaxe ici :)"
        
        res = FS.ecrire_fichier(chemin, contenu)
        
        self.assertIn("succès", res.lower())
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, chemin)))

if __name__ == '__main__':
    unittest.main()
import unittest
import os
import sys
import shutil
import tempfile
from unittest.mock import patch

# Ajout racine projet
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import features.FileSystem as FS

class TestFileSystemResolver(unittest.TestCase):
    
    def setUp(self):
        """On crée un environnement avec un fichier caché."""
        self.test_dir = tempfile.mkdtemp()
        
        # On crée un fichier réel
        self.real_filename = "secret_data.json"
        self.real_path = os.path.join(self.test_dir, self.real_filename)
        with open(self.real_path, 'w', encoding='utf-8') as f:
            f.write("TOP SECRET CONTENT")
            
        # On redirige get_path pour qu'il travaille DANS ce dossier temporaire
        # Cela isole complètement le test de votre vrai dossier projet
        self.patcher = patch('features.FileSystem.get_path', side_effect=lambda p: os.path.join(self.test_dir, p))
        self.mock_get_path = self.patcher.start()
        
        # On doit aussi patcher get_path dans SearchEngine car le Resolver l'utilise
        self.patcher_search = patch('features.SearchEngine.get_path', side_effect=lambda p: os.path.join(self.test_dir, p))
        self.mock_search_path = self.patcher_search.start()

    def tearDown(self):
        self.patcher.stop()
        self.patcher_search.stop()
        shutil.rmtree(self.test_dir)

    def test_lecture_avec_resolution_automatique(self):
        """
        SCÉNARIO :
        1. On demande de lire "secret_data" (sans extension).
        2. FileSystem ne le trouve pas.
        3. Il appelle le Resolver.
        4. Le Resolver (Fuzzy Logic) trouve "secret_data.json".
        5. FileSystem lit le contenu.
        """
        # Demande vague (sans .json)
        nom_vague = "secret_data"
        
        print(f"\n🔹 Test: Tentative de lecture de '{nom_vague}'...")
        contenu = FS.lire_fichier(nom_vague)
        
        # Vérifications
        self.assertEqual(contenu, "TOP SECRET CONTENT")
        print("✅ Succès : Le contenu a été récupéré malgré le nom incomplet.")

    def test_echec_si_introuvable(self):
        """Vérifie que ça échoue proprement si rien ne correspond."""
        contenu = FS.lire_fichier("fichier_imaginaire_total")
        self.assertIn("Erreur", contenu)
        print("✅ Succès : L'erreur est bien remontée pour un fichier inexistant.")

if __name__ == '__main__':
    unittest.main()
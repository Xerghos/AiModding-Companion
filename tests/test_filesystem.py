import unittest
import shutil
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ajout racine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Module à tester
import features.FileSystem as FS

class TestFileSystem(unittest.TestCase):
    
    def setUp(self):
        """Création d'une SANDBOX (Environnement isolé) + Mocks Système."""
        # 1. Dossier temporaire (Sandbox)
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        
        # 2. Mocks Système (Session, Logs, Queue)
        self.mock_session = MagicMock()
        self.mock_queue = MagicMock()
        self.mock_log_path = "dummy_log.json"
        self.mock_task_queue = MagicMock()
        
        self.sys_args = {
            "session": self.mock_session,
            "action_log_path": self.mock_log_path,
            "result_queue": self.mock_queue,
            "task_queue": self.mock_task_queue 
        }
        
        # 3. Mocks Effets de Bord
        self.patcher_backup = patch('features.core_backup.create_backup')
        self.mock_backup = self.patcher_backup.start()
        
        self.patcher_log = patch('features.Shared.log_action')
        self.mock_log = self.patcher_log.start()

        # 4. CRITIQUE : DÉTOURNEMENT DE get_path et SÉCURITÉ
        # On force get_path à renvoyer notre dossier temporaire pour TOUS les appels
        self.patcher_path = patch('features.FileSystem.get_path')
        self.mock_get_path = self.patcher_path.start()
        
        # Logique du mock : si on demande ".", on renvoie temp_dir, sinon on combine
        def side_effect_get_path(path_rel):
            if path_rel == ".": return self.test_dir
            return os.path.join(self.test_dir, path_rel)
        self.mock_get_path.side_effect = side_effect_get_path

        # On désactive la sécurité pour le test (car temp_dir est hors du projet réel)
        self.patcher_secu = patch('features.ai_helper._security_check', return_value=None)
        self.mock_secu = self.patcher_secu.start()

    def tearDown(self):
        """Nettoyage."""
        shutil.rmtree(self.test_dir) # Supprime la sandbox
        self.patcher_backup.stop()
        self.patcher_log.stop()
        self.patcher_path.stop()
        self.patcher_secu.stop()

    # --- TESTS FONCTIONNELS ---

    def test_ecrire_et_lire_fichier(self):
        """Test simple : Écriture -> Lecture."""
        nom_fichier = "test_doc.txt"
        contenu = "Hello World"
        
        # Écriture
        res_write = FS.execute_ecrire_fichier(nom_fichier, contenu, **self.sys_args)
        
        # Vérification (insensible à la casse)
        self.assertIn("succès", str(res_write).lower())
        
        # On vérifie physiquement DANS LA SANDBOX
        chemin_sandbox = os.path.join(self.test_dir, nom_fichier)
        self.assertTrue(os.path.exists(chemin_sandbox), "Le fichier n'a pas été créé dans la sandbox")
        
        # Lecture
        res_read = FS.execute_lire_fichier(nom_fichier, **self.sys_args)
        self.assertEqual(res_read, contenu)

    def test_ecrire_dans_sous_dossier_auto(self):
        """L'outil doit créer les dossiers parents manquants automatiquement."""
        chemin = "dossier/sous_dossier/fichier.txt"
        contenu = "Deep content"
        
        FS.execute_ecrire_fichier(chemin, contenu, **self.sys_args)
        
        chemin_sandbox = os.path.join(self.test_dir, "dossier", "sous_dossier", "fichier.txt")
        self.assertTrue(os.path.exists(chemin_sandbox))

    def test_lister_arborescence(self):
        """Vérifie que l'outil voit bien les fichiers de la SANDBOX."""
        # On peuple la sandbox manuellement
        os.makedirs(os.path.join(self.test_dir, "src"))
        with open(os.path.join(self.test_dir, "src/main.py"), "w") as f: f.write("print('hi')")
        
        res = FS.execute_lister_arborescence(".", **self.sys_args)
        
        self.assertIn("src", res)
        self.assertIn("main.py", res)
        # On vérifie qu'on ne voit PAS les fichiers du vrai projet
        self.assertNotIn("AiModding-Companion", res)

    def test_supprimer_fichier(self):
        """Vérifie la suppression."""
        f = "todelete.txt"
        p = os.path.join(self.test_dir, f)
        with open(p, "w") as file: file.write("bye")
        
        FS.execute_supprimer_fichier(f, **self.sys_args)
        self.assertFalse(os.path.exists(p))

if __name__ == '__main__':
    unittest.main()
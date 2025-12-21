import unittest
import shutil
import tempfile
import os
import sys
import time
import zipfile
from unittest.mock import MagicMock, patch

# Ajout racine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Modules à tester
import features.BackupManager as BM
import features.core_backup as CoreBackup

class TestBackupManager(unittest.TestCase):
    
    def setUp(self):
        """Configuration d'une Sandbox de Backup."""
        # 1. Dossiers temporaires
        self.test_root = tempfile.mkdtemp()      
        self.project_dir = os.path.join(self.test_root, "MyProject") 
        self.backup_dir = os.path.join(self.test_root, "Backups")    
        
        os.makedirs(self.project_dir)
        os.makedirs(self.backup_dir)
        
        # 2. Création d'un fichier à sauvegarder
        with open(os.path.join(self.project_dir, "data.txt"), "w") as f:
            f.write("Important Data")

        # 3. Mocks Système
        self.mock_sys_args = {
            "session": MagicMock(),
            "action_log_path": "dummy.json",
            "result_queue": MagicMock(),
            "task_queue": MagicMock()
        }

        # 4. PATCH CRITIQUE (Isolation)
        
        # A. Patch destination dans moteur
        self.p_core_dest = patch('features.core_backup.BACKUP_DIR', self.backup_dir)
        self.p_core_dest.start()
        
        # B. Patch source (String)
        self.p_app_to_backup = patch('features.core_backup.APP_TO_BACKUP', self.project_dir)
        self.p_app_to_backup.start()
        
        # C. Patch destination dans wrapper UI
        self.p_bm_dest = patch('features.BackupManager.BACKUP_DIR', self.backup_dir)
        self.p_bm_dest.start()
        
        # D. Settings
        self.p_settings = patch.dict('config.settings.APP_SETTINGS', {
            "backup": {"backup_dir": self.backup_dir}
        })
        self.p_settings.start()

    def tearDown(self):
        """Nettoyage."""
        self.p_core_dest.stop()
        self.p_app_to_backup.stop()
        self.p_bm_dest.stop()
        self.p_settings.stop()
        shutil.rmtree(self.test_root)

    # --- TESTS ---

    def test_creation_backup_zip(self):
        """Vérifie qu'un ZIP est bien créé et valide."""
        res = BM.execute_creer_backup(commentaire="TestInit", **self.mock_sys_args)
        
        # Vérification souple (réussie ou Succès)
        self.assertTrue("réussie" in str(res) or "Succès" in str(res), f"Message inattendu: {res}")
        
        # Vérification Fichier
        zips = [f for f in os.listdir(self.backup_dir) if f.endswith(".zip")]
        self.assertEqual(len(zips), 1)
        
        # Vérification Contenu
        zip_path = os.path.join(self.backup_dir, zips[0])
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files_in_zip = zf.namelist()
            self.assertTrue(any("data.txt" in f for f in files_in_zip))

    def test_rotation_backups(self):
        """Vérifie que les vieux backups sont supprimés."""
        with patch('features.core_backup.MAX_BACKUPS_TO_KEEP', 2):
            f1 = os.path.join(self.backup_dir, "backup_old.zip")
            f2 = os.path.join(self.backup_dir, "backup_mid.zip")
            f3 = os.path.join(self.backup_dir, "backup_new.zip")
            
            for f, offset in [(f1, 100), (f2, 50), (f3, 0)]:
                with open(f, 'w') as zipf: zipf.write("PK") 
                t = time.time() - offset
                os.utime(f, (t, t))
                
            CoreBackup._clean_old_backups()
            
            restants = os.listdir(self.backup_dir)
            self.assertEqual(len(restants), 2)
            self.assertIn("backup_new.zip", restants)
            self.assertNotIn("backup_old.zip", restants)

    def test_lister_backups(self):
        """Vérifie que l'outil liste bien les fichiers de la sandbox."""
        with open(os.path.join(self.backup_dir, "manuel.zip"), 'w') as f: f.write("PK")
        res = BM.execute_lister_backups(**self.mock_sys_args)
        self.assertIn("manuel.zip", str(res))

if __name__ == '__main__':
    unittest.main()
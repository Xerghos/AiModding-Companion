import os
import shutil
import datetime
import logging
import zipfile
import threading

# Imports Configuration Modulaire
from config.settings import (
    BACKUP_DIR, 
    APP_TO_BACKUP, 
    MAX_BACKUPS_TO_KEEP,
    BACKUP_INTERVAL_MINUTES
)
from config.logs import get_logger
from features.Decorators import trace_action

log = get_logger("features.core_backup")

# Verrou pour éviter que deux backups se lancent en même temps
_backup_lock = threading.Lock()
_last_backup_time = 0

@trace_action(source="core_backup")
def create_backup(force=False, comment="Auto"):
    """
    Crée une sauvegarde complète du projet (ZIP).
    Args:
        force (bool): Si True, ignore le délai minimum (Anti-Spam).
        comment (str): Motif ou commentaire du backup (utilisé pour les logs/métadonnées).
    """
    global _last_backup_time
    
    with _backup_lock:
        try:
            # Vérification du délai (sauf si forcé)
            if not force:
                import time
                now = time.time()
                # Conversion minutes -> secondes
                interval_sec = BACKUP_INTERVAL_MINUTES * 60
                if (now - _last_backup_time) < interval_sec:
                    log.debug(f"Backup ignoré (Délai {BACKUP_INTERVAL_MINUTES}m non écoulé).")
                    return None

            # Préparation du dossier
            if not os.path.exists(BACKUP_DIR):
                os.makedirs(BACKUP_DIR)

            # Sécurisation : Chemin absolu pour exclusion
            backup_dir_abs = os.path.abspath(BACKUP_DIR)

            # Nom du fichier : backup_YYYYMMDD_HHMMSS.zip
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            # On pourrait intégrer le commentaire dans le nom si c'était court, 
            # mais pour la sécurité des OS, on garde un timestamp propre.
            backup_filename = f"backup_{timestamp}.zip"
            backup_path = os.path.join(BACKUP_DIR, backup_filename)

            # Log avec le commentaire
            log.info(f"Démarrage Backup ({comment}) : {backup_filename} ...")

            # Liste d'exclusion explicite
            EXCLUDED_DIR_NAMES = {
                "__pycache__", "venv", "env", "node_modules", "dist", "build", 
                "logs", "db", ".idea", ".vscode", ".git", "sandbox" # Sandbox exclu par défaut ? À voir selon besoin
            }
            
            EXCLUDED_EXTENSIONS = {".pyc", ".pyd", ".pyo", ".log", ".zip", ".tmp"}

            file_count = 0
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(APP_TO_BACKUP):
                    # 1. Protection Anti-Récursion
                    if os.path.abspath(root).startswith(backup_dir_abs):
                        dirs[:] = []
                        continue

                    # 2. Filtrage Intelligent des Dossiers
                    dirs_to_keep = []
                    for d in dirs:
                        if d in EXCLUDED_DIR_NAMES: continue
                        if d.startswith('.'): continue
                        if os.path.abspath(os.path.join(root, d)) == backup_dir_abs: continue
                        dirs_to_keep.append(d)
                    
                    dirs[:] = dirs_to_keep
                    
                    for file in files:
                        # 3. Filtrage Fichiers
                        if file.startswith('.') and file != ".gitignore": continue
                        
                        _, ext = os.path.splitext(file)
                        if ext.lower() in EXCLUDED_EXTENSIONS: continue
                            
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, APP_TO_BACKUP)
                        
                        try:
                            zipf.write(file_path, arcname)
                            file_count += 1
                        except Exception as e:
                            log.warning(f"Impossible de backuper {file}: {e}")

            # Mise à jour du timestamp
            import time
            _last_backup_time = time.time()
            
            log.info(f"✅ Backup terminé : {backup_filename} ({file_count} fichiers).")
            
            # Nettoyage des vieux backups
            _clean_old_backups()
            
            return backup_path

        except Exception as e:
            log.error(f"❌ Echec Critique Backup : {e}")
            # On propage l'erreur pour que le Manager soit au courant
            raise e

@trace_action(source="core_backup")
def _clean_old_backups():
    """
    Supprime les anciens backups pour ne garder que les N derniers.
    """
    try:
        if not os.path.exists(BACKUP_DIR): return
        
        backups = []
        for f in os.listdir(BACKUP_DIR):
            if f.startswith("backup_") and f.endswith(".zip"):
                path = os.path.join(BACKUP_DIR, f)
                backups.append(path)
        
        backups.sort(key=os.path.getmtime)
        
        if len(backups) > MAX_BACKUPS_TO_KEEP:
            to_delete = backups[:-MAX_BACKUPS_TO_KEEP]
            for f in to_delete:
                try:
                    os.remove(f)
                except Exception as e:
                    log.warning(f"Echec suppression {f}: {e}")
                    
    except Exception as e:
        log.error(f"Erreur nettoyage backups: {e}")
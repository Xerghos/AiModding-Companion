import os
import logging
import glob
import zipfile
import shutil
import time
from datetime import datetime

# Imports Configuration Modulaire
from config.paths import get_path
from config.logs import get_logger
from config.settings import BACKUP_DIR

# Imports Features & Core
from features.Shared import log_action
from features.Decorators import trace_action

# Import Robuste du Core Backup (Logique Bas Niveau)
try:
    import features.core_backup as core_backup
except ImportError:
    try:
        import core_backup
    except ImportError:
        core_backup = None

log = get_logger("features.BackupManager")

# --- UTILITAIRES ---

def _format_size(size_bytes):
    """Formate une taille en octets vers une chaîne lisible."""
    for unit in ['o', 'Ko', 'Mo', 'Go']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} To"

# --- WRAPPERS DISPATCHER ---

@trace_action(source="BackupManager")
def execute_creer_backup(commentaire=None, force=False, session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Crée une sauvegarde complète du projet.
    Args:
        commentaire (str): Note optionnelle.
        force (bool): Si True, force le backup même si le délai n'est pas écoulé.
    """
    # Récupération souple des arguments
    comment = commentaire or kwargs.get('commentaire', f"Backup Auto {datetime.now().strftime('%H:%M')}")
    # L'IA peut envoyer le booléen sous forme de string ou bool
    force_flag = force or kwargs.get('force', False)
    if isinstance(force_flag, str):
        force_flag = force_flag.lower() == 'true'

    if not core_backup:
        return "❌ Module technique 'core_backup' introuvable. Impossible de créer la sauvegarde."

    try:
        if result_queue:
            result_queue.put({"type": "ui_update", "widget": "status", "text": "⏳ Création backup..."})

        # Appel au module technique
        # [FIX CRITIQUE] On passe le paramètre force
        zip_path = core_backup.create_backup(comment=comment, force=force_flag)
        
        # [FIX CRITIQUE] Gestion du cas où le backup est ignoré (Cooldown)
        if zip_path is None:
            msg = "⚠️ Backup ignoré : Le délai minimum entre deux sauvegardes n'est pas écoulé. (Utilisez force=True pour outrepasser)."
            if result_queue:
                result_queue.put({"type": "ui_update", "widget": "message", "text": "Backup ignoré (Délai)"})
            return msg

        filename = os.path.basename(zip_path)
        msg_success = f"✅ Sauvegarde réussie : `{filename}`"
        
        if action_log_path:
            log_action("creer_backup", f"Fichier: {filename} | Note: {comment}", "BackupManager", action_log_path)
        
        if result_queue:
            result_queue.put({"type": "ui_update", "widget": "message", "text": f"Backup OK : {filename}"})

        return msg_success

    except Exception as e:
        log.error(f"Erreur création backup : {e}")
        if result_queue:
            result_queue.put({"type": "error", "text": f"Echec Backup: {e}"})
        return f"❌ Erreur lors de la création du backup : {e}"

@trace_action(source="BackupManager")
def execute_lister_backups(session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Liste les sauvegardes disponibles dans le dossier dédié.
    """
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        return "Le dossier de sauvegarde était vide (et a été créé)."

    zip_files = glob.glob(os.path.join(BACKUP_DIR, "*.zip"))
    zip_files.sort(key=os.path.getmtime, reverse=True)
    
    backups_data = []
    ai_report = "📦 **Liste des Sauvegardes Disponibles :**\n\n"
    
    if not zip_files:
        if result_queue: result_queue.put({"type": "backup_list_data", "data": []})
        return "Aucune sauvegarde trouvée."

    for zip_path in zip_files:
        try:
            filename = os.path.basename(zip_path)
            stats = os.stat(zip_path)
            date_str = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            size_str = _format_size(stats.st_size)
            
            backups_data.append({
                "filename": filename,
                "date": date_str,
                "size": size_str,
                "original": filename, 
                "path": zip_path
            })
            
            if len(backups_data) <= 10:
                ai_report += f"- **{date_str}** : `{filename}` ({size_str})\n"
                
        except Exception as e:
            log.warning(f"Erreur lecture métadonnées {zip_path}: {e}")

    if len(zip_files) > 10:
        ai_report += f"\n*(... et {len(zip_files) - 10} autres sauvegardes plus anciennes)*"

    if result_queue:
        result_queue.put({"type": "backup_list_data", "data": backups_data})

    return ai_report

@trace_action(source="BackupManager")
def execute_restaurer_backup(nom_backup, session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Restaure une sauvegarde spécifique.
    """
    if not nom_backup:
        return "❌ Erreur : Aucun nom de backup fourni."

    backup_path = os.path.join(BACKUP_DIR, nom_backup)
    
    if not os.path.exists(backup_path):
        if os.path.exists(nom_backup): 
            backup_path = nom_backup
        else:
            return f"❌ Erreur : Le fichier de sauvegarde '{nom_backup}' est introuvable."
    
    if result_queue: 
        result_queue.put({"type": "ui_update", "widget": "message", "text": "⏳ Sécurité : Création point de restauration..."})
    
    # 1. Backup de sécurité (avec Force=True pour être sûr qu'il passe)
    if core_backup:
        try:
            core_backup.create_backup(comment="AUTO-SAFETY: Avant restauration", force=True)
        except Exception as e:
            return f"❌ Annulation : Impossible de créer le backup de sécurité ({e})."
    else:
        return "❌ Annulation : Module de backup HS."

    # 2. Restauration
    try:
        dest_dir = get_path(".")
        
        if result_queue: 
            result_queue.put({"type": "ui_update", "widget": "message", "text": f"⏳ Restauration de {os.path.basename(backup_path)}..."})
        
        with zipfile.ZipFile(backup_path, 'r') as zf:
            zf.extractall(dest_dir)
            
        msg = f"✅ Restauration terminée avec succès : **{os.path.basename(backup_path)}** a été appliqué."
        
        if action_log_path:
            log_action("restaurer_backup", f"Source: {nom_backup}", "BackupManager", action_log_path)
        
        if result_queue:
            result_queue.put({"type": "ui_update", "widget": "message", "text": "✅ Restauration OK."})
            result_queue.put({"type": "reload_system"}) 

        return msg

    except Exception as e:
        log.error(f"Erreur critique restauration : {e}")
        return f"❌ CRITICAL : Erreur lors de la restauration : {e}"
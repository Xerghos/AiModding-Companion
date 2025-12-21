import time
import sys
import logging
from features.core_backup import perform_backup_and_rotation

# Importation des constantes de config
try:
    from config import BACKUP_INTERVAL_MINUTES, MAX_BACKUPS_TO_KEEP, get_logger
except ImportError as e:
    print(f"Erreur d'importation des constantes de config: {e}. Vérifiez config.py")
    sys.exit(1)

# Utilisation du logger unifié
logger = get_logger(__name__)

def run_scheduler():
    """Lance la boucle de planification des sauvegardes."""
    
    # Convertir l'intervalle en secondes
    interval_seconds = BACKUP_INTERVAL_MINUTES * 60
    
    logger.info(f"Système de backup démarré.")
    logger.info(f"Intervalle de sauvegarde : {BACKUP_INTERVAL_MINUTES} minutes.")
    logger.info(f"Nombre maximum de backups à conserver : {MAX_BACKUPS_TO_KEEP} (voir config.py).")
    
    # Exécuter la première sauvegarde immédiatement
    perform_backup_and_rotation()
    
    while True:
        try:
            logger.info(f"Prochaine sauvegarde dans {BACKUP_INTERVAL_MINUTES} minutes...")
            time.sleep(interval_seconds)
            perform_backup_and_rotation()
        except KeyboardInterrupt:
            logger.info("Arrêt du système de backup par l'utilisateur.")
            break
        except Exception as e:
            logger.error(f"Une erreur inattendue est survenue dans la boucle principale : {e}")
            # Attendre 5 minutes avant de réessayer
            time.sleep(300) 

if __name__ == "__main__":
    run_scheduler()

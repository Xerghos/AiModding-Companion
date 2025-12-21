# Exposition des modules pour compatibilité
from .paths import get_path
# CORRECTION : On ne charge plus UnifiedLogger ni setup_logging d'ici car ils sont gérés ailleurs
from .logs import get_logger
from .settings import (
    load_app_settings, save_app_settings, 
    get_default_settings, APP_SETTINGS,
    SETTINGS_FILE, HISTORY_FILE, OLD_HISTORY_FILE, ACTION_LOG_FILE, SYNTHESIS_FILE, CONTEXT_FILE, KEY_STATUS_FILE,
    SECONDARY_HISTORY_FILE, SECONDARY_OLD_HISTORY_FILE, SECONDARY_ACTION_LOG_FILE, SECONDARY_SYNTHESIS_FILE, SECONDARY_CONTEXT_FILE,
    ROADMAP_FILE, FULL_ROADMAP_FILE, ROADMAP_BACKUP_DIR,
    KB_DATABASE_FILE, KB_DRIVE_FOLDER_NAME, KB_DRIVE_FILE_ID_CACHE, KB_ZIP_NAME,
    SECONDARY_KB_DATABASE_FILE, SECONDARY_KB_DRIVE_FOLDER_NAME, SECONDARY_KB_DRIVE_FILE_ID_CACHE,
    GDRIVE_SCOPES, GDRIVE_TOKEN_FILE, GDRIVE_CREDS_FILE,
    APP_TO_BACKUP, BACKUP_DIR, BACKUP_INTERVAL_MINUTES, MAX_BACKUPS_TO_KEEP,
    MAX_SEARCH_RESULTS, API_COOLDOWN_SECONDS,
    charger_json_robuste, sauvegarder_json, 
    charger_historique_robuste_worker, sauvegarder_historique_worker,
    charger_liens_contexte_worker, sauvegarder_liens_contexte_worker
)
from .constants import SUPPORTED_FILE_EXTENSIONS

# Variables dérivées
MAX_HISTORY = APP_SETTINGS.get("system_settings", {}).get("max_history_retention", 500)
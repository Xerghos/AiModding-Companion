from .paths import get_path

# --- TYPES DE FICHIERS SUPPORTÉS ---
SUPPORTED_FILE_EXTENSIONS = (
    ".lua", ".xml", ".txt", ".json", ".md", ".py", 
    ".js", ".html", ".css", ".ini", ".log", ".java", ".cpp", ".h", ".cs", ".ts"
)

# --- NOMS DE FICHIERS ---
SETTINGS_FILE = "app_settings.json"
HISTORY_FILE = "prompt_history.json"
ACTION_LOG_FILE = "action_log.json"
CONTEXT_FILE = "context_links.json"

# --- CONSTANTES GDRIVE & RAG ---
GDRIVE_SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets.readonly']
GDRIVE_TOKEN_FILE = 'gdrive_token.json'
GDRIVE_CREDS_FILE = 'credentials.json'

KB_DATABASE_FILE = "db/knowledge_base_hybrid" 
KB_DRIVE_FOLDER_NAME = "Gemini_Assistant_Knowledge_Base" 
KB_DRIVE_FILE_ID_CACHE = "kb_drive_file_id.json"
KB_ZIP_NAME = "hybrid_db_archive.zip"

# --- BACKUPS & SYSTEME ---
APP_TO_BACKUP = get_path(".")
BACKUP_DIR = get_path("backups")
ROADMAP_BACKUP_DIR = get_path("backups/roadmaps") 
BACKUP_INTERVAL_MINUTES = 30
MAX_BACKUPS_TO_KEEP = 40

# --- PROJET & ROADMAP ---
ROADMAP_FILE = "roadmap.md"
FULL_ROADMAP_FILE = "full_detailled_roadmap.md"

# --- DIVERS ---
MAX_RAW_DISPLAY = 30
MAX_SEARCH_RESULTS = 5 
MAX_HISTORY = 30 

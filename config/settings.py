import os
import json
import logging
from pathlib import Path

# --- CONSTANTES GLOBALES (DÉFAUTS) ---
PERMISSIVE_SAFETY_SETTINGS = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    }
]
DEFAULT_SETTINGS = {
    "safety_settings": PERMISSIVE_SAFETY_SETTINGS,
    "api_keys": {
        "google_gemini": "",
        "deepseek": "",  # [NOUVEAU] Clé pour l'Architecte et le Coder V3.2
        "openai": "",
        "anthropic": "",
        "mistral": "",
        "groq": "",
        "openrouter": "",
        "huggingface": ""
    },
    "ai_engine": {
        "provider": "google_gemini",
        "model": "gemini-2.5-flash",
        "temperature": 0.7,
        "max_tokens": 8192,
        "available_models": [],
        "cloud_models_registry": {
            # --- PROFILS GÉNÉRIQUES ---
            "fast": "gemini-2.5-flash", 
            "compressor": "gemini-2.5-flash-lite",
            
            # --- PROFILS INTELLIGENTS (Mise à jour DeepSeek) ---
            "smart": "DeepSeek-V3.2",           # Le "Daily Driver" GPT-5 level
            "coder": "DeepSeek-V3.2",           # Supporte le "Thinking in Tool-Use"
            "architect": "DeepSeek-V3.2-Speciale", # Raisonnement pur (API Only, pas d'outils)
            "reasoning": "DeepSeek-V3.2-Speciale", # Alias pour le mode réflexion intense
            
            # --- BACKUPS (Au cas où) ---
            "legacy_smart": "gemini-2.5-pro",
            "creative": "gemini-2.5-flash"
        }
    },
    "repo_map_cache": {
        "ttl_seconds": 300,  # 5 minutes par défaut
        "watch_directories": ["features/", "ai_core/", "worker/"],
        "watch_files": ["config/architecture_map.json"]
    },
    "security": {
        "enable_sanity_check": True,
        "block_outside_project": True,
        "protected_directories": [
            ".git", 
            ".vscode", 
            "__pycache__", 
            "venv", 
            "env",
            "logs"
        ],
        "protected_files": [
            "config/settings.py", 
            "config/keys.py",
            "Agents/agent_personas.py"
        ]
    },
    "system_settings": {
        "theme": "Dark",
        "font_size": 12,
        "scroll_speed": 4,
        "scroll_modifier_key": "Alt_L",
        "scroll_modifier_multiplier": 4,
        "auto_backup": True,
        "backup_interval": 30,
        "max_backups": 10,
        "rag_enabled": True,
        "use_onnx_acceleration": False,
        "rag_database_path": "db/knowledge_base_hybrid",
        "max_history_retention": 50
    },
    "database_settings": {
        "indexing_queue_size": 1000,
        "inference_batch_size": 64
    },
    "general_settings": {
        "chat_pool_size": 4, 
        "secondary_chat_pool_size": 1, 
        "api_cooldown_seconds": 60.0, 
        "audit_interval_seconds": 0.1
    },
    "cli_bridge": {
        "enabled": False,
        "models": [],
        # Nombre d’échanges (user+assistant) à inclure dans le prompt CLI
        "max_history_turns": 3,
        # Limites (en caractères) pour éviter les plafonds Windows/CLI
        "prompt_limits": {
            "total": 24000,
            "arch": 7000,
            "tree": 7000,
            "ltm": 4000,
            "rag": 8000,
            "history": 6000,
            "message": 6000
        },
        # Isolation du CLI: neutralise GEMINI.md et remplace le system prompt du CLI
        "isolation": {
            "enabled": True,
            # Force le CLI à ne charger aucun fichier de contexte (GEMINI.md)
            "context_file_name": "__AIMODDING_DISABLED__.md",
            "discovery_max_dir": 1
        },
        # Options additionnelles pour le system.md injecté dans le CLI
        "system_md": {
            "extra": ""
        }
    },
    "agents_config": {
        "react_max_steps_cloud": 15,
        "active_agents": ["coder", "architect", "documenter"]
    },
    "swarm_settings": {
        "mode": "hierarchical",
        "autonomy_level": "supervised",
        "role_mapping": {
            # [MISE A JOUR STRATÉGIQUE]
            "manager": "smart",        # Utilise DeepSeek-V3.2
            "coder": "coder",          # Utilise DeepSeek-V3.2 (avec Outils)
            "architect": "architect",  # Utilise DeepSeek-V3.2-Speciale (Planification pure)
            "reviewer": "smart",       # Utilise DeepSeek-V3.2
            "writer": "creative",      # Reste sur Gemini Flash (rapide & pas cher)
            "compressor": "compressor" # Reste sur Gemini Flash Lite
        },
        "max_auto_loop": 5,
    },
    "key_bindings": {
        "send_message": "<Return>",
        "new_line": "<Shift-Return>",
        "toggle_sidebar": "<Control-b>",
        "focus_input": "<Control-l>",
        "close_tab": "<Control-w>",
        "next_tab": "<Control-Tab>"
    },
    "logging_channels": {
        "SYSTEM": True,
        "WORKER": True,
        "MEMORY": False,
        "DATABASE": False,
        "SETTINGS": False,
        "NETWORK": True,
        "UI": False,
        "FILES": True,
        "AUDIO": False,
        "SYMBOL_GRAPH": False
    },
    "automation": {
        "arch_update_interval": 900,
        "auto_backup_interval": 3600
    },
    "migration_flags": {
        "use_litellm": False  # Phase 1 : Activer LiteLLM (Proxy Universel)
    },
}

# --- FICHIERS DE CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(BASE_DIR, "app_settings.json")

# Chemins des données
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
OLD_HISTORY_FILE = os.path.join(BASE_DIR, "old_history.json")
ACTION_LOG_FILE = os.path.join(BASE_DIR, "action_log.json")
SYNTHESIS_FILE = os.path.join(BASE_DIR, "synthesis_log.md")
CONTEXT_FILE = os.path.join(BASE_DIR, "project_context.json")
KEY_STATUS_FILE = os.path.join(BASE_DIR, "key_status.json")
TOKEN_USAGE_FILE = os.path.join(BASE_DIR, "token_usage.json")

# Chemins Secondaires
SECONDARY_HISTORY_FILE = os.path.join(BASE_DIR, "secondary_history.json")
SECONDARY_OLD_HISTORY_FILE = os.path.join(BASE_DIR, "secondary_old_history.json")
SECONDARY_ACTION_LOG_FILE = os.path.join(BASE_DIR, "secondary_action_log.json")
SECONDARY_SYNTHESIS_FILE = os.path.join(BASE_DIR, "secondary_synthesis_log.md")
SECONDARY_CONTEXT_FILE = os.path.join(BASE_DIR, "secondary_project_context.json")

# Chemins Roadmap
ROADMAP_FILE = os.path.join(BASE_DIR, "roadmap.md")
FULL_ROADMAP_FILE = os.path.join(BASE_DIR, "ROADMAP_COMPLETE.md")
ROADMAP_BACKUP_DIR = os.path.join(BASE_DIR, "roadmap_backups")

# Chemins RAG / Drive
KB_DATABASE_FILE = "knowledge_base.json"
KB_DRIVE_FOLDER_NAME = "AiModding_KnowledgeBase"
KB_DRIVE_FILE_ID_CACHE = "drive_folder_id.txt"
KB_ZIP_NAME = "knowledge_base.zip"

SECONDARY_KB_DATABASE_FILE = "secondary_knowledge_base.json"
SECONDARY_KB_DRIVE_FOLDER_NAME = "AiModding_KnowledgeBase_Secondary"
SECONDARY_KB_DRIVE_FILE_ID_CACHE = "secondary_drive_folder_id.txt"

# Chemins Google Drive Auth
GDRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.file']
GDRIVE_TOKEN_FILE = 'token.json'
GDRIVE_CREDS_FILE = 'credentials.json'

# --- CONSTANTES OPÉRATIONNELLES ---
APP_TO_BACKUP = BASE_DIR
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
BACKUP_INTERVAL_MINUTES = 30
MAX_BACKUPS_TO_KEEP = 10
MAX_SEARCH_RESULTS = 5

# --- Variables Globales Modifiables ---
API_COOLDOWN_SECONDS = 60.0
AUDIT_INTERVAL_SECONDS = 0.1

# --- FONCTIONS DE GESTION ---

def load_app_settings():
    global API_COOLDOWN_SECONDS, AUDIT_INTERVAL_SECONDS
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                merged = DEFAULT_SETTINGS.copy()
                
                for section, content in saved.items():
                    if section in merged and isinstance(content, dict):
                        merged[section].update(content)
                    else:
                        merged[section] = content
                
                # Conversion liste -> dict pour les clés
                if "api_keys_list" in saved:
                    gemini_keys = []
                    deepseek_keys = []
                    
                    for item in saved["api_keys_list"]:
                        prov = item.get("provider")
                        key = item.get("key")
                        if prov == "gemini": gemini_keys.append(key)
                        elif prov == "deepseek": deepseek_keys.append(key) # Support DeepSeek
                        
                    if gemini_keys:
                        merged["api_keys"]["google_gemini"] = ",".join(gemini_keys)
                    if deepseek_keys:
                        merged["api_keys"]["deepseek"] = ",".join(deepseek_keys)

                # Mise à jour des globales
                gen_settings = merged.get("general_settings", {})
                API_COOLDOWN_SECONDS = gen_settings.get("api_cooldown_seconds", 60.0)
                AUDIT_INTERVAL_SECONDS = gen_settings.get("audit_interval_seconds", 0.1)

                return merged
        except Exception as e:
            print(f"⚠️ Erreur lecture {SETTINGS_FILE} : {e}")
            return DEFAULT_SETTINGS.copy()
    else:
        save_app_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

def save_app_settings(new_settings=None):
    data_to_save = new_settings if new_settings else APP_SETTINGS
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Erreur sauvegarde settings : {e}")
        return False

def reload_app_settings():
    global APP_SETTINGS
    new_settings = load_app_settings()
    APP_SETTINGS.clear()
    APP_SETTINGS.update(new_settings)
    return APP_SETTINGS

def get_default_settings():
    return DEFAULT_SETTINGS.copy()

# --- INITIALISATION ---
APP_SETTINGS = load_app_settings()

# --- HELPERS JSON ---
def charger_json_robuste(chemin, default=None):
    if default is None: default = {}
    if not os.path.exists(chemin): return default
    try:
        with open(chemin, 'r', encoding='utf-8') as f: return json.load(f)
    except: return default

def sauvegarder_json(chemin, data):
    try:
        with open(chemin, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except: return False

def charger_historique_robuste_worker(fp): return charger_json_robuste(fp, [])
def sauvegarder_historique_worker(fp, h): return sauvegarder_json(fp, h)
def charger_liens_contexte_worker(fp): return charger_json_robuste(fp, {})
def sauvegarder_liens_contexte_worker(fp, l): return sauvegarder_json(fp, l)

# --- LOGGING ---
LOGGING_CHANNELS = APP_SETTINGS.get("logging_channels", DEFAULT_SETTINGS["logging_channels"])

LOG_SOURCE_MAP = {
    "factory": "SYSTEM", "core": "SYSTEM", "run": "SYSTEM", "settings": "SETTINGS", "config": "SYSTEM",
    "features.UnifiedLogger": "SYSTEM",
    "worker.core": "WORKER", "swarm_manager": "WORKER", "agent_personas": "WORKER", "Worker": "WORKER",
    "SemanticMemory": "MEMORY", "features.context": "MEMORY", "features.context.symbol_graph": "SYMBOL_GRAPH", "database": "DATABASE", "rag": "MEMORY",
    "features.SemanticMemory": "MEMORY", "features.context.database": "DATABASE", "sqlite": "DATABASE",
    "symbol_graph": "SYMBOL_GRAPH",
    "github": "NETWORK", "keys": "NETWORK", "ai_core.keys": "NETWORK", "google_api": "NETWORK",
    "main_window": "UI", "widgets": "UI", "syntax": "UI", "explorer": "UI", "ui.main_window": "UI",
    "BackupManager": "FILES", "ProjectManager": "FILES", "FileSystem": "FILES", "core_backup": "FILES",
    "audio": "AUDIO", "features.audio": "AUDIO"
}
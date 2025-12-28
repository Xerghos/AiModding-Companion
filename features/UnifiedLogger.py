import os
import json
import datetime
import threading
import glob
import sys
import ctypes

# --- CONFIGURATION DU DOSSIER LOGS ---
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# [MODIF] Horodatage de démarrage de l'application (lazy initialization)
# Le timestamp est généré lors de la première écriture et reste constant pour toute la session
# Si un fichier de log récent existe (créé dans les 5 dernières minutes), il est réutilisé
# Format : Jour-Mois_Heure-Minute-Seconde pour identifier la session
_app_start_ts = None
LOG_FILE = None

def _get_or_create_log_file():
    """
    Récupère le fichier de log existant (s'il est récent) ou en crée un nouveau.
    Le timestamp est généré lors de la première écriture et reste constant.
    """
    global _app_start_ts, LOG_FILE
    
    if LOG_FILE is not None and os.path.exists(LOG_FILE):
        # Le fichier existe déjà, le réutiliser
        return LOG_FILE
    
    # Chercher un fichier de log récent (créé dans les 5 dernières minutes)
    log_pattern = os.path.join(LOG_DIR, "global_debug_*.log")
    existing_files = glob.glob(log_pattern)
    
    if existing_files:
        # Trier par date de modification (plus récent en premier)
        existing_files.sort(key=os.path.getmtime, reverse=True)
        
        # Vérifier si le fichier le plus récent a été créé dans les 5 dernières minutes
        most_recent = existing_files[0]
        file_mtime = os.path.getmtime(most_recent)
        time_diff = datetime.datetime.now().timestamp() - file_mtime
        
        if time_diff < 300:  # 5 minutes = 300 secondes
            # Réutiliser le fichier existant
            LOG_FILE = most_recent
            # Extraire le timestamp du nom de fichier
            filename = os.path.basename(most_recent)
            # Format: global_debug_26-Dec_23h11_39.log
            if "_" in filename:
                parts = filename.replace("global_debug_", "").replace(".log", "").split("_")
                if len(parts) >= 3:
                    _app_start_ts = "_".join(parts[:3])  # 26-Dec_23h11_39
            return LOG_FILE
    
    # Créer un nouveau fichier avec un nouveau timestamp
    _app_start_ts = datetime.datetime.now().strftime("%d-%b_%Hh%M_%S")
    LOG_FILE = os.path.join(LOG_DIR, f"global_debug_{_app_start_ts}.log")
    return LOG_FILE

LOCK = threading.Lock()

# --- [AJOUT] FONCTION NETTOYAGE (RETENTION DYNAMIQUE) ---
def _clean_old_logs():
    """
    Supprime les anciens fichiers de logs pour respecter la limite définie.
    Récupère 'log_retention_count' dans system_settings (Défaut: 10).
    """
    try:
        # Import local pour éviter les imports circulaires
        try:
            from config.settings import APP_SETTINGS
            # On cherche dans system_settings, sinon défaut 10
            max_files = APP_SETTINGS.get("system_settings", {}).get("log_retention_count", 10)
        except ImportError:
            max_files = 10

        # Récupération des logs debug
        log_pattern = os.path.join(LOG_DIR, "global_debug_*.log")
        files = glob.glob(log_pattern)
        
        # Si on dépasse la limite
        if len(files) >= max_files:
            # Tri par date de modification (le plus vieux en premier)
            files.sort(key=os.path.getmtime)
            
            # On garde (max_files - 1) places pour le fichier actuel
            nb_to_delete = len(files) - (max_files - 1)
            
            if nb_to_delete > 0:
                for f in files[:nb_to_delete]:
                    try:
                        os.remove(f)
                    except OSError:
                        pass
    except Exception as e:
        print(f"⚠️ Erreur nettoyage logs: {e}")

# Exécution du nettoyage au chargement du module
_clean_old_logs()

# --- ACTIVATION FORCEE DES COULEURS WINDOWS ---
def enable_windows_ansi():
    if os.name == 'nt':
        try:
            kernel32 = ctypes.windll.kernel32
            hOut = kernel32.GetStdHandle(-11)
            out_mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(hOut, ctypes.byref(out_mode))
            new_mode = out_mode.value | 0x0004
            kernel32.SetConsoleMode(hOut, new_mode)
        except Exception: pass 

enable_windows_ansi()

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GRAY = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"

class UnifiedLogger:
    """
    Logger Centralisé Hybride (V3 - Metrics Beautifier).
    """

    @staticmethod
    def write(source, msg_type, message, data=None):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        timestamp_full = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Vérification si le canal est activé (même logique que pour le terminal)
        should_log = True
        is_important = msg_type in ["ERROR", "CRITICAL", "BAN", "WARNING", "FAIL", "METRICS"]
        
        if not is_important:
            try:
                from config.settings import LOGGING_CHANNELS, LOG_SOURCE_MAP
                clean_source = source.split(".")[-1]
                channel = LOG_SOURCE_MAP.get(source) or LOG_SOURCE_MAP.get(clean_source) or "SYSTEM"
                
                if not LOGGING_CHANNELS.get(channel, True):
                    should_log = False
            except ImportError:
                should_log = True
        
        # 1. ÉCRITURE FICHIER (Complet & Technique) - seulement si le canal est activé
        if should_log:
            log_entry = f"[{timestamp}] [{threading.current_thread().name:<15}] [{source:<15}] [{msg_type:<10}] {message}"
            if data:
                try:
                    if isinstance(data, str):
                        log_entry += f"\nData: {data}"
                    else:
                        safe_data = json.dumps(data, default=str, indent=2)
                        log_entry += f"\n{safe_data}"
                except:
                    log_entry += f"\n[Data Error]: {str(data)[:100]}"
            
            log_entry += "\n" + "-"*80 + "\n"

            with LOCK:
                try:
                    log_file_path = _get_or_create_log_file()
                    with open(log_file_path, "a", encoding="utf-8") as f:
                        f.write(log_entry)
                except: pass

        # 2. AFFICHAGE TERMINAL (Design & Metrics)
        UnifiedLogger._print_beautified(timestamp, source, msg_type, message, data)

    @staticmethod
    def _print_beautified(timestamp, source, msg_type, message, data):
        # --- A. FILTRAGE ---
        should_print = True
        is_important = msg_type in ["ERROR", "CRITICAL", "BAN", "WARNING", "FAIL", "METRICS"] 

        if not is_important:
            try:
                from config.settings import LOGGING_CHANNELS, LOG_SOURCE_MAP
                clean_source = source.split(".")[-1]
                channel = LOG_SOURCE_MAP.get(source) or LOG_SOURCE_MAP.get(clean_source) or "SYSTEM"
                
                if not LOGGING_CHANNELS.get(channel, True):
                    should_print = False
            except ImportError:
                should_print = True

        if not should_print: return

        # --- B. STYLES & ICONES ---
        type_styles = {
            "START":      (Colors.CYAN,  "🚀"),
            "SUCCESS":    (Colors.GREEN, "✅"),
            "ERROR":      (Colors.RED,   "❌"),
            "WARNING":    (Colors.YELLOW,"⚠️ "),
            "INFO":       (Colors.BLUE,  "ℹ️ "),
            "CRITICAL":   (Colors.BG_RED + Colors.WHITE, "🔥"),
            "AUDIT_START":(Colors.MAGENTA,"🕵️"),
            "AUDIT_END":  (Colors.MAGENTA,"🏁"),
            "METRICS":    (Colors.CYAN,  "📊"), 
            "BAN":        (Colors.RED,   "🚫"),
            "QUOTA":      (Colors.YELLOW,"⏳"),
            "CACHE_HIT":  (Colors.GREEN, "⚡"),
            "CACHE_MISS": (Colors.YELLOW,"📉")
        }

        color, icon = type_styles.get(msg_type, (Colors.WHITE, "🔹"))

        # --- C. PRE-TRAITEMENT MESSAGE ---
        if "[" in message and "]" in message:
            parts = message.split("] ", 1)
            if len(parts) == 2:
                message = f"{Colors.DIM}{parts[0]}]{Colors.RESET} {parts[1]}"
        
        # --- D. TRAITEMENT SPECIAL METRICS ---
        if msg_type == "METRICS" and isinstance(data, dict):
            # 1. Extraction Identité (Provider / Model / Agent)
            raw_prov = data.get("provider", "AI")
            provider = raw_prov.replace("google_", "").replace("_", " ").title()
            
            p_icons = {"Gemini": "✨", "Groq": "⚡", "Openai": "🧠", "Deepseek": "🐳"}
            p_icon = p_icons.get(provider, "🤖")
            
            # 1. Récupération distincte
            agent = data.get("agent", "Unknown")
            model = data.get("model", "Unknown")

            # 2. Normalisation affichage agent / modèle
            agent_display = None
            if agent and agent != "Unknown":
                # On force un affichage en MAJUSCULE pour bien distinguer le rôle / profil
                agent_display = str(agent).upper()

            model_display = model if model and model != "Unknown" else "Unknown-model"
           
            # 3. Construction Ligne Principale (Résumé)
            
            # -> Cas CACHE (DeepSeek / Gemini Caching)
            if "billed" in data or "cache_hit" in data:
                hit = int(data.get("cache_hit", 0))
                billed = int(data.get("billed", 0) or data.get("cache_miss", 0))
                total = hit + billed
                savings = int((hit / total * 100)) if total > 0 else 0
                
                # Format cible:
                # ✨ Gemini │ COMPRESSOR │ Gemini-2.5-flash-lite │ Miss / Hit / Éco
                base = f"{p_icon} {provider:<8} │ "
                if agent_display:
                    base += f"{Colors.BOLD}{agent_display:<12}{Colors.RESET} │ {model_display:<22}"
                else:
                    # Si pas d'agent explicite, on n'affiche que le modèle
                    base += f"{Colors.BOLD}{model_display:<12}{Colors.RESET}"

                message = (
                    f"{base} │ "
                    f"{Colors.YELLOW}Miss: {billed:<5}{Colors.RESET} │ "
                    f"{Colors.GREEN}Hit: {hit:<5}{Colors.RESET} │ "
                    f"💲 Payés: {Colors.CYAN}{billed}{Colors.RESET} "
                    f"(Éco: {Colors.BOLD}{savings}%{Colors.RESET})"
                )
            
            # -> Cas STANDARD (Gemini Flash/Pro sans cache explicite)
            else:
                # Format cible:
                # ✨ Gemini │ COMPRESSOR │ Gemini-2.5-flash-lite
                if agent_display:
                    message = (
                        f"{p_icon} {provider:<8} │ "
                        f"{Colors.BOLD}{agent_display:<12}{Colors.RESET} │ "
                        f"{model_display}"
                    )
                else:
                    # Pas d'agent : on garde un format compact
                    message = f"{p_icon} {provider:<8} │ {Colors.BOLD}{model_display}{Colors.RESET}"

        # --- E. AFFICHAGE PRINCIPAL (Ligne 1) ---
        src_display = source.split(".")[-1][:12]
        line = f"{Colors.DIM}{timestamp}{Colors.RESET} │ {Colors.BOLD}{src_display:<12}{Colors.RESET} │ {color}{icon} {msg_type:<10}{Colors.RESET} │ {message}"
        
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode('ascii', 'ignore').decode('ascii'))

        # --- F. AFFICHAGE ARBORESCENCE (Ligne 2+) ---
        if data:
            # 1. METRICS : Détails Techniques (In/Out/Time)
            if msg_type == "METRICS" and isinstance(data, dict):
                parts = []
                if "in" in data:
                    parts.append(f"📥 {Colors.CYAN}{data['in']}{Colors.RESET} in")
                if "out" in data:
                    parts.append(f"📤 {Colors.GREEN}{data['out']}{Colors.RESET} out")
                if "time" in data:
                    parts.append(f"⏱️ {data['time']}")
                
                if parts:
                    metrics_line = " | ".join(parts)
                    try:
                        print(f"                 │ {Colors.DIM}└──{Colors.RESET} {metrics_line}")
                    except UnicodeEncodeError:
                        # Remplacer les caractères Unicode par des équivalents ASCII
                        safe_line = metrics_line.replace("📥", "[IN]").replace("📤", "[OUT]").replace("⏱️", "[TIME]")
                        safe_line = safe_line.replace("│", "|").replace("└──", "+--")
                        print(f"                 | {Colors.DIM}+--{Colors.RESET} {safe_line}")

            # 2. ERREUR : Texte Rouge
            elif msg_type in ["ERROR", "WARNING", "CRITICAL"]:
                err = str(data.get('error', data))
                try:
                    print(f"                 │ {Colors.RED}└── 💥 {err[:200]}...{Colors.RESET}")
                except UnicodeEncodeError:
                    # Remplacer les caractères Unicode par des équivalents ASCII
                    safe_err = err[:200].encode('ascii', 'ignore').decode('ascii')
                    print(f"                 | {Colors.RED}+-- [!] {safe_err}...{Colors.RESET}")

            # 3. RESULTAT : Résumé
            elif "result_summary" in data and str(data["result_summary"]) != "None":
                smry = str(data["result_summary"])
                if len(smry) > 5:
                    try:
                        print(f"                 │ {Colors.GREEN}└── 📄 {smry[:100]}...{Colors.RESET}")
                    except UnicodeEncodeError:
                        # Remplacer les caractères Unicode par des équivalents ASCII
                        safe_smry = smry[:100].encode('ascii', 'ignore').decode('ascii')
                        print(f"                 | {Colors.GREEN}+-- [FILE] {safe_smry}...{Colors.RESET}")
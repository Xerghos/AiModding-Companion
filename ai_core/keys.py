import time
import json
import os
import threading
import random
import keyring  # pip install keyring
import requests
import base64
from cryptography.fernet import Fernet # pip install cryptography

from config.settings import APP_SETTINGS, KEY_STATUS_FILE, save_app_settings
# On déduit le chemin du fichier secrets par rapport au fichier stats existant
SECRETS_FILE = os.path.join(os.path.dirname(KEY_STATUS_FILE), "secrets.enc")

from features.UnifiedLogger import UnifiedLogger

# Constantes de gestion
SERVICE_ID = "AiModding_Companion"  # Identifiant Keyring
KEK_NAME = "MasterKey_KEK"          # Nom de la clé maîtresse dans le Keyring
INIT_HEALTH = 100.0
RECOVERY_RATE = 5.0
COST_SUCCESS = 0.1
COST_ERROR_QUOTA = 100.0
COST_ERROR_OTHER = 20.0

class KeyStats:
    def __init__(self, key, provider, alias=None):
        self.key = key
        # Short ID unique pour lier les stats sans révéler la clé
        self.short_id = key.strip()[-6:] if len(key) > 6 else key
        self.provider = provider
        self.alias = alias or f"{provider.capitalize()} ({self.short_id})"
        
        self.health = INIT_HEALTH
        self.last_used = 0
        self.cooldown_until = 0
        self.usage_count = 0
        self.errors = 0

    def to_dict(self):
        """Export pour l'UI (sans la clé complète si possible, ou juste pour info)"""
        return {
            "alias": self.alias,
            "short_id": self.short_id,
            "provider": self.provider,
            "health": self.health,
            "last_used": self.last_used,
            "cooldown_until": self.cooldown_until,
            "usage_count": self.usage_count,
            "errors": self.errors
        }

    def from_dict_stats(self, data):
        """Restaure uniquement les métriques de santé."""
        self.health = data.get("health", INIT_HEALTH)
        self.last_used = data.get("last_used", 0)
        self.cooldown_until = data.get("cooldown_until", 0)
        self.usage_count = data.get("usage_count", 0)
        self.errors = data.get("errors", 0)

class KeyManager:
    def __init__(self):
        self.keys = {}  # {key_str: KeyStats}
        self.lock = threading.Lock()
        self.fernet = None # Instance de chiffrement

        # Mapping pour rotation
        self.model_provider_map = {
            "gemini": "google_gemini", "flash": "google_gemini", "pro": "google_gemini",
            "learnlm": "google_gemini", "groq": "groq", "llama": "groq", 
            "mixtral": "groq", "gemma": "groq", "deepseek": "deepseek"
        }

        # 1. INITIALISATION CRYPTO (Envelope Encryption)
        self._init_crypto_engine()

        # 2. CHARGEMENT DU COFFRE (Secrets chiffrés)
        self._load_encrypted_vault()

        # 3. MIGRATION & NETTOYAGE (Import legacy settings/keyring)
        self._migrate_legacy_sources()
        
        # 4. RESTAURATION STATS (Santé)
        self._load_stats_state()

    # --- PARTIE 1 : MOTEUR CRYPTO (ENVELOPE) ---

    def _init_crypto_engine(self):
        """
        Récupère ou Crée la Clé Maîtresse (KEK) dans le Windows Credential Manager.
        """
        try:
            # Tente de lire la KEK existante
            kek_b64 = keyring.get_password(SERVICE_ID, KEK_NAME)
            
            if not kek_b64:
                # Création nouvelle KEK (32 bytes url-safe base64)
                UnifiedLogger.write("KEY_MGR", "SETUP", "Génération nouvelle MasterKey (KEK)...")
                key = Fernet.generate_key() # returns bytes
                kek_b64 = key.decode('utf-8')
                keyring.set_password(SERVICE_ID, KEK_NAME, kek_b64)
            
            self.fernet = Fernet(kek_b64.encode('utf-8'))
            UnifiedLogger.write("KEY_MGR", "SECURE", "Moteur Crypto initialisé avec succès.")
            
        except Exception as e:
            UnifiedLogger.write("KEY_MGR", "CRITICAL", f"Echec init crypto: {e}")
            # Mode dégradé (lecture seule impossible, crash probable si on continue)
            raise RuntimeError(f"Impossible d'accéder au Keyring pour la KEK: {e}")

    def _save_encrypted_vault(self):
        """
        Sérialise self.keys (secrets + métadonnées) -> JSON -> Chiffrement -> Disque.
        """
        try:
            # On ne stocke que le nécessaire pour reconstruire l'objet (Secret, Provider, Alias)
            # Les stats de santé vont dans un autre fichier (KEY_STATUS_FILE)
            vault_data = {}
            for k, stats in self.keys.items():
                vault_data[k] = {
                    "provider": stats.provider,
                    "alias": stats.alias
                }
            
            json_bytes = json.dumps(vault_data).encode('utf-8')
            encrypted_data = self.fernet.encrypt(json_bytes)
            
            with open(SECRETS_FILE, 'wb') as f:
                f.write(encrypted_data)
                
        except Exception as e:
            UnifiedLogger.write("KEY_MGR", "ERROR", f"Echec sauvegarde coffre chiffré: {e}")

    def _load_encrypted_vault(self):
        """
        Lit Disque -> Déchiffrement -> JSON -> Peuple self.keys.
        """
        if not os.path.exists(SECRETS_FILE):
            UnifiedLogger.write("KEY_MGR", "INFO", "Aucun coffre chiffré trouvé (Premier lancement ?).")
            return

        try:
            with open(SECRETS_FILE, 'rb') as f:
                encrypted_data = f.read()
            
            if not encrypted_data: return

            decrypted_bytes = self.fernet.decrypt(encrypted_data)
            vault_data = json.loads(decrypted_bytes.decode('utf-8'))
            
            count = 0
            for k, meta in vault_data.items():
                if k not in self.keys:
                    self.keys[k] = KeyStats(k, meta.get("provider", "unknown"), meta.get("alias"))
                    count += 1
            
            UnifiedLogger.write("KEY_MGR", "INIT", f"{count} secrets déchiffrés et chargés en mémoire.")

        except Exception as e:
            UnifiedLogger.write("KEY_MGR", "CRITICAL", f"Echec ouverture coffre (Clé invalide ou fichier corrompu): {e}")

    # --- PARTIE 2 : MIGRATION (LEGACY -> ENVELOPE) ---

    def _migrate_legacy_sources(self):
        """
        Aspire les clés depuis settings.json ET les anciennes entrées Keyring individuelles.
        Sauvegarde dans le coffre chiffré, puis supprime les sources non sécurisées.
        """
        api_conf = APP_SETTINGS.get("api_keys", {})
        dirty = False
        migrated_total = 0
        
        known_providers = ["google_gemini", "groq", "openai", "mistral", "deepseek"]

        # A. Migration depuis settings.json (Texte Clair)
        for provider in known_providers:
            keys_in_clear = api_conf.get(provider, "")
            if keys_in_clear and len(str(keys_in_clear).strip()) > 5:
                # Parsing
                key_list = []
                if isinstance(keys_in_clear, list): key_list = keys_in_clear
                else: key_list = [k.strip() for k in keys_in_clear.split(',') if k.strip()]
                
                for idx, k in enumerate(key_list):
                    if k not in self.keys:
                        # Génération Alias
                        short = k[-6:]
                        # On regarde si un alias existait dans les settings globaux
                        existing_alias_map = APP_SETTINGS.get("key_aliases", {})
                        alias = existing_alias_map.get(short, f"Clé {provider.capitalize()} {idx+1} (Import)")
                        
                        self.keys[k] = KeyStats(k, provider, alias)
                        dirty = True
                        migrated_total += 1
                
                # Nettoyage source
                api_conf[provider] = ""

        # B. Migration depuis Keyring "Legacy" (Si l'utilisateur a utilisé la version précédente qui crashait)
        # On vérifie si des entrées existent pour les providers
        for provider in known_providers:
            try:
                legacy_content = keyring.get_password(SERVICE_ID, provider)
                if legacy_content:
                    # C'est une ancienne entrée (CSV de clés)
                    raw_keys = [k.strip() for k in legacy_content.split(',') if k.strip()]
                    for k in raw_keys:
                        if k not in self.keys:
                            self.keys[k] = KeyStats(k, provider, f"{provider.capitalize()} (Legacy Ring)")
                            dirty = True
                            migrated_total += 1
                    
                    # Suppression de l'entrée Keyring obsolète (On ne garde que la MasterKey maintenant)
                    keyring.delete_password(SERVICE_ID, provider)
                    UnifiedLogger.write("KEY_MGR", "CLEAN", f"Entrée Keyring legacy '{provider}' supprimée.")
            except: pass # Pas d'entrée ou erreur access, on ignore

        if dirty:
            self._save_encrypted_vault() # Sauvegarde dans le nouveau coffre .enc
            
            # Sauvegarde Settings (pour valider le nettoyage des champs texte clair)
            try:
                save_app_settings(APP_SETTINGS)
                UnifiedLogger.write("KEY_MGR", "MIGRATION", f"Migration terminée : {migrated_total} clés sécurisées dans secrets.enc")
            except Exception as e:
                UnifiedLogger.write("KEY_MGR", "ERROR", f"Erreur save settings post-migration: {e}")

    # --- PARTIE 3 : GESTION ETAT (STATS) ---

    def _save_stats_state(self):
        """Sauvegarde les stats (Santé/Usage) en utilisant short_id comme index (Pas de leak de clé)."""
        try:
            data = {}
            for k, stats in self.keys.items():
                # On utilise short_id pour ne pas écrire la clé complète dans un fichier JSON clair
                idx = stats.short_id 
                data[idx] = stats.to_dict() # to_dict ne contient pas le secret complet
            
            with open(KEY_STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except: pass

    def _load_stats_state(self):
        """Recharge les stats en faisant le lien via short_id."""
        if not os.path.exists(KEY_STATUS_FILE): return
        try:
            with open(KEY_STATUS_FILE, 'r') as f:
                data = json.load(f)
            
            # On mappe short_id -> KeyStats obj
            map_short_to_obj = {stats.short_id: stats for stats in self.keys.values()}
            
            count = 0
            for short_id, stats_data in data.items():
                if short_id in map_short_to_obj:
                    map_short_to_obj[short_id].from_dict_stats(stats_data)
                    count += 1
                    
        except Exception as e:
            UnifiedLogger.write("KEY_MGR", "WARNING", f"Echec chargement stats: {e}")

    # --- API PUBLIQUE (UI & FACTORY) ---

    def add_key(self, provider, new_key_value, alias_name):
        new_key_value = new_key_value.strip()
        if not new_key_value: return False
        
        with self.lock:
            if new_key_value not in self.keys:
                self.keys[new_key_value] = KeyStats(new_key_value, provider, alias=alias_name)
            else:
                self.keys[new_key_value].alias = alias_name # Update alias
            
            self._save_encrypted_vault()
            UnifiedLogger.write("KEY_MGR", "ADD", f"Nouvelle clé ajoutée au coffre: {alias_name}")
            return True

    def edit_key(self, provider, old_key_value, new_key_value, new_alias):
        with self.lock:
            old_key_value = old_key_value.strip()
            new_key_value = new_key_value.strip()
            
            # Si changement de clé
            if old_key_value != new_key_value:
                if old_key_value in self.keys:
                    del self.keys[old_key_value]
                self.keys[new_key_value] = KeyStats(new_key_value, provider, alias=new_alias)
            else:
                # Juste alias
                if old_key_value in self.keys:
                    self.keys[old_key_value].alias = new_alias
            
            self._save_encrypted_vault()
            UnifiedLogger.write("KEY_MGR", "EDIT", f"Clé éditée: {new_alias}")
            return True

    def delete_key(self, provider, key_value):
        with self.lock:
            if key_value in self.keys:
                del self.keys[key_value]
                self._save_encrypted_vault()
                # On nettoie aussi l'entrée stats si on veut être propre, 
                # mais le _save_stats_state le fera au prochain cycle
                UnifiedLogger.write("KEY_MGR", "DELETE", "Clé supprimée du coffre.")
                return True
            return False

    def get_all_keys_info(self):
        """Retourne la liste pour l'UI."""
        return [s.to_dict() for s in self.keys.values()]

    # --- LOGIQUE ROTATION (INCHANGÉE) ---

    def _get_provider_for_model(self, model_name):
        m = model_name.lower()
        for keyword, provider in self.model_provider_map.items():
            if keyword in m: return provider
        return "google_gemini"

    def get_key(self, model_name, exclude_key=None):
        provider = self._get_provider_for_model(model_name)
        with self.lock:
            now = time.time()
            candidates = []
            for k, stats in self.keys.items():
                if stats.provider != provider: continue
                if k == exclude_key: continue
                if stats.cooldown_until > now: continue 
                
                # Regen
                time_since_use = (now - stats.last_used) / 60.0
                if time_since_use > 5:
                    regain = int(time_since_use * RECOVERY_RATE)
                    stats.health = min(100.0, stats.health + regain)
                candidates.append(stats)

            if not candidates:
                # Mode Survie
                candidates = [s for s in self.keys.values() if s.provider == provider and s.key != exclude_key]
                if not candidates: return None

            candidates.sort(key=lambda s: (s.health, -s.last_used), reverse=True)
            top_n = candidates[:3]
            selected = random.choice(top_n)
            
            selected.last_used = now
            return selected.key

    def report_error(self, key, exception=None, model_name="unknown"):
        """Signale une erreur sur une clé."""
        if not key or key not in self.keys: return
        
        with self.lock:
            stats = self.keys[key]
            err_str = str(exception).lower()
            is_quota = "429" in err_str or "quota" in err_str or "exhausted" in err_str
            
            if is_quota:
                stats.health = 0.0
                stats.cooldown_until = time.time() + 3600
                UnifiedLogger.write("KEY_MGR", "PUNISH", f"Clé {stats.alias} épuisée (429).")
            else:
                stats.health = max(0.0, stats.health - COST_ERROR_OTHER)
            
            stats.errors += 1
            self._save_stats_state()

    def mark_success(self, key, model_name="unknown"):
        if not key or key not in self.keys: return
        with self.lock:
            stats = self.keys[key]
            stats.usage_count += 1
            stats.health = max(0.0, stats.health - COST_SUCCESS)
            if stats.health < 50: stats.health += 1.0
            self._save_stats_state()

    @property
    def num_keys(self): return len(self.keys)

    # --- DISCOVERY TOOLS ---
    def discover_models(self):
        discovered = {"deepseek": [], "groq": [], "gemini": []}
        dk = self.get_key("deepseek")
        if dk:
            models = self._fetch_openai_compatible_models(dk, "https://api.deepseek.com")
            if models: discovered["deepseek"] = models
        gk = self.get_key("groq")
        if gk:
            models = self._fetch_openai_compatible_models(gk, "https://api.groq.com/openai/v1")
            if models: discovered["groq"] = models
        return discovered

    def _fetch_openai_compatible_models(self, api_key, base_url):
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(f"{base_url}/models", headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model["id"] for model in data.get("data", [])]
        except: pass
        return []

# --- WRAPPER MODULE LEVEL ---
def discover_models():
    try:
        mgr = KeyManager()
        return mgr.discover_models()
    except: return {"deepseek": [], "groq": [], "gemini": []}
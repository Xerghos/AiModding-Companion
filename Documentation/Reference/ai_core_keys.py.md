# Documentation Technique du Fichier `ai_core/keys.py`

## 1. En-tête

### Titre
Module de Gestion des Clés API et de leur Santé

### Description concise
Ce module implémente un système robuste de gestion des clés API pour les services d'IA. Il assure le stockage sécurisé des clés via un mécanisme de chiffrement (Envelope Encryption utilisant `keyring` et `cryptography`), la migration transparente depuis des sources moins sécurisées, le suivi de l'état de santé et d'utilisation de chaque clé, ainsi qu'un mécanisme intelligent de rotation et de pénalisation/récupération pour optimiser la fiabilité et la disponibilité des requêtes API.

### Dépendances
*   **Bibliothèques Standard Python**:
    *   `time`: Pour la gestion des timestamps (dernière utilisation, cooldown).
    *   `json`: Pour la sérialisation/désérialisation des données de clés et de statistiques.
    *   `os`: Pour les opérations sur les chemins de fichiers (secrets.enc, key_status.json).
    *   `threading`: Pour la synchronisation des accès aux clés via `threading.Lock`.
    *   `random`: Pour la sélection aléatoire des clés parmi les meilleures candidates.
    *   `requests`: Pour la découverte des modèles auprès des fournisseurs d'API.
*   **Bibliothèques Tierces (`pip install`)**:
    *   `keyring`: Pour le stockage sécurisé de la Clé d'Encryption de Clé (KEK - Master Key) dans le gestionnaire de secrets du système d'exploitation (ex: Windows Credential Manager).
    *   `cryptography.fernet.Fernet`: Pour le chiffrement symétrique des secrets API via une KEK.
*   **Modules Internes**:
    *   `config.settings`: Pour accéder aux paramètres de l'application (`APP_SETTINGS`), aux chemins de fichiers (`KEY_STATUS_FILE`) et pour sauvegarder les paramètres (`save_app_settings`).
    *   `features.UnifiedLogger`: Pour la journalisation unifiée des événements du gestionnaire de clés.

## 2. Classes & Fonctions

### Constantes Globales

*   `SERVICE_ID` (str): `"AiModding_Companion"` - Identifiant utilisé par `keyring` pour grouper les secrets liés à l'application.
*   `KEK_NAME` (str): `"MasterKey_KEK"` - Nom de la Clé Maîtresse (Key Encryption Key) stockée dans `keyring`.
*   `INIT_HEALTH` (float): `100.0` - Valeur de santé initiale pour une nouvelle clé.
*   `RECOVERY_RATE` (float): `5.0` - Taux de récupération de la santé d'une clé par minute d'inactivité.
*   `COST_SUCCESS` (float): `0.1` - Coût en santé pour une utilisation réussie de la clé.
*   `COST_ERROR_QUOTA` (float): `100.0` - Coût en santé pour une erreur de quota (entraîne une mise en "cooldown" immédiate).
*   `COST_ERROR_OTHER` (float): `20.0` - Coût en santé pour les autres types d'erreurs.
*   `SECRETS_FILE` (str): Chemin d'accès au fichier chiffré (`secrets.enc`) contenant les clés API. Déduit du `KEY_STATUS_FILE`.

### Class `KeyStats`
Représente les métadonnées et les statistiques de santé/d'utilisation pour une clé API individuelle.

#### `__init__(self, key, provider, alias=None)`
*   **Signature**: `KeyStats(key: str, provider: str, alias: Optional[str] = None)`
*   **Arguments**:
    *   `key` (str): La valeur de la clé API.
    *   `provider` (str): Le fournisseur de services associé à la clé (ex: "google_gemini", "groq").
    *   `alias` (str, optional): Un nom convivial pour la clé, utilisé pour l'affichage (par défaut: `"Provider (short_id)"`).
*   **Retours**: Aucune.
*   **Logique interne**:
    Initialise une nouvelle instance de `KeyStats`. Génère un `short_id` (les 6 derniers caractères de la clé) pour une identification non sensible. Définit la santé initiale, le timestamp de la dernière utilisation, le temps de cooldown, le compteur d'utilisation et le compteur d'erreurs.

#### `to_dict(self)`
*   **Signature**: `to_dict(self) -> dict`
*   **Arguments**: Aucun.
*   **Retours**: `dict` - Un dictionnaire contenant les informations non sensibles de la clé (alias, short_id, provider, santé, etc.), adapté pour l'affichage dans l'interface utilisateur.
*   **Logique interne**:
    Crée un dictionnaire à partir des attributs de l'instance, excluant la valeur complète de la clé API pour des raisons de sécurité lors de l'exportation.

#### `from_dict_stats(self, data)`
*   **Signature**: `from_dict_stats(self, data: dict) -> None`
*   **Arguments**:
    *   `data` (dict): Un dictionnaire contenant les métriques de santé et d'utilisation (tel que généré par `to_dict`).
*   **Retours**: Aucune.
*   **Logique interne**:
    Restaure les métriques de santé (`health`, `last_used`, `cooldown_until`, `usage_count`, `errors`) à partir d'un dictionnaire fourni. Utilisé pour recharger l'état persistant des clés.

### Class `KeyManager`
La classe principale gérant le cycle de vie complet des clés API, y compris le stockage sécurisé, la migration, la rotation, le suivi de la santé et la persistance.

#### `__init__(self)`
*   **Signature**: `__init__(self)`
*   **Arguments**: Aucun.
*   **Retours**: Aucune.
*   **Logique interne**:
    Initialise le gestionnaire de clés.
    1.  `self.keys`: Un dictionnaire pour stocker les instances de `KeyStats`, indexées par la valeur complète de la clé API.
    2.  `self.lock`: Un verrou de thread (`threading.Lock`) pour assurer la sécurité des accès concurrents à `self.keys`.
    3.  `self.fernet`: Instance du moteur de chiffrement `Fernet`, initialisée après la récupération de la KEK.
    4.  `self.model_provider_map`: Mappage des mots-clés de modèles vers les fournisseurs d'API correspondants.
    L'initialisation procède en quatre étapes critiques:
    *   Appel à `_init_crypto_engine()`: Initialise le système de chiffrement.
    *   Appel à `_load_encrypted_vault()`: Charge les clés API chiffrées depuis le disque.
    *   Appel à `_migrate_legacy_sources()`: Gère la migration des clés stockées de manière moins sécurisée.
    *   Appel à `_load_stats_state()`: Charge les statistiques de santé et d'utilisation des clés.

#### `_init_crypto_engine(self)`
*   **Signature**: `_init_crypto_engine(self) -> None`
*   **Arguments**: Aucun.
*   **Retours**: Aucune (lève une `RuntimeError` en cas d'échec critique).
*   **Logique interne**:
    Tente de récupérer la Clé Maîtresse (KEK) nommée `KEK_NAME` pour `SERVICE_ID` depuis le `keyring` du système. Si la KEK n'existe pas, elle en génère une nouvelle, la stocke dans le `keyring` et initialise l'objet `Fernet` avec cette clé. En cas d'échec d'accès au `keyring`, une `RuntimeError` est levée, empêchant l'application de démarrer en mode non sécurisé.

#### `_save_encrypted_vault(self)`
*   **Signature**: `_save_encrypted_vault(self) -> None`
*   **Arguments**: Aucun.
*   **Retours**: Aucune.
*   **Logique interne**:
    Sérialise les informations essentielles des clés (valeur, fournisseur, alias) dans un dictionnaire, le convertit en JSON, chiffre le JSON résultant avec `self.fernet`, puis écrit les données chiffrées dans le fichier `SECRETS_FILE`. Ne stocke pas les statistiques de santé, qui sont gérées séparément.

#### `_load_encrypted_vault(self)`
*   **Signature**: `_load_encrypted_vault(self) -> None`
*   **Arguments**: Aucun.
*   **Retours**: Aucune.
*   **Logique interne**:
    Lit le contenu du fichier `SECRETS_FILE`. Si le fichier est vide ou n'existe pas, ou si les données ne peuvent être déchiffrées ou désérialisées (ex: clé KEK invalide, fichier corrompu), la fonction logue une erreur. Sinon, elle déchiffre les données, les désérialise en JSON, et peuple `self.keys` avec de nouvelles instances `KeyStats` basées sur les données récupérées.

#### `_migrate_legacy_sources(self)`
*   **Signature**: `_migrate_legacy_sources(self) -> None`
*   **Arguments**: Aucun.
*   **Retours**: Aucune.
*   **Logique interne**:
    Effectue une migration des clés API stockées de manière non sécurisée (champs en texte clair dans `APP_SETTINGS.api_keys`) ou dans d'anciennes entrées `keyring` (qui stockaient des listes de clés par fournisseur) vers le nouveau coffre chiffré (`SECRETS_FILE`). Après migration, les sources obsolètes sont vidées (dans `APP_SETTINGS`) ou supprimées (dans `keyring`) et les `APP_SETTINGS` sont sauvegardés.

#### `_save_stats_state(self)`
*   **Signature**: `_save_stats_state(self) -> None`
*   **Arguments**: Aucun.
*   **Retours**: Aucune.
*   **Logique interne**:
    Sauvegarde l'état actuel de toutes les statistiques de clé (santé, usage, cooldown) dans le fichier `KEY_STATUS_FILE`. Utilise le `short_id` de chaque clé comme index pour éviter d'écrire la clé complète en texte clair dans ce fichier JSON.

#### `_load_stats_state(self)`
*   **Signature**: `_load_stats_state(self) -> None`
*   **Arguments**: Aucun.
*   **Retours**: Aucune.
*   **Logique interne**:
    Charge les statistiques de clé depuis `KEY_STATUS_FILE`. Une fois les données chargées, elles sont mappées aux objets `KeyStats` existants dans `self.keys` en utilisant le `short_id` comme identifiant, restaurant ainsi leur état persistant.

#### `add_key(self, provider, new_key_value, alias_name)`
*   **Signature**: `add_key(self, provider: str, new_key_value: str, alias_name: str) -> bool`
*   **Arguments**:
    *   `provider` (str): Le fournisseur de la nouvelle clé.
    *   `new_key_value` (str): La valeur de la nouvelle clé API.
    *   `alias_name` (str): L'alias à attribuer à la clé.
*   **Retours**: `bool` - `True` si la clé a été ajoutée/mise à jour, `False` si `new_key_value` est vide.
*   **Logique interne**:
    Ajoute une nouvelle clé API au gestionnaire. Si la clé existe déjà, son alias est mis à jour. Le coffre chiffré est ensuite sauvegardé. Protégé par un verrou de thread.

#### `edit_key(self, provider, old_key_value, new_key_value, new_alias)`
*   **Signature**: `edit_key(self, provider: str, old_key_value: str, new_key_value: str, new_alias: str) -> bool`
*   **Arguments**:
    *   `provider` (str): Le fournisseur de la clé.
    *   `old_key_value` (str): La valeur actuelle de la clé à modifier.
    *   `new_key_value` (str): La nouvelle valeur de la clé (peut être identique à `old_key_value`).
    *   `new_alias` (str): Le nouvel alias pour la clé.
*   **Retours**: `bool` - `True` si la clé a été éditée avec succès.
*   **Logique interne**:
    Modifie une clé existante. Si la valeur de la clé change, l'ancienne entrée est supprimée et une nouvelle est ajoutée. Sinon, seul l'alias est mis à jour. Le coffre chiffré est sauvegardé. Protégé par un verrou de thread.

#### `delete_key(self, provider, key_value)`
*   **Signature**: `delete_key(self, provider: str, key_value: str) -> bool`
*   **Arguments**:
    *   `provider` (str): Le fournisseur de la clé.
    *   `key_value` (str): La valeur de la clé à supprimer.
*   **Retours**: `bool` - `True` si la clé a été supprimée, `False` sinon.
*   **Logique interne**:
    Supprime une clé API du gestionnaire si elle existe. Le coffre chiffré est sauvegardé. Protégé par un verrou de thread.

#### `get_all_keys_info(self)`
*   **Signature**: `get_all_keys_info(self) -> List[dict]`
*   **Arguments**: Aucun.
*   **Retours**: `List[dict]` - Une liste de dictionnaires, chacun représentant les informations non sensibles (`to_dict()`) d'une clé gérée.
*   **Logique interne**:
    Fournit une vue d'ensemble de toutes les clés gérées pour l'interface utilisateur, sans exposer les clés complètes.

#### `_get_provider_for_model(self, model_name)`
*   **Signature**: `_get_provider_for_model(self, model_name: str) -> str`
*   **Arguments**:
    *   `model_name` (str): Le nom du modèle d'IA (ex: "gemini-pro", "llama3-8b").
*   **Retours**: `str` - Le nom du fournisseur d'API correspondant au modèle.
*   **Logique interne**:
    Utilise le `model_provider_map` pour faire correspondre un modèle donné à son fournisseur d'API. Par défaut, retourne "google_gemini".

#### `get_key(self, model_name, exclude_key=None)`
*   **Signature**: `get_key(self, model_name: str, exclude_key: Optional[str] = None) -> Optional[str]`
*   **Arguments**:
    *   `model_name` (str): Le nom du modèle pour lequel une clé est requise.
    *   `exclude_key` (str, optional): Une clé à exclure de la sélection (utile pour les retries).
*   **Retours**: `str` - La valeur de la clé API sélectionnée, ou `None` si aucune clé valide n'est trouvée.
*   **Logique interne**:
    1.  Identifie le `provider` pour le `model_name`.
    2.  Filtre les clés pour ne retenir que celles du bon fournisseur, non exclues et non en cooldown.
    3.  Calcule la récupération de santé pour les clés qui n'ont pas été utilisées récemment.
    4.  Trie les clés candidates par santé (décroissante) puis par dernière utilisation (décroissante, pour favoriser les clés moins utilisées récemment).
    5.  Sélectionne aléatoirement une clé parmi les 3 meilleures candidates.
    6.  Met à jour le timestamp `last_used` de la clé sélectionnée.
    7.  Protégé par un verrou de thread.

#### `report_error(self, key, exception=None, model_name="unknown")`
*   **Signature**: `report_error(self, key: str, exception: Optional[Exception] = None, model_name: str = "unknown") -> None`
*   **Arguments**:
    *   `key` (str): La clé API pour laquelle une erreur est signalée.
    *   `exception` (Exception, optional): L'objet exception qui a causé l'erreur.
    *   `model_name` (str, optional): Le modèle utilisé lors de l'erreur.
*   **Retours**: Aucune.
*   **Logique interne**:
    Décrémente la santé de la clé signalée. Si l'erreur est liée à un quota (code 429 ou mots-clés spécifiques), la santé est mise à 0 et la clé est placée en "cooldown" pendant 1 heure. Incrémente le compteur d'erreurs et sauvegarde l'état des statistiques. Protégé par un verrou de thread.

#### `mark_success(self, key, model_name="unknown")`
*   **Signature**: `mark_success(self, key: str, model_name: str = "unknown") -> None`
*   **Arguments**:
    *   `key` (str): La clé API pour laquelle un succès est signalé.
    *   `model_name` (str, optional): Le modèle utilisé lors du succès.
*   **Retours**: Aucune.
*   **Logique interne**:
    Décrémente légèrement la santé de la clé (`COST_SUCCESS`) et incrémente son compteur d'utilisation. Si la santé descend sous un certain seuil, elle est légèrement régénérée pour éviter un épuisement trop rapide. Sauvegarde l'état des statistiques. Protégé par un verrou de thread.

#### `@property num_keys`
*   **Signature**: `num_keys`
*   **Arguments**: Aucun.
*   **Retours**: `int` - Le nombre total de clés API actuellement gérées.
*   **Logique interne**: Simple accesseur à la taille du dictionnaire `self.keys`.

#### `discover_models(self)`
*   **Signature**: `discover_models(self) -> Dict[str, List[str]]`
*   **Arguments**: Aucun.
*   **Retours**: `dict` - Un dictionnaire où les clés sont les noms des fournisseurs (`"deepseek"`, `"groq"`, `"gemini"`) et les valeurs sont des listes de chaînes de caractères représentant les IDs des modèles découverts.
*   **Logique interne**:
    Tente de récupérer des modèles disponibles auprès de fournisseurs d'API spécifiques (Deepseek, Groq) en utilisant les clés API configurées. Utilise la méthode privée `_fetch_openai_compatible_models`.

#### `_fetch_openai_compatible_models(self, api_key, base_url)`
*   **Signature**: `_fetch_openai_compatible_models(self, api_key: str, base_url: str) -> List[str]`
*   **Arguments**:
    *   `api_key` (str): La clé API à utiliser pour l'authentification.
    *   `base_url` (str): L'URL de base de l'API (ex: "https://api.groq.com/openai/v1").
*   **Retours**: `List[str]` - Une liste des IDs des modèles découverts, ou une liste vide en cas d'échec.
*   **Logique interne**:
    Envoie une requête HTTP GET à l'endpoint `/models` d'une API compatible OpenAI, en utilisant la clé API pour l'authentification. Parse la réponse JSON pour extraire les IDs des modèles.

### Fonction `discover_models()` (au niveau du module)
Fonction utilitaire pour encapsuler l'instanciation de `KeyManager` et la découverte de modèles.

*   **Signature**: `discover_models() -> Dict[str, List[str]]`
*   **Arguments**: Aucun.
*   **Retours**: `dict` - Un dictionnaire où les clés sont les noms des fournisseurs et les valeurs sont des listes de modèles découverts (ex: `{"deepseek": ["deepseek-chat"], "groq": ["llama3-8b"]}`). En cas d'erreur lors de l'initialisation du KeyManager, retourne un dictionnaire vide.
*   **Logique interne**:
    Crée une instance de `KeyManager` puis appelle sa méthode `discover_models()`. Permet une découverte de modèles simplifiée sans interaction directe avec l'objet `KeyManager` complet.

## 3. Exemple d'Usage

```python
import os
import sys

# Ajouter le chemin racine du projet pour que les imports fonctionnent
# Cet exemple suppose que ai_core est dans le répertoire parent du script
# Pour un environnement de test, il peut être nécessaire d'ajuster sys.path
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, os.pardir, os.pardir))
sys.path.insert(0, project_root)

# Simuler les dépendances externes pour l'exemple
# Normalement, ces fichiers seraient configurés dans le projet réel
class MockAppSettings:
    def get(self, key, default=None):
        return {"api_keys": {}}.get(key, default)

def mock_save_app_settings(settings):
    pass # Ne rien faire pour l'exemple

# Mocking UnifiedLogger pour que l'exemple soit exécutable
class MockUnifiedLogger:
    def write(self, *args):
        print(f"[LOG] {' '.join(map(str, args))}")

# Remplacer les importations réelles par les mocks si nécessaire pour l'exécution standalone
# Dans un environnement réel, ces lignes ne seraient pas nécessaires
# from config.settings import APP_SETTINGS, KEY_STATUS_FILE, save_app_settings
# from features.UnifiedLogger import UnifiedLogger
APP_SETTINGS = MockAppSettings()
KEY_STATUS_FILE = "mock_key_status.json" # Fichier temporaire pour l'exemple
UnifiedLogger = MockUnifiedLogger()


# Assurez-vous que keyring et cryptography sont installés
# from ai_core.keys import KeyManager, discover_models # Utiliser l'importation réelle

# Pour cet exemple, je vais coller la KeyManager et discover_models pour qu'il soit auto-suffisant
# car les mocks de config.settings et UnifiedLogger ne sont pas directement accessibles à l'intérieur du fichier keys.py

# --- Contenu du fichier ai_core/keys.py (simulé ici pour l'exemple) ---
import time
import json
import os
import threading
import random
import keyring # pip install keyring
import requests
import base64
from cryptography.fernet import Fernet # pip install cryptography

# Utilisation des mocks pour cet exemple
# from config.settings import APP_SETTINGS, KEY_STATUS_FILE, save_app_settings
# from features.UnifiedLogger import UnifiedLogger

SECRETS_FILE = os.path.join(os.path.dirname(KEY_STATUS_FILE), "secrets.enc")

SERVICE_ID = "AiModding_Companion"
KEK_NAME = "MasterKey_KEK"
INIT_HEALTH = 100.0
RECOVERY_RATE = 5.0
COST_SUCCESS = 0.1
COST_ERROR_QUOTA = 100.0
COST_ERROR_OTHER = 20.0

class KeyStats:
    def __init__(self, key, provider, alias=None):
        self.key = key
        self.short_id = key.strip()[-6:] if len(key) > 6 else key
        self.provider = provider
        self.alias = alias or f"{provider.capitalize()} ({self.short_id})"
        self.health = INIT_HEALTH
        self.last_used = 0
        self.cooldown_until = 0
        self.usage_count = 0
        self.errors = 0

    def to_dict(self):
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
        self.health = data.get("health", INIT_HEALTH)
        self.last_used = data.get("last_used", 0)
        self.cooldown_until = data.get("cooldown_until", 0)
        self.usage_count = data.get("usage_count", 0)
        self.errors = data.get("errors", 0)

class KeyManager:
    def __init__(self):
        self.keys = {}
        self.lock = threading.Lock()
        self.fernet = None

        self.model_provider_map = {
            "gemini": "google_gemini", "flash": "google_gemini", "pro": "google_gemini",
            "learnlm": "google_gemini", "groq": "groq", "llama": "groq", 
            "mixtral": "groq", "gemma": "groq", "deepseek": "deepseek"
        }

        self._init_crypto_engine()
        self._load_encrypted_vault()
        self._migrate_legacy_sources() # This might clear APP_SETTINGS in real use
        self._load_stats_state()

    def _init_crypto_engine(self):
        try:
            kek_b64 = keyring.get_password(SERVICE_ID, KEK_NAME)
            if not kek_b64:
                UnifiedLogger.write("KEY_MGR", "SETUP", "Génération nouvelle MasterKey (KEK)...")
                key = Fernet.generate_key()
                kek_b64 = key.decode('utf-8')
                keyring.set_password(SERVICE_ID, KEK_NAME, kek_b64)
            
            self.fernet = Fernet(kek_b64.encode('utf-8'))
            UnifiedLogger.write("KEY_MGR", "SECURE", "Moteur Crypto initialisé avec succès.")
        except Exception as e:
            UnifiedLogger.write("KEY_MGR", "CRITICAL", f"Echec init crypto: {e}")
            raise RuntimeError(f"Impossible d'accéder au Keyring pour la KEK: {e}")

    def _save_encrypted_vault(self):
        try:
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

    def _migrate_legacy_sources(self):
        api_conf = APP_SETTINGS.get("api_keys", {})
        dirty = False
        migrated_total = 0
        known_providers = ["google_gemini", "groq", "openai", "mistral", "deepseek"]

        for provider in known_providers:
            keys_in_clear = api_conf.get(provider, "")
            if keys_in_clear and len(str(keys_in_clear).strip()) > 5:
                key_list = []
                if isinstance(keys_in_clear, list): key_list = keys_in_clear
                else: key_list = [k.strip() for k in keys_in_clear.split(',') if k.strip()]
                
                for idx, k in enumerate(key_list):
                    if k not in self.keys:
                        short = k[-6:]
                        existing_alias_map = APP_SETTINGS.get("key_aliases", {})
                        alias = existing_alias_map.get(short, f"Clé {provider.capitalize()} {idx+1} (Import)")
                        self.keys[k] = KeyStats(k, provider, alias)
                        dirty = True
                        migrated_total += 1
                api_conf[provider] = ""

        for provider in known_providers:
            try:
                legacy_content = keyring.get_password(SERVICE_ID, provider)
                if legacy_content:
                    raw_keys = [k.strip() for k in legacy_content.split(',') if k.strip()]
                    for k in raw_keys:
                        if k not in self.keys:
                            self.keys[k] = KeyStats(k, provider, f"{provider.capitalize()} (Legacy Ring)")
                            dirty = True
                            migrated_total += 1
                    keyring.delete_password(SERVICE_ID, provider)
                    UnifiedLogger.write("KEY_MGR", "CLEAN", f"Entrée Keyring legacy '{provider}' supprimée.")
            except: pass

        if dirty:
            self._save_encrypted_vault()
            try:
                # mock_save_app_settings(APP_SETTINGS) # Don't actually save mock
                UnifiedLogger.write("KEY_MGR", "MIGRATION", f"Migration terminée : {migrated_total} clés sécurisées dans secrets.enc")
            except Exception as e:
                UnifiedLogger.write("KEY_MGR", "ERROR", f"Erreur save settings post-migration: {e}")

    def _save_stats_state(self):
        try:
            data = {}
            for k, stats in self.keys.items():
                idx = stats.short_id 
                data[idx] = stats.to_dict()
            with open(KEY_STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except: pass

    def _load_stats_state(self):
        if not os.path.exists(KEY_STATUS_FILE): return
        try:
            with open(KEY_STATUS_FILE, 'r') as f:
                data = json.load(f)
            map_short_to_obj = {stats.short_id: stats for stats in self.keys.values()}
            count = 0
            for short_id, stats_data in data.items():
                if short_id in map_short_to_obj:
                    map_short_to_obj[short_id].from_dict_stats(stats_data)
                    count += 1
        except Exception as e:
            UnifiedLogger.write("KEY_MGR", "WARNING", f"Echec chargement stats: {e}")

    def add_key(self, provider, new_key_value, alias_name):
        new_key_value = new_key_value.strip()
        if not new_key_value: return False
        with self.lock:
            if new_key_value not in self.keys:
                self.keys[new_key_value] = KeyStats(new_key_value, provider, alias=alias_name)
            else:
                self.keys[new_key_value].alias = alias_name
            self._save_encrypted_vault()
            UnifiedLogger.write("KEY_MGR", "ADD", f"Nouvelle clé ajoutée au coffre: {alias_name}")
            return True

    def edit_key(self, provider, old_key_value, new_key_value, new_alias):
        with self.lock:
            old_key_value = old_key_value.strip()
            new_key_value = new_key_value.strip()
            if old_key_value != new_key_value:
                if old_key_value in self.keys:
                    del self.keys[old_key_value]
                self.keys[new_key_value] = KeyStats(new_key_value, provider, alias=new_alias)
            else:
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
                UnifiedLogger.write("KEY_MGR", "DELETE", "Clé supprimée du coffre.")
                return True
            return False

    def get_all_keys_info(self):
        return [s.to_dict() for s in self.keys.values()]

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
                
                time_since_use = (now - stats.last_used) / 60.0
                if time_since_use > 5:
                    regain = int(time_since_use * RECOVERY_RATE)
                    stats.health = min(100.0, stats.health + regain)
                candidates.append(stats)

            if not candidates:
                candidates = [s for s in self.keys.values() if s.provider == provider and s.key != exclude_key]
                if not candidates: return None

            candidates.sort(key=lambda s: (s.health, -s.last_used), reverse=True)
            top_n = candidates[:3]
            selected = random.choice(top_n)
            
            selected.last_used = now
            return selected.key

    def report_error(self, key, exception=None, model_name="unknown"):
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

    def discover_models(self):
        discovered = {"deepseek": [], "groq": [], "gemini": []}
        # Not actually making API calls in this example
        # For a real example, you'd need actual keys and network access
        UnifiedLogger.write("KEY_MGR", "INFO", "Discovery de modèles simulée.")
        return discovered

    def _fetch_openai_compatible_models(self, api_key, base_url):
        # Mock this for the example
        return []

# Wrapper module level (using the mocked KeyManager)
def discover_models():
    try:
        mgr = KeyManager()
        return mgr.discover_models()
    except Exception as e:
        UnifiedLogger.write("KEY_MGR", "ERROR", f"Erreur lors de la découverte de modèles: {e}")
        return {"deepseek": [], "groq": [], "gemini": []}

# --- FIN du contenu simulé ---

# Nettoyage des fichiers temporaires pour l'exemple
def cleanup_example_files():
    for f in [KEY_STATUS_FILE, SECRETS_FILE]:
        if os.path.exists(f):
            os.remove(f)
            print(f"Fichier de l'exemple supprimé: {f}")

if __name__ == "__main__":
    cleanup_example_files()
    
    print("\n--- Initialisation du KeyManager ---")
    try:
        key_manager = KeyManager()
    except RuntimeError as e:
        print(f"Erreur critique lors de l'initialisation du KeyManager: {e}")
        print("Veuillez vous assurer que keyring est correctement configuré pour votre système.")
        exit()

    print(f"Nombre de clés initialement chargées: {key_manager.num_keys}")

    print("\n--- Ajout de clés API ---")
    key_manager.add_key("google_gemini", "GEMINI_API_KEY_123456", "Ma Clé Gemini Pro")
    key_manager.add_key("groq", "GROQ_API_KEY_789012", "Clé Groq Llama3")
    key_manager.add_key("deepseek", "DEEPSEEK_API_KEY_ABCDEF", "Clé Deepseek Chat")
    key_manager.add_key("google_gemini", "GEMINI_API_KEY_789012", "Ma Seconde Clé Gemini")

    print(f"Nombre de clés après ajout: {key_manager.num_keys}")
    print("\nInfos sur toutes les clés:")
    for key_info in key_manager.get_all_keys_info():
        print(f"- Alias: {key_info['alias']}, Provider: {key_info['provider']}, Santé: {key_info['health']:.1f}")

    print("\n--- Obtention et utilisation d'une clé ---")
    model_name_gemini = "gemini-pro"
    selected_gemini_key = key_manager.get_key(model_name_gemini)
    if selected_gemini_key:
        print(f"Clé sélectionnée pour {model_name_gemini}: ...{selected_gemini_key[-6:]}")
        key_manager.mark_success(selected_gemini_key, model_name_gemini)
        print(f"Santé de la clé après succès: {key_manager.keys[selected_gemini_key].health:.1f}")
    else:
        print(f"Aucune clé disponible pour {model_name_gemini}.")

    model_name_groq = "llama3-8b"
    selected_groq_key = key_manager.get_key(model_name_groq)
    if selected_groq_key:
        print(f"Clé sélectionnée pour {model_name_groq}: ...{selected_groq_key[-6:]}")
        # Simuler une erreur de quota
        key_manager.report_error(selected_groq_key, exception=Exception("429 Too Many Requests - Quota Exceeded"), model_name=model_name_groq)
        print(f"Santé de la clé après erreur de quota: {key_manager.keys[selected_groq_key].health:.1f}")
        print(f"Cooldown de la clé Groq: jusqu'à {time.ctime(key_manager.keys[selected_groq_key].cooldown_until)}")
    else:
        print(f"Aucune clé disponible pour {model_name_groq}.")

    print("\n--- Édition d'une clé ---")
    old_gemini_key = "GEMINI_API_KEY_123456"
    key_manager.edit_key("google_gemini", old_gemini_key, old_gemini_key, "Ma Clé Gemini Renommée")
    print("\nInfos sur toutes les clés après édition:")
    for key_info in key_manager.get_all_keys_info():
        print(f"- Alias: {key_info['alias']}, Provider: {key_info['provider']}, Santé: {key_info['health']:.1f}")

    print("\n--- Suppression d'une clé ---")
    key_to_delete = "GEMINI_API_KEY_789012"
    key_manager.delete_key("google_gemini", key_to_delete)
    print(f"Nombre de clés après suppression: {key_manager.num_keys}")
    print("\nInfos sur toutes les clés après suppression:")
    for key_info in key_manager.get_all_keys_info():
        print(f"- Alias: {key_info['alias']}, Provider: {key_info['provider']}, Santé: {key_info['health']:.1f}")

    print("\n--- Découverte de modèles (simulée) ---")
    models = discover_models()
    print(f"Modèles découverts: {models}")

    print("\n--- Nettoyage des fichiers d'exemple ---")
    cleanup_example_files()
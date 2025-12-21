import os
import json
import threading
from config.settings import TOKEN_USAGE_FILE
from features.UnifiedLogger import UnifiedLogger
from features.Decorators import trace_action

class TokenManager:
    """
    Gestionnaire centralisé de la consommation de tokens.
    Suit l'usage par Modèle et par Clé API.
    """
    _lock = threading.Lock()
    _stats = {
        "total_global": {"in": 0, "out": 0},
        "by_model": {},
        "by_key": {}
    }

    @staticmethod
    def load():
        with TokenManager._lock:
            if os.path.exists(TOKEN_USAGE_FILE):
                try:
                    with open(TOKEN_USAGE_FILE, 'r', encoding='utf-8') as f:
                        TokenManager._stats = json.load(f)
                except Exception as e:
                    UnifiedLogger.write("TokenManager", "ERROR", f"Erreur chargement stats: {e}")

    @staticmethod
    def save():
        with TokenManager._lock:
            try:
                with open(TOKEN_USAGE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(TokenManager._stats, f, indent=2, ensure_ascii=False)
            except Exception as e:
                UnifiedLogger.write("TokenManager", "ERROR", f"Erreur sauvegarde stats: {e}")

    @staticmethod
    def add_usage(model, api_key_mask, input_tokens, output_tokens):
        """Enregistre une consommation."""
        TokenManager.load() # Recharge pour être à jour (multi-thread)
        
        with TokenManager._lock:
            stats = TokenManager._stats
            
            # 1. Total Global
            stats["total_global"]["in"] += input_tokens
            stats["total_global"]["out"] += output_tokens
            
            # 2. Par Modèle
            if model not in stats["by_model"]:
                stats["by_model"][model] = {"in": 0, "out": 0, "calls": 0}
            stats["by_model"][model]["in"] += input_tokens
            stats["by_model"][model]["out"] += output_tokens
            stats["by_model"][model]["calls"] += 1
            
            # 3. Par Clé (Masquée)
            key_id = api_key_mask[-6:] if len(api_key_mask) > 6 else "unknown"
            if key_id not in stats["by_key"]:
                stats["by_key"][key_id] = {"in": 0, "out": 0, "provider": "gemini"} # Ou autre selon contexte
            stats["by_key"][key_id]["in"] += input_tokens
            stats["by_key"][key_id]["out"] += output_tokens
            
        TokenManager.save()
        
        # Log discret pour confirmation
        # UnifiedLogger.write("TokenManager", "METRICS", f"Usage {model}: +{input_tokens} in / +{output_tokens} out")

# Initialisation au chargement
TokenManager.load()
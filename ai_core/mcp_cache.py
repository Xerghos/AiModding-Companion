"""
Cache de découverte MCP pour éviter de redécouvrir les outils à chaque requête.
Stocke la liste des outils découverts avec un hash du serveur MCP pour invalidation.
"""

import json
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


def _calculate_server_hash(server_config: Dict[str, Any]) -> str:
    """
    Calcule un hash du serveur MCP pour détecter les changements.
    
    Args:
        server_config: Configuration du serveur MCP (command, args, cwd, etc.)
        
    Returns:
        Hash string représentant la configuration du serveur
    """
    # Créer une représentation simple de la configuration
    config_str = json.dumps(server_config, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(config_str.encode('utf-8')).hexdigest()


def _get_cache_file_path() -> Path:
    """Retourne le chemin du fichier de cache."""
    cache_dir = Path(__file__).parent.parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / "mcp_tools_cache.json"


def load_mcp_cache(server_config: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Charge le cache des outils MCP si le serveur n'a pas changé.
    
    Args:
        server_config: Configuration actuelle du serveur MCP
        
    Returns:
        Liste des outils en cache, ou None si le cache est invalide/inexistant
    """
    cache_file = _get_cache_file_path()
    
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # Vérifier le hash du serveur
        cached_hash = cache_data.get("server_hash")
        current_hash = _calculate_server_hash(server_config)
        
        if cached_hash != current_hash:
            # Le serveur a changé, le cache est invalide
            return None
        
        # Vérifier l'âge du cache (optionnel: invalider après 24h)
        cache_timestamp = cache_data.get("timestamp")
        if cache_timestamp:
            try:
                cache_time = datetime.fromisoformat(cache_timestamp)
                age_hours = (datetime.now() - cache_time).total_seconds() / 3600
                if age_hours > 24:
                    # Cache trop vieux, invalider
                    return None
            except Exception:
                pass
        
        # Retourner les outils en cache
        return cache_data.get("tools", None)
        
    except Exception:
        # En cas d'erreur, considérer le cache comme invalide
        return None


def save_mcp_cache(server_config: Dict[str, Any], tools: List[Dict[str, Any]]):
    """
    Sauvegarde le cache des outils MCP.
    
    Args:
        server_config: Configuration du serveur MCP
        tools: Liste des outils découverts
    """
    cache_file = _get_cache_file_path()
    
    try:
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "server_hash": _calculate_server_hash(server_config),
            "server_config": server_config,  # Stocker aussi la config pour debug
            "tools": tools,
            "tools_count": len(tools)
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        
    except Exception as e:
        # Ne pas bloquer si le cache échoue
        from features.UnifiedLogger import UnifiedLogger
        UnifiedLogger.write(
            "AI_CORE",
            "WARNING",
            f"Échec sauvegarde cache MCP: {e}"
        )


def invalidate_mcp_cache():
    """Invalide le cache MCP en supprimant le fichier."""
    cache_file = _get_cache_file_path()
    try:
        if cache_file.exists():
            cache_file.unlink()
    except Exception:
        pass


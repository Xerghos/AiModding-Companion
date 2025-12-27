"""
Validateur et normalisateur pour les credentials OAuth Google.
Assure la conformité avec le format attendu par google.oauth2.credentials.Credentials
et compatible avec gemini-cli.
"""

import os
import json
import time
from typing import Dict, Any, Optional, Tuple
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

from features.UnifiedLogger import UnifiedLogger


# Format attendu pour Credentials.from_authorized_user_info()
# Référence: https://google-auth.readthedocs.io/en/stable/reference/google.oauth2.credentials.html
REQUIRED_FIELDS = {
    "token_uri": str,
    "client_id": str,
    "client_secret": str,
}

OPTIONAL_FIELDS = {
    "token": (str, type(None)),  # Peut être None si expiré
    "refresh_token": (str, type(None)),  # Peut être None pour certains types
    "scopes": list,  # Liste de strings
    "type": str,  # "authorized_user" pour OAuth 2.0 user credentials
}

# Format complet attendu (selon Google Auth Library)
EXPECTED_FORMAT = {
    "type": "authorized_user",  # Type de credentials
    "client_id": str,
    "client_secret": str,
    "refresh_token": str,
    "token_uri": "https://oauth2.googleapis.com/token",
    "token": (str, type(None)),  # Access token (peut être None si expiré)
    "scopes": list,  # Liste des scopes autorisés
}

_last_refresh_time: Optional[float] = None
TOKEN_REFRESH_THRESHOLD_SECONDS = 30 * 60  # 30 minutes


def _timestamp_path_for_token(token_path: str) -> str:
    return token_path + ".timestamp"


def _load_last_refresh_time(token_path: str) -> float:
    """
    Charge l'horodatage du dernier refresh.
    Fallback: mtime du token JSON (utile si gemini-cli a refresh sans ecrire .timestamp).
    """
    ts_path = _timestamp_path_for_token(token_path)

    # Priorite au fichier timestamp
    if os.path.exists(ts_path):
        try:
            with open(ts_path, "r") as f:
                return float((f.read() or "").strip() or "0")
        except Exception:
            return 0.0

    # Fallback: mtime du token json
    if os.path.exists(token_path):
        try:
            return float(os.path.getmtime(token_path))
        except Exception:
            return 0.0

    return 0.0


def _save_last_refresh_time(token_path: str, refresh_time: Optional[float] = None) -> None:
    """Sauvegarde l'horodatage du dernier refresh dans token_path + '.timestamp'."""
    ts_path = _timestamp_path_for_token(token_path)
    t = time.time() if refresh_time is None else float(refresh_time)
    os.makedirs(os.path.dirname(token_path), exist_ok=True)
    with open(ts_path, "w") as f:
        f.write(str(t))


def should_refresh_token(
    token_path: str,
    threshold_seconds: int = TOKEN_REFRESH_THRESHOLD_SECONDS
) -> bool:
    """
    Indique si on doit forcer un refresh proactif du token OAuth.
    Regle: si aucun refresh depuis threshold_seconds.
    """
    global _last_refresh_time
    if _last_refresh_time is None:
        _last_refresh_time = _load_last_refresh_time(token_path)

    age = time.time() - float(_last_refresh_time or 0.0)
    return age > float(threshold_seconds)


def validate_oauth_credentials(token_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Valide le format des credentials OAuth.
    
    Args:
        token_data: Dictionnaire contenant les credentials OAuth
        
    Returns:
        Tuple (is_valid, error_message)
    """
    if not isinstance(token_data, dict):
        return False, "Les credentials doivent être un dictionnaire JSON"
    
    # Vérifier les champs requis
    for field, field_type in REQUIRED_FIELDS.items():
        if field not in token_data:
            return False, f"Champ requis manquant: {field}"
        if not isinstance(token_data[field], field_type):
            return False, f"Type incorrect pour {field}: attendu {field_type.__name__}, reçu {type(token_data[field]).__name__}"
    
    # Vérifier les champs optionnels (si présents, doivent être du bon type)
    for field, field_type in OPTIONAL_FIELDS.items():
        if field in token_data:
            if isinstance(field_type, tuple):
                # Type peut être l'un ou l'autre
                if not isinstance(token_data[field], field_type):
                    return False, f"Type incorrect pour {field}: attendu {field_type}, reçu {type(token_data[field]).__name__}"
            else:
                if not isinstance(token_data[field], field_type):
                    return False, f"Type incorrect pour {field}: attendu {field_type.__name__}, reçu {type(token_data[field]).__name__}"
    
    # Vérifications spécifiques
    if "scopes" in token_data and not isinstance(token_data["scopes"], list):
        return False, "Le champ 'scopes' doit être une liste"
    
    if "token_uri" in token_data and not token_data["token_uri"].startswith("https://"):
        return False, "Le champ 'token_uri' doit être une URL HTTPS valide"
    
    if "refresh_token" not in token_data or not token_data["refresh_token"]:
        return False, "Le champ 'refresh_token' est requis et ne peut pas être vide"
    
    return True, None


def normalize_oauth_credentials(token_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise les credentials OAuth pour garantir la conformité.
    
    Args:
        token_data: Dictionnaire contenant les credentials OAuth (peut être incomplet)
        
    Returns:
        Dictionnaire normalisé avec tous les champs requis
    """
    normalized = token_data.copy()
    
    # Ajouter le type si manquant
    if "type" not in normalized:
        normalized["type"] = "authorized_user"
    
    # S'assurer que token_uri est présent et valide
    if "token_uri" not in normalized or not normalized["token_uri"]:
        normalized["token_uri"] = "https://oauth2.googleapis.com/token"
    
    # Normaliser scopes (doit être une liste)
    # Note: Google ajoute automatiquement "openid" aux scopes, c'est normal
    if "scopes" in normalized:
        if isinstance(normalized["scopes"], str):
            # Si c'est une string, la convertir en liste
            normalized["scopes"] = [normalized["scopes"]]
        elif not isinstance(normalized["scopes"], list):
            normalized["scopes"] = []
        # Accepter "openid" si présent (ajouté automatiquement par Google)
    else:
        normalized["scopes"] = []
    
    # S'assurer que token peut être None (si expiré)
    if "token" not in normalized:
        normalized["token"] = None
    
    return normalized


def save_oauth_credentials(credentials: Credentials, token_path: str) -> bool:
    """
    Sauvegarde les credentials OAuth au format normalisé.
    
    Args:
        credentials: Objet Credentials de google.oauth2.credentials
        token_path: Chemin où sauvegarder le fichier JSON
        
    Returns:
        True si la sauvegarde a réussi, False sinon
    """
    try:
        # Créer le répertoire si nécessaire
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        
        # Extraire les données des credentials
        token_data = {
            "type": "authorized_user",
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "token": credentials.token,  # Peut être None si expiré
            "scopes": list(credentials.scopes) if credentials.scopes else [],
        }
        
        # Normaliser et valider
        token_data = normalize_oauth_credentials(token_data)
        is_valid, error_msg = validate_oauth_credentials(token_data)
        
        if not is_valid:
            UnifiedLogger.write(
                "AI_CORE",
                "ERROR",
                f"❌ Format credentials OAuth invalide avant sauvegarde: {error_msg}"
            )
            return False
        
        # Sauvegarder avec indentation pour lisibilité
        with open(token_path, 'w') as f:
            json.dump(token_data, f, indent=2)

        # Mettre a jour le timestamp de refresh (utilise par le refresh proactif 30min)
        try:
            global _last_refresh_time
            _last_refresh_time = time.time()
            _save_last_refresh_time(token_path, _last_refresh_time)
        except Exception:
            # Ne pas bloquer si le timestamp ne peut pas etre ecrit
            pass
        
        # Vérifier que le fichier peut être rechargé
        try:
            test_creds = Credentials.from_authorized_user_file(token_path)
            if test_creds:
                UnifiedLogger.write(
                    "AI_CORE",
                    "AUTH",
                    f"✅ Credentials OAuth sauvegardés et validés: {token_path}"
                )
                return True
        except Exception as e:
            UnifiedLogger.write(
                "AI_CORE",
                "ERROR",
                f"❌ Échec validation credentials après sauvegarde: {e}"
            )
            return False
        
        return True
        
    except Exception as e:
        UnifiedLogger.write(
            "AI_CORE",
            "ERROR",
            f"❌ Erreur sauvegarde credentials OAuth: {e}"
        )
        return False


def load_and_validate_oauth_credentials(token_path: str) -> Tuple[Optional[Credentials], Optional[str]]:
    """
    Charge et valide les credentials OAuth depuis un fichier.
    
    Args:
        token_path: Chemin vers le fichier JSON contenant les credentials
        
    Returns:
        Tuple (Credentials, error_message)
    """
    if not os.path.exists(token_path):
        return None, f"Fichier credentials introuvable: {token_path}"
    
    try:
        # Charger le fichier JSON
        with open(token_path, 'r') as f:
            token_data = json.load(f)
        
        # Normaliser les données
        token_data = normalize_oauth_credentials(token_data)
        
        # Valider le format
        is_valid, error_msg = validate_oauth_credentials(token_data)
        if not is_valid:
            return None, f"Format credentials invalide: {error_msg}"
        
        # Créer l'objet Credentials
        creds = Credentials.from_authorized_user_info(token_data)
        
        # Vérifier si les credentials sont valides ou peuvent être rafraîchis
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Sauvegarder les credentials rafraîchis
                    save_oauth_credentials(creds, token_path)
                except RefreshError as e:
                    return None, f"Impossible de rafraîchir les credentials: {e}"
                except Exception as e:
                    return None, f"Erreur lors du rafraîchissement: {e}"
        
        UnifiedLogger.write(
            "AI_CORE",
            "AUTH",
            f"✅ Credentials OAuth chargés et validés: {token_path}"
        )
        
        return creds, None
        
    except json.JSONDecodeError as e:
        return None, f"Erreur de parsing JSON: {e}"
    except Exception as e:
        return None, f"Erreur lors du chargement: {e}"


def compare_credentials_format(our_format: Dict[str, Any], expected_format: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Compare le format de nos credentials avec le format attendu.
    
    Args:
        our_format: Format actuel de nos credentials
        expected_format: Format attendu (par défaut, EXPECTED_FORMAT)
        
    Returns:
        Dictionnaire avec les différences et recommandations
    """
    if expected_format is None:
        expected_format = EXPECTED_FORMAT
    
    comparison = {
        "missing_fields": [],
        "extra_fields": [],
        "type_mismatches": [],
        "recommendations": []
    }
    
    # Vérifier les champs manquants
    for field in expected_format:
        if field not in our_format:
            comparison["missing_fields"].append(field)
    
    # Vérifier les champs supplémentaires
    for field in our_format:
        if field not in expected_format:
            comparison["extra_fields"].append(field)
    
    # Vérifier les types
    for field in our_format:
        if field in expected_format:
            expected_type = expected_format[field]
            actual_type = type(our_format[field])
            
            if isinstance(expected_type, tuple):
                if actual_type not in expected_type:
                    comparison["type_mismatches"].append({
                        "field": field,
                        "expected": expected_type,
                        "actual": actual_type
                    })
            elif actual_type != expected_type:
                comparison["type_mismatches"].append({
                    "field": field,
                    "expected": expected_type,
                    "actual": actual_type
                })
    
    # Générer des recommandations
    if comparison["missing_fields"]:
        comparison["recommendations"].append(
            f"Ajouter les champs manquants: {', '.join(comparison['missing_fields'])}"
        )
    
    if comparison["type_mismatches"]:
        comparison["recommendations"].append(
            f"Corriger les types: {comparison['type_mismatches']}"
        )
    
    return comparison


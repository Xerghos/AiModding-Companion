import os
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build

from config import get_path, get_logger, GDRIVE_SCOPES, GDRIVE_TOKEN_FILE, GDRIVE_CREDS_FILE
from features.Decorators import trace_action

log = get_logger("Features.Context.Auth")

@trace_action(source="auth")
def get_google_services(result_queue):
    """
    Gère l'authentification Google et retourne les services Drive et Sheets.
    Gère le rafraîchissement de token et l'Auth Flow interactif si nécessaire.
    """
    creds = None
    token_path = get_path(GDRIVE_TOKEN_FILE)
    creds_path = get_path(GDRIVE_CREDS_FILE)

    if not os.path.exists(creds_path):
        log.error(f"Fichier {GDRIVE_CREDS_FILE} manquant!")
        # On ne lève pas d'erreur fatale ici pour permettre le mode hors-ligne
        if result_queue:
            result_queue.put({"type": "ui_update", "widget": "message", "text": f"⚠️ {GDRIVE_CREDS_FILE} introuvable. Mode Local uniquement."})
        return None, None

    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, GDRIVE_SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                log.info("Rafraîchissement du token Google...")
                creds.refresh(Request())
            except (RefreshError, Exception) as e:
                log.error(f"Échec du rafraîchissement token: {e}.")
                creds = None
        
        if not creds:
            try:
                if result_queue:
                    result_queue.put({"type": "ui_update", "widget": "message", "text": "--- Auth Google requise (voir navigateur) ---"})
                
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, GDRIVE_SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                log.error(f"Échec Auth Google: {e}")
                return None, None

        # Sauvegarde du nouveau token
        try:
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        except Exception as e:
            log.error(f"Impossible de sauver le token: {e}")

    try:
        service_drive = build('drive', 'v3', credentials=creds)
        service_sheets = build('sheets', 'v4', credentials=creds)
        return service_drive, service_sheets
    except Exception as e:
        log.error(f"Échec construction services Google: {e}")
        return None, None
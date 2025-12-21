import os
import io
import re
import logging
import requests
from googleapiclient.http import MediaIoBaseDownload
from config import get_logger, SUPPORTED_FILE_EXTENSIONS
from features.Decorators import trace_action

log = get_logger("Features.Context.Loaders")

@trace_action(source="loaders")
def fetch_google_doc_content(service, url):
    try:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        file_id = match.group(1) if match else None
        if not file_id: return None, f"[Erreur: ID Google Doc invalide: {url}]\n"

        file_metadata = service.files().get(fileId=file_id, fields='name').execute()
        name = file_metadata.get('name')
        log.info(f"Exportation de Google Doc '{name}'...")
        
        request = service.files().export_media(fileId=file_id, mimeType='text/plain')
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False: _, done = downloader.next_chunk()
        
        return f"GDoc: {name}", fh.getvalue().decode('utf-8')
    except Exception as e:
        log.error(f"Erreur GDoc {url}: {e}")
        return None, f"[Erreur (GDoc) {url}: {e}]\n"

@trace_action(source="loaders")
def fetch_google_sheet_content(service_sheets, url):
    try:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        sheet_id = match.group(1) if match else None
        if not sheet_id: return None, f"[Erreur: ID Google Sheet invalide: {url}]\n"

        sheet_metadata = service_sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = sheet_metadata.get('sheets', '')
        title = sheet_metadata.get('properties', {}).get('title', 'Titre Inconnu')
        
        content = ""
        for sheet in sheets:
            s_title = sheet.get("properties", {}).get("title", "Feuille Inconnue")
            res = service_sheets.spreadsheets().values().get(spreadsheetId=sheet_id, range=s_title).execute()
            vals = res.get('values', [])
            if not vals: continue
            content += f"\n--- Feuille: {s_title} ---\n"
            for row in vals: content += ", ".join([str(c) for c in row]) + "\n"
        
        return f"GSheet: {title}", content
    except Exception as e:
        log.error(f"Erreur GSheet {url}: {e}")
        return None, f"[Erreur (GSheet) {url}: {e}]\n"

@trace_action(source="loaders")
def fetch_web_content(url):
    try:
        if "github.com" in url and "/blob/" in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        
        log.info(f"Récupération Web: {url}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        source_name = f"Web: {url.split('/')[-1] if '/' in url else url}"
        return source_name, response.text
    except Exception as e:
        log.error(f"Erreur Web {url}: {e}")
        return None, f"[Erreur Web {url}: {e}]\n"

@trace_action(source="loaders")
def fetch_local_content(path):
    """Scanne un fichier ou un dossier local."""
    content_acc = ""
    path = os.path.abspath(path)
    name = os.path.basename(path)
    
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f"LocalFile: {name}", f.read()
        except Exception as e:
            return None, f"[Erreur Lecture {name}: {e}]"
            
    elif os.path.isdir(path):
        file_count = 0
        for root, _, files in os.walk(path):
            if any(x in root for x in [".git", "__pycache__", "venv", "env", "node_modules"]): continue
            
            for f in files:
                f_low = f.lower()
                # [OPTIMISATION RADICALE] Même filtrage que la database
                if f_low.endswith(('.json', '.log', '.lock', '.sqlite', '.txt')):
                    continue
                
                if any(k in f_low for k in ['debug', 'payload', 'usage', 'history']):
                    continue
                
                if f.endswith(SUPPORTED_FILE_EXTENSIONS):
                    full_p = os.path.join(root, f)
                    try:
                        with open(full_p, 'r', encoding='utf-8') as fh:
                            c = fh.read()
                            # Limite de taille pour éviter les monstres
                            if len(c) < 50000:
                                rel_p = os.path.relpath(full_p, path)
                                content_acc += f"\n--- {rel_p} ---\n{c}\n"
                                file_count += 1
                    except Exception: pass
        
        if not content_acc: return None, f"[Dossier vide: {name}]"
        return f"LocalDir: {name} ({file_count} files)", content_acc
        
    return None, f"[Chemin introuvable: {path}]"
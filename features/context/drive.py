import os
import json
import zipfile
import traceback
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

from config import (
    get_path, get_logger, KB_ZIP_NAME, 
    KB_DRIVE_FOLDER_NAME, sauvegarder_json
)
from features.Decorators import trace_action
# Import local pour éviter les cycles si on importe auth ici (auth est passé en paramètre généralement)
# Mais on a besoin de auth pour certaines opérations autonomes si on voulait.
# Ici on recoit le service en paramètre pour rester pur.

log = get_logger("Features.Context.Drive")

@trace_action(source="drive")
def get_cached_drive_file_id(cache_file_id_path):
    if os.path.exists(cache_file_id_path):
        try:
            with open(cache_file_id_path, 'r') as f:
                return json.load(f).get('file_id')
        except Exception:
            return None
    return None

@trace_action(source="drive")
def set_cached_drive_file_id(file_id, cache_file_id_path):
    sauvegarder_json(cache_file_id_path, {'file_id': file_id})

@trace_action(source="drive")
def get_or_create_folder_id(service, folder_name):
    """Cherche ou crée le dossier racine sur Drive."""
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    try:
        response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = response.get('files', [])

        if files:
            return files[0].get('id')
        else:
            file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
            folder = service.files().create(body=file_metadata, fields='id').execute()
            return folder.get('id')
    except Exception as e:
        log.error(f"Erreur dossier Drive: {e}")
        return None

@trace_action(source="drive")
def download_drive_file(service, file_id, local_db_base_path, cache_file_id_path):
    """Télécharge et décompresse l'archive KB."""
    temp_zip_path = get_path(KB_ZIP_NAME) 
    try:
        request = service.files().get_media(fileId=file_id)
        dest_dir = os.path.dirname(local_db_base_path)
        os.makedirs(dest_dir, exist_ok=True)
        
        with open(temp_zip_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                _, done = downloader.next_chunk()
        
        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)
        
        return True
    except HttpError as error:
        if error.resp.status == 404:
            log.warning("Fichier KB distant introuvable (404).")
            set_cached_drive_file_id(None, cache_file_id_path)
        return False
    except Exception as e:
        log.error(f"Erreur Download KB: {e}")
        return False
    finally:
        if os.path.exists(temp_zip_path):
            try: os.remove(temp_zip_path)
            except: pass

@trace_action(source="drive")
def upload_drive_file_worker(service, local_db_base_path, folder_id, cache_file_id_path):
    """Compresse (.sqlite, .faiss, .pkl) et upload."""
    temp_zip_path = get_path(KB_ZIP_NAME)
    dir_name = os.path.dirname(local_db_base_path)
    base_name = os.path.basename(local_db_base_path)
    
    files_to_zip = [f"{base_name}.sqlite", f"{base_name}.faiss", f"{base_name}.pkl"]

    try:
        with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files_to_zip:
                full_path = os.path.join(dir_name, file)
                if os.path.exists(full_path):
                    zipf.write(full_path, arcname=file)

        drive_file_id = get_cached_drive_file_id(cache_file_id_path)
        media = MediaFileUpload(temp_zip_path, mimetype='application/zip')
        
        if drive_file_id:
            # Update
            try:
                service.files().update(fileId=drive_file_id, media_body=media).execute()
                log.info(f"KB mise à jour (ID: {drive_file_id})")
            except HttpError:
                # Si l'ID est invalide, on retente en création
                drive_file_id = None
        
        if not drive_file_id:
            # Create
            file_metadata = {'name': KB_ZIP_NAME, 'parents': [folder_id]}
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            drive_file_id = file.get('id')
            set_cached_drive_file_id(drive_file_id, cache_file_id_path)
            log.info(f"KB créée (ID: {drive_file_id})")

        return True
    except Exception as e:
        log.error(f"Erreur Upload KB: {traceback.format_exc()}")
        return False
    finally:
        # Forçage fermeture media file handle implicite si nécessaire
        del media 
        if os.path.exists(temp_zip_path):
            try: os.remove(temp_zip_path)
            except: pass

@trace_action(source="drive")
def handle_delete_drive_kb(service, cache_file_id_path):
    """Supprime la base distante."""
    drive_file_id = get_cached_drive_file_id(cache_file_id_path)
    if not drive_file_id: return "Pas de fichier connu."
    try:
        service.files().delete(fileId=drive_file_id).execute()
        set_cached_drive_file_id(None, cache_file_id_path)
        return "Base distante supprimée."
    except Exception as e:
        return f"Erreur suppression: {e}"
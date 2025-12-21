import os
import re
import logging
import traceback
from . import database

from config import (
    get_logger, charger_json_robuste, 
    MAX_SEARCH_RESULTS, KB_DRIVE_FOLDER_NAME
)
# Imports internes au package
from .auth import get_google_services
from .drive import get_or_create_folder_id, upload_drive_file_worker, handle_delete_drive_kb as drive_delete
from .loaders import fetch_local_content, fetch_google_sheet_content, fetch_google_doc_content, fetch_web_content
from features.Decorators import trace_action

log = get_logger("Features.Context.RAG")

@trace_action(source="rag")
def chunk_text(source_name, full_text):
    chunks = []
    paragraphs = re.split(r'\n\s*\n', full_text)
    for para in paragraphs:
        content = para.strip()
        if len(content) > 50:
            chunk_hash = hash(f"{source_name}:{content}")
            chunks.append({
                "id": str(chunk_hash),
                "source": source_name,
                "content": content
            })
    return chunks

@trace_action(source="rag")
def handle_load_context(result_queue, db_path):
    """Vérifie l'état de la base locale au démarrage."""
    try:
        log.info(f"Vérification DB locale: {db_path}...")
        database.init_db(db_path)
        
        sqlite_path = f"{db_path.rstrip('/\\')}.sqlite"
        if os.path.exists(sqlite_path):
            return f"--- Base de connaissances ({os.path.basename(db_path)}) prête. ---"
        else:
            return f"--- Base de connaissances vide. Lancez l'indexation. ---"
    except Exception as e:
        log.error(f"Erreur load_context: {e}")
        return f"--- Erreur (load_context): {e} ---"

@trace_action(source="rag")
def handle_sync_kb_to_drive(result_queue, db_path, drive_folder_name, cache_file_id_path):
    try:
        result_queue.put({"type": "ui_update", "widget": "message", "text": "--- SYNCHRO DRIVE... ---"})
        service, _ = get_google_services(result_queue)
        if not service: return "--- Échec Auth Google ---"

        if not os.path.exists(f"{db_path.rstrip('/\\')}.sqlite"):
            return "--- Échec: DB vide ---"

        folder_id = get_or_create_folder_id(service, drive_folder_name)
        if upload_drive_file_worker(service, db_path, folder_id, cache_file_id_path):
            return "--- SYNCHRO DRIVE : Succès ---"
        return "--- SYNCHRO DRIVE : Échec Upload ---"
    except Exception as e:
        log.error(f"Erreur Sync: {e}")
        return f"--- Erreur Sync : {e} ---"

@trace_action(source="rag")
def handle_delete_drive_kb(result_queue, cache_file_id_path):
    """Wrapper pour la suppression Drive avec gestion UI."""
    try:
        result_queue.put({"type": "ui_update", "widget": "message", "text": "--- SUPPRESSION DRIVE... ---"})
        service, _ = get_google_services(result_queue)
        if not service: return "--- Erreur Auth ---"
        
        return drive_delete(service, cache_file_id_path)
    except Exception as e:
        return f"--- Erreur: {e} ---"

@trace_action(source="rag")
def handle_maj_contexte(result_queue, context_file_path, db_path, drive_folder_name, cache_file_id_path, session=None):
    """
    Orchestre l'indexation complète (Local -> Web -> Drive -> Vectorisation -> Upload).
    """
    try:
        liens = charger_json_robuste(context_file_path)
        if not liens: return "--- Aucun lien à indexer. ---"

        result_queue.put({"type": "ui_update", "widget": "message", "text": "--- INDEXATION : Auth Google... ---"})
        gdrive, gsheets = get_google_services(result_queue)
        # Note: gdrive peut être None si mode hors-ligne, on continue en local si possible ?
        # Pour simplifier, on exige Google si des liens Drive sont présents, sinon on continue.
        
        database.init_db(db_path)
        chunks_data = []
        
        result_queue.put({"type": "ui_update", "widget": "message", "text": f"--- INDEXATION : Traitement de {len(liens)} sources... ---"})

        for lien in liens:
            src, content = None, None
            
            if os.path.exists(lien):
                src, content = fetch_local_content(lien)
            elif "drive.google.com" in lien:
                if not gdrive: 
                    result_queue.put({"type": "ui_update", "widget": "message", "text": f"⚠️ Ignoré (Pas d'Auth): {lien}"})
                    continue
                if "spreadsheets" in lien: src, content = fetch_google_sheet_content(gsheets, lien)
                else: src, content = fetch_google_doc_content(gdrive, lien)
            else:
                src, content = fetch_web_content(lien)

            if src and content:
                for chunk in chunk_text(src, content):
                    chunks_data.append((chunk['id'], chunk['source'], chunk['content']))
            else:
                result_queue.put({"type": "ui_update", "widget": "message", "text": f"⚠️ Échec lecture: {lien}"})

        if not chunks_data: return "--- Erreur : Aucun contenu valide extrait. ---"

        result_queue.put({"type": "ui_update", "widget": "message", "text": f"--- VECTORISATION ({len(chunks_data)} chunks)... ---"})
        # Utiliser add_knowledge pour chaque chunk (compatibilité legacy)
        for chunk_id, source, content in chunks_data:
            database.add_knowledge(source, content, metadata={"chunk_id": chunk_id})

        # Synchro auto si service dispo
        if gdrive:
            return handle_sync_kb_to_drive(result_queue, db_path, drive_folder_name, cache_file_id_path)
        return "--- INDEXATION LOCALE TERMINÉE (Pas de Sync Drive) ---"

    except Exception as e:
        log.error(f"Crash Indexation: {traceback.format_exc()}")
        return f"--- Erreur Fatale Indexation : {e} ---"

@trace_action(source="rag")
def handle_chat_rag_hybrid(prompt, session, db_path):
    """Effectue la recherche RAG hybride et interroge l'IA."""
    log.info(f"RAG: Recherche hybride pour '{prompt[:20]}...'")
    
    # Utiliser la recherche hybride (FAISS + FTS5 avec RRF)
    results, err = database.search_hybrid(prompt, db_path, max_results=MAX_SEARCH_RESULTS, use_hybrid=True)
    
    if err:
        log.warning(f"Erreur recherche hybride: {err}, fallback recherche vectorielle")
        results, _ = database.search_vector_db(prompt, db_path, max_results=MAX_SEARCH_RESULTS)
    
    context_txt = ""
    if results:
        context_txt = "\n--- CONTEXTE PERTINENT (RAG Hybride) ---\n"
        for i, (source, content, score) in enumerate(results, 1):
            context_txt += f"\n[{i}] Source: {source} (Score: {score:.4f})\n{content[:500]}...\n"
    
    final_prompt = (
        f"Réponds à la question en utilisant le contexte ci-dessous (si pertinent).\n"
        f"{context_txt}\n\n"
        f"--- QUESTION ---\n{prompt}"
    )
    return session.send_message(final_prompt)
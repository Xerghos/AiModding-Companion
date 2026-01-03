"""
Moteur de base de données sémantique omniscient utilisant sqlite-vec.
Version V6 : Pipeline Streaming TOTAL (Scan -> I/O -> Encode -> DB).
Optimisation Windows/Ryzen : Démarrage instantané, zéro latence de scan.
"""

import os
import logging
import sqlite3
import sqlite_vec
import numpy as np
import threading
import hashlib
import time
import queue
from typing import Dict, Optional, List, Tuple, Any, Callable
from concurrent.futures import ThreadPoolExecutor

from config import get_logger, get_path, SUPPORTED_FILE_EXTENSIONS
from features.Decorators import trace_action

# Initialisation hardware
try:
    import ai_core.hardware_init
except ImportError:
    pass

log = get_logger("features.context.database")

# --- Constantes ---
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
DB_DIR = "db"
DB_NAME = "knowledge_base_omniscient_V4"

# --- Variables Globales ---
_ensure_libs_lock = threading.Lock()
_init_db_lock = threading.Lock()
SentenceTransformer = None
model = None
_db_initialized = False

# --- Fonctions API ---

@trace_action(source="database")
def _get_db_path():
    base = get_path(DB_DIR)
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"{DB_NAME}.sqlite")

@trace_action(source="database")
def _get_paths(db_path_base=None):
    db_path = db_path_base or _get_db_path()
    return (db_path, None, None)

def get_connection(db_path_base=None):
    db_path = db_path_base or _get_db_path()
    abs_db_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(abs_db_path), exist_ok=True)
    conn = sqlite3.connect(abs_db_path, timeout=60.0)
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except:
        sqlite_vec.load(conn)
    return conn

@trace_action(source="database")
def _ensure_model():
    global SentenceTransformer, model
    if model is not None: return

    with _ensure_libs_lock:
        if SentenceTransformer is None:
            try:
                import transformers
                from sentence_transformers import SentenceTransformer as ST
                SentenceTransformer = ST
            except Exception as e:
                log.error(f"❌ Erreur import IA : {e}")
                return

        if model is None:
            log.info(f"Chargement modèle Embedding : {EMBEDDING_MODEL_NAME}...")
            try:
                import torch
                # Force CPU pour stabilité maximale et parallélisme AVX-512
                device = "cpu"
                log.info("⚙️ Mode CPU forcé (Zen 4 Optimized)")
                base_model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
                
                # Quantification native INT8
                try:
                    base_model = torch.quantization.quantize_dynamic(
                        base_model, {torch.nn.Linear}, dtype=torch.qint8
                    )
                    log.info("✅ Modèle quantifié INT8")
                except: pass

                model = base_model
            except Exception as e:
                log.error(f"❌ Erreur _ensure_model : {e}")
                raise

@trace_action(source="database")
def init_db(db_path_base=None):
    global _db_initialized
    if _db_initialized and db_path_base is None: return

    with _init_db_lock:
        conn = get_connection(db_path_base)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        
        cursor.execute('CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, checksum TEXT, last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, file_id INTEGER, chunk_index INTEGER DEFAULT 0, 
                content TEXT, ast_type TEXT, start_line INTEGER, end_line INTEGER, 
                parent_context TEXT, metadata TEXT,
                FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE)
        ''')
        cursor.execute(f'CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[{EMBEDDING_DIM}])')
        try: cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(content, tokenize='trigram')")
        except: pass

        conn.commit()
        conn.close()
        if db_path_base is None: _db_initialized = True

@trace_action(source="database")
def index_project_files(root_path: str, progress_callback=None, use_semantic_chunking=True, **kwargs):
    """
    Indexation V6 : Pipeline Streaming TOTAL (Scan -> I/O -> Encode -> DB).
    Optimisation : Le Scan alimente la queue d'I/O en temps réel.
    """
    from .merkle_sync import MerkleTreeSync
    from .code_chunker import get_chunker
    from features.gitignore_parser import parse_gitignore
    from config.settings import APP_SETTINGS
    
    init_db()
    log.info(f"🚀 Début Indexation V6 (Full Streaming) : {root_path}")
    
    chunker = get_chunker()
    _ensure_model() # Préchauffage modèle AVANT le scan pour ne pas bloquer

    # --- PIPELINE COMPONENTS ---
    
    # file_queue: fpath (Scan -> I/O)
    file_queue = queue.Queue(maxsize=2000)
    # chunk_queue: (fpath, rel, checksum, [chunks]) (I/O -> Encoder)
    chunk_queue = queue.Queue(maxsize=1000)
    # write_queue: (file_data, vector_data) (Encoder -> Writer)
    write_queue = queue.Queue(maxsize=1000)
    
    # Stats
    stats = {'files_scanned': 0, 'files_read': 0, 'chunks_encoded': 0, 'db_writes': 0}
    
    # --- STAGE 1: SCANNER (Thread) ---
    def scanner_thread():
        gitignore_path = os.path.join(root_path, ".gitignore")
        matches_gitignore = parse_gitignore(gitignore_path) if os.path.exists(gitignore_path) else lambda x: False
        
        critical_dirs = {'.git', '__pycache__', 'venv', 'node_modules', 'db', 'logs', 'dist', 'build', 'audio_cache', '.vscode', '.idea'}
        watch_list = APP_SETTINGS.get("repo_map_cache", {}).get("watch_files", [])
        normalized_watch_list = [os.path.normpath(os.path.join(root_path, w)).lower() for w in watch_list]
        
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in critical_dirs]
            for file in files:
                fpath = os.path.join(root, file)
                
                # 1. Check Watchlist
                if os.path.normpath(fpath).lower() in normalized_watch_list:
                    file_queue.put(fpath)
                    stats['files_scanned'] += 1
                    continue
                
                # 2. Check Gitignore
                if matches_gitignore(fpath): continue
                
                # 3. Check Extension
                valid_exts = SUPPORTED_FILE_EXTENSIONS + ('.py', '.md', '.txt', '.js', '.json', '.html', '.css', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp', '.rs', '.go', '.sh', '.bat', '.ps1', '.yaml', '.yml', '.toml', '.xml', '.sql', '.ini', '.cfg')
                if not fpath.lower().endswith(valid_exts):
                    try: 
                        if os.path.getsize(fpath) > 1024 * 1024: continue
                    except: continue
                
                file_queue.put(fpath)
                stats['files_scanned'] += 1
        
        # Signal de fin pour les I/O workers (on en envoie autant que de workers)
        # Mais comme on utilise un ThreadPool, on ne peut pas envoyer de signal de fin direct dans la queue
        # car on ne sait pas quel thread prendra quoi.
        # Solution: On utilise un "poison pill" unique et le consumer gère.
        # OU MIEUX : Le thread I/O Manager détecte que scanner est fini et que la queue est vide.
        pass # Le thread s'arrête simplement

    # --- STAGE 2: I/O MANAGER (Thread) ---
    def io_manager_thread():
        # Lance les workers I/O et distribue le travail
        # Attend que le scanner ait fini ET que la queue soit vide
        
        def process_file_task(fpath):
            try:
                rel = os.path.relpath(fpath, root_path)
                with open(fpath, 'rb') as f: data = f.read()
                if b'\0' in data[:8000]: return
                checksum = hashlib.sha256(data).hexdigest()
                text = data.decode('utf-8', errors='ignore')
                chunks = chunker.chunk_file(fpath) if use_semantic_chunking and fpath.endswith('.py') else [{'content': text}]
                chunk_queue.put((fpath, rel, checksum, chunks))
                stats['files_read'] += 1
            except Exception: pass

        with ThreadPoolExecutor(max_workers=8) as executor:
            while True:
                try:
                    # On attend un fichier avec timeout pour vérifier si le scan est fini
                    fpath = file_queue.get(timeout=0.1)
                    executor.submit(process_file_task, fpath)
                except queue.Empty:
                    if not t_scan.is_alive():
                        break
        
        # Quand tout est soumis et fini
        chunk_queue.put(None) # Signal pour l'encodeur

    # --- STAGE 3: ENCODER (Thread) ---
    def encoder_thread():
        batch_size = 64
        current_batch_files = []
        current_batch_texts = []
        
        while True:
            item = chunk_queue.get()
            if item is None:
                if current_batch_texts:
                    process_encoding_batch(current_batch_files, current_batch_texts)
                write_queue.put(None)
                break
            
            fpath, rel, checksum, chunks = item
            for ch in chunks:
                txt = ch.get('content', '').strip()
                if txt:
                    current_batch_texts.append(txt)
                    current_batch_files.append((fpath, rel, checksum, ch))
            
            if len(current_batch_texts) >= batch_size:
                process_encoding_batch(current_batch_files, current_batch_texts)
                current_batch_files = []
                current_batch_texts = []

    def process_encoding_batch(meta_list, text_list):
        if not text_list: return
        try:
            vectors = model.encode(text_list, batch_size=len(text_list), convert_to_numpy=True, show_progress_bar=False)
            write_queue.put((meta_list, vectors))
            stats['chunks_encoded'] += len(vectors)
            if progress_callback and stats['chunks_encoded'] % 50 == 0:
                progress_callback(f"Indexation V6 : {stats['chunks_encoded']} chunks...")
        except Exception as e:
            log.error(f"Erreur Encodage : {e}")

    # --- STAGE 4: WRITER (Thread) ---
    def writer_thread():
        conn = get_connection()
        cursor = conn.cursor()
        file_id_cache = {}
        cursor.execute("DELETE FROM files") 
        conn.commit()
        
        while True:
            item = write_queue.get()
            if item is None:
                conn.commit()
                conn.close()
                break
            
            meta_list, vectors = item
            
            files_to_insert = {}
            for _, rel, checksum, _ in meta_list:
                if rel not in file_id_cache:
                    files_to_insert[rel] = checksum
            
            if files_to_insert:
                for rel, checksum in files_to_insert.items():
                    cursor.execute("INSERT INTO files (path, checksum) VALUES (?, ?)", (rel, checksum))
                    file_id_cache[rel] = cursor.lastrowid
            
            for (fpath, rel, checksum, ch), vec in zip(meta_list, vectors):
                fid = file_id_cache.get(rel)
                if not fid: continue # Should not happen
                
                params = {
                    'fid': fid, 'idx': 0, 'cnt': ch['content'], 'ast': ch.get('ast_type'),
                    'sl': ch.get('start_line'), 'el': ch.get('end_line'),
                    'pc': ch.get('parent_context'), 'meta': ch.get('metadata')
                }
                cursor.execute('''INSERT INTO chunks (file_id, chunk_index, content, ast_type, start_line, end_line, parent_context, metadata) VALUES (:fid, :idx, :cnt, :ast, :sl, :el, :pc, :meta)''', params)
                cid = cursor.lastrowid
                cursor.execute("INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)", (cid, vec.tobytes()))
                try: cursor.execute("INSERT INTO fts_chunks(rowid, content) VALUES (?, ?)", (cid, ch['content']))
                except: pass
            
            conn.commit()
            stats['db_writes'] += 1

    # --- ORCHESTRATION ---
    t_scan = threading.Thread(target=scanner_thread, daemon=True)
    t_io = threading.Thread(target=io_manager_thread, daemon=True)
    t_enc = threading.Thread(target=encoder_thread, daemon=True)
    t_write = threading.Thread(target=writer_thread, daemon=True)
    
    t_scan.start()
    t_io.start()
    t_enc.start()
    t_write.start()
    
    t_scan.join()
    t_io.join()
    t_enc.join()
    t_write.join()
    
    try:
        state_file = get_path("db/merkle_state_v4.json")
        MerkleTreeSync(root_path).save_state(state_file)
    except: pass

    log.info(f"✅ Indexation V6 Terminé : {stats['files_scanned']} fichiers scannés.")
    return f"Succès V6 : {stats['files_scanned']} fichiers."

# --- Autres Exports ---

def _add_chunks_batch(file_id: int, chunks_data: List[Dict]):
    _ensure_model()
    if not chunks_data or not model: return 0
    texts = [c.get('content', '') for c in chunks_data]
    vectors = model.encode(texts, convert_to_numpy=True)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        count = 0
        for i, (chunk, vector) in enumerate(zip(chunks_data, vectors)):
            params = {'file_id': file_id, 'chunk_index': i, 'content': chunk['content'], 'ast_type': chunk.get('ast_type'), 'start_line': chunk.get('start_line'), 'end_line': chunk.get('end_line'), 'parent_context': chunk.get('parent_context'), 'metadata': chunk.get('metadata')}
            cursor.execute('''INSERT INTO chunks (file_id, chunk_index, content, ast_type, start_line, end_line, parent_context, metadata) VALUES (:file_id, :chunk_index, :content, :ast_type, :start_line, :end_line, :parent_context, :metadata)''', params)
            cid = cursor.lastrowid
            cursor.execute("INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)", (cid, vector.tobytes()))
            try: cursor.execute("INSERT INTO fts_chunks(rowid, content) VALUES (?, ?)", (cid, chunk['content']))
            except: pass
            count += 1
        conn.commit()
        return count
    finally: conn.close()

def search_hybrid(query: str, db_path_base=None, limit: int = 20, **kwargs):
    _ensure_model()
    init_db(db_path_base)
    if not model: return [], "Modèle non chargé"
    try:
        query_vec = model.encode([query])[0]
        conn = get_connection(db_path_base)
        cursor = conn.cursor()
        cursor.execute('SELECT chunk_id, distance FROM vec_chunks WHERE embedding MATCH ? AND k = 50 ORDER BY distance ASC', (query_vec.tobytes(),))
        vec_results = cursor.fetchall()
        scores = {}
        for i, (cid, _) in enumerate(vec_results): scores[cid] = scores.get(cid, 0) + (1.0 / (60 + i + 1))
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        final = []
        for cid, score in sorted_ids:
            cursor.execute('SELECT f.path, c.content, c.ast_type, c.start_line FROM chunks c JOIN files f ON f.id = c.file_id WHERE c.id = ?', (cid,))
            row = cursor.fetchone()
            if row: final.append((row[0], row[1], score, row[2], row[3]))
        conn.close()
        return final, None
    except Exception as e: return [], str(e)

def search_vector_db(query, db_path_base=None, max_results=5): return search_hybrid(query, db_path_base, limit=max_results)
def store_memory(text: str, metadata: Dict = None):
    init_db(); conn = get_connection(); cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO files (path, checksum) VALUES (?, ?)", ("memory://global", "0")); fid = cursor.lastrowid
    conn.commit(); conn.close()
    return _add_chunks_batch(fid, [{'content': text, 'ast_type': 'memory'}])
def search_memories(query: str, n_results=3, **kwargs):
    res, _ = search_hybrid(query, limit=n_results)
    return [r for r in res if r[0] == "memory://global"][:n_results]
def is_model_ready(): return model is not None
def warmup_model_background(): threading.Thread(target=_ensure_model, daemon=True, name="ModelWarmup").start()
def delete_local_db():
    global _db_initialized; p = _get_db_path()
    if os.path.exists(p): 
        try:
            _db_initialized = False
            for ext in ['', '-wal', '-shm']: 
                if os.path.exists(p + ext): os.remove(p + ext)
            return "✅ Base V4 supprimée."
        except Exception as e: return f"❌ Erreur : {e}"
    return "Néant."
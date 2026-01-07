"""
Moteur de base de données sémantique omniscient utilisant sqlite-vec.
Version V8.6 : APOGÉE PERFORMANCE (15s Target).
Optimisation : PyTorch INT8 AVX-512, 4 Workers I/O, Batch 32, Buffer 5000.
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
    """Restauré pour assurer la compatibilité avec symbol_graph et repo_map."""
    db_path = db_path_base or _get_db_path()
    return (db_path, None, None)

def get_connection(db_path_base=None, fast_mode=False):
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
    
    if fast_mode:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=MEMORY;")
        cursor.execute("PRAGMA synchronous=OFF;")
        cursor.execute("PRAGMA locking_mode=EXCLUSIVE;")
        cursor.execute("PRAGMA cache_size=100000;") 
    return conn

def normalize_path(path):
    """Normalisation absolue et minuscule pour comparaison robuste sur Windows."""
    return os.path.abspath(os.path.normpath(path)).lower()

def _get_hardware_snap():
    """Capture ultra-légère de l'état CPU/RAM."""
    try:
        import psutil
        proc = psutil.Process()
        ram_mb = proc.memory_info().rss / (1024 * 1024)
        cpu_pct = psutil.cpu_percent(interval=None)
        return ram_mb, cpu_pct
    except: return 0, 0

def _generate_autopsy(total_time, timers, stats):
    """Analyse les chronomètres pour identifier le goulot d'étranglement."""
    report = [f"\n🏆 [AUTOPSIE] Indexation finie en {total_time:.1f}s"]
    
    # Calcul des parts relatives
    parts = {
        "Scan": timers.get('scan', 0),
        "I/O & Chunking": timers.get('io', 0),
        "IA (Encodage)": timers.get('encode', 0),
        "DB (Écriture)": timers.get('write', 0)
    }
    
    main_bottleneck = max(parts, key=parts.get)
    bottleneck_pct = (parts[main_bottleneck] / total_time) * 100 if total_time > 0 else 0
    
    report.append(f"📍 Goulot principal : {main_bottleneck} ({bottleneck_pct:.1f}%)")
    
    # Recommandations intelligentes
    if main_bottleneck == "IA (Encodage)":
        report.append("💡 Conseil : Augmentez 'inference_batch_size' ou tentez l'accélération ONNX.")
    elif main_bottleneck == "I/O & Chunking":
        report.append("💡 Conseil : Votre CPU semble peiner sur le parsing Tree-sitter ou le disque est lent.")
    elif main_bottleneck == "DB (Écriture)":
        report.append("💡 Conseil : Conflit d'accès SQLite détecté. Fermez les autres outils de DB.")
        
    report.append(f"📊 Débit moyen : {stats['encoded']/total_time:.1f} seg/s ({stats['scanned']} fichiers)")
    return "\n".join(report)

def is_path_exception(path: str, normalized_watch_list: List[str]) -> Tuple[bool, bool]:
    """
    Vérifie si un chemin est une exception ou mène à une exception.
    Retourne (est_inclus, doit_parcourir).
    """
    p = normalize_path(path)
    for w in normalized_watch_list:
        # Match exact ou enfant (Inclusion directe)
        if p == w or p.startswith(w + os.sep):
            return True, True
        # Parent d'une exception (Doit entrer pour trouver l'enfant)
        if w.startswith(p + os.sep):
            return False, True
    return False, False

@trace_action(source="database")
def _ensure_model():
    global SentenceTransformer, model
    from config.settings import APP_SETTINGS
    
    with _ensure_libs_lock:
        if model is not None: return
        if SentenceTransformer is None:
            try:
                from sentence_transformers import SentenceTransformer as ST
                SentenceTransformer = ST
            except Exception: return
            
        use_onnx = APP_SETTINGS.get("system_settings", {}).get("use_onnx_acceleration", False)
        
        try:
            import torch
            if use_onnx:
                # --- MODE ONNX (EXPERIMENTAL) ---
                log.info("🚀 Tentative d'activation du backend ONNX...")
                try:
                    model = SentenceTransformer(
                        EMBEDDING_MODEL_NAME, 
                        backend="onnx",
                        model_kwargs={"file_name": "onnx/model_qint8_avx512.onnx"}
                    )
                    log.info("✅ Backend ONNX chargé.")
                except Exception as e:
                    log.warning(f"⚠️ Échec ONNX ({e}). Fallback PyTorch...")
                    use_onnx = False
            
            if not use_onnx:
                # --- MODE PYTORCH (PROVEN FAST - 15s) ---
                log.info(f"Chargement modèle PyTorch : {EMBEDDING_MODEL_NAME}...")
                
                # On force le parallélisme PyTorch AVANT le chargement
                if hasattr(torch, 'set_num_threads'):
                    torch.set_num_threads(os.cpu_count())
                
                base_model = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu")
                try:
                    # Quantification Dynamique
                    base_model = torch.quantization.quantize_dynamic(base_model, {torch.nn.Linear}, dtype=torch.qint8)
                    log.info("✅ Modèle PyTorch quantifié INT8 (AVX-512 Optimized)")
                except: pass
                model = base_model
                
        except Exception as e:
            log.error(f"❌ Erreur critique modèle : {e}")

@trace_action(source="database")
def init_db(db_path_base=None):
    global _db_initialized
    if _db_initialized and db_path_base is None: return
    with _init_db_lock:
        conn = get_connection(db_path_base, fast_mode=True)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute('CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, checksum TEXT, last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        cursor.execute('''CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id INTEGER, chunk_index INTEGER DEFAULT 0, content TEXT, ast_type TEXT, start_line INTEGER, end_line INTEGER, parent_context TEXT, metadata TEXT, FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE)''')
        cursor.execute(f'CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[{EMBEDDING_DIM}])')
        try: cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(content, tokenize='trigram')")
        except: pass
        conn.commit(); conn.close()
        if db_path_base is None: _db_initialized = True

@trace_action(source="database")
def index_project_files(root_path: str, progress_callback=None, use_semantic_chunking=True, **kwargs):
    from .code_chunker import get_chunker
    from features.gitignore_parser import parse_gitignore
    from config.settings import APP_SETTINGS
    import gc
    
    overall_start = time.time()
    init_db()
    _ensure_model()
    chunker = get_chunker()

    db_config = APP_SETTINGS.get("database_settings", {})
    queue_size = int(db_config.get("indexing_queue_size", 1000))
    batch_size = int(db_config.get("inference_batch_size", 64))

    file_queue = queue.Queue(maxsize=5000)
    chunk_queue = queue.Queue(maxsize=queue_size)
    write_queue = queue.Queue(maxsize=5000)
    
    timers = {'scan': 0, 'io': 0, 'encode': 0, 'write': 0}
    stats = {'scanned': 0, 'read': 0, 'encoded': 0}
    
    # [LOGS V9.1] Thread Heartbeat
    stop_event = threading.Event()
    def heartbeat_thread():
        while not stop_event.is_set():
            time.sleep(3) # Pulse toutes les 3s pour être discret
            ram, cpu = _get_hardware_snap()
            q_io = chunk_queue.qsize()
            q_db = write_queue.qsize()
            print(f"💓 [HB] RAM: {ram:.0f}MB | CPU: {cpu:.0f}% | Queue_IO: {q_io} | Queue_DB: {q_db}", flush=True)

    hb = threading.Thread(target=heartbeat_thread, daemon=True)
    hb.start()

    def scanner_thread():
        start = time.time()
        gitignore_path = os.path.join(root_path, ".gitignore")
        matches_gitignore = parse_gitignore(gitignore_path) if os.path.exists(gitignore_path) else lambda x: False
        critical_dirs = {'.git', '__pycache__', 'venv', 'node_modules', 'db', 'logs', 'dist', 'build', 'audio_cache', '.vscode', '.idea'}
        ignored_folders = set(APP_SETTINGS.get("code_analysis", {}).get("ignored_folders", []))
        
        watch_list = APP_SETTINGS.get("repo_map_cache", {}).get("watch_files", [])
        normalized_watch_list = [normalize_path(os.path.join(root_path, w)) for w in watch_list]

        for root, dirs, files in os.walk(root_path):
            root_abs = os.path.abspath(root)
            new_dirs = []
            for d in dirs:
                dpath = os.path.join(root_abs, d)
                is_exc, should_walk = is_path_exception(dpath, normalized_watch_list)
                if should_walk or (d not in critical_dirs and d not in ignored_folders and not matches_gitignore(dpath)):
                    new_dirs.append(d)
            dirs[:] = new_dirs
            
            for file in files:
                fpath = os.path.join(root_abs, file)
                is_exc, _ = is_path_exception(fpath, normalized_watch_list)
                
                if is_exc:
                    file_queue.put(fpath)
                    stats['scanned'] += 1
                    continue
                
                if matches_gitignore(fpath): continue
                
                valid_exts = SUPPORTED_FILE_EXTENSIONS + ('.py', '.md', '.txt', '.js', '.json', '.html', '.css', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp', '.rs', '.go', '.sh', '.bat', '.ps1', '.yaml', '.yml', '.toml', '.xml', '.sql', '.ini', '.cfg')
                if not fpath.lower().endswith(valid_exts):
                    try: 
                        if os.path.getsize(fpath) > 1024 * 1024: continue
                    except: continue
                
                file_queue.put(fpath)
                stats['scanned'] += 1
        
        file_queue.put(None)
        timers['scan'] = time.time() - start
        print(f"DEBUG: [SCAN] Fini en {timers['scan']:.2f}s ({stats['scanned']} fichiers)", flush=True)

    def io_thread():
        start = time.time()
        def task(fpath):
            try:
                rel = os.path.relpath(fpath, root_path)
                with open(fpath, 'rb') as f: data = f.read()
                if b'\0' in data[:8000]: return
                checksum = hashlib.sha256(data).hexdigest()
                text = data.decode('utf-8', errors='ignore')
                chunks = chunker.chunk_file(fpath) if use_semantic_chunking and fpath.endswith('.py') else [{'content': text}]
                
                t_put_start = time.time()
                chunk_queue.put((fpath, rel, checksum, chunks))
                put_duration = time.time() - t_put_start
                
                # [LOGS V9.2] Détection Backpressure
                if put_duration > 0.5:
                    print(f"⚠️ [FLOW] Backpressure : Disque bloqué par l'IA pendant {put_duration:.1f}s (IA trop lente)", flush=True)
                
                stats['read'] += 1
            except: pass
        
        # [PROVEN FAST] 4 workers I/O pour laisser le CPU à l'encodeur
        with ThreadPoolExecutor(max_workers=4) as executor:
            while True:
                fpath = file_queue.get()
                if fpath is None: break
                executor.submit(task, fpath)
        chunk_queue.put(None)
        timers['io'] = time.time() - start
        print(f"DEBUG: [I/O] Fini en {timers['io']:.2f}s", flush=True)

    def encoder_thread():
        start = time.time()
        cur_meta, cur_texts = [], []
        segments_since_gc = 0
        
        while True:
            try:
                t_wait_start = time.time()
                item = chunk_queue.get(timeout=0.01)
                wait_duration = time.time() - t_wait_start
                
                # [LOGS V9.2] Détection Starvation
                if wait_duration > 0.5:
                    print(f"⚠️ [FLOW] Starvation : IA en attente de données pendant {wait_duration:.1f}s (Disque trop lent)", flush=True)

                if item is None:
                    if cur_texts: encode_now(cur_meta, cur_texts)
                    write_queue.put(None); break
                fpath, rel, checksum, chunks = item
                for ch in chunks:
                    txt = ch.get('content', '').strip()
                    if txt:
                        cur_texts.append(txt); cur_meta.append((fpath, rel, checksum, ch))
                
                if len(cur_texts) >= batch_size:
                    encode_now(cur_meta, cur_texts)
                    segments_since_gc += len(cur_texts)
                    cur_meta, cur_texts = [], []
                    
                    # [MODIF V9.0] Nettoyage RAM périodique
                    if segments_since_gc >= 1000:
                        gc.collect()
                        segments_since_gc = 0
                        
            except queue.Empty:
                if cur_texts: 
                    encode_now(cur_meta, cur_texts); cur_meta, cur_texts = [], []
        timers['encode'] = time.time() - start
        print(f"DEBUG: [ENCODE] Fini en {timers['encode']:.2f}s", flush=True)

    def encode_now(meta, texts):
        try:
            vecs = model.encode(texts, batch_size=len(texts), convert_to_numpy=True, show_progress_bar=False)
            write_queue.put((meta, vecs))
            stats['encoded'] += len(vecs)
            if progress_callback: progress_callback(f"Analyse IA : {stats['encoded']} segments...")
        except Exception as e: log.error(f"Error Encoding: {e}")

    def writer_thread():
        start = time.time()
        conn = get_connection(fast_mode=True)
        cursor = conn.cursor()
        file_id_cache = {}
        cursor.execute("BEGIN TRANSACTION")
        
        # [MODIF V9.3] On garde la transaction unique pour la performance
        # mais on ajoute un log clair pour le commit final.
        while True:
            item = write_queue.get()
            if item is None: break
            meta, vecs = item
            vbatch = []
            for (fpath, rel, checksum, ch), vec in zip(meta, vecs):
                if rel not in file_id_cache:
                    cursor.execute("INSERT INTO files (path, checksum) VALUES (?, ?)", (rel, checksum))
                    file_id_cache[rel] = cursor.lastrowid
                fid = file_id_cache[rel]
                cursor.execute('''INSERT INTO chunks (file_id, chunk_index, content, ast_type, start_line, end_line, parent_context, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (fid, 0, ch['content'], ch.get('ast_type'), ch.get('start_line'), ch.get('end_line'), ch.get('parent_context'), ch.get('metadata')))
                vbatch.append((cursor.lastrowid, vec.tobytes()))
            cursor.executemany("INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)", vbatch)
        
        print("💾 [DB] Synchronisation finale sur le disque (Commit)...", flush=True)
        conn.commit()
        conn.close()
        timers['write'] = time.time() - start
        print(f"DEBUG: [DB] Écriture disque terminée en {timers['write']:.2f}s", flush=True)

    ts = [threading.Thread(target=scanner_thread, name="Scanner"), 
          threading.Thread(target=io_thread, name="IO"), 
          threading.Thread(target=encoder_thread, name="Encoder"), 
          threading.Thread(target=writer_thread, name="Writer")]
    for t in ts: t.start()
    for t in ts: t.join()
    
    # Arrêt du monitoring
    stop_event.set()
    
    total = time.time() - overall_start
    autopsy = _generate_autopsy(total, timers, stats)
    print(autopsy, flush=True)
    log.info(f"📊 SUMMARY V9.1: {total:.2f}s | Scan:{timers['scan']:.1f}s | IO:{timers['io']:.1f}s | Enc:{timers['encode']:.1f}s")
    return f"Indexation terminée en {total:.1f}s."

# --- Autres Fonctions ---

def _add_chunks_batch(file_id: int, chunks_data: List[Dict]):
    _ensure_model()
    if not chunks_data or not model: return 0
    texts = [c.get('content', '') for c in chunks_data]
    vectors = model.encode(texts, convert_to_numpy=True)
    conn = get_connection(fast_mode=True); cursor = conn.cursor()
    try:
        for i, (chunk, vector) in enumerate(zip(chunks_data, vectors)):
            cursor.execute('''INSERT INTO chunks (file_id, chunk_index, content, ast_type, start_line, end_line, parent_context, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (file_id, i, chunk['content'], chunk.get('ast_type'), chunk.get('start_line'), chunk.get('end_line'), chunk.get('parent_context'), chunk.get('metadata')))
            cursor.execute("INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)", (cursor.lastrowid, vector.tobytes()))
        conn.commit()
        return len(chunks_data)
    finally: conn.close()

def search_hybrid(query: str, db_path_base=None, limit: int = 20, **kwargs):
    _ensure_model(); init_db(db_path_base)
    if not model: return [], "Modèle non chargé"
    try:
        query_vec = model.encode([query])[0]
        conn = get_connection(db_path_base); cursor = conn.cursor()
        cursor.execute('SELECT chunk_id, distance FROM vec_chunks WHERE embedding MATCH ? AND k = 50 ORDER BY distance ASC', (query_vec.tobytes(),))
        vec_results = cursor.fetchall(); scores = {}
        for i, (cid, _) in enumerate(vec_results): scores[cid] = scores.get(cid, 0) + (1.0 / (60 + i + 1))
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        final = []
        for cid, score in sorted_ids:
            cursor.execute('SELECT f.path, c.content, c.ast_type, c.start_line FROM chunks c JOIN files f ON f.id = c.file_id WHERE c.id = ?', (cid,))
            row = cursor.fetchone()
            if row: final.append((row[0], row[1], score, row[2], row[3]))
        conn.close(); return final, None
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


def calculate_indexing_stats(root_path: str, settings: dict) -> dict:


    """


    Calcule les statistiques d'indexation sans traiter les fichiers.


    Simule un scan os.walk complet en appliquant exactement la même logique que scanner_thread.


    """


    from features.gitignore_parser import parse_gitignore


    from config import SUPPORTED_FILE_EXTENSIONS


    


    stats = {"included": 0, "excluded": 0, "bypassed": 0}


    if not os.path.exists(root_path): return stats


    


    gitignore_path = os.path.join(root_path, ".gitignore")


    matches_gitignore = parse_gitignore(gitignore_path) if os.path.exists(gitignore_path) else lambda x: False


    critical_dirs = {'.git', '__pycache__', 'venv', 'node_modules', 'db', 'logs', 'dist', 'build', 'audio_cache', '.vscode', '.idea'}


    ignored_folders = set(settings.get("code_analysis", {}).get("ignored_folders", []))


    watch_list = settings.get("repo_map_cache", {}).get("watch_files", [])


    normalized_watch_list = [normalize_path(os.path.join(root_path, w)) for w in watch_list]


    


    supported_extensions = SUPPORTED_FILE_EXTENSIONS + ('.py', '.md', '.txt', '.js', '.json', '.html', '.css',


                                                       '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',


                                                       '.rs', '.go', '.sh', '.bat', '.ps1', '.yaml', '.yml',


                                                       '.toml', '.xml', '.sql', '.ini', '.cfg')


    


    for root, dirs, files in os.walk(root_path):


        root_abs = os.path.abspath(root)


        new_dirs = []


        for d in dirs:


            dpath = os.path.join(root_abs, d)


            is_exc, should_walk = is_path_exception(dpath, normalized_watch_list)


            if should_walk or (d not in critical_dirs and d not in ignored_folders and not matches_gitignore(dpath)):


                new_dirs.append(d)


        dirs[:] = new_dirs


        


        for file in files:


            fpath = os.path.join(root_abs, file)


            is_exc, _ = is_path_exception(fpath, normalized_watch_list)


            


            if is_exc:


                stats["bypassed"] += 1


                stats["included"] += 1 # Cumulatif : l'exception EST incluse


                continue


            


            if matches_gitignore(fpath) or not fpath.lower().endswith(supported_extensions):


                stats["excluded"] += 1


                continue


            


            stats["included"] += 1


    


    return stats


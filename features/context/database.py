"""
Moteur de base de données sémantique omniscient utilisant sqlite-vec.
Version ultra-stable V4 optimisée pour Ryzen AI (GPU Radeon 780M).
Correction : Autorisations SQLite, Signatures API et Robustesse.
"""

import os
import logging
import sqlite3
import sqlite_vec
import numpy as np
import threading
import hashlib
import time
import json
from typing import Dict, Optional, List, Tuple, Any

from config import get_logger, get_path, SUPPORTED_FILE_EXTENSIONS
from features.Decorators import trace_action

# Initialisation hardware (Filtres warnings)
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

# --- Fonctions de compatibilité API (Fix ImportError) ---

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

def get_connection(db_path_base=None):
    """Crée une connexion SQLite avec l'extension vec chargée."""
    db_path = db_path_base or _get_db_path()
    abs_db_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(abs_db_path), exist_ok=True)
    
    # Timeout 60s pour éviter les verrous
    conn = sqlite3.connect(abs_db_path, timeout=60.0)
    
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception as e:
        log.warning(f"⚠️ Autorisation extension SQLite dégradée : {e}")
        try:
            sqlite_vec.load(conn)
        except:
            log.error("❌ Échec critique chargement sqlite-vec")
            
    return conn

# --- Gestion du Modèle et Accélération ---

@trace_action(source="database")
def _ensure_model():
    global SentenceTransformer, model
    if model is not None:
        return

    with _ensure_libs_lock:
        if SentenceTransformer is None:
            try:
                import transformers
                from sentence_transformers import SentenceTransformer as ST
                SentenceTransformer = ST
            except Exception as e:
                log.error(f"❌ Échec import IA : {e}")
                return

        if model is None:
            log.info(f"Chargement modèle Embedding : {EMBEDDING_MODEL_NAME}...")
            try:
                import torch
                # [PLAN STABILISATION] Forcer CPU pour éviter le bug "Inference Tensor" de DirectML
                device = "cpu"
                log.info(f"⚙️ Mode CPU forcé pour stabilité indexation (Zen 4 Optimized)")
                
                base_model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)

                # Optimisation CPU Native (INT8)
                log.info("🔍 Application quantification dynamique native (INT8)...")
                try:
                    base_model = torch.quantization.quantize_dynamic(
                        base_model, {torch.nn.Linear}, dtype=torch.qint8
                    )
                    log.info("✅ Modèle quantifié INT8 (Performance Max CPU)")
                except Exception as q_e:
                    log.warning(f"⚠️ Echec quantification : {q_e}")

                model = base_model
                log.info(f"✅ Modèle prêt sur CPU")
                
            except Exception as e:
                log.error(f"❌ Erreur _ensure_model : {e}")
                raise

# --- Opérations Base de Données ---

@trace_action(source="database")
def init_db(db_path_base=None):
    """Initialise le schéma de la base de données."""
    global _db_initialized
    if _db_initialized and db_path_base is None: return

    with _init_db_lock:
        conn = get_connection(db_path_base)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        
        # 1. Table des fichiers
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                path TEXT UNIQUE NOT NULL, 
                checksum TEXT NOT NULL, 
                last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. Table des chunks (SCHEMA BLINDÉ V4)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                file_id INTEGER NOT NULL, 
                chunk_index INTEGER DEFAULT 0, 
                content TEXT NOT NULL, 
                ast_type TEXT, 
                start_line INTEGER, 
                end_line INTEGER, 
                parent_context TEXT,
                metadata TEXT,
                FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
            )
        ''')
        
        # 3. Table Vectorielle
        cursor.execute(f'''
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                chunk_id INTEGER PRIMARY KEY, 
                embedding float[{EMBEDDING_DIM}]
            )
        ''')
        
        # 4. Table FTS5
        try:
            cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(content, tokenize='trigram')")
        except: pass

        conn.commit()
        conn.close()
        if db_path_base is None: _db_initialized = True
        log.info("✅ Schéma DB Omni-V4 initialisé.")

@trace_action(source="database")
def _add_chunks_batch(file_id: int, chunks_data: List[Dict]):
    _ensure_model()
    if not chunks_data or not model: return 0
    
    texts = [c.get('content', '') for c in chunks_data]
    vectors = model.encode(texts, convert_to_numpy=True)
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            inserted_count = 0
            
            for i, (chunk, vector) in enumerate(zip(chunks_data, vectors)):
                params = {
                    'file_id': file_id,
                    'chunk_index': i,
                    'content': chunk['content'],
                    'ast_type': chunk.get('ast_type'),
                    'start_line': chunk.get('start_line'),
                    'end_line': chunk.get('end_line'),
                    'parent_context': chunk.get('parent_context'),
                    'metadata': chunk.get('metadata')
                }
                
                cursor.execute('''
                    INSERT INTO chunks (
                        file_id, chunk_index, content, ast_type, 
                        start_line, end_line, parent_context, metadata
                    )
                    VALUES (
                        :file_id, :chunk_index, :content, :ast_type, 
                        :start_line, :end_line, :parent_context, :metadata
                    )
                ''', params)
                
                cid = cursor.lastrowid
                cursor.execute("INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)", (cid, vector.tobytes()))
                try: 
                    cursor.execute("INSERT INTO fts_chunks(rowid, content) VALUES (?, ?)", (cid, chunk['content']))
                except: pass
                inserted_count += 1
            
            conn.commit()
            conn.close()
            return inserted_count
            
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            else:
                log.error(f"Erreur SQL finale : {e}")
                if 'conn' in locals(): conn.close()
                return 0
        except Exception as e:
            log.error(f"Erreur insertion batch : {e}")
            if 'conn' in locals(): conn.close()
            return 0
    return 0

@trace_action(source="database")
def search_hybrid(query: str, db_path_base=None, limit: int = 20, use_hybrid=True, **kwargs) -> Tuple[List, Optional[str]]:
    _ensure_model()
    init_db(db_path_base)
    if not model: return [], "Modèle non chargé"
    
    try:
        query_vec = model.encode([query])[0]
        conn = get_connection(db_path_base)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT chunk_id, distance 
            FROM vec_chunks 
            WHERE embedding MATCH ? AND k = 50 
            ORDER BY distance ASC
        ''', (query_vec.tobytes(),))
        vec_results = cursor.fetchall()
        
        scores = {}
        for i, (cid, _) in enumerate(vec_results): 
            scores[cid] = scores.get(cid, 0) + (1.0 / (60 + i + 1))
        
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        final_results = []
        for cid, score in sorted_ids:
            cursor.execute('''
                SELECT f.path, c.content, c.ast_type, c.start_line 
                FROM chunks c 
                JOIN files f ON f.id = c.file_id 
                WHERE c.id = ?
            ''', (cid,))
            row = cursor.fetchone()
            if row: final_results.append((row[0], row[1], score, row[2], row[3]))
            
        conn.close()
        return final_results, None
    except Exception as e:
        log.error(f"Erreur recherche : {e}")
        return [], str(e)

def search_vector_db(query, db_path_base=None, max_results=5):
    results, err = search_hybrid(query, db_path_base, limit=max_results)
    return results, err

@trace_action(source="database")
def index_project_files(root_path: str, progress_callback=None, use_semantic_chunking=True, **kwargs):
    """Indexation complète avec Mode Turbo (Massive Batch) pour >100 fichiers."""
    from .merkle_sync import MerkleTreeSync
    from .code_chunker import get_chunker
    from features.gitignore_parser import parse_gitignore
    from config.settings import APP_SETTINGS
    from concurrent.futures import ThreadPoolExecutor
    
    init_db()
    
    log.info(f"🚀 Début indexation (Mode Turbo) : {root_path}")
    
    # 1. Chargement .gitignore
    gitignore_path = os.path.join(root_path, ".gitignore")
    matches_gitignore = lambda x: False
    if os.path.exists(gitignore_path):
        try:
            matches_gitignore = parse_gitignore(gitignore_path)
        except: pass

    # 2. Détection DB vide
    db_is_empty = True
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM files")
        db_is_empty = (cursor.fetchone()[0] == 0)
        conn.close()
    except: pass

    # 3. Merkle Sync
    state_file = get_path("db/merkle_state_v4.json")
    current_tree = MerkleTreeSync(root_path)
    current_tree.build_tree()
    
    previous_hashes = MerkleTreeSync.load_state(state_file)
    from .merkle_sync import MerkleNode
    prev_tree = MerkleTreeSync(root_path)
    for p, h in previous_hashes.items(): prev_tree.node_map[p] = MerkleNode(p, is_file=True, hash_value=h)
    
    modified = current_tree.compare_trees(prev_tree)
    
    if db_is_empty and not modified:
        log.info("🔄 DB vide : Forçage complet...")
        modified = [n.path for n in current_tree.node_map.values() if n.is_file]
    elif not modified:
        return "Base déjà à jour."

    chunker = get_chunker()
    _ensure_model()
    
    # 4. Filtrage & Qualification
    critical_dirs = {'.git', '__pycache__', 'venv', 'node_modules', 'db', 'logs', 'dist', 'build', 'audio_cache', '.vscode', '.idea'}
    watch_list = APP_SETTINGS.get("repo_map_cache", {}).get("watch_files", [])
    normalized_watch_list = [os.path.normpath(os.path.join(root_path, w)).lower() for w in watch_list]
    
    to_index = []
    for fpath in modified:
        if os.path.normpath(fpath).lower() in normalized_watch_list:
            to_index.append(fpath)
            continue

        rel_path = os.path.relpath(fpath, root_path)
        if any(p in critical_dirs for p in rel_path.split(os.sep)): continue
        if matches_gitignore(fpath): continue
            
        valid_exts = SUPPORTED_FILE_EXTENSIONS + ('.py', '.md', '.txt', '.js', '.json', '.html', '.css', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp', '.rs', '.go', '.sh', '.bat', '.ps1', '.yaml', '.yml', '.toml', '.xml', '.sql', '.ini', '.cfg')
        if not fpath.lower().endswith(valid_exts):
            try:
                if os.path.getsize(fpath) > 1024 * 1024: continue
            except: continue
        
        to_index.append(fpath)

    total_files = len(to_index)
    log.info(f"📂 {total_files} fichiers à indexer.")
    
    if total_files == 0:
        return "Aucun fichier éligible."

    # --- PHASE 1 : Préparation Parallèle (Lecture + Chunking) ---
    # On utilise tous les coeurs pour lire et découper les fichiers
    def prepare_file(fpath):
        try:
            rel = os.path.relpath(fpath, root_path)
            with open(fpath, 'rb') as f: data = f.read()
            if b'\0' in data[:8000]: return None
            
            checksum = hashlib.sha256(data).hexdigest()
            text = data.decode('utf-8', errors='ignore')
            
            file_chunks = []
            if use_semantic_chunking and fpath.endswith('.py'):
                try: file_chunks = chunker.chunk_file(fpath)
                except: file_chunks = [{'content': text}]
            else:
                file_chunks = [{'content': text}]
            
            return (fpath, rel, checksum, file_chunks)
        except: return None

    log.info("⚡ Phase 1 : Lecture & Chunking parallèle...")
    prepared_data = []
    with ThreadPoolExecutor() as executor:
        results = executor.map(prepare_file, to_index)
        for res in results:
            if res: prepared_data.append(res)

    # --- PHASE 2 : Mode Turbo (>100 fichiers) ---
    if total_files >= 100:
        log.info(f"🚀 MODE TURBO ACTIVÉ : Traitement massif de {len(prepared_data)} fichiers")
        
        # A. Collecte globale des textes pour vectorisation
        all_chunks_flat = [] # (file_index, chunk_data)
        all_texts = []
        
        for f_idx, (_, _, _, chunks) in enumerate(prepared_data):
            for ch in chunks:
                txt = ch.get('content', '')
                if txt.strip():
                    all_chunks_flat.append((f_idx, ch))
                    all_texts.append(txt)
        
        # B. Vectorisation Massive (1 seul appel au modèle = 0 overhead)
        log.info(f"🧠 Vectorisation de {len(all_texts)} segments...")
        if all_texts:
            all_vectors = model.encode(all_texts, convert_to_numpy=True, show_progress_bar=True)
        else:
            all_vectors = []

        # C. Insertion Transactionnelle Unique
        log.info("💾 Écriture DB massive...")
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # 1. Mise à jour Files (Batch)
            # On supprime d'abord les anciens fichiers
            paths_to_delete = [item[1] for item in prepared_data]
            cursor.executemany("DELETE FROM files WHERE path = ?", [(p,) for p in paths_to_delete])
            
            # On insère les nouveaux et on récupère les IDs
            # Astuce: On insère un par un pour récupérer l'ID fiable, c'est très rapide en transaction
            file_ids_map = {} # f_idx -> db_id
            for f_idx, (_, rel, checksum, _) in enumerate(prepared_data):
                cursor.execute("INSERT INTO files (path, checksum) VALUES (?, ?)", (rel, checksum))
                file_ids_map[f_idx] = cursor.lastrowid

            # 2. Préparation Chunks (Batch)
            chunks_sql_data = []
            vec_sql_data = []
            fts_sql_data = []
            
            for (f_idx, ch), vec in zip(all_chunks_flat, all_vectors):
                fid = file_ids_map[f_idx]
                # On insère le chunk pour avoir son ID
                # Note: Pour aller vite, on ne peut pas utiliser executemany ET récupérer les IDs générés facilement
                # Sauf si on insère un par un dans la transaction. C'est le goulot d'étranglement.
                # Optimisation : On insère un par un mais dans la transaction globale.
                
                params = {
                    'fid': fid, 'idx': 0, # idx simplifié, pas critique
                    'cnt': ch['content'], 'ast': ch.get('ast_type'),
                    'sl': ch.get('start_line'), 'el': ch.get('end_line'),
                    'pc': ch.get('parent_context'), 'meta': ch.get('metadata')
                }
                cursor.execute('''
                    INSERT INTO chunks (file_id, chunk_index, content, ast_type, start_line, end_line, parent_context, metadata)
                    VALUES (:fid, :idx, :cnt, :ast, :sl, :el, :pc, :meta)
                ''', params)
                cid = cursor.lastrowid
                
                vec_sql_data.append((cid, vec.tobytes()))
                fts_sql_data.append((cid, ch['content']))

            # 3. Insertion Vectorielle & FTS (Batch Pur)
            cursor.executemany("INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)", vec_sql_data)
            try: cursor.executemany("INSERT INTO fts_chunks(rowid, content) VALUES (?, ?)", fts_sql_data)
            except: pass
            
            conn.commit()
            
        except Exception as e:
            log.error(f"❌ Erreur Transaction Turbo : {e}")
            conn.rollback()
        finally:
            conn.close()

    # --- PHASE 2bis : Mode Séquentiel (<100 fichiers) ---
    else:
        log.info("Mode Standard (Séquentiel)")
        count = 0
        for fpath, rel, checksum, chunks in prepared_data:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM files WHERE path = ?", (rel,))
                cursor.execute("INSERT INTO files (path, checksum) VALUES (?, ?)", (rel, checksum))
                fid = cursor.lastrowid
                conn.commit()
                conn.close()
                _add_chunks_batch(fid, chunks)
                count += 1
                if progress_callback: progress_callback(f"Indexation : {rel} ({count}/{total_files})")
            except: pass

    current_tree.save_state(state_file)
    log.info(f"✅ Indexation terminée : {total_files} fichiers traités.")
    return f"Indexation réussie : {total_files} fichiers traités."

# --- Autres Exports ---

def store_memory(text: str, metadata: Dict = None):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO files (path, checksum) VALUES (?, ?)", ("memory://global", "0"))
    fid = cursor.lastrowid
    conn.commit()
    conn.close()
    return _add_chunks_batch(fid, [{'content': text, 'ast_type': 'memory'}])

def search_memories(query: str, n_results=3, **kwargs):
    res, _ = search_hybrid(query, limit=n_results)
    return [r for r in res if r[0] == "memory://global"][:n_results]

def is_model_ready(): return model is not None
def warmup_model_background(): threading.Thread(target=_ensure_model, daemon=True, name="ModelWarmup").start()
def delete_local_db():
    global _db_initialized
    p = _get_db_path()
    if os.path.exists(p): 
        try:
            _db_initialized = False
            for ext in ['', '-wal', '-shm']:
                if os.path.exists(p + ext): os.remove(p + ext)
            return "✅ Base V4 supprimée."
        except Exception as e: return f"❌ Erreur : {e}"
    return "Néant."
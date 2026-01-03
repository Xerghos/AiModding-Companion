import logging
import os
import sqlite3
import pickle
import numpy as np
import shutil
import traceback
import threading
import hashlib
import time
import json
import glob
from typing import Dict, Optional, List, Tuple

from config import get_logger, get_path, SUPPORTED_FILE_EXTENSIONS
from features.Decorators import trace_action

log = get_logger("features.context.database")

# Lock pour protéger l'initialisation thread-safe de SentenceTransformer
_ensure_libs_lock = threading.Lock()

# Lock et cache pour protéger l'initialisation thread-safe de init_db
_init_db_lock = threading.Lock()
_initialized_dbs = set()  # Cache des DB déjà initialisées

# --- Constantes ---
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
DB_DIR = "db"
DB_NAME = "knowledge_base_hybrid_V2"

# --- Variables Globales ---
faiss_index = None
id_mapping = {} 
faiss = None
SentenceTransformer = None
model = None

@trace_action(source="database")
def _get_paths(db_path_base=None):
    if not db_path_base:
        base = get_path(DB_DIR)
        name = DB_NAME
    else:
        base = os.path.dirname(db_path_base)
        name = os.path.basename(db_path_base).replace(".sqlite", "")
    return (
        os.path.join(base, f"{name}.sqlite"),
        os.path.join(base, f"{name}.index"),
        os.path.join(base, f"{name}.pkl")
    )

@trace_action(source="database")
def _ensure_libs():
    global faiss, SentenceTransformer, model
    # Vérifier d'abord si déjà initialisé (évite le lock si possible)
    if faiss is not None and SentenceTransformer is not None and model is not None:
        return
    
    # Protection thread-safe pour éviter les chargements simultanés
    with _ensure_libs_lock:
        # Double-check après avoir acquis le lock
        if faiss is None:
            import faiss as f
            faiss = f
        if SentenceTransformer is None:
            from sentence_transformers import SentenceTransformer as ST
            SentenceTransformer = ST
        if model is None:
            log.info(f"Chargement modèle Embedding: {EMBEDDING_MODEL_NAME}...")
            try:
                model = SentenceTransformer(EMBEDDING_MODEL_NAME)
                log.info(f"✅ Modèle Embedding chargé: {EMBEDDING_MODEL_NAME}")
            except Exception as e:
                log.error(f"❌ Erreur chargement SentenceTransformer: {e}")
                # Réinitialiser pour permettre une nouvelle tentative
                model = None
                raise

@trace_action(source="database")
def init_db(db_path_base=None):
    global faiss_index, id_mapping
    
    # Calculer la clé unique pour cette DB
    sqlite_path, index_path, map_path = _get_paths(db_path_base)
    db_key = os.path.abspath(sqlite_path)
    
    # Vérifier si déjà initialisée (sans lock, rapide)
    if db_key in _initialized_dbs:
        log.debug(f"DB déjà initialisée: {db_key}")
        _ensure_libs()  # S'assurer que les libs sont chargées
        return
    
    # Protection thread-safe pour l'initialisation
    with _init_db_lock:
        # Double-check après avoir acquis le lock
        if db_key in _initialized_dbs:
            log.debug(f"DB déjà initialisée (double-check): {db_key}")
            _ensure_libs()
            return
        
        os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
        
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
    
    # Table knowledge (legacy, conservée pour compatibilité)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection TEXT,
            content TEXT,
            content_hash TEXT UNIQUE,
            metadata TEXT,
            embedding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table files : Suivi des fichiers indexés avec hachages SHA-256
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            checksum TEXT NOT NULL,
            last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table chunks : Chunks sémantiques avec métadonnées AST
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            start_line INTEGER,
            end_line INTEGER,
            content TEXT NOT NULL,
            ast_type TEXT,
            parent_context TEXT,
            content_hash TEXT,
            embedding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
        )
    ''')
    
    # Index pour recherche rapide
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_ast_type ON chunks(ast_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)')
    
    # Table virtuelle FTS5 pour recherche plein texte
    try:
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_code USING fts5(
                content,
                path UNINDEXED,
                chunk_id UNINDEXED,
                ast_type UNINDEXED,
                tokenize='trigram'
            )
        ''')
        
        # Triggers pour synchronisation automatique FTS5
        # Trigger INSERT
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS chunks_ai_fts5 AFTER INSERT ON chunks BEGIN
                INSERT INTO fts_code(rowid, content, path, chunk_id, ast_type)
                VALUES (
                    new.id,
                    new.content,
                    (SELECT path FROM files WHERE id=new.file_id),
                    new.id,
                    new.ast_type
                );
            END
        ''')
        
        # Trigger UPDATE
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS chunks_au_fts5 AFTER UPDATE ON chunks BEGIN
                UPDATE fts_code SET
                    content = new.content,
                    path = (SELECT path FROM files WHERE id=new.file_id),
                    ast_type = new.ast_type
                WHERE rowid = new.id;
            END
        ''')
        
        # Trigger DELETE
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS chunks_ad_fts5 AFTER DELETE ON chunks BEGIN
                DELETE FROM fts_code WHERE rowid = old.id;
            END
        ''')
        
        log.info("✅ Table FTS5 et triggers créés")
    except sqlite3.OperationalError as e:
        # FTS5 peut ne pas être disponible sur certaines versions SQLite
        log.warning(f"FTS5 non disponible: {e}")
    except Exception as e:
        log.warning(f"Erreur création triggers FTS5: {e}")
    
    conn.commit()
    conn.close()
    
    _ensure_libs()
    log.debug(f"Vérification index: {index_path} existe={os.path.exists(index_path)}, {map_path} existe={os.path.exists(map_path)}")
    if os.path.exists(index_path) and os.path.exists(map_path):
        try:
            log.debug(f"Chargement index depuis {index_path}...")
            loaded_index = faiss.read_index(index_path)
            with open(map_path, 'rb') as f: id_mapping = pickle.load(f)
            
            # Vérifier si c'est un IndexIDMap ou un IndexFlatL2
            if isinstance(loaded_index, faiss.IndexIDMap):
                faiss_index = loaded_index
                log.info(f"✅ DB Chargée (IndexIDMap) : {faiss_index.ntotal} vecteurs dans l'index, {len(id_mapping)} dans le mapping.")
                if faiss_index.ntotal == 0:
                    log.warning(f"⚠️ Index chargé mais vide (ntotal=0). Vérification reconstruction...")
            else:
                # Migration: convertir IndexFlatL2 en IndexIDMap
                log.info("Migration vers IndexIDMap...")
                base_index = faiss.IndexFlatL2(EMBEDDING_DIM)
                faiss_index = faiss.IndexIDMap(base_index)
                
                # Transférer les vecteurs avec leurs IDs
                if loaded_index.ntotal > 0:
                    vectors = loaded_index.reconstruct_n(0, loaded_index.ntotal)
                    # Utiliser les IDs depuis id_mapping (inversé)
                    ids = list(id_mapping.keys()) if id_mapping else list(range(loaded_index.ntotal))
                    faiss_index.add_with_ids(vectors, np.array(ids, dtype='int64'))
                
                # Sauvegarder le nouvel index
                faiss.write_index(faiss_index, index_path)
                log.info(f"Migration terminée : {faiss_index.ntotal} vecteurs migrés.")
        except Exception as e:
            log.warning(f"Erreur chargement index, création nouveau: {e}", exc_info=True)
            base_index = faiss.IndexFlatL2(EMBEDDING_DIM)
            faiss_index = faiss.IndexIDMap(base_index)
            id_mapping = {}
    else:
        # Nouveau: utiliser IndexIDMap dès le départ
        log.debug(f"Index ou mapping n'existe pas, création nouveau index vide")
        base_index = faiss.IndexFlatL2(EMBEDDING_DIM)
        faiss_index = faiss.IndexIDMap(base_index)
        id_mapping = {}
    
    # Si l'index est vide mais que des chunks existent dans la DB, reconstruire l'index
    if faiss_index.ntotal == 0:
        try:
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.cursor()
            
            # Compter les chunks et knowledge existants
            cursor.execute("SELECT COUNT(*) FROM chunks")
            chunks_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM knowledge")
            knowledge_count = cursor.fetchone()[0]
            
            if chunks_count > 0 or knowledge_count > 0:
                log.info(f"🔄 Reconstruction index FAISS depuis DB ({chunks_count} chunks, {knowledge_count} knowledge)...")
                
                # Reconstruire depuis chunks
                if chunks_count > 0:
                    cursor.execute("SELECT id, embedding FROM chunks WHERE embedding IS NOT NULL")
                    for chunk_id, embedding_blob in cursor.fetchall():
                        if embedding_blob:
                            vector = np.frombuffer(embedding_blob, dtype='float32')
                            if len(vector) == EMBEDDING_DIM:
                                faiss_index.add_with_ids(
                                    np.array([vector], dtype='float32'),
                                    np.array([chunk_id], dtype='int64')
                                )
                                id_mapping[chunk_id] = chunk_id
                
                # Reconstruire depuis knowledge (legacy)
                if knowledge_count > 0:
                    cursor.execute("SELECT id, embedding FROM knowledge WHERE embedding IS NOT NULL")
                    for know_id, embedding_blob in cursor.fetchall():
                        if embedding_blob:
                            vector = np.frombuffer(embedding_blob, dtype='float32')
                            if len(vector) == EMBEDDING_DIM:
                                faiss_index.add_with_ids(
                                    np.array([vector], dtype='float32'),
                                    np.array([know_id], dtype='int64')
                                )
                                id_mapping[know_id] = know_id
                
                # Sauvegarder l'index reconstruit
                if faiss_index.ntotal > 0:
                    faiss.write_index(faiss_index, index_path)
                    with open(map_path, 'wb') as f:
                        pickle.dump(id_mapping, f)
                    log.info(f"✅ Index FAISS reconstruit : {faiss_index.ntotal} vecteurs")
            
            conn.close()
        except Exception as e:
            log.warning(f"Erreur reconstruction index depuis DB: {e}", exc_info=True)
        
        # Marquer comme initialisée
        _initialized_dbs.add(db_key)
        log.debug(f"✅ DB initialisée: {db_key}")

@trace_action(source="database")
def add_knowledge(collection, content, metadata=None):
    global faiss_index, id_mapping
    if not content or not content.strip(): return None
    
    # Sécurité : on s'assure que les libs sont là
    _ensure_libs()
    
    # 1. Calcul du vecteur (coûteux, on le fait une fois avant de toucher à la DB)
    try:
        vector = model.encode([content])[0]
        blob_embedding = vector.tobytes()
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
    except Exception as e:
        log.error(f"Erreur Encoding: {e}")
        return None
    
    # 2. Tentative d'insertion avec Auto-Réparation SQL
    sqlite_path, index_path, map_path = _get_paths()
    
    for attempt in range(2): # On essaie 2 fois : Normal, puis après Réparation
        conn = None
        try:
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR IGNORE INTO knowledge (collection, content, content_hash, metadata, embedding)
                VALUES (?, ?, ?, ?, ?)
            ''', (collection, content, content_hash, json.dumps(metadata or {}, ensure_ascii=False), blob_embedding))
            
            conn.commit()
            sql_id = cursor.lastrowid
            
            # Si doublon (sql_id est None ou 0), on arrête là sans erreur
            if not sql_id: 
                return None 

            # Mise à jour Index Vectoriel (Mémoire)
            if faiss_index is None: 
                init_db() # Cas rare : Faiss pas init mais SQL oui
            
            faiss_index.add(np.array([vector], dtype='float32'))
            faiss_id = faiss_index.ntotal - 1
            id_mapping[faiss_id] = sql_id
            
            # Sauvegarde Index Disque
            faiss.write_index(faiss_index, index_path)
            with open(map_path, 'wb') as f: pickle.dump(id_mapping, f)
            
            return sql_id

        except sqlite3.OperationalError as e:
            # [FIX] C'est ici qu'on gère le "no such table"
            if "no such table" in str(e) and attempt == 0:
                log.warning("⚠️ Table 'knowledge' manquante. Tentative de reconstruction immédiate...")
                if conn: conn.close()
                init_db() # On force la création de la table
                continue # On réessaye la boucle (attempt 1)
            else:
                log.error(f"Erreur SQL critique: {e}")
                return None
        except Exception as e:
            log.error(f"Erreur insertion DB générique: {e}")
            return None
        finally:
            if conn: conn.close()
            
    return None

@trace_action(source="database")
def reciprocal_rank_fusion(vector_results: List[Tuple], fts_results: List[Tuple], k: int = 60) -> Dict[int, float]:
    """
    Algorithme Reciprocal Rank Fusion (RRF) pour fusionner résultats de recherche.
    
    Args:
        vector_results: Liste de (chunk_id, score) de la recherche vectorielle
        fts_results: Liste de (chunk_id, score) de la recherche FTS5
        k: Constante de lissage (défaut: 60)
    
    Returns:
        Dictionnaire {chunk_id: score_rrf}
    """
    rrf_scores = {}
    
    # Traiter résultats vectoriels (distance, donc plus petit = mieux)
    # On inverse pour avoir un rang (1 = meilleur)
    for rank, (chunk_id, distance) in enumerate(vector_results, 1):
        if chunk_id not in rrf_scores:
            rrf_scores[chunk_id] = 0.0
        rrf_scores[chunk_id] += 1.0 / (k + rank)
    
    # Traiter résultats FTS5 (score BM25, plus grand = mieux)
    # On inverse aussi pour avoir un rang
    for rank, (chunk_id, score) in enumerate(fts_results, 1):
        if chunk_id not in rrf_scores:
            rrf_scores[chunk_id] = 0.0
        rrf_scores[chunk_id] += 1.0 / (k + rank)
    
    return rrf_scores


@trace_action(source="database")
def search_vector_db(query, db_path_base=None, max_results=5):
    """Recherche vectorielle uniquement (legacy, pour compatibilité)."""
    results, _ = search_hybrid(query, db_path_base, max_results, use_hybrid=False)
    return results, None


def _sanitize_fts5_query(query: str) -> str:
    """
    Nettoie et échappe la requête pour FTS5.
    FTS5 a une syntaxe spéciale : certains caractères doivent être échappés.
    Pour les requêtes multi-mots, on filtre les stop words et utilise OR pour élargir la recherche.
    """
    if not query:
        return ""
    
    # Caractères spéciaux FTS5 qui nécessitent un échappement
    special_chars = ['"', ',', ':', '\\', '(', ')', '{', '}', '[', ']', '^', '*', '?', '+', '-', '|', '&']
    
    # Si la requête contient des opérateurs FTS5 (AND, OR, NOT), on la retourne telle quelle
    if any(op in query.upper() for op in [' AND ', ' OR ', ' NOT ']):
        # La requête contient déjà des opérateurs FTS5, on ne fait que l'échapper si nécessaire
        if any(char in query for char in special_chars):
            escaped_query = query.replace('"', '""')
            return f'"{escaped_query}"'
        return query
    
    # Stop words français à exclure (articles, prépositions, pronoms courants)
    stop_words = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou', 'à', 'au', 'aux',
                  'pour', 'avec', 'sans', 'sur', 'sous', 'dans', 'par', 'est', 'sont', 'être',
                  'avoir', 'il', 'elle', 'ils', 'elles', 'ce', 'cet', 'cette', 'ces', 'se', 'te',
                  'me', 'nous', 'vous', 'que', 'qui', 'quoi', 'où', 'quand', 'comment', 'pourquoi'}
    
    # Séparer les mots (garder seulement les caractères alphanumériques et accents)
    import re
    words = re.findall(r'\b\w+\b', query.lower(), re.UNICODE)
    
    # Filtrer les stop words et les mots trop courts (< 2 caractères sauf si mot technique)
    significant_words = [w for w in words if w not in stop_words and (len(w) >= 3 or w.isdigit())]
    
    if len(significant_words) > 1:
        # Utiliser OR pour élargir la recherche (meilleur pour FTS5)
        # Les documents contenant plusieurs mots auront un meilleur score BM25
        return ' OR '.join(significant_words)
    elif len(significant_words) == 1:
        # Un seul mot significatif, retourner tel quel
        return significant_words[0]
    elif len(words) > 0:
        # Pas de mots significatifs après filtrage, utiliser tous les mots avec OR
        return ' OR '.join(words[:5])  # Limiter à 5 mots max
    else:
        # Pas de mots trouvés, retourner la requête originale (peut contenir des caractères spéciaux)
        # Échapper si nécessaire
        if any(char in query for char in special_chars):
            escaped_query = query.replace('"', '""')
            return f'"{escaped_query}"'
        return query


@trace_action(source="database")
def search_hybrid(query, db_path_base=None, max_results=50, use_hybrid=True):
    """
    Recherche hybride combinant recherche dense (FAISS) et sparse (FTS5).
    
    Args:
        query: Requête de recherche
        db_path_base: Chemin de base de la DB
        max_results: Nombre maximum de résultats
        use_hybrid: Si False, utilise uniquement la recherche vectorielle
    
    Returns:
        Tuple (results, error) où results est une liste de (source, content, score)
    """
    global faiss_index, id_mapping
    
    if not query:
        return [], None
    
    _ensure_libs()
    if faiss_index is None or faiss_index.ntotal == 0:
        init_db(db_path_base)
        if faiss_index is None or faiss_index.ntotal == 0:
            log.warning("FAISS index non initialisé ou vide après init_db.")
            return [], None
    
    sqlite_path, _, _ = _get_paths(db_path_base)
    
    try:
        # 1. Recherche Dense (FAISS)
        query_vector = model.encode([query])[0]
        
        # Rechercher plus de résultats pour la fusion
        search_k = min(max_results * 3, faiss_index.ntotal)
        D, I = faiss_index.search(np.array([query_vector], dtype='float32'), search_k)
        
        vector_results = []
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        for i, result_id in enumerate(I[0]):
            if result_id == -1:
                continue
            
            # Avec IndexIDMap, result_id est directement le chunk_id ou knowledge_id
            chunk_id = int(result_id)
            distance = float(D[0][i])
            
            # Récupérer le contenu depuis chunks ou knowledge avec métadonnées AST
            cursor.execute('''
                SELECT c.content, f.path, c.ast_type, c.parent_context, c.start_line, c.end_line
                FROM chunks c
                JOIN files f ON c.file_id = f.id
                WHERE c.id = ?
            ''', (chunk_id,))
            row = cursor.fetchone()
            
            if not row:
                # Essayer knowledge (legacy)
                cursor.execute("SELECT collection, content FROM knowledge WHERE id=?", (chunk_id,))
                row = cursor.fetchone()
                if row:
                    vector_results.append((chunk_id, distance, row[1], row[0], None, None, None, None))
            else:
                content, path, ast_type, parent_context, start_line, end_line = row
                source = f"{path}" if path else f"chunk_{chunk_id}"
                vector_results.append((chunk_id, distance, content, source, ast_type, parent_context, start_line, end_line))
        
        # 2. Recherche Sparse (FTS5)
        fts_results = []
        if use_hybrid:
            try:
                # Vérifier si FTS5 est disponible
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fts_code'")
                if cursor.fetchone():
                    # Recherche FTS5 avec BM25
                    # Note: FTS5 utilise rowid comme clé primaire (mappé à chunk.id via trigger)
                    try:
                        # Nettoyer la requête pour éviter les erreurs de syntaxe FTS5
                        fts5_query = _sanitize_fts5_query(query)
                        # Récupérer les métadonnées depuis chunks via jointure
                        cursor.execute('''
                            SELECT fts.rowid, bm25(fts_code) as score, fts.content, fts.path, fts.ast_type,
                                   c.parent_context, c.start_line, c.end_line
                            FROM fts_code fts
                            LEFT JOIN chunks c ON c.id = fts.rowid
                            WHERE fts_code MATCH ?
                            ORDER BY score
                            LIMIT ?
                        ''', (fts5_query, search_k))
                        
                        rows = cursor.fetchall()
                        log.debug(f"FTS5 BM25: {len(rows)} résultats trouvés")
                        for row in rows:
                            chunk_id, score, content, path, ast_type, parent_context, start_line, end_line = row
                            source = path if path else f"chunk_{chunk_id}"
                            fts_results.append((chunk_id, -score, content, source, ast_type, parent_context, start_line, end_line))  # Négatif car BM25 plus grand = mieux
                    except sqlite3.OperationalError as bm25_err:
                        if "no such function: bm25" in str(bm25_err):
                            # BM25 non disponible, utiliser MATCH simple avec rowid
                            # Nettoyer la requête pour éviter les erreurs de syntaxe FTS5
                            fts5_query = _sanitize_fts5_query(query)
                            cursor.execute('''
                                SELECT fts.rowid, fts.content, fts.path, fts.ast_type,
                                       c.parent_context, c.start_line, c.end_line
                                FROM fts_code fts
                                LEFT JOIN chunks c ON c.id = fts.rowid
                                WHERE fts_code MATCH ?
                                LIMIT ?
                            ''', (fts5_query, search_k))
                            
                            for rank, row in enumerate(cursor.fetchall(), 1):
                                chunk_id, content, path, ast_type, parent_context, start_line, end_line = row
                                source = path if path else f"chunk_{chunk_id}"
                                # Utiliser le rang comme score (plus petit = mieux)
                                fts_results.append((chunk_id, rank, content, source, ast_type, parent_context, start_line, end_line))
                        else:
                            raise
                else:
                    log.debug("FTS5 table non trouvée, recherche hybride dégradée en recherche vectorielle uniquement")
            except Exception as e:
                log.warning(f"Erreur recherche FTS5: {e}", exc_info=True)
        
        conn.close()
        
        # 3. Fusion RRF
        if use_hybrid and fts_results:
            # Préparer les listes pour RRF (chunk_id, score)
            # IMPORTANT: Trier les résultats par pertinence avant RRF
            # Pour vector_results: distance (plus petit = mieux) → tri croissant
            vector_list = [(cid, dist) for cid, dist, _, _, _, _, _, _ in vector_results]
            vector_list = sorted(vector_list, key=lambda x: x[1])  # Trier par distance croissante
            
            # Pour fts_results: score BM25 négatif (plus négatif = mieux) → tri croissant
            fts_list = [(cid, score) for cid, score, _, _, _, _, _, _ in fts_results]
            fts_list = sorted(fts_list, key=lambda x: x[1])  # Trier par score croissant (car négatif)
            
            log.debug(f"RRF: {len(vector_list)} résultats vectoriels, {len(fts_list)} résultats FTS5")
            rrf_scores = reciprocal_rank_fusion(vector_list, fts_list)
            log.debug(f"RRF: {len(rrf_scores)} scores RRF calculés")
            
            # Créer un dictionnaire de résultats complets avec métadonnées
            results_dict = {}
            for cid, dist, content, source, ast_type, parent_context, start_line, end_line in vector_results:
                if cid not in results_dict:
                    results_dict[cid] = {
                        'content': content,
                        'source': source,
                        'ast_type': ast_type,
                        'parent_context': parent_context,
                        'start_line': start_line,
                        'end_line': end_line,
                        'rrf_score': rrf_scores.get(cid, 0.0)
                    }
            
            for cid, score, content, source, ast_type, parent_context, start_line, end_line in fts_results:
                if cid not in results_dict:
                    results_dict[cid] = {
                        'content': content,
                        'source': source,
                        'ast_type': ast_type,
                        'parent_context': parent_context,
                        'start_line': start_line,
                        'end_line': end_line,
                        'rrf_score': rrf_scores.get(cid, 0.0)
                    }
            
            # Trier par score RRF décroissant
            sorted_results = sorted(
                results_dict.items(),
                key=lambda x: x[1]['rrf_score'],
                reverse=True
            )[:max_results]
            
            # Formater les résultats avec métadonnées
            results = [
                (
                    item['source'],
                    item['content'],
                    item['rrf_score'],
                    item['ast_type'],
                    item['parent_context'],
                    item['start_line'],
                    item['end_line']
                )
                for _, item in sorted_results
            ]
        else:
            # Pas de fusion, utiliser uniquement résultats vectoriels
            results = [
                (
                    source,
                    content,
                    distance,
                    ast_type,
                    parent_context,
                    start_line,
                    end_line
                )
                for _, distance, content, source, ast_type, parent_context, start_line, end_line in vector_results[:max_results]
            ]
        
        return results, None
        
    except Exception as e:
        log.error(f"Erreur recherche hybride: {e}", exc_info=True)
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        return [], error_msg

# --- [FIX ISSUE 1] COMMANDES MANQUANTES ---

@trace_action(source="database")
def _get_or_create_file_id(file_path: str, checksum: str, db_path_base=None) -> int:
    """Récupère ou crée l'ID d'un fichier dans la table files."""
    sqlite_path, _, _ = _get_paths(db_path_base)
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    try:
        # Chercher le fichier existant
        cursor.execute("SELECT id FROM files WHERE path=?", (file_path,))
        row = cursor.fetchone()
        
        if row:
            file_id = row[0]
            # Mettre à jour le checksum et timestamp
            cursor.execute(
                "UPDATE files SET checksum=?, last_indexed=CURRENT_TIMESTAMP WHERE id=?",
                (checksum, file_id)
            )
            conn.commit()
        else:
            # Créer nouveau fichier
            cursor.execute(
                "INSERT INTO files (path, checksum) VALUES (?, ?)",
                (file_path, checksum)
            )
            file_id = cursor.lastrowid
            conn.commit()
        
        return file_id
    finally:
        conn.close()


@trace_action(source="database")
def _add_chunk_to_db(file_id: int, chunk_index: int, chunk_data: Dict, db_path_base=None) -> Optional[int]:
    """Ajoute un chunk à la base de données et retourne son ID."""
    global faiss_index, id_mapping
    
    _ensure_libs()
    sqlite_path, index_path, map_path = _get_paths(db_path_base)
    
    content = chunk_data.get('content', '')
    if not content or not content.strip():
        return None
    
    try:
        # Calculer le vecteur
        vector = model.encode([content])[0]
        blob_embedding = vector.tobytes()
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        try:
            # Insérer le chunk
            cursor.execute('''
                INSERT INTO chunks (file_id, chunk_index, start_line, end_line, 
                                 content, ast_type, parent_context, content_hash, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_id,
                chunk_index,
                chunk_data.get('start_line'),
                chunk_data.get('end_line'),
                content,
                chunk_data.get('ast_type'),
                chunk_data.get('parent_context'),
                content_hash,
                blob_embedding
            ))
            
            chunk_id = cursor.lastrowid
            conn.commit()
            
            # Ajouter au index FAISS avec l'ID du chunk
            if faiss_index is None:
                init_db(db_path_base)
            
            # Utiliser add_with_ids pour IndexIDMap
            if isinstance(faiss_index, faiss.IndexIDMap):
                faiss_index.add_with_ids(
                    np.array([vector], dtype='float32'),
                    np.array([chunk_id], dtype='int64')
                )
            else:
                # Fallback si pas IndexIDMap (ne devrait pas arriver)
                faiss_index.add(np.array([vector], dtype='float32'))
                faiss_id = faiss_index.ntotal - 1
                id_mapping[faiss_id] = chunk_id
            
            # Sauvegarder index
            faiss.write_index(faiss_index, index_path)
            if not isinstance(faiss_index, faiss.IndexIDMap):
                with open(map_path, 'wb') as f:
                    pickle.dump(id_mapping, f)
            
            return chunk_id
            
        finally:
            conn.close()
            
    except Exception as e:
        log.error(f"Erreur ajout chunk: {e}")
        return None


@trace_action(source="database")
def _delete_file_chunks(file_id: int, db_path_base=None):
    """Supprime tous les chunks d'un fichier."""
    global faiss_index, id_mapping
    
    sqlite_path, index_path, map_path = _get_paths(db_path_base)
    
    try:
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        # Récupérer les IDs des chunks à supprimer
        cursor.execute("SELECT id FROM chunks WHERE file_id=?", (file_id,))
        chunk_ids = [row[0] for row in cursor.fetchall()]
        
        # Supprimer de FAISS si IndexIDMap
        if chunk_ids and isinstance(faiss_index, faiss.IndexIDMap):
            faiss_index.remove_ids(np.array(chunk_ids, dtype='int64'))
            faiss.write_index(faiss_index, index_path)
        
        # Supprimer de SQLite (CASCADE supprimera automatiquement)
        cursor.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))
        conn.commit()
        conn.close()
        
        log.info(f"Supprimé {len(chunk_ids)} chunks pour file_id={file_id}")
        
    except Exception as e:
        log.error(f"Erreur suppression chunks: {e}")


@trace_action(source="database")
def index_project_files(root_path, progress_callback=None, use_semantic_chunking=True):
    """
    Scan et indexe tous les fichiers du projet.
    
    Args:
        root_path: Chemin racine du projet
        progress_callback: Fonction de callback pour le progrès
        use_semantic_chunking: Si True, utilise le chunking sémantique Tree-sitter
    """
    from .code_chunker import get_chunker
    
    count = 0
    errors = 0
    total_chunks = 0
    
    # Extensions supportées (importées de config)
    exts = SUPPORTED_FILE_EXTENSIONS
    
    # Initialiser le chunker si nécessaire
    chunker = None
    semantic_chunking_active = False
    if use_semantic_chunking:
        try:
            chunker = get_chunker()
            # Vérifier si le chunking sémantique est réellement disponible
            if chunker and hasattr(chunker, 'is_available') and chunker.is_available:
                semantic_chunking_active = True
                log.info("✅ Chunking sémantique activé pour les fichiers Python")
            else:
                log.info("ℹ️ Chunking sémantique demandé mais non disponible - utilisation du chunking basique")
        except Exception as e:
            log.warning(f"Impossible d'initialiser le chunker sémantique: {e}")
            use_semantic_chunking = False
    
    files_to_index = []
    for root, _, files in os.walk(root_path):
        # Exclusions Dossiers (Système & Cache)
        if any(x in root for x in [".git", "__pycache__", "venv", "env", "node_modules", "db", "logs", "dist", "build", "audio_cache"]):
            continue
            
        for file in files:
            f_low = file.lower()
            
            # 1. Exclusion par extension "bruit"
            if f_low.endswith(('.json', '.log', '.lock', '.sqlite', '.pkl', '.index', '.csv')):
                continue
                
            # 2. Exclusion par mots-clés (Anti-Auto-Inclusion)
            if any(k in f_low for k in ['debug', 'payload', 'usage', 'history', 'chat', 'action_log']):
                continue

            # 3. Inclusion sélective (Python pour chunking sémantique, autres pour fallback)
            if f_low.endswith(exts):
                files_to_index.append(os.path.join(root, file))
    
    total = len(files_to_index)
    semantic_status = "ACTIF" if semantic_chunking_active else "INACTIF (fallback basique)"
    log.info(f"Début indexation : {total} fichiers trouvés | Chunking sémantique: {semantic_status}")
    
    for i, file_path in enumerate(files_to_index):
        try:
            rel_path = os.path.relpath(file_path, root_path)
            
            # Calculer le checksum SHA-256
            with open(file_path, 'rb') as f:
                file_content = f.read()
            checksum = hashlib.sha256(file_content).hexdigest()
            
            # Récupérer ou créer l'ID du fichier
            file_id = _get_or_create_file_id(rel_path, checksum)
            
            # Supprimer les anciens chunks de ce fichier
            _delete_file_chunks(file_id)
            
            # Chunking sémantique pour Python, fallback pour autres
            is_python = file_path.lower().endswith('.py')
            
            if use_semantic_chunking and is_python and chunker and semantic_chunking_active:
                # Utiliser le chunker sémantique
                chunks = chunker.chunk_file(file_path)
                log.debug(f"Chunking sémantique utilisé pour {rel_path}: {len(chunks)} chunks créés")
            else:
                # Fallback: chunking basique
                try:
                    content = file_content.decode('utf-8', errors='ignore')
                    if len(content) < 10:
                        continue
                    
                    # Chunking simple par taille
                    chunk_size = 1500
                    chunks = []
                    lines = content.split('\n')
                    current_chunk = []
                    current_start = 1
                    
                    for line_num, line in enumerate(lines, 1):
                        current_chunk.append(line)
                        if len('\n'.join(current_chunk)) >= chunk_size:
                            chunk_text = '\n'.join(current_chunk)
                            chunks.append({
                                'content': f"Fichier: {os.path.basename(file_path)}\n{chunk_text}",
                                'start_line': current_start,
                                'end_line': line_num,
                                'ast_type': 'text_block',
                                'parent_context': f"Fichier: {os.path.basename(file_path)}",
                                'raw_content': chunk_text
                            })
                            current_chunk = []
                            current_start = line_num + 1
                    
                    # Dernier chunk
                    if current_chunk:
                        chunk_text = '\n'.join(current_chunk)
                        chunks.append({
                            'content': f"Fichier: {os.path.basename(file_path)}\n{chunk_text}",
                            'start_line': current_start,
                            'end_line': len(lines),
                            'ast_type': 'text_block',
                            'parent_context': f"Fichier: {os.path.basename(file_path)}",
                            'raw_content': chunk_text
                        })
                except Exception as e:
                    log.warning(f"Erreur chunking basique {file_path}: {e}")
                    continue
            
            # Ajouter les chunks à la base
            for chunk_idx, chunk_data in enumerate(chunks):
                chunk_id = _add_chunk_to_db(file_id, chunk_idx, chunk_data)
                if chunk_id:
                    total_chunks += 1
            
            count += 1
                
            if progress_callback and i % 5 == 0:
                progress_callback(f"Indexation: {rel_path} ({i}/{total}) - {len(chunks)} chunks")
                
        except Exception as e:
            errors += 1
            log.warning(f"⚠️ Échec indexation {os.path.basename(file_path)}: {e}")
            
    return f"Indexation terminée. {count} fichiers indexés, {total_chunks} chunks créés, {errors} erreurs."

@trace_action(source="database")
def delete_local_db():
    """Supprime physiquement les fichiers de la base de données."""
    global faiss_index, id_mapping
    
    sqlite_path, index_path, map_path = _get_paths()
    deleted = []
    
    try:
        # Reset mémoire
        faiss_index = None
        id_mapping = {}
        
        # Suppression disque
        for p in [sqlite_path, index_path, map_path]:
            if os.path.exists(p):
                os.remove(p)
                deleted.append(os.path.basename(p))
                
        # Réinit immédiate pour éviter crash si appel suivant
        init_db()
        return f"Base supprimée : {', '.join(deleted)}"
    except Exception as e:
        return f"Erreur suppression : {e}"

# --- Support Mémoire Sémantique ---
@trace_action(source="database")
def store_memory(text_content, metadata=None):
    try:
        mem_id = hashlib.md5(f"{text_content}{time.time()}".encode()).hexdigest()[:8]
        if not metadata: metadata = {}
        metadata.update({"type": "memory", "memory_id": mem_id})
        
        success = add_knowledge(f"memory://{mem_id}", text_content, metadata=metadata)
        if success: log.info(f"🧠 Souvenir ancré : {mem_id}")
        return success
    except Exception as e:
        log.error(f"Erreur mémoire: {e}")
        return False

@trace_action(source="database")
def search_memories(query, n_results=3):
    try:
        raw_results, _ = search_vector_db(query, max_results=n_results * 4)
        memories = []
        for path, content, score in raw_results:
            if path and path.startswith("memory://"):
                memories.append((path, content, score))
                if len(memories) >= n_results: break
        return memories
    except Exception: return []


@trace_action(source="database")
def sync_incremental(root_path: str, progress_callback=None, state_file: str = None):
    """
    Synchronisation incrémentale: ré-indexe uniquement les fichiers modifiés.
    
    Utilise Merkle Tree pour détecter les changements en O(log n).
    
    Args:
        root_path: Chemin racine du projet
        progress_callback: Fonction de callback pour le progrès
        state_file: Chemin du fichier de sauvegarde d'état (optionnel)
    
    Returns:
        Message de résultat
    """
    from .merkle_sync import MerkleTreeSync
    
    if state_file is None:
        state_file = get_path("db/merkle_state.json")
    
    # Construire l'arbre Merkle actuel
    current_tree = MerkleTreeSync(root_path)
    current_tree.build_tree()
    
    # Charger l'état précédent
    previous_hashes = MerkleTreeSync.load_state(state_file)
    
    # Construire un arbre minimal pour la comparaison
    from .merkle_sync import MerkleNode
    
    previous_tree = MerkleTreeSync(root_path)
    for file_path, file_hash in previous_hashes.items():
        if os.path.exists(file_path):
            node = MerkleNode(file_path, is_file=True, hash_value=file_hash)
            previous_tree.node_map[file_path] = node
    
    # Comparer les arbres
    modified_files = current_tree.compare_trees(previous_tree)
    
    if not modified_files:
        log.info("✅ Aucun fichier modifié détecté")
        return "Aucun fichier modifié. Index à jour."
    
    log.info(f"📝 {len(modified_files)} fichiers modifiés détectés")
    
    # Ré-indexer uniquement les fichiers modifiés
    count = 0
    errors = 0
    
    for file_path in modified_files:
        try:
            rel_path = os.path.relpath(file_path, root_path)
            
            # Calculer le checksum
            with open(file_path, 'rb') as f:
                file_content = f.read()
            checksum = hashlib.sha256(file_content).hexdigest()
            
            # Récupérer ou créer l'ID du fichier
            file_id = _get_or_create_file_id(rel_path, checksum)
            
            # Supprimer les anciens chunks
            _delete_file_chunks(file_id)
            
            # Chunking et indexation (utiliser la même logique que index_project_files)
            from .code_chunker import get_chunker
            
            chunker = get_chunker()
            is_python = file_path.lower().endswith('.py')
            
            if is_python and chunker.parser:
                chunks = chunker.chunk_file(file_path)
            else:
                # Fallback chunking basique
                content = file_content.decode('utf-8', errors='ignore')
                if len(content) < 10:
                    continue
                
                chunks = [{
                    'content': f"Fichier: {os.path.basename(file_path)}\n{content}",
                    'start_line': 1,
                    'end_line': len(content.split('\n')),
                    'ast_type': 'text_block',
                    'parent_context': f"Fichier: {os.path.basename(file_path)}",
                    'raw_content': content
                }]
            
            # Ajouter les chunks
            for chunk_idx, chunk_data in enumerate(chunks):
                _add_chunk_to_db(file_id, chunk_idx, chunk_data)
            
            count += 1
            
            if progress_callback:
                progress_callback(f"Sync: {rel_path} ({count}/{len(modified_files)})")
                
        except Exception as e:
            errors += 1
            log.warning(f"⚠️ Échec sync {os.path.basename(file_path)}: {e}")
    
    # Sauvegarder le nouvel état
    current_tree.save_state(state_file)
    
    return f"Sync incrémentale terminée. {count} fichiers ré-indexés, {errors} erreurs."
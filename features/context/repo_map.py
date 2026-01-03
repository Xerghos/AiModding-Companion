"""
Module de génération de la Repo Map (carte compressée du dépôt).
Extrait uniquement les signatures (sans corps) pour injection dans le contexte LLM.
"""

import os
import logging
import time
import hashlib
import threading
from typing import List, Dict, Optional, Any
from config import get_logger, get_path
from config.utils import charger_json_robuste, sauvegarder_json
from features.Documentation import calculate_file_hash
from features.context.merkle_sync import MerkleTreeSync, get_ready_merkle_tree
from features.Decorators import trace_action

log = get_logger("features.context.repo_map")

# Cache pour la Repo Map (gain estimé: 2-3s par requête)
_repo_map_cache: Optional[Dict[str, any]] = None
REPO_MAP_CACHE_TIMEOUT = 60  # 60 secondes comme spécifié dans le plan

# Constantes pour le cache persistant
CACHE_DIR = "cache"  # Dossier relatif au workspace
REPO_MAP_CACHE_FILE = "repo_map_cache.json"
REPO_MAP_HASH_FILE = "repo_map_hash.json"

# Variables globales pour le Request Coalescing (Fusion de requêtes)
_active_generation_event: Optional[threading.Event] = None
_coalescing_lock = threading.Lock()


class RepoMapGenerator:
    """
    Générateur de Repo Map : carte structurelle compressée du projet.
    """
    
    def __init__(self, db_path_base=None):
        """
        Args:
            db_path_base: Chemin de base de la base de données
        """
        self.db_path_base = db_path_base
        self._last_hash_check_time = 0
        self._last_hash_check_result = False
    
    def _get_cache_path(self, filename: str) -> str:
        """Retourne le chemin absolu du fichier de cache."""
        cache_dir = get_path(CACHE_DIR)
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, filename)
    
    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """Charge le cache depuis le disque (utilise utilitaire amélioré)."""
        cache_path = self._get_cache_path(REPO_MAP_CACHE_FILE)
        cache_data = charger_json_robuste(cache_path, default_return=None)
        if cache_data and isinstance(cache_data, dict):
            log.debug(f"✅ Cache Repo Map chargé depuis {cache_path}")
            return cache_data
        return None
    
    def _save_cache(self, content: str, top_n: int, db_path_base: str) -> None:
        """Sauvegarde le cache sur le disque (utilise utilitaire existant)."""
        cache_path = self._get_cache_path(REPO_MAP_CACHE_FILE)
        cache_data = {
            "content": content,
            "timestamp": time.time(),
            "top_n": top_n,
            "db_path_base": str(db_path_base) if db_path_base else None
        }
        if sauvegarder_json(cache_path, cache_data):
            log.info(f"✅ Cache Repo Map sauvegardé: {len(content)} caractères")
        else:
            log.warning(f"⚠️ Échec sauvegarde cache Repo Map")
    
    def _get_project_hash(self) -> str:
        """Calcule le hash global du projet via UN SEUL arbre Merkle (optimisé).
        Utilise la même optimisation que CacheManager pour éviter les constructions multiples.
        """
        from config.settings import APP_SETTINGS
        
        # OPTIMISATION : Construire UN SEUL arbre Merkle pour la racine du projet
        project_root = os.path.dirname(get_path("."))  # Racine du projet
        
        hasher = hashlib.sha256()
        
        # 1. Arbre Merkle pour TOUT le projet (une seule construction au lieu de 3)
        try:
            # Utiliser get_ready_merkle_tree() pour obtenir l'arbre déjà construit (thread-safe)
            merkle, root = get_ready_merkle_tree(project_root)
            if root and root.hash:
                hasher.update(root.hash.encode())
                log.debug(f"✅ Arbre Merkle projet: {len(merkle.node_map)} nœuds")
        except Exception as e:
            log.warning(f"Erreur construction Merkle projet: {e}")
        
        # 2. Ajouter les fichiers surveillés individuellement (si en dehors de l'arbre)
        cache_config = APP_SETTINGS.get("repo_map_cache", {})
        watch_files = cache_config.get("watch_files", ["config/architecture_map.json"])
        for file_path in watch_files:
            abs_file = get_path(file_path) if not os.path.isabs(file_path) else file_path
            if os.path.exists(abs_file):
                file_hash = calculate_file_hash(abs_file)
                if file_hash:
                    hasher.update(file_hash.encode())
        
        return hasher.hexdigest()
    
    def _save_project_hash(self, project_hash: str) -> None:
        """Sauvegarde le hash du projet (utilise utilitaire amélioré)."""
        hash_path = self._get_cache_path(REPO_MAP_HASH_FILE)
        sauvegarder_json(hash_path, {"hash": project_hash, "timestamp": time.time()})
    
    def _load_project_hash(self) -> Optional[str]:
        """Charge le hash précédent (utilise utilitaire amélioré)."""
        hash_path = self._get_cache_path(REPO_MAP_HASH_FILE)
        data = charger_json_robuste(hash_path, default_return=None)
        return data.get("hash") if isinstance(data, dict) else None
    
    def _is_cache_valid(self, cache_data: Dict[str, Any]) -> bool:
        """Vérifie si le cache est valide (basé uniquement sur le hash du projet)."""
        if not cache_data:
            return False
        
        # 1. Protection anti-spam pour le hash check (max 1 check toutes les 5s)
        current_time = time.time()
        if current_time - self._last_hash_check_time < 5.0:
            return self._last_hash_check_result

        # Note: On ne vérifie plus l'âge du cache. Tant que le hash du projet 
        # (calculé via Merkle Tree) est identique, le cache est valide.
        # Le Merkle Tree est très rapide à vérifier grâce au cache niveau OS/Python.
        
        # Vérifier le hash
        previous_hash = self._load_project_hash()
        current_hash = self._get_project_hash()
        
        is_valid = (previous_hash == current_hash)
        if not is_valid:
            log.debug(f"Hash projet changé: {previous_hash[:8] if previous_hash else 'None'}... -> {current_hash[:8]}...")
        
        self._last_hash_check_time = current_time
        self._last_hash_check_result = is_valid
        return is_valid
    
    def invalidate_cache(self) -> None:
        """Invalide le cache manuellement."""
        cache_path = self._get_cache_path(REPO_MAP_CACHE_FILE)
        hash_path = self._get_cache_path(REPO_MAP_HASH_FILE)
        try:
            if os.path.exists(cache_path):
                os.remove(cache_path)
            if os.path.exists(hash_path):
                os.remove(hash_path)
            log.info("🗑️ Cache Repo Map invalidé manuellement")
        except Exception as e:
            log.warning(f"Erreur invalidation cache: {e}")
    
    def _regenerate_and_save(self, top_n: int) -> str:
        """Exécute la régénération effective (synchrone)."""
        import time
        total_start = time.time()
        
        try:
            from .symbol_graph import get_symbol_graph
            
            step_start = time.time()
            symbol_graph = get_symbol_graph(self.db_path_base)
            log.info(f"  ⏱️  get_symbol_graph: {time.time() - step_start:.2f}s")
            
            step_start = time.time()
            top_files = symbol_graph.get_top_files(top_n)
            log.info(f"  ⏱️  get_top_files({top_n}): {time.time() - step_start:.2f}s")
            
            if not top_files:
                log.warning("Aucun fichier trouvé pour la Repo Map")
                return ""
            
            log.info(f"  📝 Extraction signatures de {len(top_files)} fichiers...")
            step_start = time.time()
            
            repo_map_lines = []
            repo_map_lines.append("# Repo Map - Fichiers Centraux\n")
            
            for idx, (file_path, pagerank_score) in enumerate(top_files, 1):
                abs_path = get_path(file_path) if not os.path.isabs(file_path) else file_path
                
                if not os.path.exists(abs_path):
                    continue
                
                file_start = time.time()
                signatures_data = self._extract_signatures(abs_path)
                file_elapsed = time.time() - file_start
                
                if file_elapsed > 1.0:  # Log seulement si > 1s
                    log.info(f"    ⚠️  {os.path.basename(file_path)}: {file_elapsed:.2f}s")
                
                if signatures_data:
                    repo_map_lines.append(f"\n# Fichier: {file_path} (PageRank: {pagerank_score:.4f})")
                    
                    classes = [s for s in signatures_data if s.get('ast_type') == 'class']
                    functions = [s for s in signatures_data if s.get('ast_type') == 'function']
                    
                    for class_data in classes:
                        class_sig = class_data['signature']
                        if class_data.get('docstring'):
                            class_sig += f"\n    \"\"\"{class_data['docstring']}\"\"\""
                        repo_map_lines.append(f"{class_sig}")
                        
                        methods = class_data.get('methods', [])
                        for method_data in methods:
                            method_sig = method_data['signature']
                            if method_data.get('docstring'):
                                method_sig += f"  # {method_data['docstring']}"
                            repo_map_lines.append(f"  {method_sig}")
                    
                    for func_data in functions:
                        func_sig = func_data['signature']
                        if func_data.get('docstring'):
                            func_sig += f"  # {func_data['docstring']}"
                        repo_map_lines.append(func_sig)
            
            extraction_elapsed = time.time() - step_start
            log.info(f"  ⏱️  Extraction signatures: {extraction_elapsed:.2f}s")
            
            repo_map_text = "\n".join(repo_map_lines)
            # Log seulement en cas de régénération (pas pour utilisation silencieuse du cache)
            log.info(f"✅ Repo Map régénérée: {len(top_files)} fichiers, {len(repo_map_text)} caractères")
            
            step_start = time.time()
            self._save_cache(repo_map_text, top_n, self.db_path_base)
            project_hash = self._get_project_hash()
            self._save_project_hash(project_hash)
            cache_elapsed = time.time() - step_start
            log.info(f"  ⏱️  Sauvegarde cache: {cache_elapsed:.2f}s")
            
            # Mettre à jour le cache mémoire global
            global _repo_map_cache
            _repo_map_cache = {
                'content': repo_map_text,
                'timestamp': time.time()
            }
            
            total_elapsed = time.time() - total_start
            log.info(f"  ⏱️  Total régénération: {total_elapsed:.2f}s")
            
            return repo_map_text
        except Exception as e:
            log.warning(f"Erreur régénération Repo Map: {e}")
            import traceback
            log.debug(traceback.format_exc())
            return ""

    @trace_action(source="repo_map")
    def generate_repo_map(self, top_n: int = 20) -> str:
        """
        Génère la Repo Map avec mécanisme 'Request Coalescing'.
        Garantit qu'une seule régénération s'exécute à la fois, même avec N threads appelants.
        """
        global _active_generation_event
        
        # 1. Vérifier le cache (Fast Path)
        cache_data = self._load_cache()
        if cache_data and self._is_cache_valid(cache_data):
            return cache_data.get('content', '')
        
        # 2. Gestion de la concurrence (Request Coalescing)
        my_event = None
        i_am_generator = False
        
        with _coalescing_lock:
            # Re-vérifier le cache sous lock (Double-Check Locking)
            cache_data = self._load_cache()
            if cache_data and self._is_cache_valid(cache_data):
                return cache_data.get('content', '')
            
            # Si une génération est déjà en cours, on attend
            if _active_generation_event is not None:
                event_to_wait = _active_generation_event
            else:
                # Sinon, on devient le générateur
                i_am_generator = True
                my_event = threading.Event()
                _active_generation_event = my_event
        
        if not i_am_generator:
            # On attend que le générateur finisse
            log.debug("⏳ Attente de la fin de régénération Repo Map en cours...")
            if event_to_wait.wait(timeout=30.0):
                # Récupérer le résultat frais
                cache_data = self._load_cache()
                return cache_data.get('content', '') if cache_data else ""
            else:
                log.warning("⚠️ Timeout attente régénération Repo Map")
                # Fallback: utiliser le vieux cache si dispo
                return cache_data.get('content', '') if cache_data else ""
        
        # 3. Exécution de la génération (Seulement par le générateur)
        try:
            log.info("🚀 Démarrage régénération unique Repo Map...")
            result = self._regenerate_and_save(top_n)
            return result
        finally:
            # 4. Libération et notification
            with _coalescing_lock:
                _active_generation_event = None
            if my_event:
                my_event.set()  # Réveille tous les threads en attente
    
    def _extract_signatures(self, file_path: str) -> List[Dict[str, str]]:
        """
        Extrait les signatures enrichies (avec paramètres, types, docstrings) d'un fichier Python.
        
        Args:
            file_path: Chemin du fichier
        
        Returns:
            Liste de dictionnaires avec 'signature', 'parent', 'ast_type', 'docstring', 'methods' (pour classes)
        """
        signatures_data = []
        
        if not file_path.lower().endswith('.py'):
            return signatures_data
        
        try:
            import time
            chunk_start = time.time()
            from .code_chunker import get_chunker
            
            chunker = get_chunker()
            chunk_elapsed = time.time() - chunk_start
            if chunk_elapsed > 0.5:  # Log seulement si > 0.5s (initialisation tree-sitter)
                log.info(f"    🔧 get_chunker(): {chunk_elapsed:.2f}s")
            
            if not chunker.parser:
                # Fallback: extraction basique
                return self._extract_signatures_basic_enriched(file_path)
            
            # Lire le fichier pour extraire les signatures complètes
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()
            
            source_bytes = source_code.encode('utf-8')
            tree = chunker.parser.parse(source_bytes)
            
            # Extraire classes et fonctions/méthodes en parcourant l'AST
            classes = {}
            functions = []
            
            def traverse_node(node, parent_class=None):
                """Traverse récursivement l'AST pour trouver classes et fonctions."""
                if node.type == 'class_definition':
                    # Extraire signature de classe
                    class_sig = chunker._extract_class_signature(node, source_bytes)
                    if class_sig:
                        class_name = None
                        for child in node.children:
                            if child.type == 'identifier':
                                class_name = self._get_node_text(child, source_bytes)
                                break
                        
                        if class_name:
                            docstring = self._extract_docstring_from_class(node, source_bytes)
                            classes[class_name] = {
                                'signature': class_sig,
                                'parent': f"Fichier: {os.path.basename(file_path)}",
                                'ast_type': 'class',
                                'docstring': docstring,
                                'name': class_name,
                                'methods': []
                            }
                            
                            # Parcourir les enfants pour trouver les méthodes
                            for child in node.children:
                                if child.type == 'class_body':
                                    for stmt in child.children:
                                        if stmt.type == 'function_definition':
                                            traverse_node(stmt, parent_class=class_name)
                elif node.type == 'function_definition':
                    # Extraire signature de fonction/méthode
                    func_name = None
                    for child in node.children:
                        if child.type == 'identifier':
                            func_name = self._get_node_text(child, source_bytes)
                            break
                    
                    if func_name:
                        # Filtrer les fonctions triviales
                        if self._is_trivial_function(node, source_bytes, func_name):
                            return
                        
                        # Extraire signature complète
                        full_sig = chunker._extract_function_signature(node, source_bytes)
                        if not full_sig:
                            return
                        
                        # Extraire docstring
                        docstring = self._extract_docstring_from_function(node, source_bytes)
                        
                        func_data = {
                            'signature': full_sig,
                            'ast_type': 'method' if parent_class else 'function',
                            'docstring': docstring,
                            'name': func_name,
                            'class': parent_class
                        }
                        
                        if parent_class:
                            # C'est une méthode, l'ajouter à la classe
                            if parent_class in classes:
                                classes[parent_class]['methods'].append(func_data)
                            else:
                                # Classe non trouvée (cas rare), traiter comme fonction globale
                                func_data['parent'] = f"Fichier: {os.path.basename(file_path)}"
                                functions.append(func_data)
                        else:
                            # Fonction globale
                            func_data['parent'] = f"Fichier: {os.path.basename(file_path)}"
                            functions.append(func_data)
                else:
                    # Parcourir récursivement les enfants
                    for child in node.children:
                        traverse_node(child, parent_class)
            
            # Parcourir l'AST depuis la racine
            traverse_node(tree.root_node)
        
        except Exception as e:
            log.warning(f"Erreur extraction signatures {file_path}: {e}")
            return self._extract_signatures_basic_enriched(file_path)
        
        # Organiser les résultats : classes avec leurs méthodes, puis fonctions globales
        result = []
        
        # Ajouter classes avec leurs méthodes
        for class_name, class_data in classes.items():
            result.append({
                'signature': class_data['signature'],
                'parent': class_data['parent'],
                'ast_type': 'class',
                'docstring': class_data['docstring'],
                'name': class_name,
                'methods': class_data.get('methods', [])
            })
        
        # Ajouter fonctions globales
        result.extend(functions)
        
        return result
    
    def _is_trivial_function(self, func_node, source_bytes: bytes, func_name: str) -> bool:
        """
        Détecte si une fonction est triviale (wrapper, accesseur simple).
        
        Patterns détectés:
        - Getters simples: return self.attr
        - Setters simples: self.attr = value
        - Wrappers: return other_func()
        - Fonctions très courtes (< 3 lignes de corps)
        """
        try:
            # Trouver le corps de la fonction
            body = None
            for child in func_node.children:
                if child.type == 'block':
                    body = child
                    break
            
            if not body or len(body.children) == 0:
                return True  # Fonction vide = triviale
            
            # Compter les statements non-triviaux
            non_trivial_count = 0
            body_text = ""
            
            for stmt in body.children:
                if stmt.type in ['expression_statement', 'return_statement', 'if_statement', 
                                'for_statement', 'while_statement', 'try_statement', 'with_statement']:
                    stmt_text = self._get_node_text(stmt, source_bytes).strip()
                    # Ignorer docstrings et pass
                    if stmt_text and not stmt_text.startswith('"""') and not stmt_text.startswith("'''") and stmt_text != 'pass':
                        non_trivial_count += 1
                        body_text += stmt_text + " "
            
            # Si moins de 2 statements non-triviaux, considérer comme trivial
            if non_trivial_count < 2:
                # Vérifier si c'est un simple wrapper/accesseur
                body_lower = body_text.lower()
                patterns_trivial = [
                    f'return self.{func_name}',  # Getter auto-ref
                    f'self.{func_name} =',  # Setter auto-ref
                    'return self.',  # Simple getter
                    'self. = ',  # Simple setter
                ]
                
                # Si le corps est très court et correspond à un pattern trivial
                if len(body_text.strip()) < 50:
                    for pattern in patterns_trivial:
                        if pattern in body_lower:
                            return True
            
            return False
        except Exception:
            return False
    
    def _get_node_text(self, node, source_bytes: bytes) -> str:
        """Helper pour extraire le texte d'un nœud."""
        from .code_chunker import get_chunker
        chunker = get_chunker()
        if hasattr(chunker, '_get_node_text'):
            result = chunker._get_node_text(node, source_bytes)
            # _get_node_text dans code_chunker retourne déjà une string
            if isinstance(result, str):
                return result
            # Si c'est des bytes, décoder
            return result.decode('utf-8', errors='ignore')
        # Fallback: extraire bytes et décoder
        start_byte = node.start_byte
        end_byte = node.end_byte
        return source_bytes[start_byte:end_byte].decode('utf-8', errors='ignore')
    
    def _extract_docstring_from_function(self, func_node, source_bytes: bytes) -> str:
        """Extrait la docstring d'une fonction (première ligne seulement)."""
        try:
            body = None
            for child in func_node.children:
                if child.type == 'block':
                    body = child
                    break
            
            if body and len(body.children) > 0:
                first_stmt = body.children[0]
                if first_stmt.type == 'expression_statement':
                    expr = first_stmt.children[0] if first_stmt.children else None
                    if expr and expr.type == 'string':
                        docstring = self._get_node_text(expr, source_bytes).strip('"\'').strip()
                        # Prendre seulement la première ligne
                        first_line = docstring.split('\n')[0].strip()
                        if len(first_line) > 100:
                            first_line = first_line[:100] + "..."
                        return first_line
        except Exception:
            pass
        return ""
    
    def _extract_docstring_from_class(self, class_node, source_bytes: bytes) -> str:
        """Extrait la docstring d'une classe (première ligne seulement)."""
        try:
            body = None
            for child in class_node.children:
                if child.type == 'class_body':
                    body = child
                    break
            
            if body and len(body.children) > 0:
                first_stmt = body.children[0]
                if first_stmt.type == 'expression_statement':
                    expr = first_stmt.children[0] if first_stmt.children else None
                    if expr and expr.type == 'string':
                        docstring = self._get_node_text(expr, source_bytes).strip('"\'').strip()
                        first_line = docstring.split('\n')[0].strip()
                        if len(first_line) > 100:
                            first_line = first_line[:100] + "..."
                        return first_line
        except Exception:
            pass
        return ""
    
    def _extract_signatures_basic_enriched(self, file_path: str) -> List[Dict[str, str]]:
        """Extraction basique enrichie des signatures (fallback)."""
        signatures_data = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            current_class = None
            
            for line in lines:
                line_stripped = line.strip()
                # Détecter les définitions de classes
                if line_stripped.startswith('class ') and ':' in line_stripped:
                    class_sig = line_stripped.split(':')[0].strip()
                    class_name = class_sig.replace('class ', '').split('(')[0].strip()
                    current_class = class_name
                    signatures_data.append({
                        'signature': class_sig,
                        'parent': f"Fichier: {os.path.basename(file_path)}",
                        'ast_type': 'class',
                        'docstring': '',
                        'name': class_name,
                        'methods': []
                    })
                # Détecter les définitions de fonctions
                elif line_stripped.startswith('def ') and ':' in line_stripped:
                    func_sig = line_stripped.split(':')[0].strip()
                    func_name = func_sig.replace('def ', '').split('(')[0].strip()
                    if current_class:
                        parent = f"Fichier: {os.path.basename(file_path)} > Classe: {current_class}"
                        ast_type = 'method'
                    else:
                        parent = f"Fichier: {os.path.basename(file_path)}"
                        ast_type = 'function'
                    signatures_data.append({
                        'signature': func_sig,
                        'parent': parent,
                        'ast_type': ast_type,
                        'docstring': '',
                        'name': func_name,
                        'class': current_class
                    })
        
        except Exception as e:
            log.warning(f"Erreur extraction basique {file_path}: {e}")
        
        return signatures_data
    
    @trace_action(source="repo_map")
    def get_repo_map(self) -> str:
        """
        Retourne la Repo Map complète pour le cache (sans limite de taille).
        
        Returns:
            Repo Map complète
        """
        return self.generate_repo_map()
    
    @trace_action(source="repo_map")
    def get_repo_map_for_context(self, max_chars: Optional[int] = None) -> str:
        """
        Retourne la Repo Map formatée pour injection dans le contexte LLM.
        
        Args:
            max_chars: Nombre maximum de caractères (None = pas de limite)
        
        Returns:
            Repo Map complète (non tronquée par défaut)
        """
        repo_map = self.generate_repo_map()
        
        # Tronquer seulement si max_chars est spécifié et non None
        if max_chars is not None and len(repo_map) > max_chars:
            repo_map = repo_map[:max_chars] + "\n... (tronqué)"
        
        return repo_map


# Instance globale
_repo_map_generator: Optional[RepoMapGenerator] = None

def get_repo_map_generator(db_path_base=None) -> RepoMapGenerator:
    """Retourne l'instance singleton du générateur Repo Map."""
    global _repo_map_generator
    if _repo_map_generator is None:
        _repo_map_generator = RepoMapGenerator(db_path_base)
    return _repo_map_generator


def get_cached_repo_map(db_path_base=None, max_chars: Optional[int] = None) -> str:
    """
    Récupère la Repo Map. Utilise le générateur qui gère le cache et la régénération async.
    
    Args:
        db_path_base: Chemin de base de la base de données
        max_chars: Nombre maximum de caractères (None = pas de limite)
    
    Returns:
        Repo Map formatée
    """
    global _repo_map_cache
    
    repo_map_gen = get_repo_map_generator(db_path_base)
    
    # generate_repo_map gère déjà:
    # 1. Le cache mémoire/disque
    # 2. La validation (hash check avec debounce)
    # 3. La régénération asynchrone si périmé
    # 4. Le lock anti-doublon pour les threads
    cached_content = repo_map_gen.generate_repo_map()
    
    if max_chars is not None and len(cached_content) > max_chars:
        return cached_content[:max_chars] + "\n... (tronqué)"
    return cached_content


def invalidate_repo_map_cache():
    """Invalide le cache Repo Map (mémoire + disque)."""
    global _repo_map_cache, _repo_map_generator
    _repo_map_cache = None
    
    # Invalider aussi le cache disque
    if _repo_map_generator:
        _repo_map_generator.invalidate_cache()
    else:
        # Si le générateur n'existe pas encore, supprimer directement les fichiers
        cache_dir = get_path(CACHE_DIR)
        cache_file = os.path.join(cache_dir, REPO_MAP_CACHE_FILE)
        hash_file = os.path.join(cache_dir, REPO_MAP_HASH_FILE)
        for f in [cache_file, hash_file]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
    
    log.debug("🗑️ Cache Repo Map invalidé (mémoire + disque)")


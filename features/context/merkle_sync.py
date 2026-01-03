"""
Module de synchronisation incrémentale via arbre de Merkle.
Détecte les fichiers modifiés sans ré-indexer l'intégralité du projet.
"""

import os
import hashlib
import logging
import fnmatch
import threading
import time
from typing import Dict, List, Optional, Tuple
from config import get_logger
from features.Decorators import trace_action

log = get_logger("features.context.merkle_sync")

# Import pour PathSpec (optionnel, géré par gitignore_parser)
try:
    from pathspec import PathSpec
    PATHSPEC_AVAILABLE = True
except ImportError:
    PathSpec = None
    PATHSPEC_AVAILABLE = False

# Cache pour les patterns d'exclusion
import time
_exclusion_cache = {
    'timestamp': 0,
    'data': None,
    'root_path': None
}
EXCLUSION_CACHE_TTL = 10  # 10 secondes

def get_exclusion_patterns(root_path: str) -> Tuple[Optional['PathSpec'], set[str], set[str]]:
    """
    Récupère tous les patterns d'exclusion depuis :
    1. .gitignore (via pathspec)
    2. code_analysis.ignored_folders (settings)
    3. system_settings.ignored_files (settings)
    4. Liste de fallback par défaut
    
    Args:
        root_path: Chemin racine du projet
    
    Returns:
        (gitignore_spec, excluded_dirs_set, excluded_files_set)
    """
    global _exclusion_cache
    current_time = time.time()
    
    # Vérifier le cache
    if (_exclusion_cache['data'] and 
        _exclusion_cache['root_path'] == root_path and 
        current_time - _exclusion_cache['timestamp'] < EXCLUSION_CACHE_TTL):
        return _exclusion_cache['data']

    from features.gitignore_parser import load_gitignore_patterns
    from config.settings import APP_SETTINGS
    
    # 1. Charger .gitignore
    gitignore_spec = load_gitignore_patterns(root_path)
    
    # 2. Charger depuis settings
    ignored_folders = APP_SETTINGS.get("code_analysis", {}).get("ignored_folders", [])
    ignored_files = APP_SETTINGS.get("system_settings", {}).get("ignored_files", [])
    
    # 3. Fallback par défaut
    default_dirs = {'.git', '__pycache__', 'venv', 'env', 'node_modules', 
                   'db', 'logs', 'dist', 'build', 'audio_cache', '.idea', '.vscode', '.cursor'}
    default_files = {'.pyc', '.pyo', '.pyd', '.log', '.tmp', '.cache'}
    
    # Combiner tous les patterns
    excluded_dirs = set(default_dirs)
    excluded_files = set(default_files)
    
    # Ajouter les patterns depuis settings (supporter wildcards)
    for pattern in ignored_folders:
        if pattern:
            excluded_dirs.add(pattern.strip())
    
    for pattern in ignored_files:
        if pattern:
            excluded_files.add(pattern.strip())
    
    result = (gitignore_spec, excluded_dirs, excluded_files)
    
    # Mettre à jour le cache
    _exclusion_cache['timestamp'] = current_time
    _exclusion_cache['root_path'] = root_path
    _exclusion_cache['data'] = result
    
    return result


def should_exclude_path(file_path: str, root_path: str, 
                        gitignore_spec: Optional['PathSpec'],
                        excluded_dirs: set[str],
                        excluded_files: set[str]) -> bool:
    """
    Vérifie si un chemin doit être exclu selon toutes les sources.
    
    Args:
        file_path: Chemin absolu du fichier/dossier
        root_path: Chemin racine du projet
        gitignore_spec: PathSpec pré-chargé depuis .gitignore
        excluded_dirs: Set de patterns de dossiers à exclure
        excluded_files: Set de patterns de fichiers à exclure
    
    Returns:
        True si le chemin doit être exclu
    """
    from features.gitignore_parser import should_ignore_path
    
    # 1. Vérifier .gitignore
    if gitignore_spec and should_ignore_path(file_path, root_path, gitignore_spec):
        return True
    
    # 2. Vérifier les patterns de dossiers
    try:
        rel_path = os.path.relpath(file_path, root_path).replace('\\', '/')
        path_segments = rel_path.split('/')
        
        for pattern in excluded_dirs:
            # Support wildcards
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(os.path.basename(file_path), pattern):
                return True
            # Support segment exact (comme dans Documentation.py)
            if pattern in path_segments:
                return True
        
        # 3. Vérifier les patterns de fichiers
        filename = os.path.basename(file_path)
        for pattern in excluded_files:
            if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_path, pattern):
                return True
    except ValueError:
        # Chemin hors de root_path
        pass
    
    return False


class MerkleNode:
    """Représente un nœud dans l'arbre de Merkle."""
    
    def __init__(self, path: str, is_file: bool = True, hash_value: Optional[str] = None):
        self.path = path
        self.is_file = is_file
        self.hash = hash_value
        self.children: List['MerkleNode'] = []
    
    def add_child(self, child: 'MerkleNode'):
        """Ajoute un enfant au nœud."""
        self.children.append(child)
    
    def compute_hash(self) -> str:
        """Calcule le hachage du nœud."""
        if self.is_file:
            # Pour un fichier, le hash est déjà calculé
            if not self.hash:
                self.hash = self._hash_file(self.path)
            return self.hash
        else:
            # Pour un répertoire, concaténer les hashs des enfants
            if not self.children:
                return hashlib.sha256(b"").hexdigest()
            
            child_hashes = sorted([child.compute_hash() for child in self.children])
            combined = "".join(child_hashes).encode('utf-8')
            self.hash = hashlib.sha256(combined).hexdigest()
            return self.hash
    
    @staticmethod
    def _hash_file(file_path: str) -> str:
        """Calcule le hash SHA-256 d'un fichier."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            log.warning(f"Erreur hachage fichier {file_path}: {e}")
            return hashlib.sha256(b"").hexdigest()


class MerkleTreeSync:
    """
    Gestionnaire de synchronisation incrémentale via arbre de Merkle.
    Permet de détecter les fichiers modifiés en O(log n).
    """
    
    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(root_path)
        self.root_node: Optional[MerkleNode] = None
        self.node_map: Dict[str, MerkleNode] = {}  # path -> node
    
    @trace_action(source="merkle_sync")
    def build_tree(self, exclude_dirs: Optional[List[str]] = None) -> MerkleNode:
        """
        Construit l'arbre de Merkle pour le système de fichiers.
        Utilise .gitignore + settings pour les exclusions.
        Thread-safe : peut être appelé depuis plusieurs threads.
        
        Args:
            exclude_dirs: Liste optionnelle de dossiers à exclure (s'ajoute aux exclusions depuis settings)
        
        Returns:
            Le nœud racine de l'arbre
        """
        # Utiliser un lock interne pour protéger la construction
        if not hasattr(self, '_build_lock'):
            self._build_lock = threading.Lock()
        
        with self._build_lock:
            # Si déjà construit, retourner le root_node existant
            if self.root_node is not None and self.root_node.hash:
                return self.root_node
            
            # Charger les exclusions depuis toutes les sources
            gitignore_spec, excluded_dirs_set, excluded_files_set = get_exclusion_patterns(self.root_path)
            
            # Si exclude_dirs est fourni explicitement, l'ajouter
            if exclude_dirs:
                excluded_dirs_set.update(exclude_dirs)
            
            # Utiliser excluded_dirs_set au lieu de exclude_dirs hardcodé
            self.root_node = self._build_node(self.root_path, excluded_dirs_set, 
                                              gitignore_spec, excluded_files_set)
            self.root_node.compute_hash()
            
            # Réduire la verbosité : seulement si vraiment nécessaire pour diagnostic
            if len(self.node_map) > 1000:  # Seulement pour gros arbres
                log.debug(f"✅ Arbre Merkle construit: {len(self.node_map)} nœuds")
            return self.root_node
    
    def _build_node(self, path: str, excluded_dirs: set[str], 
                    gitignore_spec: Optional['PathSpec'],
                    excluded_files: set[str]) -> MerkleNode:
        """Construit récursivement un nœud et ses enfants.
        
        Args:
            path: Chemin du fichier/dossier
            excluded_dirs: Set de patterns de dossiers à exclure
            gitignore_spec: PathSpec pré-chargé depuis .gitignore
            excluded_files: Set de patterns de fichiers à exclure
        
        Returns:
            MerkleNode pour ce chemin
        """
        if not os.path.exists(path):
            return MerkleNode(path, is_file=False, hash_value=hashlib.sha256(b"").hexdigest())
        
        # Vérifier si le chemin doit être exclu
        if should_exclude_path(path, self.root_path, gitignore_spec, excluded_dirs, excluded_files):
            return MerkleNode(path, is_file=False, hash_value=hashlib.sha256(b"").hexdigest())
        
        if os.path.isfile(path):
            # Fichier: créer un nœud feuille
            node = MerkleNode(path, is_file=True)
            self.node_map[path] = node
            return node
        else:
            # Répertoire: créer un nœud et parcourir les enfants
            node = MerkleNode(path, is_file=False)
            self.node_map[path] = node
            
            try:
                entries = sorted(os.listdir(path))
                for entry in entries:
                    entry_path = os.path.join(path, entry)
                    
                    # Vérifier exclusion avant de descendre
                    if should_exclude_path(entry_path, self.root_path, gitignore_spec, excluded_dirs, excluded_files):
                        continue
                    
                    child_node = self._build_node(entry_path, excluded_dirs, gitignore_spec, excluded_files)
                    node.add_child(child_node)
            except PermissionError:
                log.warning(f"Permission refusée pour {path}")
            except Exception as e:
                log.warning(f"Erreur parcours {path}: {e}")
            
            return node
    
    @trace_action(source="merkle_sync")
    def compare_trees(self, other_tree: 'MerkleTreeSync') -> List[str]:
        """
        Compare deux arbres de Merkle et retourne la liste des fichiers modifiés.
        
        Args:
            other_tree: L'autre arbre à comparer (généralement l'état précédent)
        
        Returns:
            Liste des chemins de fichiers modifiés
        """
        if not self.root_node or not other_tree.root_node:
            return []
        
        modified_files = []
        self._compare_nodes(self.root_node, other_tree.root_node, modified_files)
        
        return modified_files
    
    def _compare_nodes(self, node1: MerkleNode, node2: MerkleNode, modified_files: List[str]):
        """Compare récursivement deux nœuds."""
        # Si les hashs sont identiques, rien n'a changé dans cette branche
        if node1.hash == node2.hash:
            return
        
        # Si c'est un fichier et que le hash diffère, il est modifié
        if node1.is_file and node2.is_file:
            modified_files.append(node1.path)
            return
        
        # Pour les répertoires, comparer les enfants
        if not node1.is_file and not node2.is_file:
            # Créer un map des enfants par nom
            children1_map = {os.path.basename(c.path): c for c in node1.children}
            children2_map = {os.path.basename(c.path): c for c in node2.children}
            
            # Comparer les enfants communs
            common_names = set(children1_map.keys()) & set(children2_map.keys())
            for name in common_names:
                self._compare_nodes(children1_map[name], children2_map[name], modified_files)
            
            # Fichiers nouveaux ou supprimés
            new_files = set(children1_map.keys()) - set(children2_map.keys())
            deleted_files = set(children2_map.keys()) - set(children1_map.keys())
            
            for name in new_files:
                child = children1_map[name]
                if child.is_file:
                    modified_files.append(child.path)
                else:
                    # Nouveau répertoire: ajouter tous les fichiers dedans
                    self._collect_files(child, modified_files)
            
            for name in deleted_files:
                child = children2_map[name]
                if child.is_file:
                    # Fichier supprimé (on ne l'ajoute pas, mais on pourrait)
                    pass
                else:
                    # Répertoire supprimé: on ignore (sera géré par la suppression de la table)
                    pass
    
    def _collect_files(self, node: MerkleNode, files: List[str]):
        """Collecte récursivement tous les fichiers d'un nœud."""
        if node.is_file:
            files.append(node.path)
        else:
            for child in node.children:
                self._collect_files(child, files)
    
    @trace_action(source="merkle_sync")
    def get_file_hash(self, file_path: str) -> Optional[str]:
        """Retourne le hash d'un fichier spécifique."""
        node = self.node_map.get(file_path)
        if node and node.is_file:
            return node.compute_hash()
        return None
    
    def save_state(self, state_file: str):
        """Sauvegarde l'état actuel (hashs) dans un fichier."""
        import json
        
        state = {
            'root_hash': self.root_node.hash if self.root_node else None,
            'file_hashes': {
                path: node.hash
                for path, node in self.node_map.items()
                if node.is_file
            }
        }
        
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            log.info(f"État Merkle sauvegardé: {len(state['file_hashes'])} fichiers")
        except Exception as e:
            log.error(f"Erreur sauvegarde état: {e}")
    
    @staticmethod
    def load_state(state_file: str) -> Dict[str, str]:
        """Charge un état précédent depuis un fichier."""
        import json
        
        if not os.path.exists(state_file):
            return {}
        
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            return state.get('file_hashes', {})
        except Exception as e:
            log.error(f"Erreur chargement état: {e}")
            return {}

# Variables globales pour le cache partagé
_merkle_tree_cache = None
_merkle_tree_root_node = None  # Cache du root_node construit
_merkle_tree_lock = threading.Lock()
_merkle_tree_timestamp = 0
_merkle_tree_hash = None  # Hash du projet pour validation
_MERKLE_TREE_CACHE_TTL = 10  # 10 secondes de cache

@trace_action(source="merkle_sync")
def get_ready_merkle_tree(root_path: str, project_hash: str = None, force_rebuild: bool = False) -> Tuple[MerkleTreeSync, MerkleNode]:
    """Retourne une instance MerkleTreeSync et son root_node déjà construit.
    
    Cette fonction garantit que l'arbre est déjà construit et thread-safe.
    L'appelant n'a pas besoin d'appeler .build_tree().
    
    Args:
        root_path: Chemin racine du projet
        project_hash: Hash du projet pour validation (optionnel)
        force_rebuild: Si True, force la reconstruction même si cache valide
    
    Returns:
        Tuple (MerkleTreeSync instance, MerkleNode root_node)
    """
    global _merkle_tree_cache, _merkle_tree_root_node, _merkle_tree_timestamp, _merkle_tree_hash
    
    current_time = time.time()
    
    # Vérifier si le cache est valide
    if (not force_rebuild and 
        _merkle_tree_cache is not None and 
        _merkle_tree_cache.root_path == root_path and
        _merkle_tree_root_node is not None and
        current_time - _merkle_tree_timestamp < _MERKLE_TREE_CACHE_TTL):
        # Vérifier le hash si fourni
        if project_hash is None or _merkle_tree_hash == project_hash:
            return _merkle_tree_cache, _merkle_tree_root_node
    
    # Acquérir le lock pour créer/mettre à jour l'instance
    with _merkle_tree_lock:
        # Double-check après avoir acquis le lock
        if (not force_rebuild and 
            _merkle_tree_cache is not None and 
            _merkle_tree_cache.root_path == root_path and
            _merkle_tree_root_node is not None and
            current_time - _merkle_tree_timestamp < _MERKLE_TREE_CACHE_TTL):
            if project_hash is None or _merkle_tree_hash == project_hash:
                return _merkle_tree_cache, _merkle_tree_root_node
        
        # Créer une nouvelle instance et construire l'arbre (thread-safe)
        log.debug(f"🔨 Construction arbre Merkle pour {root_path}...")
        _merkle_tree_cache = MerkleTreeSync(root_path)
        _merkle_tree_root_node = _merkle_tree_cache.build_tree()  # Construction thread-safe
        _merkle_tree_timestamp = current_time
        _merkle_tree_hash = project_hash
        log.debug(f"✅ Arbre Merkle construit: {len(_merkle_tree_cache.node_map)} nœuds")
        return _merkle_tree_cache, _merkle_tree_root_node

# Alias pour compatibilité
def get_merkle_tree(root_path: str, force_rebuild: bool = False) -> MerkleTreeSync:
    """Alias simplifié qui retourne seulement l'instance (pour compatibilité legacy)."""
    tree, _ = get_ready_merkle_tree(root_path, force_rebuild=force_rebuild)
    return tree

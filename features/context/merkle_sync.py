"""
Module de synchronisation incrémentale via arbre de Merkle.
Détecte les fichiers modifiés sans ré-indexer l'intégralité du projet.
"""

import os
import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from config import get_logger
from features.Decorators import trace_action

log = get_logger("features.context.merkle_sync")


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
        
        Args:
            exclude_dirs: Liste de dossiers à exclure (ex: ['.git', '__pycache__'])
        
        Returns:
            Le nœud racine de l'arbre
        """
        if exclude_dirs is None:
            exclude_dirs = ['.git', '__pycache__', 'venv', 'env', 'node_modules', 
                          'db', 'logs', 'dist', 'build', 'audio_cache', '.idea', '.vscode']
        
        self.root_node = self._build_node(self.root_path, exclude_dirs)
        self.root_node.compute_hash()
        
        log.info(f"✅ Arbre Merkle construit: {len(self.node_map)} nœuds, hash racine: {self.root_node.hash[:16]}...")
        return self.root_node
    
    def _build_node(self, path: str, exclude_dirs: List[str]) -> MerkleNode:
        """Construit récursivement un nœud et ses enfants."""
        if not os.path.exists(path):
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
                    # Exclure certains dossiers
                    if entry in exclude_dirs:
                        continue
                    
                    entry_path = os.path.join(path, entry)
                    child_node = self._build_node(entry_path, exclude_dirs)
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


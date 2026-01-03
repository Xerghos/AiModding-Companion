"""
Module de construction et gestion du graphe de symboles.
Utilise NetworkX pour calculer PageRank et identifier les fichiers centraux.
"""

import os
import logging
import sqlite3
import time
from typing import Dict, List, Optional, Tuple, Set
from config import get_logger, get_path
from features.Decorators import trace_action

log = get_logger("features.context.symbol_graph")

# Import NetworkX avec gestion d'erreur
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None


class SymbolGraph:
    """
    Gestionnaire du graphe de symboles du projet.
    
    Utilise NetworkX pour calculer PageRank et identifier les fichiers centraux.
    """
    
    def __init__(self, db_path_base=None):
        """
        Args:
            db_path_base: Chemin de base de la base de données
        """
        self.db_path_base = db_path_base
        self.graph = None
        self._module_map: Dict[str, List[str]] = {} # Cache pour résolution rapide module -> fichiers
        
        if NETWORKX_AVAILABLE:
            self.graph = nx.DiGraph()
        else:
            log.warning("NetworkX non disponible. Le graphe de symboles sera limité.")
    
    @trace_action(source="symbol_graph")
    def extract_dependencies(self, file_path: str) -> Tuple[List[str], List[str]]:
        """
        Extrait les dépendances d'un fichier (imports et appels de fonctions).
        
        Note: Une implémentation complète nécessiterait Tree-sitter.
        Cette version utilise une approximation basique.
        
        Args:
            file_path: Chemin du fichier à analyser
        
        Returns:
            Tuple (imports, function_calls)
        """
        imports = []
        function_calls = []
        
        if not os.path.exists(file_path) or not file_path.lower().endswith('.py'):
            return imports, function_calls
            
        # Protection contre les gros fichiers (> 1MB)
        file_size = 0
        try:
            file_size = os.path.getsize(file_path)
        except Exception:
            pass
        
        try:
            # Lecture optimisée : lire ligne par ligne pour les imports, tout pour regex
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Lire les 500 premières lignes pour les imports (généralement au début)
                head_lines = []
                for i in range(500):
                    line = f.readline()
                    if not line: break
                    head_lines.append(line)
                
                # Revenir au début pour lire tout le contenu (pour regex appels)
                # Note: On limite la lecture complète aux fichiers de taille raisonnable
                f.seek(0)
                if file_size < 200 * 1024: # 200KB max pour analyse regex complète
                    content = f.read()
                else:
                    content = "".join(head_lines) # Analyser seulement l'entête
            
            # Extraction basique des imports (sur l'entête)
            for line in head_lines:
                line = line.strip()
                if not line: continue
                if line.startswith('import '):
                    # import module
                    # import module.submodule as alias
                    parts = line.split()
                    if len(parts) >= 2:
                        # Nettoyer l'import (enlever le 'import ' et les alias)
                        # On prend juste le package racine ou module
                        module_parts = parts[1].split('.')
                        if module_parts:
                            imports.append(module_parts[0])
                elif line.startswith('from '):
                    # from module import ...
                    # from module.submodule import ...
                    parts = line.split()
                    if len(parts) >= 2:
                        module_parts = parts[1].split('.')
                        if module_parts:
                            imports.append(module_parts[0])
            
            # Extraction basique des appels (approximation)
            # On cherche les patterns comme module.function() ou Class.method()
            if content:
                import re
                # Optimisation regex : limiter la recherche
                call_pattern = r'(?<!def\s)(?<!class\s)(\w+)\.(\w+)\s*\('
                matches = re.findall(call_pattern, content)
                for module_or_class, func_name in matches:
                    if module_or_class and func_name:
                        # Filtrer les appels trop communs
                        if module_or_class not in ['self', 'np', 'pd', 'plt', 'os', 'sys', 're', 'logging', 'json']:
                            function_calls.append(f"{module_or_class}.{func_name}")
        
        except Exception as e:
            log.warning(f"Erreur extraction dépendances {file_path}: {e}")
        
        return imports, function_calls
    
    def _build_module_map(self, files: List[Tuple[int, str]]) -> None:
        """Construit une map optimisée module_name -> [paths] pour résolution O(1)."""
        self._module_map = {}
        for _, path in files:
            filename = os.path.basename(path)
            module_name = os.path.splitext(filename)[0]
            
            if module_name not in self._module_map:
                self._module_map[module_name] = []
            self._module_map[module_name].append(path)
            
            # Gestion des packages (__init__.py)
            if filename == '__init__.py':
                parent_dir = os.path.basename(os.path.dirname(path))
                if parent_dir not in self._module_map:
                    self._module_map[parent_dir] = []
                self._module_map[parent_dir].append(path)

    @trace_action(source="symbol_graph")
    def build_graph_from_db(self):
        """Construit le graphe à partir de la base de données (Optimisé O(N))."""
        import time
        start = time.time()
        
        if not NETWORKX_AVAILABLE:
            log.warning("NetworkX non disponible")
            return
        
        from .database import _get_paths
        
        sqlite_path, _, _ = _get_paths(self.db_path_base)
        
        if not os.path.exists(sqlite_path):
            log.warning(f"Base de données introuvable: {sqlite_path}")
            return
        
        self.graph = nx.DiGraph()
        conn = None
        
        try:
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.cursor()
            
            # Récupérer tous les fichiers
            cursor.execute("SELECT id, path FROM files")
            files = cursor.fetchall()
            
            # On peut fermer la connexion dès qu'on a les données
            conn.close()
            conn = None
            
            log.info(f"📂 {len(files)} fichiers à analyser pour le graphe")
            
            # 1. Prétraitement : Construction map module -> fichiers (O(N))
            self._build_module_map(files)
            
            processed = 0
            edges_count = 0
            
            # 2. Analyse des dépendances (O(N))
            for file_id, file_path in files:
                abs_path = get_path(file_path) if not os.path.isabs(file_path) else file_path
                
                # Ajouter le nœud fichier
                self.graph.add_node(file_path)
                
                if not os.path.exists(abs_path):
                    continue
                
                imports, function_calls = self.extract_dependencies(abs_path)
                
                # Résolution des imports (O(1) grâce à la map)
                for imp in imports:
                    candidates = self._module_map.get(imp, [])
                    for candidate_path in candidates:
                        if candidate_path != file_path:
                            self.graph.add_edge(file_path, candidate_path)
                            edges_count += 1
                
                # Résolution des appels (approximation)
                for call in function_calls:
                    module_or_class = call.split('.')[0]
                    candidates = self._module_map.get(module_or_class, [])
                    for candidate_path in candidates:
                        if candidate_path != file_path:
                            self.graph.add_edge(file_path, candidate_path)
                            edges_count += 1

                processed += 1
                if processed % 100 == 0:
                    elapsed = time.time() - start
                    log.info(f"  ⏳ Graphe: {processed}/{len(files)} fichiers traités ({elapsed:.1f}s)")
            
            elapsed = time.time() - start
            log.info(f"✅ Graphe construit: {len(self.graph.nodes)} nœuds, {len(self.graph.edges)} arêtes ({elapsed:.2f}s)")
        
        except Exception as e:
            log.error(f"Erreur construction graphe: {e}")
        finally:
            if conn:
                conn.close()
    
    @trace_action(source="symbol_graph")
    def calculate_pagerank(self, damping: float = 0.85, max_iter: int = 100) -> Dict[str, float]:
        """
        Calcule le PageRank pour identifier les fichiers centraux.
        """
        import time
        start = time.time()
        
        if not NETWORKX_AVAILABLE or not self.graph:
            return {}
        
        try:
            if len(self.graph.nodes) == 0:
                return {}
            
            pagerank_scores = nx.pagerank(self.graph, alpha=damping, max_iter=max_iter)
            
            elapsed = time.time() - start
            log.info(f"📊 PageRank calculé: {len(pagerank_scores)} fichiers ({elapsed:.2f}s)")
            return pagerank_scores
        
        except Exception as e:
            log.error(f"Erreur calcul PageRank: {e}")
            return {}
    
    @trace_action(source="symbol_graph")
    def get_top_files(self, n: int = 10) -> List[Tuple[str, float]]:
        """
        Retourne les N fichiers les plus centraux selon PageRank.
        """
        pagerank_scores = self.calculate_pagerank()
        
        if not pagerank_scores:
            return []
        
        sorted_files = sorted(
            pagerank_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_files[:n]
    
    def save_to_db(self):
        pass


# Instance globale
_symbol_graph_instance: Optional[SymbolGraph] = None

def get_symbol_graph(db_path_base=None) -> SymbolGraph:
    """Retourne l'instance singleton du graphe de symboles."""
    global _symbol_graph_instance
    if _symbol_graph_instance is None:
        import time
        start = time.time()
        log.info("📊 Construction graphe symboles (première fois)...")
        _symbol_graph_instance = SymbolGraph(db_path_base)
        _symbol_graph_instance.build_graph_from_db()
        elapsed = time.time() - start
        log.info(f"✅ Graphe symboles prêt ({elapsed:.2f}s)")
    return _symbol_graph_instance
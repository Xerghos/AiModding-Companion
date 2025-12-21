"""
Module de construction et gestion du graphe de symboles.
Utilise NetworkX pour calculer PageRank et identifier les fichiers centraux.
"""

import os
import logging
import sqlite3
from typing import Dict, List, Optional, Tuple
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
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            # Extraction basique des imports
            for line in lines:
                line = line.strip()
                if line.startswith('import '):
                    # import module
                    module = line[7:].split(' as ')[0].split()[0]
                    imports.append(module)
                elif line.startswith('from '):
                    # from module import ...
                    parts = line[5:].split(' import ')
                    if len(parts) == 2:
                        module = parts[0].strip()
                        imports.append(module)
            
            # Extraction basique des appels (approximation)
            # On cherche les patterns comme module.function() ou Class.method()
            import re
            call_pattern = r'(\w+)\.(\w+)\s*\('
            matches = re.findall(call_pattern, content)
            for module_or_class, func_name in matches:
                if module_or_class and func_name:
                    function_calls.append(f"{module_or_class}.{func_name}")
        
        except Exception as e:
            log.warning(f"Erreur extraction dépendances {file_path}: {e}")
        
        return imports, function_calls
    
    @trace_action(source="symbol_graph")
    def build_graph_from_db(self):
        """Construit le graphe à partir de la base de données."""
        if not NETWORKX_AVAILABLE:
            log.warning("NetworkX non disponible")
            return
        
        from .database import _get_paths
        
        sqlite_path, _, _ = _get_paths(self.db_path_base)
        
        if not os.path.exists(sqlite_path):
            log.warning(f"Base de données introuvable: {sqlite_path}")
            return
        
        self.graph = nx.DiGraph()
        
        try:
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.cursor()
            
            # Récupérer tous les fichiers
            cursor.execute("SELECT id, path FROM files")
            files = cursor.fetchall()
            
            file_map = {fid: path for fid, path in files}
            
            # Pour chaque fichier, extraire les dépendances
            for file_id, file_path in files:
                abs_path = get_path(file_path) if not os.path.isabs(file_path) else file_path
                
                if not os.path.exists(abs_path):
                    continue
                
                imports, function_calls = self.extract_dependencies(abs_path)
                
                # Ajouter le nœud fichier
                self.graph.add_node(file_path)
                
                # Ajouter les arêtes pour les imports
                for imp in imports:
                    # Chercher le fichier correspondant
                    # Approximation: chercher dans les autres fichiers
                    for other_id, other_path in files:
                        if other_path == file_path:
                            continue
                        
                        # Vérifier si l'import correspond au fichier
                        module_name = os.path.splitext(os.path.basename(other_path))[0]
                        if imp.endswith(module_name) or module_name in imp:
                            self.graph.add_edge(file_path, other_path)
                            break
            
            conn.close()
            
            log.info(f"✅ Graphe construit: {len(self.graph.nodes)} nœuds, {len(self.graph.edges)} arêtes")
        
        except Exception as e:
            log.error(f"Erreur construction graphe: {e}")
    
    @trace_action(source="symbol_graph")
    def calculate_pagerank(self, damping: float = 0.85, max_iter: int = 100) -> Dict[str, float]:
        """
        Calcule le PageRank pour identifier les fichiers centraux.
        
        Args:
            damping: Facteur d'amortissement (défaut: 0.85)
            max_iter: Nombre maximum d'itérations
        
        Returns:
            Dictionnaire {file_path: pagerank_score}
        """
        if not NETWORKX_AVAILABLE or not self.graph:
            return {}
        
        try:
            if len(self.graph.nodes) == 0:
                return {}
            
            pagerank_scores = nx.pagerank(self.graph, alpha=damping, max_iter=max_iter)
            
            log.info(f"✅ PageRank calculé pour {len(pagerank_scores)} fichiers")
            return pagerank_scores
        
        except Exception as e:
            log.error(f"Erreur calcul PageRank: {e}")
            return {}
    
    @trace_action(source="symbol_graph")
    def get_top_files(self, n: int = 10) -> List[Tuple[str, float]]:
        """
        Retourne les N fichiers les plus centraux selon PageRank.
        
        Args:
            n: Nombre de fichiers à retourner
        
        Returns:
            Liste de tuples (file_path, pagerank_score) triée par score décroissant
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
        """Sauvegarde le graphe dans la base de données (optionnel)."""
        # TODO: Implémenter sauvegarde du graphe si nécessaire
        pass


# Instance globale
_symbol_graph_instance: Optional[SymbolGraph] = None

def get_symbol_graph(db_path_base=None) -> SymbolGraph:
    """Retourne l'instance singleton du graphe de symboles."""
    global _symbol_graph_instance
    if _symbol_graph_instance is None:
        _symbol_graph_instance = SymbolGraph(db_path_base)
        _symbol_graph_instance.build_graph_from_db()
    return _symbol_graph_instance


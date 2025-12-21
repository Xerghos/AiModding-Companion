"""
Module de génération de la Repo Map (carte compressée du dépôt).
Extrait uniquement les signatures (sans corps) pour injection dans le contexte LLM.
"""

import os
import logging
from typing import List, Dict, Optional
from config import get_logger, get_path
from features.Decorators import trace_action

log = get_logger("features.context.repo_map")


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
    
    @trace_action(source="repo_map")
    def generate_repo_map(self, top_n: int = 20) -> str:
        """
        Génère la Repo Map en extrayant les signatures des fichiers les plus importants.
        
        Args:
            top_n: Nombre de fichiers à inclure (selon PageRank)
        
        Returns:
            Repo Map formatée en texte
        """
        from .symbol_graph import get_symbol_graph
        
        # Obtenir les fichiers les plus centraux
        symbol_graph = get_symbol_graph(self.db_path_base)
        top_files = symbol_graph.get_top_files(top_n)
        
        if not top_files:
            log.warning("Aucun fichier trouvé pour la Repo Map")
            return ""
        
        repo_map_lines = []
        repo_map_lines.append("# Repo Map - Fichiers Centraux\n")
        
        for file_path, pagerank_score in top_files:
            abs_path = get_path(file_path) if not os.path.isabs(file_path) else file_path
            
            if not os.path.exists(abs_path):
                continue
            
            signatures_data = self._extract_signatures(abs_path)
            if signatures_data:
                repo_map_lines.append(f"\n# Fichier: {file_path} (PageRank: {pagerank_score:.4f})")
                
                # Organiser par type : classes d'abord, puis fonctions globales
                classes = [s for s in signatures_data if s.get('ast_type') == 'class']
                functions = [s for s in signatures_data if s.get('ast_type') == 'function']
                
                # Afficher classes avec leurs méthodes
                for class_data in classes:
                    class_sig = class_data['signature']
                    if class_data.get('docstring'):
                        class_sig += f"\n    \"\"\"{class_data['docstring']}\"\"\""
                    repo_map_lines.append(f"{class_sig}")
                    
                    # Ajouter méthodes de la classe (indentées)
                    methods = class_data.get('methods', [])
                    for method_data in methods:
                        method_sig = method_data['signature']
                        if method_data.get('docstring'):
                            method_sig += f"  # {method_data['docstring']}"
                        repo_map_lines.append(f"  {method_sig}")
                
                # Afficher fonctions globales
                for func_data in functions:
                    func_sig = func_data['signature']
                    if func_data.get('docstring'):
                        func_sig += f"  # {func_data['docstring']}"
                    repo_map_lines.append(func_sig)
        
        repo_map_text = "\n".join(repo_map_lines)
        log.info(f"✅ Repo Map générée: {len(top_files)} fichiers, {len(repo_map_text)} caractères")
        
        return repo_map_text
    
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
            from .code_chunker import get_chunker
            
            chunker = get_chunker()
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


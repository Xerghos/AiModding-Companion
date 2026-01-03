"""
Module de chunking sémantique pour code Python utilisant Tree-sitter.
Découpe le code en chunks intelligents basés sur la structure AST.
"""

import os
import logging
import threading
from typing import List, Dict, Optional, Tuple
from config import get_logger
from features.Decorators import trace_action

log = get_logger("features.context.code_chunker")

# Import Tree-sitter avec gestion d'erreur
try:
    import tree_sitter
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    tree_sitter = None

# Constantes pour le chunking
MIN_CHUNK_SIZE = 50  # Taille minimale d'un chunk (caractères)
MAX_CHUNK_SIZE = 2000  # Taille maximale d'un chunk (caractères)
MAX_FUNCTION_SIZE = 1500  # Si une fonction dépasse ça, on la divise


class SemanticChunker:
    """
    Chunker sémantique utilisant Tree-sitter pour découper le code Python
    en chunks intelligents basés sur la structure AST.
    """
    _init_done = False # Lock visuel pour les logs
    
    def __init__(self):
        self._local = threading.local()
        self.is_available = False  # Flag pour indiquer si le chunking sémantique est disponible
        self._init_tree_sitter()
    
    def _init_tree_sitter(self):
        """
        Initialise Tree-sitter pour Python via le language-pack.
        """
        if not TREE_SITTER_AVAILABLE:
            if not SemanticChunker._init_done:
                log.warning("⚠️ Tree-sitter non disponible.")
                SemanticChunker._init_done = True
            return
        
        try:
            from tree_sitter_language_pack import get_language
            lang = get_language('python')
            if lang:
                self._local.language = lang
                self._local.parser = Parser(lang)
                self.is_available = True
                if not SemanticChunker._init_done:
                    log.info("✅ Tree-sitter prêt (Language Pack)")
                    SemanticChunker._init_done = True
                return
        except Exception as e:
            if not SemanticChunker._init_done:
                log.debug(f"Échec Language Pack: {e}")
        
        self.is_available = False
    
    def _query_ast(self, tree, query_string: str) -> List:
        """Exécute une requête Tree-sitter sur l'AST."""
        if not hasattr(self._local, "parser") or not self._local.parser:
            self._init_tree_sitter()
            
        if not self._local.parser or not self._local.language:
            return []
        
        try:
            # Utiliser Query() constructor (lang.query() est déprécié)
            from tree_sitter import Query, QueryCursor
            query = Query(self._local.language, query_string)
            
            # Utiliser QueryCursor pour exécuter la requête
            cursor = QueryCursor(query)
            captures_dict = cursor.captures(tree.root_node)
            
            # Convertir le dict en liste de tuples (node, capture_name) comme attendu par le reste du code
            captures_list = []
            for capture_name, nodes in captures_dict.items():
                for node in nodes:
                    captures_list.append((node, capture_name))
            
            return captures_list
        except Exception as e:
            log.warning(f"Erreur requête AST: {e}")
            return []
    
    def _get_node_text(self, node, source_code: bytes) -> str:
        """Extrait le texte d'un nœud AST."""
        start_byte = node.start_byte
        end_byte = node.end_byte
        return source_code[start_byte:end_byte].decode('utf-8', errors='ignore')
    
    def _get_node_lines(self, node) -> Tuple[int, int]:
        """Retourne les numéros de ligne (start, end) d'un nœud."""
        return (node.start_point[0] + 1, node.end_point[0] + 1)  # Tree-sitter utilise 0-indexed
    
    def _extract_class_signature(self, class_node, source_code: bytes) -> Optional[str]:
        """Extrait la signature d'une classe (nom + bases + docstring)."""
        try:
            # Trouver le nom de la classe
            name_node = None
            for child in class_node.children:
                if child.type == 'identifier':
                    name_node = child
                    break
            
            if not name_node:
                return None
            
            class_name = self._get_node_text(name_node, source_code)
            
            # Trouver les bases (héritage)
            bases = []
            for child in class_node.children:
                if child.type == 'argument_list':
                    for base in child.children:
                        if base.type == 'identifier':
                            bases.append(self._get_node_text(base, source_code))
            
            base_str = f"({', '.join(bases)})" if bases else ""
            
            # Trouver la docstring
            docstring = ""
            body = None
            for child in class_node.children:
                if child.type == 'block':
                    body = child
                    break
            
            if body and len(body.children) > 0:
                first_stmt = body.children[0]
                if first_stmt.type == 'expression_statement':
                    expr = first_stmt.children[0] if first_stmt.children else None
                    if expr and expr.type == 'string':
                        docstring = self._get_node_text(expr, source_code).strip('"\'')
                        if len(docstring) > 100:
                            docstring = docstring[:100] + "..."
            
            signature = f"class {class_name}{base_str}"
            if docstring:
                signature += f"\n    \"\"\"{docstring}\"\"\""
            
            return signature
        except Exception as e:
            log.warning(f"Erreur extraction signature classe: {e}")
            return None
    
    def _extract_function_signature(self, func_node, source_code: bytes) -> Optional[str]:
        """Extrait la signature d'une fonction (nom + paramètres)."""
        try:
            # Trouver le nom
            name_node = None
            for child in func_node.children:
                if child.type == 'identifier':
                    name_node = child
                    break
            
            if not name_node:
                return None
            
            func_name = self._get_node_text(name_node, source_code)
            
            # Trouver les paramètres
            params = []
            for child in func_node.children:
                if child.type == 'parameters':
                    for param in child.children:
                        if param.type == 'identifier':
                            params.append(self._get_node_text(param, source_code))
                        elif param.type == 'typed_parameter':
                            param_name = None
                            for pchild in param.children:
                                if pchild.type == 'identifier':
                                    param_name = self._get_node_text(pchild, source_code)
                                    break
                            if param_name:
                                params.append(param_name)
            
            params_str = ', '.join(params) if params else ''
            return f"def {func_name}({params_str})"
        except Exception as e:
            log.warning(f"Erreur extraction signature fonction: {e}")
            return None
    
    def _build_parent_context(self, node, source_code: bytes, file_path: str) -> str:
        """Construit le contexte parent (Fichier > Classe > Méthode)."""
        context_parts = [f"Fichier: {os.path.basename(file_path)}"]
        
        # Remonter l'arbre pour trouver les classes parentes
        current = node.parent
        classes = []
        
        while current:
            if current.type == 'class_definition':
                name_node = None
                for child in current.children:
                    if child.type == 'identifier':
                        name_node = child
                        break
                if name_node:
                    class_name = self._get_node_text(name_node, source_code)
                    classes.insert(0, class_name)
            current = current.parent
        
        for class_name in classes:
            context_parts.append(f"Classe: {class_name}")
        
        return " > ".join(context_parts)
    
    def _chunk_node(self, node, source_code: bytes, file_path: str, 
                   parent_context: str = "", ast_type: str = "") -> Optional[Dict]:
        """Crée un chunk à partir d'un nœud AST."""
        try:
            node_text = self._get_node_text(node, source_code)
            start_line, end_line = self._get_node_lines(node)
            
            if len(node_text.strip()) < MIN_CHUNK_SIZE:
                return None
            
            # Construire le contexte enrichi
            if not parent_context:
                parent_context = self._build_parent_context(node, source_code, file_path)
            
            # Format "Sticky Headers" : Contexte > Contenu
            enriched_content = f"{parent_context}\n{node_text}"
            
            return {
                'content': enriched_content,
                'start_line': start_line,
                'end_line': end_line,
                'ast_type': ast_type,
                'parent_context': parent_context,
                'raw_content': node_text
            }
        except Exception as e:
            log.warning(f"Erreur création chunk: {e}")
            return None
    
    def _chunk_large_function(self, func_node, source_code: bytes, file_path: str, 
                             parent_context: str) -> List[Dict]:
        """Divise une fonction trop grande en plusieurs chunks."""
        chunks = []
        try:
            body = None
            for child in func_node.children:
                if child.type == 'block':
                    body = child
                    break
            
            if not body:
                return chunks
            
            # Extraire la signature
            signature = self._extract_function_signature(func_node, source_code)
            if not signature:
                signature = "def function(...)"
            
            # Chunker le corps par statements
            current_chunk_lines = []
            current_start = func_node.start_point[0] + 1
            
            for stmt in body.children:
                if stmt.type in ['expression_statement', 'if_statement', 'for_statement', 
                                'while_statement', 'try_statement', 'with_statement']:
                    stmt_text = self._get_node_text(stmt, source_code)
                    stmt_start, stmt_end = self._get_node_lines(stmt)
                    
                    # Si l'ajout dépasse la limite, créer un chunk
                    if len('\n'.join(current_chunk_lines) + '\n' + stmt_text) > MAX_FUNCTION_SIZE:
                        if current_chunk_lines:
                            chunk_content = f"{parent_context} > {signature}\n" + '\n'.join(current_chunk_lines)
                            chunks.append({
                                'content': chunk_content,
                                'start_line': current_start,
                                'end_line': stmt_start - 1,
                                'ast_type': 'function_part',
                                'parent_context': parent_context,
                                'raw_content': '\n'.join(current_chunk_lines)
                            })
                        current_chunk_lines = [stmt_text]
                        current_start = stmt_start
                    else:
                        current_chunk_lines.append(stmt_text)
            
            # Ajouter le dernier chunk
            if current_chunk_lines:
                chunk_content = f"{parent_context} > {signature}\n" + '\n'.join(current_chunk_lines)
                chunks.append({
                    'content': chunk_content,
                    'start_line': current_start,
                    'end_line': func_node.end_point[0] + 1,
                    'ast_type': 'function_part',
                    'parent_context': parent_context,
                    'raw_content': '\n'.join(current_chunk_lines)
                })
        except Exception as e:
            log.warning(f"Erreur chunking fonction large: {e}")
        
        return chunks
    
    def chunk_file(self, file_path: str) -> List[Dict]:
        """
        Chunk un fichier Python en utilisant Tree-sitter.
        """
        if not os.path.exists(file_path):
            return []
        
        # Initialisation lazy pour le thread courant
        if not hasattr(self._local, "parser") or not self._local.parser:
            self._init_tree_sitter()
            
        # Fallback si Tree-sitter indisponible
        if not self._local.parser or not self._local.language:
            return self._chunk_basic(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()
            
            if len(source_code.strip()) < MIN_CHUNK_SIZE:
                return []
            
            source_bytes = source_code.encode('utf-8')
            tree = self._local.parser.parse(source_bytes)
            
            chunks = []
            
            # Requête pour extraire classes et fonctions
            query_string = """
            (class_definition) @class
            (function_definition) @function
            """
            
            captures = self._query_ast(tree, query_string)
            
            # Organiser par type
            classes = []
            functions = []
            
            for node, capture_name in captures:
                if capture_name == 'class':
                    classes.append(node)
                elif capture_name == 'function':
                    functions.append(node)
            
            # 1. Niveau Macro: Signatures de classes
            for class_node in classes:
                signature = self._extract_class_signature(class_node, source_bytes)
                if signature:
                    parent_context = self._build_parent_context(class_node, source_bytes, file_path)
                    macro_chunk = {
                        'content': f"{parent_context} > {signature}",
                        'start_line': class_node.start_point[0] + 1,
                        'end_line': class_node.start_point[0] + 2,
                        'ast_type': 'class_signature',
                        'parent_context': parent_context,
                        'raw_content': signature
                    }
                    chunks.append(macro_chunk)
            
            # 2. Niveau Micro: Fonctions et méthodes complètes
            for func_node in functions:
                parent_context = self._build_parent_context(func_node, source_bytes, file_path)
                func_text = self._get_node_text(func_node, source_bytes)
                func_size = len(func_text)
                
                # Déterminer le type (méthode si dans une classe, fonction sinon)
                is_method = False
                current = func_node.parent
                while current:
                    if current.type == 'class_definition':
                        is_method = True
                        break
                    current = current.parent
                
                ast_type = 'method' if is_method else 'function'
                
                # Si la fonction est trop grande, la diviser
                if func_size > MAX_FUNCTION_SIZE:
                    sub_chunks = self._chunk_large_function(func_node, source_bytes, file_path, parent_context)
                    chunks.extend(sub_chunks)
                else:
                    chunk = self._chunk_node(func_node, source_bytes, file_path, parent_context, ast_type)
                    if chunk:
                        chunks.append(chunk)
            
            # 3. Code orphelin (imports, constantes globales en haut du fichier)
            if not chunks or chunks[0]['start_line'] > 10:
                orphan_text = source_code.split('\n')[:chunks[0]['start_line'] - 1] if chunks else source_code.split('\n')[:50]
                orphan_content = '\n'.join(orphan_text).strip()
                if len(orphan_content) >= MIN_CHUNK_SIZE:
                    chunks.insert(0, {
                        'content': f"Fichier: {os.path.basename(file_path)}\n{orphan_content}",
                        'start_line': 1,
                        'end_line': chunks[0]['start_line'] - 1 if chunks else len(source_code.split('\n')),
                        'ast_type': 'module_header',
                        'parent_context': f"Fichier: {os.path.basename(file_path)}",
                        'raw_content': orphan_content
                    })
            
            return chunks
            
        except Exception as e:
            # Fallback: chunking basique
            return self._chunk_basic(file_path)
    
    def _chunk_basic(self, file_path: str) -> List[Dict]:
        """
        Chunking basique de fallback si Tree-sitter n'est pas disponible.
        Découpe par lignes avec regroupement intelligent.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            chunks = []
            current_chunk = []
            current_start = 1
            
            for i, line in enumerate(lines, 1):
                current_chunk.append(line)
                
                # Créer un chunk si on atteint la taille max ou si on trouve une séparation naturelle
                chunk_text = ''.join(current_chunk)
                if len(chunk_text) >= MAX_CHUNK_SIZE or (line.strip() == '' and len(chunk_text) >= MIN_CHUNK_SIZE):
                    chunks.append({
                        'content': f"Fichier: {os.path.basename(file_path)}\n{chunk_text}",
                        'start_line': current_start,
                        'end_line': i,
                        'ast_type': 'text_block',
                        'parent_context': f"Fichier: {os.path.basename(file_path)}",
                        'raw_content': chunk_text
                    })
                    current_chunk = []
                    current_start = i + 1
            
            # Ajouter le dernier chunk
            if current_chunk:
                chunk_text = ''.join(current_chunk)
                if len(chunk_text.strip()) >= MIN_CHUNK_SIZE:
                    chunks.append({
                        'content': f"Fichier: {os.path.basename(file_path)}\n{chunk_text}",
                        'start_line': current_start,
                        'end_line': len(lines),
                        'ast_type': 'text_block',
                        'parent_context': f"Fichier: {os.path.basename(file_path)}",
                        'raw_content': chunk_text
                    })
            
            return chunks
        except Exception as e:
            log.error(f"Erreur chunking basique {file_path}: {e}")
            return []


# Instance globale
_chunker_instance = None

def get_chunker() -> SemanticChunker:
    """Retourne l'instance singleton du chunker."""
    global _chunker_instance
    if _chunker_instance is None:
        _chunker_instance = SemanticChunker()
        # Logger l'état d'initialisation
        if _chunker_instance.is_available:
            log.info("✅ Chunker sémantique prêt (Tree-sitter activé)")
        else:
            log.info("ℹ️ Chunker en mode fallback (Tree-sitter non disponible - chunking basique)")
    return _chunker_instance


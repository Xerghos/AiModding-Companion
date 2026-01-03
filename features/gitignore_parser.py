"""
Parser pour .gitignore compatible avec les patterns Git.
Utilise pathspec pour parser les patterns .gitignore.
"""
import os
from pathlib import Path
from typing import Optional, Callable

try:
    from pathspec import PathSpec
    PATHSPEC_AVAILABLE = True
except ImportError:
    PATHSPEC_AVAILABLE = False
    PathSpec = None


def load_gitignore_patterns(root_path: str) -> Optional[PathSpec]:
    """
    Charge les patterns depuis .gitignore.
    """
    if not PATHSPEC_AVAILABLE:
        return None
    
    gitignore_path = Path(root_path) / ".gitignore"
    if not gitignore_path.exists():
        return None
    
    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if not patterns:
            return None
        
        return PathSpec.from_lines('gitwildmatch', patterns)
    except Exception:
        return None


def parse_gitignore(gitignore_path: str) -> Callable[[str], bool]:
    """
    Parse un fichier .gitignore et retourne une fonction de matching.
    
    Args:
        gitignore_path: Chemin complet vers le fichier .gitignore
        
    Returns:
        Une fonction qui prend un chemin ABSOLU et retourne True s'il doit être ignoré.
    """
    if not PATHSPEC_AVAILABLE:
        # Si pathspec manquant, on n'ignore rien via gitignore (fallback safe)
        return lambda x: False
        
    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
        spec = PathSpec.from_lines('gitwildmatch', patterns)
        root_dir = os.path.dirname(gitignore_path)
        
        def matcher(file_path: str) -> bool:
            try:
                # Convertir en relatif pour le matching
                rel_path = os.path.relpath(file_path, root_dir)
                # Normaliser pour pathspec (qui attend des forward slashes)
                rel_path = rel_path.replace('\\', '/')
                return spec.match_file(rel_path)
            except ValueError:
                return False # Hors du dossier
                
        return matcher
        
    except Exception as e:
        import logging
        logging.getLogger("Features.gitignore_parser").warning(f"Erreur parse_gitignore: {e}")
        return lambda x: False # En cas d'erreur, on n'ignore rien


def should_ignore_path(file_path: str, root_path: str, gitignore_spec: Optional[PathSpec] = None) -> bool:
    """
    Vérifie si un chemin doit être ignoré selon .gitignore.
    """
    if gitignore_spec is None:
        gitignore_spec = load_gitignore_patterns(root_path)
    
    if gitignore_spec is None:
        return False
    
    try:
        rel_path = os.path.relpath(file_path, root_path)
        rel_path = rel_path.replace('\\', '/')
        if rel_path == '.' or rel_path == '':
            return False
        return gitignore_spec.match_file(rel_path)
    except ValueError:
        return False
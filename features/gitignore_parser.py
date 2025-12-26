"""
Parser pour .gitignore compatible avec les patterns Git.
Utilise pathspec pour parser les patterns .gitignore.
"""
import os
from pathlib import Path
from typing import Optional

try:
    from pathspec import PathSpec
    PATHSPEC_AVAILABLE = True
except ImportError:
    PATHSPEC_AVAILABLE = False
    PathSpec = None


def load_gitignore_patterns(root_path: str) -> Optional[PathSpec]:
    """
    Charge les patterns depuis .gitignore.
    
    Args:
        root_path: Chemin racine du projet
        
    Returns:
        PathSpec pour matcher les fichiers ignorés, ou None si non disponible
    """
    if not PATHSPEC_AVAILABLE:
        # Fallback : liste basique si pathspec non disponible
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
    except Exception as e:
        # En cas d'erreur de lecture, retourner None
        import logging
        log = logging.getLogger("Features.gitignore_parser")
        log.debug(f"Erreur chargement .gitignore: {e}")
        return None


def should_ignore_path(file_path: str, root_path: str, gitignore_spec: Optional[PathSpec] = None) -> bool:
    """
    Vérifie si un chemin doit être ignoré selon .gitignore.
    
    Args:
        file_path: Chemin du fichier/dossier (absolu ou relatif)
        root_path: Chemin racine du projet
        gitignore_spec: PathSpec pré-chargé (optionnel)
        
    Returns:
        True si le chemin doit être ignoré
    """
    if gitignore_spec is None:
        gitignore_spec = load_gitignore_patterns(root_path)
    
    if gitignore_spec is None:
        return False
    
    # Convertir en chemin relatif depuis root_path
    try:
        rel_path = os.path.relpath(file_path, root_path)
        # Normaliser les séparateurs pour Windows
        rel_path = rel_path.replace('\\', '/')
        # Ne pas ignorer le dossier racine lui-même
        if rel_path == '.' or rel_path == '':
            return False
        return gitignore_spec.match_file(rel_path)
    except ValueError:
        # Chemin hors de root_path
        return False


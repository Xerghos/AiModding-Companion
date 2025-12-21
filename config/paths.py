import os
import sys

try:
    # On remonte d'un cran car on est dans config/paths.py
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(script_path))
except NameError:
    project_root = os.path.abspath(sys.argv[0] if sys.argv else '.')

def get_path(filename):
    """Retourne le chemin absolu d'un fichier par rapport à la racine du projet."""
    return os.path.join(project_root, filename)
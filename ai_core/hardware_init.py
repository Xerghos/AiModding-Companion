"""
Module d'initialisation hardware pour AiModding-Companion.
Optimise l'environnement pour le GPU AMD Radeon (DirectML).
"""
import sys
import warnings

# 1. Filtre global d'avertissements pour les messages système non critiques
warnings.filterwarnings("ignore", message=".*Triton.*")
warnings.filterwarnings("ignore", message=".*DirectML.*")

def init_hardware():
    """Initialisation minimale pour la stabilité."""
    # Plus de torchao, plus de monkeypatch complexe.
    # On garde juste une structure propre pour d'éventuels futurs besoins matériels.
    pass

# Exécuter immédiatement lors de l'import
init_hardware()
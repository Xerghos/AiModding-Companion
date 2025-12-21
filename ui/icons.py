"""
Stockage des assets graphiques (Icônes Base64).
Évite de dépendre de fichiers externes .png/.ico.
"""
import tkinter as tk
from features.Decorators import trace_action

# Icône Dossier (16x16)
FOLDER_ICON_DATA = "R0lGODlhEAAQAMQQAPb29t/f3+vr6+fn5+jo6Pj4+O/v7/X19e3t7fHx8e/v7/T09P///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACH5BAEAABAALAAAAAAQABAAAAVRICaOZFkaLnsGz6SZOBoRz+AWguILGJk0MoYByEMk1bgiAyCwUBlQoM0tCSgDkOowCCuFIzBYVAaBwkcy0iYJq1s0iUUBgSlCQA7"

# Icône Fichier (16x16)
FILE_ICON_DATA = "R0lGODlhEAAQAMQQAPb29t/f3+vr6+fn5+jo6Pj4+O/v7/X19e3t7fHx8e/v7/T09P///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACH5BAEAABAALAAAAAAQABAAAAVV4Cd+DOCNqGfDGFpq+6KbaIBs1uA5n4iJ0b22AAKFJ7P106IeBaGJwEpQyIYRqLChxO0VAFG60DbExsIoWnQGA62xz2gIaDclJAA7"

class IconProvider:
    """
    Singleton pour charger les PhotoImage Tkinter une seule fois.
    Nécessite qu'une instance Tk() racine existe déjà.
    """
    _folder_icon = None
    _file_icon = None

    @classmethod
    @trace_action(source="icons")
    def get_folder_icon(cls):
        if not cls._folder_icon:
            cls._folder_icon = tk.PhotoImage(data=FOLDER_ICON_DATA)
        return cls._folder_icon

    @classmethod
    @trace_action(source="icons")
    def get_file_icon(cls):
        if not cls._file_icon:
            cls._file_icon = tk.PhotoImage(data=FILE_ICON_DATA)
        return cls._file_icon
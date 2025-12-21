import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import os
from config import get_path, SUPPORTED_FILE_EXTENSIONS
from ui.widgets import COLORS
from ui.icons import IconProvider
from features.Decorators import trace_action

class FileExplorer(ctk.CTkFrame):
    """
    Widget latéral pour naviguer dans les fichiers du projet.
    Gère l'affichage en arbre (Treeview) et les interactions souris.
    """
    def __init__(self, master, on_file_open, on_context_action, **kwargs):
        """
        :param on_file_open: Callback(path) quand un fichier est double-cliqué.
        :param on_context_action: Callback(text) pour injecter du texte dans le chat (ex: Analyse de ...).
        """
        super().__init__(master, width=250, corner_radius=0, **kwargs)
        self.on_file_open = on_file_open
        self.on_context_action = on_context_action
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 1. Header
        self._setup_header()
        
        # 2. Arbre (Treeview)
        self._setup_treeview()
        
        # 3. Footer (Boutons)
        ctk.CTkButton(self, text="Actualiser", command=self.refresh, fg_color="transparent", border_width=1).grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        # Initialisation
        self.refresh()

    @trace_action(source="explorer")
    def _setup_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=10, padx=10)
        ctk.CTkLabel(header, text="EXPLORATEUR", font=("Arial", 12, "bold")).pack(side="left")
        # Le bouton toggle est géré par le parent (Main Window), on le laisse ici pour l'instant ou on le retire si géré ailleurs.
        # Pour rester fidèle à l'UI, on peut mettre un bouton "Cacher" qui appelle une méthode du parent si besoin.

    @trace_action(source="explorer")
    def _setup_treeview(self):
        self.tree_frame = ctk.CTkFrame(self, fg_color=COLORS["BG_WIDGET"])
        self.tree_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Style Treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", 
                        background="#252525", 
                        foreground="#E0E0E0", 
                        fieldbackground="#252525", 
                        borderwidth=0)
        style.map("Treeview", background=[('selected', '#007ACC')])
        
        self.tree = ttk.Treeview(self.tree_frame, show="tree", selectmode="extended")
        self.tree.pack(fill="both", expand=True, side="left")
        
        # Bindings
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<<TreeviewOpen>>", self._on_expand)
        
        # Scrollbar
        sb = ctk.CTkScrollbar(self.tree_frame, command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

    @trace_action(source="explorer")
    def refresh(self):
        """Recharge la racine de l'arbre."""
        self._populate_tree("", get_path('.'))

    @trace_action(source="explorer")
    def _populate_tree(self, parent, path):
        if parent == "":
            for i in self.tree.get_children(): self.tree.delete(i)
        else:
            for i in self.tree.get_children(parent): self.tree.delete(i)
            
        try:
            # Tri : Dossiers d'abord, puis fichiers, ordre alphabétique
            items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
            
            for item in items:
                # Filtrage basique
                if item.startswith(".") or item == "__pycache__": continue
                
                abspath = os.path.join(path, item)
                is_dir = os.path.isdir(abspath)
                
                if not is_dir and not item.endswith(SUPPORTED_FILE_EXTENSIONS): continue
                
                # Icônes
                icon = IconProvider.get_folder_icon() if is_dir else IconProvider.get_file_icon()
                
                oid = self.tree.insert(parent, "end", text=f" {item}", open=False, values=[abspath, "dir" if is_dir else "file"], image=icon)
                
                # Dummy node pour permettre l'extension
                if is_dir: self.tree.insert(oid, "end", text="loading...") 
        except Exception: 
            pass

    @trace_action(source="explorer")
    def _on_expand(self, event):
        item_id = self.tree.focus()
        values = self.tree.item(item_id, "values")
        if values and values[1] == "dir":
            self._populate_tree(item_id, values[0])

    @trace_action(source="explorer")
    def _on_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item: return
        values = self.tree.item(item, "values")
        if values and values[1] == "file":
            if self.on_file_open:
                self.on_file_open(values[0])

    @trace_action(source="explorer")
    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item: return
        
        # Gestion multi-sélection
        current_sel = self.tree.selection()
        if item not in current_sel:
            self.tree.selection_set(item)
            current_sel = (item,)
        
        paths = []
        for sel_item in current_sel:
            val = self.tree.item(sel_item, "values")
            if val: paths.append(val[0])
        if not paths: return
        
        # Chemins relatifs pour l'IA
        rel_paths = [os.path.relpath(p, get_path(".")) for p in paths]
        paths_str = ", ".join(rel_paths)
        
        # Menu Contextuel
        menu = tk.Menu(self, tearoff=0)
        
        @trace_action(source="explorer")
        def trigger_action(prefix):
            if self.on_context_action:
                self.on_context_action(f"{prefix} {paths_str}")

        menu.add_command(label="🔍 Analyser / Expliquer", command=lambda: trigger_action("Analyse et explique ce code :"))
        menu.add_command(label="🛡️ Audit Qualité & Sécurité", command=lambda: trigger_action("Fais un audit qualité et sécurité de :"))
        menu.add_command(label="🧪 Générer Tests", command=lambda: trigger_action("Génère des tests unitaires pour :"))
        menu.add_command(label="🔨 Refactoriser", command=lambda: trigger_action("Propose un refactoring pour :"))
        menu.add_separator()
        menu.add_command(label="📝 Copier chemin(s)", command=lambda: self.clipboard_append(paths_str))
        
        menu.post(event.x_root, event.y_root)
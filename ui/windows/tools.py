import customtkinter as ctk
from tkinter import messagebox, ttk
from ui.widgets import COLORS
from ui.windows.base import BaseWindow
from features.Decorators import trace_action

class WaitingListWindow(BaseWindow):
    """
    Affiche la liste des tâches en attente dans le Worker.
    """
    def __init__(self, master, task_queue):
        super().__init__(master, "File d'attente Tâches", 500, 400)
        self.task_queue = task_queue
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=COLORS["BG_WIDGET"], foreground=COLORS["FG_PRIMARY"], fieldbackground=COLORS["BG_WIDGET"], borderwidth=0, rowheight=25)
        
        self.tree = ttk.Treeview(self, columns=("ID", "Type", "Status"), show="headings")
        self.tree.heading("ID", text="#")
        self.tree.heading("Type", text="Action")
        self.tree.heading("Status", text="État")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkButton(self, text="Rafraîchir", command=self._refresh).pack(pady=5)
        self._refresh()

    @trace_action(source="tools")
    def _refresh(self):
        self.task_queue.put({'type': 'get_queue_status'}) # Correction du type de message
        self.after(2000, self._refresh)

    @trace_action(source="tools")
    def update_list(self, tasks):
        try:
            for item in self.tree.get_children(): self.tree.delete(item)
            # Gestion du format de réponse {current: ..., waiting: [...]}
            if isinstance(tasks, dict):
                current = tasks.get("current", "-")
                waiting = tasks.get("waiting", [])
                self.tree.insert("", "end", values=("NOW", current, "Running"))
                for i, t in enumerate(waiting):
                    self.tree.insert("", "end", values=(i+1, t, "Pending"))
            # Fallback ancien format liste
            elif isinstance(tasks, list):
                for i, t in enumerate(tasks):
                    action = t.get('action', '?') if isinstance(t, dict) else str(t)
                    self.tree.insert("", "end", values=(i, action, 'Pending'))
        except Exception: pass

class DbManagerWindow(BaseWindow):
    def __init__(self, master, task_queue, on_clear_chat=None):
        super().__init__(master, "Gestionnaire RAG (Mémoire)", 600, 500)
        self.task_queue = task_queue
        self.on_clear_chat = on_clear_chat
        self._build()
    
    @trace_action(source="tools")
    def _build(self):
        try:
            main = ctk.CTkFrame(self, fg_color="transparent")
            main.pack(fill="both", expand=True, padx=20, pady=20)
            
            # --- Câblage Direct (Bypass IA) ---
            
            ctk.CTkButton(
                main, 
                text="🔄 Reconstruire l'Index (RAG)",
                fg_color="#2ecc71", hover_color="#27ae60",
                command=self._reindex_direct
            ).pack(fill="x", pady=5)
            
            if self.on_clear_chat:
                ctk.CTkButton(
                    main, 
                    text="Effacer Chat", 
                    command=self.on_clear_chat
                ).pack(fill="x", pady=5)
            
            ctk.CTkButton(
                main, 
                text="🗑️ Supprimer Base Locale", 
                fg_color=COLORS["ERROR"], hover_color="#c0392b", 
                command=self._delete_db_direct
            ).pack(fill="x", pady=5)
            
            self.lbl_status = ctk.CTkLabel(main, text="Statut: Prêt", text_color="gray")
            self.lbl_status.pack(pady=10)
        except Exception as e:
            self.report_error("DbManager", e)

    def _reindex_direct(self):
        # Envoi direct au Worker sans passer par le chat
        self.task_queue.put({'type': 'reindex_db'})
        self.destroy()

    def _delete_db_direct(self):
        if messagebox.askyesno("Confirmation", "Supprimer la base de connaissances locale ?", parent=self):
            self.task_queue.put({'type': 'delete_db'})
            self.destroy()

class BackupManagerWindow(BaseWindow):
    """
    Gestionnaire de Backups.
    """
    def __init__(self, master, task_queue):
        super().__init__(master, "Gestionnaire de Sauvegardes", 900, 600)
        self.task_queue = task_queue
        if hasattr(master, 'windows'):
            master.windows['backup_manager'] = self
        self._build_ui()
        self._refresh()

    @trace_action(source="tools")
    def _build_ui(self):
        try:
            toolbar = ctk.CTkFrame(self, height=40, fg_color="transparent")
            toolbar.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(toolbar, text="Historique (Time Machine)", font=("Arial", 14, "bold"), text_color=COLORS["ACCENT"]).pack(side="left")
            
            # Bouton corrigé
            ctk.CTkButton(toolbar, text="📸 Créer Backup", command=self._create_backup, fg_color=COLORS["ACCENT"], width=120).pack(side="right", padx=5)
            ctk.CTkButton(toolbar, text="🔄 Actualiser", command=self._refresh, width=100).pack(side="right", padx=5)

            self.tree_frame = ctk.CTkFrame(self)
            self.tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            
            style = ttk.Style()
            style.theme_use("clam")
            style.configure("Treeview", background=COLORS["BG_WIDGET"], foreground=COLORS["FG_PRIMARY"], fieldbackground=COLORS["BG_WIDGET"], rowheight=25)
            
            columns = ("Date", "Fichier Original", "Taille", "Nom de Backup")
            self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings")
            self.tree.heading("Date", text="Date"); self.tree.heading("Fichier Original", text="Source")
            self.tree.heading("Taille", text="Taille"); self.tree.heading("Nom de Backup", text="Fichier Backup")
            self.tree.column("Date", width=150); self.tree.column("Fichier Original", width=250)
            self.tree.column("Taille", width=80); self.tree.column("Nom de Backup", width=250)
            
            self.tree.pack(fill="both", expand=True, side="left")
            sb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
            sb.pack(fill="y", side="right")
            self.tree.configure(yscrollcommand=sb.set)

            action_frame = ctk.CTkFrame(self, fg_color="transparent")
            action_frame.pack(fill="x", padx=10, pady=20)
            ctk.CTkLabel(action_frame, text="Sélectionnez une ligne pour restaurer.", text_color="gray").pack(side="left")
            ctk.CTkButton(action_frame, text="🔙 Restaurer la version sélectionnée", fg_color=COLORS["ERROR"], hover_color="#AA0000", command=self._restore_selected).pack(side="right")
        except Exception as e:
            self.report_error("Build Backup UI", e)

    @trace_action(source="tools")
    def _create_backup(self):
        # Correction : Appel direct au Worker (type 'backup_now') au lieu de passer par le chat
        self.task_queue.put({'type': 'backup_now'})
        messagebox.showinfo("Info", "Sauvegarde lancée en arrière-plan.", parent=self)

    @trace_action(source="tools")
    def _refresh(self):
        self.task_queue.put({'type': 'get_backup_list'})

    def update_list(self, backups_data):
        try:
            for item in self.tree.get_children(): self.tree.delete(item)
            for b in backups_data:
                date = b.get("date", "?"); orig = b.get("original", "") or b.get("count", "-")
                size = b.get("size", "0b"); fname = b.get("filename", "")
                self.tree.insert("", "end", values=(date, orig, size, fname))
        except Exception as e:
            self.report_error("Update Backup List", e)

    @trace_action(source="tools")
    def _restore_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Attention", "Veuillez sélectionner un fichier à restaurer.", parent=self)
            return
        item = self.tree.item(selected[0])
        backup_filename = item['values'][3]
        if messagebox.askyesno("Confirmer la restauration", f"Voulez-vous écraser les fichiers actuels avec {backup_filename} ?", parent=self):
            self.task_queue.put({'type': 'restore_backup', 'filename': backup_filename})
            self.destroy()
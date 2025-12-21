import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import logging
import time
import re # Nécessaire pour la recherche/remplacement

log = logging.getLogger("ui.widgets")

# --- COULEURS GLOBALES ---
COLORS = {
    "BG_MAIN": "#1E1E1E",
    "BG_SECONDARY": "#252526", 
    "BG_WIDGET": "#2D2D30",
    "ACCENT": "#007ACC",
    "ACCENT_HOVER": "#0098FF",
    "FG_PRIMARY": "#CCCCCC",
    "FG_SECONDARY": "#858585",
    "ERROR": "#F44336",
    "SUCCESS": "#4CAF50",
    "WARNING": "#FF9800",
    "INFO": "#2196F3"
}

class TextEditorWithLineNumbers(ctk.CTkFrame):
    """
    Éditeur de texte avancé avec numéros de ligne et Barre de Recherche (Ctrl+F).
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.pack_propagate(False)
        
        self.last_search_index = "1.0"

        # Configuration de la police
        self.editor_font = ctk.CTkFont(family="Consolas", size=11) # Police Code
        self.line_number_canvas_width = 40

        # Frame principal
        main_editor_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_editor_frame.pack(fill="both", expand=True)

        # Zone des numéros de ligne (Canvas pour plus de flexibilité)
        self.line_numbers = tk.Text(main_editor_frame, width=4, padx=4, takefocus=0, borderwidth=0,
                                    background=COLORS["BG_SECONDARY"], foreground=COLORS["FG_SECONDARY"],
                                    state="disabled", font=self.editor_font)
        self.line_numbers.pack(side="left", fill="y")
        
        # Scrollbars
        self.vsb = ctk.CTkScrollbar(main_editor_frame, command=self._on_scroll_y)
        self.vsb.pack(side="right", fill="y")

        # Zone de texte principale
        self.text_area = ctk.CTkTextbox(main_editor_frame, font=self.editor_font, wrap="none", undo=True,
                                        fg_color=COLORS["BG_WIDGET"], text_color=COLORS["FG_PRIMARY"])
        self.text_area.pack(side="left", fill="both", expand=True)
        
        # Configuration Scroll Sync
        self.text_area.configure(yscrollcommand=self._on_scroll_text_y)
        
        # Tags pour la recherche
        # Note: CTkTextbox n'expose pas directement tag_config de manière standard, on accède au widget tk sous-jacent si besoin
        # Mais CTkTextbox hérite de beaucoup de méthodes. On va essayer via l'API publique ou bypass.
        try:
            self.text_area._textbox.tag_config("found_match", background="#FFFF00", foreground="#000000")
        except: pass

        # Barre de Recherche (Cachée par défaut)
        self.find_bar_frame = ctk.CTkFrame(self, fg_color=COLORS["BG_SECONDARY"], height=35)
        self._setup_find_bar()

        # Bindings
        self.text_area.bind("<<Change>>", self._on_content_changed)
        self.text_area.bind("<KeyRelease>", self._on_content_changed)
        self.text_area.bind("<Return>", self._on_content_changed)
        self.text_area.bind("<BackSpace>", self._on_content_changed)
        self.text_area.bind("<Control-f>", self.open_find_bar)
        
        # Init
        self._update_line_numbers()

    def _setup_find_bar(self):
        # Entry Recherche
        self.find_entry = ctk.CTkEntry(self.find_bar_frame, placeholder_text="Chercher...", width=200)
        self.find_entry.pack(side="left", padx=5, pady=2)
        self.find_entry.bind("<Return>", self.find_next)
        
        # Boutons
        ctk.CTkButton(self.find_bar_frame, text="▼", width=30, command=self.find_next).pack(side="left", padx=2)
        
        # Entry Remplacement
        self.replace_entry = ctk.CTkEntry(self.find_bar_frame, placeholder_text="Remplacer...", width=200)
        self.replace_entry.pack(side="left", padx=5, pady=2)
        
        ctk.CTkButton(self.find_bar_frame, text="Remplacer Tout", width=100, command=self.replace_all).pack(side="left", padx=2)
        
        # Fermer
        ctk.CTkButton(self.find_bar_frame, text="X", width=30, fg_color=COLORS["ERROR"], command=self.close_find_bar).pack(side="right", padx=5)

    def open_find_bar(self, event=None):
        self.find_bar_frame.pack(side="bottom", fill="x", before=self.text_area.master) # Hack pour mettre en bas
        self.find_entry.focus_set()
        return "break"

    def close_find_bar(self, event=None):
        self.find_bar_frame.pack_forget()
        self.text_area.focus_set()
        # Nettoyage surlignage
        try: self.text_area._textbox.tag_remove("found_match", "1.0", "end")
        except: pass

    def find_next(self, event=None):
        term = self.find_entry.get()
        if not term: return
        
        try:
            # Recherche via le widget TK sous-jacent pour avoir accès à 'search'
            tk_text = self.text_area._textbox
            
            # Nettoyage précédent
            tk_text.tag_remove("found_match", "1.0", "end")
            
            # Recherche
            start_pos = tk_text.search(term, self.last_search_index, stopindex="end", nocase=True)
            if not start_pos:
                # Boucle au début
                start_pos = tk_text.search(term, "1.0", stopindex="end", nocase=True)
            
            if start_pos:
                end_pos = f"{start_pos}+{len(term)}c"
                tk_text.tag_add("found_match", start_pos, end_pos)
                tk_text.see(start_pos)
                self.last_search_index = end_pos
            else:
                self.last_search_index = "1.0"
        except Exception as e:
            log.error(f"Erreur recherche UI: {e}")

    def replace_all(self, event=None):
        target = self.find_entry.get()
        replacement = self.replace_entry.get()
        if not target: return
        
        content = self.text_area.get("1.0", "end")
        # Remplacement Python simple (plus stable que manipulation index TK)
        new_content = content.replace(target, replacement)
        
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", new_content)
        self._update_line_numbers()

    def _on_scroll_y(self, *args):
        self.text_area.yview(*args)
        self.line_numbers.yview(*args)

    def _on_scroll_text_y(self, *args):
        self.vsb.set(*args)
        self.line_numbers.yview_moveto(args[0])

    def _on_content_changed(self, event=None):
        self._update_line_numbers()

    def _update_line_numbers(self):
        line_count = int(self.text_area.index('end-1c').split('.')[0])
        lines = "\n".join(str(i) for i in range(1, line_count + 1))
        
        self.line_numbers.configure(state="normal")
        self.line_numbers.delete("1.0", "end")
        self.line_numbers.insert("1.0", lines)
        self.line_numbers.configure(state="disabled")

    # Méthodes proxy
    def get(self, *args, **kwargs): return self.text_area.get(*args, **kwargs)
    def insert(self, *args, **kwargs): 
        self.text_area.insert(*args, **kwargs)
        self._update_line_numbers()
    def delete(self, *args, **kwargs): 
        self.text_area.delete(*args, **kwargs)
        self._update_line_numbers()
    def see(self, *args, **kwargs): self.text_area.see(*args, **kwargs)
    def configure(self, **kwargs): self.text_area.configure(**kwargs)
    def focus(self): self.text_area.focus()
    
    @property
    def tag_config(self): return self.text_area.tag_config

class ApiKeyStatusMenu(ctk.CTkButton):
    """
    Bouton + Menu avec gestion temps réel des clés.
    """
    def __init__(self, master, task_queue=None, **kwargs):
        super().__init__(master, text="API Status ⏳", width=120, command=self.toggle_menu, **kwargs)
        self.task_queue = task_queue
        self.menu = None
        self.is_visible = False
        self.last_statuses = {}
        # Timer pour mise à jour locale des cooldowns
        self.after(1000, self._local_tick)

    def toggle_menu(self):
        if self.is_visible: self.hide()
        else: self.show()

    def show(self):
        if self.menu: self.hide()
        self.menu = ctk.CTkToplevel(self.winfo_toplevel())
        self.menu.wm_overrideredirect(True)
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self.menu.geometry(f"350x450+{x}+{y}")
        self.menu.configure(fg_color=COLORS["BG_SECONDARY"])
        
        # Header
        f = ctk.CTkFrame(self.menu, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f, text="État des Clés API", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkButton(f, text="🔄", width=30, command=self._request_audit).pack(side="right")
        
        self.scroll = ctk.CTkScrollableFrame(self.menu, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.menu.bind("<FocusOut>", lambda e: self.hide())
        self.menu.focus_set()
        self.is_visible = True
        self._refresh_menu_content()

    def hide(self):
        if self.menu:
            self.menu.destroy()
            self.menu = None
        self.is_visible = False

    def update_statuses(self, statuses):
        """Reçoit les données brutes du Worker."""
        self.last_statuses = statuses
        self._update_button_label()
        if self.is_visible:
            self._refresh_menu_content()

    def _update_button_label(self):
        # Calcul global
        total = 0
        valid = 0
        burned = 0
        cooldown = 0
        
        for provider, info in self.last_statuses.items():
            total += info.get('total', 0)
            valid += info.get('valid', 0)
            for d in info.get('details', []):
                if d['status'] == 'BURNED': burned += 1
                if d['status'] == 'QUOTA': cooldown += 1
        
        if burned > 0 and valid == 0:
            self.configure(text=f"API: 💀 ({burned})", fg_color=COLORS["ERROR"])
        elif cooldown > 0 and valid == 0:
            self.configure(text=f"API: ⏳ ({cooldown})", fg_color=COLORS["WARNING"])
        elif valid > 0:
            self.configure(text=f"API: 🟢 ({valid}/{total})", fg_color=COLORS["SUCCESS"])
        else:
            self.configure(text="API Status ⚪", fg_color=COLORS["FG_SECONDARY"])

    def _refresh_menu_content(self):
        if not self.menu: return
        for w in self.scroll.winfo_children(): w.destroy()
        
        for provider, info in self.last_statuses.items():
            p_frame = ctk.CTkFrame(self.scroll, fg_color=COLORS["BG_WIDGET"])
            p_frame.pack(fill="x", pady=5)
            
            ctk.CTkLabel(p_frame, text=f"Provider: {provider.upper()}", font=("Arial", 11, "bold")).pack(anchor="w", padx=5)
            
            details = info.get('details', [])
            for key_info in details:
                k_frame = ctk.CTkFrame(p_frame, fg_color="transparent", height=20)
                k_frame.pack(fill="x", padx=10, pady=1)
                
                key_mask = key_info['key']
                status = key_info['status']
                
                color = COLORS["FG_PRIMARY"]
                icon = "🔹"
                extra = ""
                
                if status == "OK": 
                    color = COLORS["SUCCESS"]; icon = "✅"
                elif status == "BURNED": 
                    color = COLORS["ERROR"]; icon = "💀"
                elif status == "QUOTA": 
                    color = COLORS["WARNING"]; icon = "⏳"
                    if 'cooldown_end' in key_info:
                        remaining = int(key_info['cooldown_end'] - time.time())
                        if remaining > 0: extra = f"({remaining}s)"
                
                ctk.CTkLabel(k_frame, text=f"{icon} {key_mask} {extra}", text_color=color, font=("Consolas", 10)).pack(side="left")
                ctk.CTkLabel(k_frame, text=status, text_color=color, font=("Consolas", 10)).pack(side="right")

    def _local_tick(self):
        """Met à jour les timers visuels toutes les secondes si le menu est ouvert."""
        if self.is_visible:
            self._refresh_menu_content()
        self.after(1000, self._local_tick)

    def _request_audit(self):
        if self.task_queue:
            self.task_queue.put({"type": "command", "command": "!native_tool {\"name\": \"audit_keys\", \"args\": {}}"})

class ReasoningModeSwitch(ctk.CTkFrame):
    """
    Switch pour activer/désactiver le mode Raisonnement (Thinking).
    """
    def __init__(self, master, command=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.command = command
        self.var_reasoning = ctk.BooleanVar(value=False)
        
        self.switch = ctk.CTkSwitch(self, text="Raisonnement", variable=self.var_reasoning,
                                    font=("Arial", 11), text_color="gray",
                                    command=self._on_toggle)
        self.switch.pack(side="left", padx=5)

    def _on_toggle(self):
        state = "Activé" if self.var_reasoning.get() else "Désactivé"
        log.info(f"Mode Raisonnement {state}")
        if self.command:
            self.command() # Appel du callback
            
    def get_mode(self):
        # [CORRECTION] Renvoie un Booléen pur (True/False) au lieu de string "thinking"/"normal"
        # Cela corrige le bug où le Worker voyait toujours True car "normal" (str) est Truthy.
        return self.var_reasoning.get()
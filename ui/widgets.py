import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import logging
import time
import re # Nécessaire pour la recherche/remplacement

# Import CTkMessagebox pour remplacer messagebox tkinter
try:
    from CTkMessagebox import CTkMessagebox
    CTKMESSAGEBOX_AVAILABLE = True
except ImportError:
    CTKMESSAGEBOX_AVAILABLE = False
    # Fallback vers messagebox tkinter si CTkMessagebox n'est pas disponible
    from tkinter import messagebox as CTkMessagebox

# Import CTkToolTip pour les tooltips modernes
try:
    from CTkToolTip import CTkToolTip
    CTKTOOLTIP_AVAILABLE = True
except ImportError:
    CTKTOOLTIP_AVAILABLE = False
    CTkToolTip = None

def add_tooltip(widget, message, delay=0.5):
    """
    Ajoute un tooltip à un widget si CTkToolTip est disponible.
    
    Args:
        widget: Widget auquel ajouter le tooltip
        message: Message du tooltip
        delay: Délai avant affichage en secondes
    """
    if CTKTOOLTIP_AVAILABLE and CTkToolTip:
        CTkToolTip(widget, message=message, delay=delay)

log = logging.getLogger("ui.widgets")

# Import CTkCodeBox
from features.CTkCodeBox import CTkCodeBox

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

# --- WRAPPER CTkMessagebox ---
def show_messagebox(title, message, icon="info", parent=None, **kwargs):
    """
    Wrapper pour CTkMessagebox avec API similaire à messagebox tkinter.
    
    Args:
        title: Titre de la boîte de dialogue
        message: Message à afficher
        icon: Type d'icône ("info", "warning", "error", "question", "check")
        parent: Fenêtre parente
        **kwargs: Arguments supplémentaires pour CTkMessagebox
    
    Returns:
        Résultat de la boîte de dialogue (pour askyesno: True/False)
    """
    if not CTKMESSAGEBOX_AVAILABLE:
        # Fallback vers messagebox tkinter
        from tkinter import messagebox
        if icon == "info":
            return messagebox.showinfo(title, message, parent=parent)
        elif icon == "warning":
            return messagebox.showwarning(title, message, parent=parent)
        elif icon == "error" or icon == "cancel":
            return messagebox.showerror(title, message, parent=parent)
        elif icon == "question":
            return messagebox.askyesno(title, message, parent=parent)
        else:
            return messagebox.showinfo(title, message, parent=parent)
    
    # Mapping des icônes
    icon_map = {
        "info": "info",
        "warning": "warning",
        "error": "cancel",
        "cancel": "cancel",
        "question": "question",
        "check": "check"
    }
    
    ctk_icon = icon_map.get(icon, "info")
    
    # Pour les questions (askyesno), utiliser option_1 et option_2
    if icon == "question":
        result = CTkMessagebox(
            title=title,
            message=message,
            icon=ctk_icon,
            option_1="Oui",
            option_2="Non",
            parent=parent,
            **kwargs
        )
        # CTkMessagebox retourne "Oui" ou "Non", convertir en booléen
        return result.get() == "Oui"
    else:
        # Pour les autres types, pas de retour de valeur
        CTkMessagebox(
            title=title,
            message=message,
            icon=ctk_icon,
            parent=parent,
            **kwargs
        )
        return None

# --- MAPPING LANGAGES POUR CTkCodeBox ---
def _detect_language_from_filename(filename):
    """
    Détecte le langage depuis le nom de fichier pour CTkCodeBox.
    Retourne le nom de langage compatible avec CTkCodeBox.
    """
    if not filename:
        return "text"
    
    ext = filename.lower().split('.')[-1] if '.' in filename else ""
    
    # Mapping des extensions vers les langages CTkCodeBox
    lang_map = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "jsx": "react",
        "html": "html",
        "css": "css",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "xml": "xml",
        "c": "c",
        "cpp": "cpp",
        "cxx": "cpp",
        "cc": "cpp",
        "h": "c",
        "hpp": "cpp",
        "cs": "c#",
        "java": "java",
        "go": "go",
        "rs": "rust",
        "php": "php",
        "rb": "ruby",
        "lua": "lua",
        "kt": "kotlin",
        "swift": "swift",
        "pl": "perl",
        "md": "text",  # Markdown n'est pas dans les langages supportés
        "txt": "text",
    }
    
    return lang_map.get(ext, "text")

class TextEditorWithLineNumbers(ctk.CTkFrame):
    """
    Éditeur de code moderne utilisant CTkCodeBox avec syntax highlighting intégré.
    """
    def __init__(self, master, filename=None, language=None, **kwargs):
        super().__init__(master, **kwargs)
        self.pack_propagate(False)
        self.filename = filename
        self.last_search_index = "1.0"
        
        # Détection du langage
        if language:
            detected_lang = language
        elif filename:
            detected_lang = _detect_language_from_filename(filename)
        else:
            detected_lang = "text"
        
        # Création du CTkCodeBox
        self.code_box = CTkCodeBox(
            self,
            language=detected_lang,
            theme="monokai",  # Thème dark populaire
            line_numbering=True,
            undo=True,
            menu=True,
            wrap=False,  # Pas de wrap pour l'édition de code
            height=kwargs.get("height", 200),
            fg_color=COLORS.get("BG_WIDGET", "#2D2D30"),
            text_color=COLORS.get("FG_PRIMARY", "#CCCCCC"),
        )
        self.code_box.pack(fill="both", expand=True)
        
        # Barre de recherche (CTkCodeBox n'a pas cette fonctionnalité)
        self.find_bar_frame = ctk.CTkFrame(self, fg_color=COLORS["BG_SECONDARY"], height=35)
        self._setup_find_bar()
        
        # Bindings pour la recherche
        self.code_box.bind("<Control-f>", self.open_find_bar)
        
        # Pour compatibilité avec l'ancien code
        self.text_area = self.code_box

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
        """Ouvre la barre de recherche."""
        self.find_bar_frame.pack(side="bottom", fill="x")
        self.find_entry.focus_set()
        return "break"

    def close_find_bar(self, event=None):
        """Ferme la barre de recherche."""
        self.find_bar_frame.pack_forget()
        self.text_area.focus_set()
        # Nettoyage surlignage
        try:
            self.text_area._textbox.tag_remove("found_match", "1.0", "end")
        except:
            pass

    def find_next(self, event=None):
        """Recherche le terme suivant."""
        term = self.find_entry.get()
        if not term:
            return
        
        try:
            # Recherche via le widget TK sous-jacent
            tk_text = self.text_area._textbox
            
            # Nettoyage précédent
            try:
                tk_text.tag_remove("found_match", "1.0", "end")
            except:
                pass
            
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
        """Remplace toutes les occurrences."""
        target = self.find_entry.get()
        replacement = self.replace_entry.get()
        if not target:
            return
        
        content = self.text_area.get("1.0", "end")
        new_content = content.replace(target, replacement)
        
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", new_content)
    
    # Méthodes proxy pour compatibilité
    def get(self, *args, **kwargs):
        """Proxy vers get."""
        return self.text_area.get(*args, **kwargs)
    
    def insert(self, *args, **kwargs):
        """Proxy vers insert."""
        return self.text_area.insert(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Proxy vers delete."""
        return self.text_area.delete(*args, **kwargs)
    
    def see(self, *args, **kwargs):
        """Proxy vers see."""
        return self.text_area.see(*args, **kwargs)
    
    def configure(self, **kwargs):
        """Proxy vers configure."""
        return self.text_area.configure(**kwargs)
    
    def focus(self):
        """Proxy vers focus."""
        return self.text_area.focus()
    
    @property
    def tag_config(self):
        """Proxy vers tag_config."""
        return self.text_area.tag_config

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
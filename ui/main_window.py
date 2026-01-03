import time
import tkinter as tk
from tkinter import filedialog, ttk
import customtkinter as ctk
import os
import logging
import threading
import queue
import sys
import json
import traceback

# --- Imports Configuration & Constantes ---
from config.constants import SUPPORTED_FILE_EXTENSIONS
from config.settings import APP_SETTINGS, LOGGING_CHANNELS, save_app_settings
from config.paths import get_path
from config.logs import get_logger

# --- Imports Architecture ---
from worker.core import Worker
import features.audio as audio_manager
import ui.syntax as syntax_highlighter

# --- Imports UI Components ---
from ui.widgets import TextEditorWithLineNumbers, MarkdownViewer, _is_markdown_content, _is_thinking_content, _parse_mixed_content, _group_thinking_and_response, ThinkingWidget, ResponseContainer, CollapsibleMarkdownWidget, COLORS, ApiKeyStatusMenu, ReasoningModeSwitch, show_messagebox, add_tooltip
from ui.windows import (
    SettingsWindow, DbManagerWindow, 
    WaitingListWindow, BackupManagerWindow,
    ApiKeyManager
)
from ui.windows.markdown_viewer import MarkdownViewerWindow
from features.UnifiedLogger import UnifiedLogger
from features.Decorators import trace_action

log = get_logger("ui.main_window")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# --- Queues ---
task_queue = queue.Queue()
result_queue = queue.Queue()

# --- Prompts ---
QUICK_PROMPTS = {
    "Audit Qualité": "Analyse la qualité et la sécurité de ce code : ",
    "Générer Tests": "Génère des tests unitaires (pytest) pour ce fichier : ",
    "Refactoring": "Propose un refactoring pour améliorer la lisibilité et la performance de : ",
    "Documentation": "Génère la documentation (docstrings + README) pour : ",
    "Expliquer": "Explique le fonctionnement de ce code étape par étape : "
}

class GeminiApp:
    def __init__(self, root):
        self.root = root
        # Configuration Grid Root
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Variables d'état
        self.current_file_path = None
        self.status_var = tk.StringVar(value="Initialisation...")
        self.is_working = False
        self.is_streaming = False
        self._stream_prefix_added = False  # Flag pour gérer le préfixe du premier chunk
        self.windows = {} 
        self.prompt_history = []
        self.history_index = -1
        self.sidebar_visible = True
        
        # Variables de préchauffage
        self._prewarm_triggered = False
        self._prewarm_in_progress = False  # Nouveau : indique si préchauffage en cours
        self._prewarm_thread = None
        self._maintenance_thread = None
        self._cache_lock = threading.Lock()
        
        # Init UI
        self._setup_layout()
        self._setup_bindings()
        self._setup_log_menu()
        
        # Worker
        self._init_worker()
        
        # Polling
        self.check_result_queue()
        
        # Préchauffage du modèle SentenceTransformer en arrière-plan
        from features.context import database
        database.warmup_model_background()
        
        # Déclencher le préchauffage au démarrage (au lieu d'attendre le focus)
        # 100ms après l'init pour laisser l'UI se charger
        self.root.after(100, self._prewarm_context_intelligent)

    @trace_action(source="main_window")
    def _setup_layout(self):
        """Reconstruction du Layout Classique (Sidebar | Tabs)."""
        
        # --- 1. SIDEBAR (Gauche) ---
        self.sidebar = ctk.CTkFrame(self.root, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1)
        
        # Header Sidebar
        lbl_title = ctk.CTkLabel(self.sidebar, text="EXPLORATEUR", font=("Arial", 12, "bold"))
        lbl_title.grid(row=0, column=0, padx=20, pady=10)
        
        # Bouton Actualiser
        btn_refresh = ctk.CTkButton(self.sidebar, text="Actualiser", height=25, command=self._refresh_explorer)
        btn_refresh.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        add_tooltip(btn_refresh, "Actualise l'arborescence des fichiers")
        
        # Treeview
        self.tree_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.tree_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b", foreground="#dce4ee", borderwidth=0, highlightthickness=0)
        style.map("Treeview", background=[('selected', '#007ACC')])
        
        self.tree = ttk.Treeview(self.tree_frame, show="tree", selectmode="extended")
        self.tree.pack(fill="both", expand=True, side="left")
        
        sb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        # --- 2. MAIN AREA (Droite) ---
        self.main_area = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_area.grid_rowconfigure(1, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        # A. Toolbar (Haut)
        self.toolbar = ctk.CTkFrame(self.main_area, height=40, fg_color="transparent")
        self.toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._create_toolbar_buttons()

        # B. Onglets Chat (Centre)
        self.tab_view = ctk.CTkTabview(self.main_area)
        self.tab_view.grid(row=1, column=0, sticky="nsew")
        
        # Chat Principal - Approche hybride avec affichage mixte
        self.tab_view.add("Chat Principal")
        chat1_container = ctk.CTkFrame(
            self.tab_view.tab("Chat Principal"), 
            fg_color="transparent",
            corner_radius=0,
            border_width=0
        )
        chat1_container.pack(fill="both", expand=True)
        
        # ScrollableFrame principal qui contiendra toutes les textboxes et widgets
        self.chat1_scroll = ctk.CTkScrollableFrame(
            chat1_container, 
            fg_color="transparent",
            corner_radius=0,
            border_width=0
        )
        self.chat1_scroll.pack(fill="both", expand=True)
        
        # Container pour widgets Markdown (sera ajouté dynamiquement)
        self.chat1_widgets_container = self.chat1_scroll
        
        # Chat Secondaire - Approche hybride avec affichage mixte
        self.tab_view.add("Chat Secondaire")
        chat2_container = ctk.CTkFrame(
            self.tab_view.tab("Chat Secondaire"), 
            fg_color="transparent",
            corner_radius=0,
            border_width=0
        )
        chat2_container.pack(fill="both", expand=True)
        
        # ScrollableFrame principal qui contiendra toutes les textboxes et widgets
        self.chat2_scroll = ctk.CTkScrollableFrame(
            chat2_container, 
            fg_color="transparent",
            corner_radius=0,
            border_width=0
        )
        self.chat2_scroll.pack(fill="both", expand=True)
        
        # Container pour widgets Markdown (sera ajouté dynamiquement)
        self.chat2_widgets_container = self.chat2_scroll
        
        # Les tags seront configurés lors de la création des textboxes dynamiques

        # C. Input Zone (Bas)
        self.input_frame = ctk.CTkFrame(self.main_area, height=100)
        self.input_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        
        self.btn_mic = ctk.CTkButton(self.input_frame, text="🎤", width=40, height=40, 
                                     command=lambda: task_queue.put({'type': 'start_asr'}))
        self.btn_mic.pack(side="left", padx=5, pady=5)
        add_tooltip(self.btn_mic, "Démarrer la reconnaissance vocale")
        
        self.btn_speak = ctk.CTkButton(self.input_frame, text="🔊", width=40, height=40, 
                                       command=lambda: task_queue.put({'type': 'start_tts', 'text': self._get_last_response()}))
        self.btn_speak.pack(side="left", padx=5, pady=5)
        add_tooltip(self.btn_speak, "Lire la dernière réponse à voix haute")

        self.input_txt = ctk.CTkTextbox(self.input_frame, height=60, font=("Arial", 12))
        self.input_txt.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        
        self.right_input_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.right_input_frame.pack(side="right", padx=5, pady=5)
        
        self.send_btn = ctk.CTkButton(self.right_input_frame, text="Envoyer ➤", width=100, height=40, command=self._on_send_click)
        self.send_btn.pack(pady=(0, 5))
        
        self.quick_menu = ctk.CTkOptionMenu(self.right_input_frame, values=list(QUICK_PROMPTS.keys()), 
                                            command=self._on_quick_action, width=100)
        self.quick_menu.set("Actions...")
        self.quick_menu.pack()

        # D. Status Bar
        self.status_bar = ctk.CTkLabel(self.main_area, textvariable=self.status_var, anchor="w", text_color="gray")
        self.status_bar.grid(row=3, column=0, sticky="ew", pady=(5,0))

        self._refresh_explorer()

    @trace_action(source="main_window")
    def _create_toolbar_buttons(self):
        """Crée les boutons de la toolbar."""
        
        # 1. Menu Fichiers
        self.file_menu_var = tk.StringVar(value="Fichiers 📂")
        self.file_menu = ctk.CTkOptionMenu(
            self.toolbar, 
            values=["Sauvegarder", "Ouvrir"], 
            command=self._on_file_menu_action,
            variable=self.file_menu_var,
            width=110
        )
        self.file_menu.pack(side="left", padx=2)

        # 2. Paramètres
        ctk.CTkButton(self.toolbar, text="⚙️ Paramètres", width=100, 
                      command=self._open_settings).pack(side="left", padx=2)
        
        # 3. API Status (Widget Custom)
        try:
            self.api_status_menu = ApiKeyStatusMenu(self.toolbar, task_queue=task_queue)
            self.api_status_menu.pack(side="left", padx=2)
        except Exception as e:
            log.error(f"Erreur init API Menu: {e}")
        
        # 4. Autres Outils
        ctk.CTkButton(self.toolbar, text="🧠 Base Vectorielle", width=110, command=self._open_db_manager).pack(side="left", padx=2)
        ctk.CTkButton(self.toolbar, text="📦 Backups", width=80, command=self._open_backup_manager).pack(side="left", padx=2)
        ctk.CTkButton(self.toolbar, text="⏳ File d'attente", width=100, command=self._open_waiting_list).pack(side="left", padx=2)
        
        # 5. Switch Raisonnement
        self.reasoning_switch = ReasoningModeSwitch(self.toolbar, command=self._on_reasoning_mode_change)
        self.reasoning_switch.pack(side="right", padx=5)

    def _on_file_menu_action(self, choice):
        if choice == "Sauvegarder": self._on_save_file()
        elif choice == "Ouvrir": self._on_open_file()
        self.file_menu_var.set("Fichiers 📂")

    # --- Actions Fichiers ---

    def _on_save_file(self):
        if not self.current_file_path:
            path = filedialog.asksaveasfilename(defaultextension=".py")
            if not path: return
            self.current_file_path = path
            
        try:
            current_tab = self.tab_view.get()
            if current_tab in ["Chat Principal", "Chat Secondaire"]:
                show_messagebox("Info", "Impossible de sauvegarder le chat comme fichier code.", icon="info")
                return

            tab_frame = self.tab_view.tab(current_tab)
            editor_widget = None
            # Recherche du widget éditeur
            for child in tab_frame.winfo_children():
                if hasattr(child, 'get_text'): # Notre TextEditorWithLineNumbers a get_text via mixin ou get
                    editor_widget = child
                    break
                # Fallback : check class name string ou instance
                if "TextEditorWithLineNumbers" in str(child.__class__):
                    editor_widget = child
                    break
            
            # Fallback si get_text n'existe pas mais text_area oui
            if not editor_widget:
                from ui.widgets import TextEditorWithLineNumbers
                for child in tab_frame.winfo_children():
                    if isinstance(child, TextEditorWithLineNumbers):
                        editor_widget = child
                        break

            if editor_widget:
                # get("1.0", "end-1c") est standard pour Tkinter Text
                content = editor_widget.text_area.get("1.0", "end-1c")
                with open(self.current_file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.status_var.set(f"Sauvegardé : {os.path.basename(self.current_file_path)}")
                task_queue.put({"type": "file_updated", "path": self.current_file_path})
            else:
                show_messagebox("Erreur", "Impossible de trouver l'éditeur.", icon="warning")

        except Exception as e:
            show_messagebox("Erreur", f"Erreur sauvegarde : {e}", icon="error")

    def _on_open_file(self):
        path = filedialog.askopenfilename()
        if path: self._open_file_in_tab(path)

    # --- Gestion Fenêtres Secondaires ---
    def _open_settings(self):
        if 'settings' not in self.windows or not self.windows['settings'].winfo_exists():
            self.windows['settings'] = SettingsWindow(self.root, task_queue)
        else: self.windows['settings'].focus()

    def _open_db_manager(self):
        if 'db_manager' not in self.windows or not self.windows['db_manager'].winfo_exists():
            try: self.windows['db_manager'] = DbManagerWindow(self.root, task_queue, self._clear_chat)
            except TypeError: self.windows['db_manager'] = DbManagerWindow(self.root)
        else: self.windows['db_manager'].focus()

    def _open_backup_manager(self):
        if 'backup_manager' not in self.windows or not self.windows['backup_manager'].winfo_exists():
            self.windows['backup_manager'] = BackupManagerWindow(self.root, task_queue)
        else: self.windows['backup_manager'].focus()
        task_queue.put({"type": "get_backup_list"})

    def _open_waiting_list(self):
        if 'waiting_list' not in self.windows or not self.windows['waiting_list'].winfo_exists():
            self.windows['waiting_list'] = WaitingListWindow(self.root, task_queue)
        else: self.windows['waiting_list'].focus()

    # --- Menu Logs ---
    def _setup_log_menu(self):
        if not hasattr(self, "menubar"):
            self.menubar = tk.Menu(self.root)
            self.root.config(menu=self.menubar)
        
        self.log_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Logs 🛠️", menu=self.log_menu)
        
        self.log_vars = {}
        for channel, enabled in LOGGING_CHANNELS.items():
            var = tk.BooleanVar(value=enabled)
            self.log_vars[channel] = var
            self.log_menu.add_checkbutton(label=f"Canal {channel}", variable=var, 
                                          command=lambda c=channel: self._toggle_log_channel(c))
            
        self.log_menu.add_separator()
        self.log_menu.add_command(label="Ouvrir fichier Log", command=lambda: os.startfile("global_debug.log") if os.name=='nt' else None)

    def _toggle_log_channel(self, channel):
        val = self.log_vars[channel].get()
        LOGGING_CHANNELS[channel] = val
        APP_SETTINGS["logging_channels"] = LOGGING_CHANNELS
        save_app_settings()
        UnifiedLogger.write("UI", "INFO", f"Log {channel} -> {val}")

    # --- Worker & Bindings ---
    @trace_action(source="main_window")
    def _init_worker(self):
        self.stop_event = threading.Event()
        self.worker_thread = Worker(task_queue, result_queue, self.stop_event)
        self.worker_thread.start()
        self._load_prompt_history()
        # [OPTIMISATION] Pré-chauffage immédiat du CLI pour éliminer le Cold Start
        task_queue.put({'type': 'prewarm_cli'})

    @trace_action(source="main_window")
    def _setup_bindings(self):
        self.input_txt.bind("<Return>", self._on_enter)
        self.input_txt.bind("<Up>", self._history_up)
        self.input_txt.bind("<Down>", self._history_down)
        self.input_txt.bind("<FocusIn>", self._on_input_focus)
        self.input_txt.bind("<Button-1>", self._on_input_click)
        
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        stop_key = APP_SETTINGS.get("key_bindings", {}).get("stop_generation", "<Delete>")
        self.root.bind(stop_key, self._on_stop_shortcut)
    def _on_stop_shortcut(self, event=None):
        """Action déclenchée par la touche Suppr."""
        if self.is_working or self.is_streaming:
            self._on_send_click() # Le bouton 'Envoyer' est devenu 'STOP', donc on clique dessus virtuellement
    # --- Actions UI ---
    
    def _on_enter(self, event):
        """Gère l'envoi avec Entrée (sans Shift)."""
        # 0x0001 est le masque pour Shift sur Windows/Linux souvent, ou event.state & 1
        # Pour être sûr : on regarde si shift est pressé
        if event.state & 0x0001: 
            return None # Laisse passer le saut de ligne
        self._on_send_click()
        return "break" # Empêche le saut de ligne par défaut

    def _on_send_click(self):
        # 1. Mode STOP (Si déjà en train de travailler)
        if self.is_working or self.is_streaming:
            task_queue.put({'type': 'stop_generation'})
            # On ne change pas l'UI tout de suite, on attend la confirmation du worker (fin de stream)
            # Mais on peut forcer un feedback visuel
            self.status_var.set("Arrêt en cours...")
            return

        # 2. Mode ENVOYER (Normal)
        msg = self.input_txt.get("1.0", "end").strip()
        if not msg: return
        
        # Gestion Historique
        if not self.prompt_history or self.prompt_history[0] != msg:
            self.prompt_history.insert(0, msg)
            self._save_prompt_history()
        self.history_index = -1
        
        self.input_txt.delete("1.0", "end")
        
        target = self.tab_view.get()
        # Déterminer le container approprié
        if target == "Chat Secondaire":
            scroll_container = self.chat2_scroll
            widgets_container = self.chat2_widgets_container
        else:
            scroll_container = self.chat1_scroll
            widgets_container = self.chat1_widgets_container
        
        # Créer une nouvelle textbox pour le message utilisateur
        textbox = self._create_message_textbox(widgets_container, "user")
        textbox.configure(state="normal")
        textbox.insert("1.0", f"Vous: {msg}", "user")
        textbox.configure(state="disabled")
        
        # Scroll vers le bas
        def scroll_to_bottom():
            try:
                if hasattr(scroll_container, '_parent_canvas'):
                    canvas = scroll_container._parent_canvas
                    canvas.update_idletasks()
                    canvas.yview_moveto(1.0)
            except:
                pass
        scroll_container.after(100, scroll_to_bottom)
        
        task_type = 'secondary_user_prompt' if target == "Chat Secondaire" else 'user_prompt'
        
        task_queue.put({
            "type": task_type,
            "prompt": msg,
            "context_files": [self.current_file_path] if self.current_file_path else []
        })
        
        # Passage en mode "Travail" (Bouton devient STOP)
        self._start_animation()

    # --- Explorateur ---
    def _refresh_explorer(self):
        self.tree.delete(*self.tree.get_children())
        self._populate_tree("", get_path("."))

    def _populate_tree(self, parent, path):
        try:
            items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
            for item in items:
                if item.startswith(".") or item in ["__pycache__", "venv", "node_modules"]: continue
                abspath = os.path.join(path, item)
                is_dir = os.path.isdir(abspath)
                
                oid = self.tree.insert(parent, "end", text=f" {item}", open=False, values=[abspath])
                if is_dir: self.tree.insert(oid, "end", text="Chargement...")
        except Exception: pass

    def _on_tree_open(self, event):
        item_id = self.tree.focus()
        if not item_id: return
        children = self.tree.get_children(item_id)
        if len(children) == 1 and self.tree.item(children[0], "text") == "Chargement...":
            self.tree.delete(children[0])
            path = self.tree.item(item_id, "values")[0]
            self._populate_tree(item_id, path)

    def _on_tree_double_click(self, event):
        item = self.tree.selection()[0]
        val = self.tree.item(item, "values")
        if val:
            path = val[0]
            if os.path.isfile(path):
                self._open_file_in_tab(path)

    def _open_file_in_tab(self, path):
        filename = os.path.basename(path)
        if filename in self.tab_view._tab_dict:
            self.tab_view.set(filename)
            return
        
        self.tab_view.add(filename)
        try:
            with open(path, 'r', encoding='utf-8') as f: content = f.read()
        except: content = "Erreur lecture."
        
        # Détection Markdown/HTML
        ext = filename.split('.')[-1].lower() if '.' in filename else ""
        
        if ext in ['md', 'html', 'htm']:
            # Utiliser MarkdownViewer pour les fichiers Markdown/HTML
            viewer = MarkdownViewer(
                self.tab_view.tab(filename),
                content=content,
                is_markdown=(ext == 'md')
            )
            viewer.pack(fill="both", expand=True)
        else:
            # Comportement actuel avec TextEditorWithLineNumbers pour les autres fichiers
            editor = TextEditorWithLineNumbers(self.tab_view.tab(filename), filename=filename)
            editor.pack(fill="both", expand=True)
            editor.insert("1.0", content)
            # Note: CTkCodeBox gère déjà le syntax highlighting automatiquement
            # On n'a plus besoin d'appeler apply_highlighting_to_editor
        
        self.tab_view.set(filename)
        self.current_file_path = path

    # --- Helpers & Polling ---
    def _on_reasoning_mode_change(self):
        mode = self.reasoning_switch.get_mode()
        task_queue.put({"type": "set_reasoning_mode", "mode": mode})

    def _configure_chat_tags(self, widget):
        widget.tag_config("user", foreground=COLORS["ACCENT"])
        widget.tag_config("gemini", foreground=COLORS["FG_PRIMARY"])
        widget.tag_config("info", foreground=COLORS["INFO"])
        widget.tag_config("error", foreground=COLORS["ERROR"])
        syntax_highlighter.configure_tags(widget)

    def _create_message_textbox(self, container, tag="gemini", content=""):
        """Crée une nouvelle textbox pour un message avec hauteur adaptative. Pas de scrollbar."""
        # Récupérer la taille de police depuis les settings
        font_size = APP_SETTINGS.get("system_settings", {}).get("font_size", 12)
        
        # Calculer la hauteur approximative basée sur le contenu
        if content:
            # Compter les lignes réelles (avec wrap approximatif)
            lines = content.count('\n') + 1
            # Estimer les lignes avec wrap (environ 80 caractères par ligne)
            avg_chars_per_line = 80
            wrapped_lines = sum(len(line) // avg_chars_per_line + 1 for line in content.split('\n'))
            total_lines = max(lines, wrapped_lines)
            # Calculer la hauteur en fonction de la taille de police
            line_height = max(int(font_size * 1.0), 13)  # Harmonisé avec widgets.py
            estimated_height = total_lines * line_height  # Pas de padding supplémentaire ni de minimum
        else:
            estimated_height = 20  # Hauteur minimale très réduite pour les textboxes vides
        
        # Créer la textbox avec la taille de police configurée et SANS scrollbars ni scroll
        textbox = ctk.CTkTextbox(
            container, 
            wrap="word", 
            font=("Consolas", font_size), 
            height=estimated_height,
            activate_scrollbars=False,  # Désactiver les scrollbars
            yscrollcommand=None,  # Désactiver le scroll vertical
            xscrollcommand=None,   # Désactiver le scroll horizontal
            corner_radius=0,      # Espacement minimal
            border_spacing=0       # Texte touche les bords
        )
        # pady=1 pour un léger espacement entre les box (scaled automatiquement par CustomTkinter)
        textbox.pack(fill="x", padx=0, pady=1)
        textbox.configure(state="disabled")
        self._configure_chat_tags(textbox)
        
        return textbox
    
    def _adjust_textbox_height(self, textbox):
        """Ajuste la hauteur d'une textbox pour qu'elle corresponde exactement au contenu."""
        try:
            textbox.update_idletasks()
            # Obtenir le nombre de lignes réelles dans la textbox
            line_count = int(textbox.index("end-1c").split('.')[0])
            if line_count > 0:
                # Calculer la hauteur nécessaire
                font_size = APP_SETTINGS.get("system_settings", {}).get("font_size", 12)
                line_height = max(int(font_size * 1.0), 13)
                new_height = line_count * line_height  # Pas de minimum
                textbox.configure(height=new_height)
                textbox.update_idletasks()
        except Exception as e:
            log.debug(f"Erreur ajustement hauteur textbox: {e}")
    
    def _log_chat(self, widget, text, tag, thought_content=None):
        """
        Affiche un message dans le chat.
        
        Args:
            widget: Widget parent (None pour chat principal)
            text: Contenu principal du message
            tag: Tag pour le style (user, gemini, etc.)
            thought_content: Contenu de pensée optionnel (si fourni, utilisé directement au lieu de la regex)
        """
        # Nettoyer les séquences \n\n échappées
        text = text.replace('\\n\\n', '\n\n').replace('\\n', '\n')
        
        # Déterminer quel container utiliser (chat1 par défaut si widget est None)
        if widget is None or (hasattr(self, 'chat1_scroll') and not hasattr(self, 'chat1_txt')):
            scroll_container = self.chat1_scroll
            widgets_container = self.chat1_widgets_container
        elif hasattr(widget, 'master') and widget.master == self.chat2_scroll:
            scroll_container = self.chat2_scroll
            widgets_container = self.chat2_widgets_container
        else:
            scroll_container = self.chat1_scroll
            widgets_container = self.chat1_widgets_container
        
        # Si thought_content est fourni explicitement, l'utiliser directement
        # Sinon, utiliser la regex comme fallback pour compatibilité historique
        if thought_content is not None:
            thinking_content = thought_content
            # Si thought est fourni, le texte principal ne contient que la réponse
            response_parts = _group_thinking_and_response(text) if text.strip() else []
        else:
            # Fallback : utiliser la regex pour séparer thinking et réponse
            thinking_content, response_parts = _group_thinking_and_response(text)
        
        # Afficher le thinking (un seul widget regroupé, collapsed par défaut)
        if thinking_content:
            thinking_widget = ThinkingWidget(
                widgets_container,
                content=thinking_content
            )
            # pady=1 pour un léger espacement entre les box (scaled automatiquement par CustomTkinter)
            thinking_widget.pack(fill="x", padx=0, pady=1)
        
        # Créer le ResponseContainer pour la réponse finale
        if response_parts:
            response_container = ResponseContainer(widgets_container)
            # Utiliser fill="x" et expand=False pour éviter l'expansion verticale inutile
            # pady=1 pour un léger espacement entre les box (scaled automatiquement par CustomTkinter)
            response_container.pack(fill="x", expand=False, padx=0, pady=1)
            
            # Ajouter tous les éléments de la réponse au container
            for part_type, part_content in response_parts:
                if part_type == 'text' and part_content.strip():
                    # Ajouter une textbox
                    textbox = response_container.add_textbox(part_content, tag)
                    self._configure_chat_tags(textbox)
                elif part_type == 'markdown':
                    # Ajouter un widget Markdown
                    response_container.add_markdown_widget(
                        content=part_content,
                        is_markdown=True,
                        on_open_in_tab=self._open_markdown_in_tab
                    )
        elif not thinking_content:
            # Si pas de thinking et pas de réponse structurée, afficher le texte simple
            # Le pady=1 est déjà géré dans _create_message_textbox.pack()
            textbox = self._create_message_textbox(widgets_container, tag, text)
            textbox.configure(state="normal")
            textbox.insert("1.0", text, tag)
            textbox.configure(state="disabled")
            # Ajuster la hauteur après insertion du texte
            self.root.after(10, lambda: self._adjust_textbox_height(textbox))
        
        # Scroll vers le bas
        def scroll_to_bottom():
            try:
                if hasattr(scroll_container, '_parent_canvas'):
                    canvas = scroll_container._parent_canvas
                    canvas.update_idletasks()
                    canvas.yview_moveto(1.0)
            except:
                pass
        scroll_container.after(100, scroll_to_bottom)
    
    def _open_markdown_in_tab(self, content, is_markdown):
        """Ouvre le contenu Markdown dans un onglet séparé."""
        import time
        tab_name = f"Markdown_{int(time.time())}"
        
        self.tab_view.add(tab_name)
        
        viewer = MarkdownViewer(
            self.tab_view.tab(tab_name),
            content=content,
            is_markdown=is_markdown
        )
        viewer.pack(fill="both", expand=True)
        self.tab_view.set(tab_name)

    def _get_last_response(self):
        # Récupérer le dernier message depuis le container
        try:
            # Chercher la dernière textbox dans le container
            children = self.chat1_widgets_container.winfo_children()
            for child in reversed(children):
                if isinstance(child, ctk.CTkTextbox):
                    content = child.get("1.0", "end")
                    if content.strip():
                        return content
        except:
            pass
        return ""

    def _clear_chat(self):
        # Supprimer tous les widgets du container
        try:
            for widget in self.chat1_widgets_container.winfo_children():
                widget.destroy()
        except:
            pass
        task_queue.put({'type': 'reset_memory'})
        self.status_var.set("🧹 Chat et Mémoire effacés.")

    def check_result_queue(self):
        try:
            while not result_queue.empty():
                res = result_queue.get_nowait()
                msg_type = res.get('type')
                
                # DEBUG: Log tous les messages reçus pour diagnostiquer
                if msg_type in ['ui_stream_chunk', 'ui_stream_thinking', 'ui_stream_start', 'ui_stream_end']:
                    log.debug(f"📨 Message reçu: type={msg_type}, keys={list(res.keys())}, has_text={'text' in res}")

                if msg_type == 'chat_response':
                    self._stop_animation()
                    # Le message système (toolcall) doit être affiché même pendant le stream
                    # Nouveau format structuré : utiliser content et thought séparément
                    content = res.get('content', res.get('text', ''))  # Fallback sur 'text' pour compatibilité
                    thought = res.get('thought', None)
                    # Utiliser _log_chat qui gère correctement la création des widgets
                    self._log_chat(None, content, "gemini", thought_content=thought)
                
                elif msg_type == 'ui_stream_start':
                    # Réinitialiser les buffers pour le nouveau stream
                    self._stream_prefix_added = False
                    self.is_streaming = True
                    self._stream_buffer = ""  # Buffer pour accumuler la réponse finale
                    self._thinking_buffer = ""  # Buffer pour accumuler les thinking
                    self._current_stream_textbox = None  # Pas de textbox pendant le stream
                
                elif msg_type == 'ui_stream_thinking':
                    # Accumuler les thinking séparément
                    if not hasattr(self, '_thinking_buffer'):
                        self._thinking_buffer = ""
                    text = res['text'].replace('\\n\\n', '\n\n').replace('\\n', '\n')
                    self._thinking_buffer += text
                    log.info(f"🔵 THINKING accumulé: {len(text)} chars, total: {len(self._thinking_buffer)} chars")
                
                elif msg_type == 'ui_stream_chunk':
                    # Accumuler le contenu de la réponse finale dans le buffer (ne pas afficher pendant le stream)
                    # Initialiser le buffer s'il n'existe pas (défense contre les messages hors ordre)
                    if not hasattr(self, '_stream_buffer'):
                        log.warning("⚠️ ui_stream_chunk reçu avant ui_stream_start, initialisation du buffer")
                        self._stream_buffer = ""
                    
                    try:
                        text = res.get('text', '')
                        if not text:
                            log.warning(f"⚠️ ui_stream_chunk reçu avec texte vide: {res}")
                            return
                        
                        text = text.replace('\\n\\n', '\n\n').replace('\\n', '\n')
                        self._stream_buffer += text
                        log.info(f"🟢 CONTENU accumulé: {len(text)} chars, total: {len(self._stream_buffer)} chars")
                    except Exception as e:
                        log.error(f"❌ Erreur traitement ui_stream_chunk: {e}", exc_info=True)
                
                elif msg_type == 'ui_stream_end':
                    self._stop_animation() 
                    # Réinitialiser le flag pour le prochain stream
                    self._stream_prefix_added = False
                    self.is_streaming = False
                    
                    # Afficher le thinking séparément si présent (détecté nativement via champ 'thought')
                    # IMPORTANT: Ne créer le ThinkingWidget que si _thinking_buffer contient vraiment du contenu
                    thinking_buffer_content = getattr(self, '_thinking_buffer', None)
                    if thinking_buffer_content and thinking_buffer_content.strip():
                        try:
                            thinking_content = thinking_buffer_content.replace('\\n\\n', '\n\n').replace('\\n', '\n')
                            log.info(f"🔵 Displaying thinking widget: {len(thinking_content)} chars")
                            thinking_widget = ThinkingWidget(
                                self.chat1_widgets_container,
                                content=thinking_content
                            )
                            # pady=1 pour un léger espacement entre les box (scaled automatiquement par CustomTkinter)
                            thinking_widget.pack(fill="x", padx=0, pady=1)
                            if hasattr(self, '_thinking_buffer'):
                                del self._thinking_buffer
                        except Exception as e:
                            log.error(f"Erreur affichage thinking: {e}", exc_info=True)
                            if hasattr(self, '_thinking_buffer'):
                                del self._thinking_buffer
                    elif hasattr(self, '_thinking_buffer'):
                        # Buffer vide ou None, nettoyer
                        log.debug("Thinking buffer is empty, skipping thinking widget")
                        del self._thinking_buffer
                    
                    # Traiter la réponse finale (sans thinking, déjà séparé)
                    # IMPORTANT: Vérifier que _stream_buffer contient bien du contenu (pas vide)
                    stream_buffer_content = getattr(self, '_stream_buffer', None)
                    
                    # DEBUG: Log le contenu du buffer avant traitement
                    log.info(f"🔍 DEBUG ui_stream_end: stream_buffer_content type={type(stream_buffer_content)}, length={len(stream_buffer_content) if stream_buffer_content else 0}, preview={str(stream_buffer_content)[:200] if stream_buffer_content else 'None'}")
                    
                    if stream_buffer_content and stream_buffer_content.strip():
                        try:
                            # Nettoyer le buffer
                            streamed_text = stream_buffer_content.replace('\\n\\n', '\n\n').replace('\\n', '\n')
                            
                            # CRITIQUE: Le thinking a déjà été séparé dans _thinking_buffer et affiché séparément
                            # Le streamed_text ne devrait contenir QUE la réponse finale, pas de thinking
                            # Mais on vérifie quand même pour filtrer les pensées qui pourraient s'y être glissées
                            # IMPORTANT: Ne PAS utiliser _is_thinking_content() directement car elle peut être trop agressive
                            # et supprimer toute la réponse si elle commence par un pattern de thinking
                            
                            # Utiliser _group_thinking_and_response pour séparer proprement thinking et réponse
                            thinking_content_filtered, response_parts = _group_thinking_and_response(streamed_text)
                            
                            if thinking_content_filtered:
                                # Reconstruire streamed_text sans les pensées (filtrer tous les types sauf thinking)
                                filtered_parts = [p[1] for p in response_parts if p[0] != 'thinking']
                                if filtered_parts:
                                    streamed_text = "\n\n".join(filtered_parts)
                                    log.info(f"🔵 Pensées filtrées du streamed_text ({len(thinking_content_filtered)} chars), réponse restante: {len(streamed_text)} chars")
                                else:
                                    # Si après filtrage il ne reste rien, c'est que tout était du thinking
                                    streamed_text = ""
                                    log.info(f"🔵 Streamed text contient uniquement du thinking, filtré de la réponse")
                            elif response_parts:
                                # S'il y a des response_parts mais pas de thinking_content_filtered,
                                # reconstruire quand même pour être sûr (au cas où _parse_mixed_content a mal classé)
                                filtered_parts = [p[1] for p in response_parts if p[0] != 'thinking']
                                if filtered_parts:
                                    streamed_text = "\n\n".join(filtered_parts)
                            # Si pas de response_parts, garder streamed_text tel quel (c'est probablement de la réponse pure)
                            
                            if not streamed_text or not streamed_text.strip():
                                log.info(f"ℹ️ Streamed text vide après filtrage des pensées - réponse finale vide")
                                # Nettoyer le buffer et sortir
                                if hasattr(self, '_stream_buffer'):
                                    del self._stream_buffer
                                return
                            
                            log.info(f"🟢 Displaying response container: {len(streamed_text)} chars, preview: {streamed_text[:200]}")
                            
                            # IMPORTANT: Le thinking a déjà été séparé et filtré, donc on ne doit PAS utiliser _parse_mixed_content
                            # qui pourrait détecter incorrectement le texte comme du thinking.
                            # On parse seulement pour détecter Markdown vs texte simple.
                            
                            # Vérifier si c'est du Markdown
                            is_markdown = _is_markdown_content(streamed_text)
                            log.info(f"📝 Markdown détecté: {is_markdown}")
                            
                            # Créer le ResponseContainer pour la réponse finale
                            # Pas de hauteur limitée, affichage en grand, scrollbar masquée
                            response_container = ResponseContainer(self.chat1_widgets_container)
                            # Utiliser fill="x" et expand=False pour éviter l'expansion verticale inutile
                            # pady=1 pour un léger espacement entre les box (scaled automatiquement par CustomTkinter)
                            response_container.pack(fill="x", expand=False, padx=0, pady=1)
                            
                            if is_markdown:
                                # Ajouter un widget Markdown
                                response_container.add_markdown_widget(
                                    content=streamed_text,
                                    is_markdown=True,
                                    on_open_in_tab=self._open_markdown_in_tab
                                )
                            else:
                                # Ajouter une textbox pour le texte simple
                                textbox = response_container.add_textbox(streamed_text, "gemini")
                                self._configure_chat_tags(textbox)
                            
                            # Nettoyer le buffer
                            if hasattr(self, '_stream_buffer'):
                                del self._stream_buffer
                        except Exception as e:
                            log.error(f"Erreur traitement stream: {e}", exc_info=True)
                            # En cas d'erreur, afficher le contenu brut
                            if hasattr(self, '_stream_buffer') and self._stream_buffer:
                                textbox = self._create_message_textbox(self.chat1_widgets_container, "gemini", self._stream_buffer)
                                textbox.configure(state="normal")
                                textbox.insert("1.0", f"🤖 {self._stream_buffer}", "gemini")
                                textbox.configure(state="disabled")
                                # Ajuster la hauteur après insertion du texte
                                self.root.after(10, lambda: self._adjust_textbox_height(textbox))
                                del self._stream_buffer
                    elif hasattr(self, '_stream_buffer'):
                        # Buffer vide ou None, mais log pour debug
                        log.warning(f"⚠️ Stream buffer is empty at ui_stream_end. Content was: {repr(stream_buffer_content)}")
                        # Vérifier s'il y a du thinking mais pas de réponse finale
                        thinking_content = getattr(self, '_thinking_buffer', None)
                        if thinking_content and thinking_content.strip():
                            log.info(f"ℹ️ Thinking présent ({len(thinking_content)} chars) mais pas de réponse finale - c'est normal si l'IA n'a généré que des pensées")
                        del self._stream_buffer
                    else:
                        # Buffer n'existe même pas - problème d'initialisation
                        log.error("❌ _stream_buffer n'existe pas à ui_stream_end - ui_stream_start n'a peut-être pas été reçu")
                    
                    # Scroll vers le bas
                    def scroll_to_bottom():
                        try:
                            if hasattr(self.chat1_scroll, '_parent_canvas'):
                                canvas = self.chat1_scroll._parent_canvas
                                canvas.update_idletasks()
                                canvas.yview_moveto(1.0)
                        except:
                            pass
                    self.chat1_scroll.after(100, scroll_to_bottom)
                    
                elif msg_type == 'ui_update':
                    if res.get('widget') == 'status': self.status_var.set(res['text'])
                    elif res.get('widget') == 'message': self._log_chat(None, f"ℹ️ {res['text']}", "info")
                
                elif msg_type == 'error':
                    self._stop_animation()
                    self._log_chat(None, f"❌ {res['text']}", "error")
                
                elif msg_type == 'init_done':
                    self.status_var.set(f"Prêt ({res.get('key_name')})")
                    task_queue.put({'type': 'load_context'})

                elif msg_type == 'worker_status':
                    if self.api_status_menu: self.api_status_menu.update_statuses(res['statuses'])
                
                elif msg_type == 'backup_list_data':
                    if 'backup_manager' in self.windows: self.windows['backup_manager'].update_list(res['data'])
                
                elif msg_type == 'waiting_list_update':
                    if 'waiting_list' in self.windows: self.windows['waiting_list'].update_list(res['tasks'])
                
                elif msg_type == 'asr_done':
                    self._handle_asr_done(res)

        except queue.Empty: pass
        finally:
            self.root.after(100, self.check_result_queue)

    def _handle_asr_done(self, res):
        self.input_txt.insert("end", res['text'] + " ")

    def _start_animation(self):
        self.is_working = True
        # [DESIGN] Le bouton devient ROUGE et affiche STOP
        self.send_btn.configure(text="STOP 🛑", fg_color=COLORS["ERROR"], state="normal")
        self.status_var.set("IA réfléchit...")

    def _stop_animation(self):
        self.is_working = False
        self.is_streaming = False
        # [DESIGN] Retour à la normale
        self.send_btn.configure(text="Envoyer ➤", fg_color=COLORS["ACCENT"], state="normal")
        self.status_var.set("Prêt")

    # Actions Menu Clic Droit
    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Analyser", command=lambda: self._on_quick_action("Audit Qualité"))
            menu.post(event.x_root, event.y_root)

    def _on_quick_action(self, choice):
        if not self.current_file_path: return
        prompt = QUICK_PROMPTS.get(choice, "")
        task_queue.put({"type": "analyze_file", "file_path": self.current_file_path, "prompt": prompt})
        self._log_chat(None, f"Action: {choice} sur {os.path.basename(self.current_file_path)}", "info")

    # --- GESTION HISTORIQUE COMMANDES ---

    def _history_up(self, event):
        """Remonte dans l'historique (Flèche Haut)."""
        if self.prompt_history and self.history_index < len(self.prompt_history) - 1:
            self.history_index += 1
            self.input_txt.delete("1.0", "end")
            self.input_txt.insert("end", self.prompt_history[self.history_index])
        return "break"

    def _history_down(self, event):
        """Descend dans l'historique (Flèche Bas)."""
        if self.history_index > -1:
            self.history_index -= 1
            self.input_txt.delete("1.0", "end")
            if self.history_index >= 0:
                self.input_txt.insert("end", self.prompt_history[self.history_index])
        return "break"

    def _load_prompt_history(self):
        """Charge l'historique depuis le JSON."""
        try:
            hist_path = get_path("prompt_history.json")
            if os.path.exists(hist_path):
                with open(hist_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Compatibilité : Si c'est une liste de dicts (ancienne version), on extrait le texte
                    if data and isinstance(data[0], dict):
                        self.prompt_history = [item.get("prompt", "") for item in data]
                    else:
                        self.prompt_history = data
        except Exception as e:
            log.warning(f"Erreur chargement historique: {e}")
            self.prompt_history = []

    def _on_input_focus(self, event=None):
        """Déclenche le préchauffage intelligent au focus."""
        if not self._prewarm_triggered:
            self._prewarm_triggered = True
            self._prewarm_context_intelligent()
        return None

    def _on_input_click(self, event=None):
        """Déclenche aussi le préchauffage au clic."""
        self._on_input_focus(event)
        return None

    def _prewarm_context_intelligent(self):
        """Préchauffe intelligemment les composants selon les dépendances."""
        # Vérifier si déjà en cours pour éviter les doublons
        with self._cache_lock:
            if self._prewarm_in_progress:
                log.debug("⚠️ Préchauffage déjà en cours, ignoré")
                return
            self._prewarm_in_progress = True
        
        def prewarm_task():
            try:
                log.debug("🔥 Démarrage préchauffage contextuel...")
                
                # Phase 1 : Composants indépendants en parallèle (gain: ~1.1s)
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {
                        'session': executor.submit(self._prewarm_session),
                        'rag_db': executor.submit(self._prewarm_rag_db),
                        'tree': executor.submit(self._prewarm_tree),
                        'repo_map': executor.submit(self._prewarm_repo_map)
                    }
                    
                    # Attendre la fin de tous les composants critiques
                    for name, future in futures.items():
                        try:
                            future.result(timeout=5)  # Timeout de sécurité
                            log.debug(f"✅ {name} préchauffé")
                        except Exception as e:
                            log.warning(f"⚠️ Erreur préchauffage {name}: {e}")
                
                # Phase 2 : Composants dépendants (après Phase 1)
                try:
                    self._prewarm_mcp_tools()
                except Exception as e:
                    log.debug(f"Erreur préchauffage MCP: {e}")
                
                try:
                    self._prewarm_cache_manager()
                except Exception as e:
                    log.debug(f"Erreur préchauffage CacheManager: {e}")
                
                log.info("✅ Préchauffage contextuel terminé")
                
                # Démarrer la maintenance asynchrone continue
                self._start_maintenance_thread()
                
            except Exception as e:
                log.warning(f"Erreur préchauffage: {e}")
            finally:
                # Libérer le flag
                with self._cache_lock:
                    self._prewarm_in_progress = False
        
        self._prewarm_thread = threading.Thread(
            target=prewarm_task, 
            daemon=True, 
            name="ContextPrewarm"
        )
        self._prewarm_thread.start()

    def _prewarm_session(self):
        """Précharge la session principale."""
        try:
            if self.worker:
                self.worker.get_main_session()  # Lazy loading, mais précharge
        except Exception as e:
            log.debug(f"Erreur préchauffage session: {e}")

    def _prewarm_rag_db(self):
        """Préinitialise la base RAG (FAISS + SentenceTransformer).
        Approche "Fire and Forget" : si le modèle n'est pas prêt, on annule silencieusement.
        Le préchauffage RAG est une optimisation, pas une fonctionnalité critique.
        """
        try:
            from features.context import database
            from config.settings import APP_SETTINGS
            from config.paths import get_path
            
            # Vérifier si le modèle est prêt avant de préchauffer
            if not database.is_model_ready():
                # Annuler silencieusement : le préchauffage est une optimisation
                # L'utilisateur déclenchera le chargement naturel lors de sa première requête
                log.debug("ℹ️ RAG DB pas encore prête (modèle en cours de chargement), préchauffage reporté")
                return
            
            # Modèle prêt, on peut préchauffer
            db_path = APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid")
            if not os.path.isabs(db_path):
                db_path = get_path(db_path)
            database.init_db(db_path)
        except Exception as e:
            # Améliorer les logs d'erreur (capturer traceback complet)
            error_msg = str(e) if e else "Exception sans message"
            error_type = type(e).__name__
            error_traceback = traceback.format_exc()
            
            # Ne pas logger comme warning si c'est une erreur attendue
            expected_errors = [
                "meta tensor",  # Erreur PyTorch lors du chargement parallèle
                "already initialized",  # Déjà initialisé
                "already loaded",  # Déjà chargé
            ]
            
            is_expected = any(expected in error_msg.lower() for expected in expected_errors)
            
            if not is_expected and error_msg:
                log.debug(f"Erreur préchauffage RAG ({error_type}): {error_msg}")
                log.debug(f"Traceback: {error_traceback}")
            elif not error_msg:
                log.debug(f"Erreur préchauffage RAG ({error_type}): exception sans message")
                log.debug(f"Traceback: {error_traceback}")
            # Si c'est attendu, ne rien logger (c'est normal)

    def _prewarm_tree(self):
        """Préchauffe l'arborescence avec cache Merkle."""
        try:
            from features.CacheManager import GlobalCacheManager
            if GlobalCacheManager:
                GlobalCacheManager.prepare_tree_only()
        except Exception as e:
            log.debug(f"Erreur préchauffage tree: {e}")

    def _prewarm_repo_map(self):
        """Préinitialise la Repo Map."""
        try:
            from features.context.repo_map import get_cached_repo_map, is_repo_map_regenerating, wait_for_repo_map_regeneration
            from config.settings import APP_SETTINGS
            from config.paths import get_path
            
            db_path = APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid")
            if not os.path.isabs(db_path):
                db_path = get_path(db_path)
            
            # Vérifier si une régénération est en cours
            if is_repo_map_regenerating():
                log.debug("ℹ️ Repo Map en cours de régénération, attente...")
                if wait_for_repo_map_regeneration(max_wait=5.0):
                    # La régénération est terminée, récupérer depuis le cache
                    get_cached_repo_map(db_path_base=db_path, max_chars=None)
                else:
                    log.debug("ℹ️ Timeout attente régénération Repo Map, utilisation cache existant")
            else:
                # Pas de régénération en cours, récupérer normalement
                get_cached_repo_map(db_path_base=db_path, max_chars=None)
        except Exception as e:
            log.debug(f"Erreur préchauffage repo_map: {e}")

    def _prewarm_mcp_tools(self):
        """Précharge les outils MCP depuis le cache."""
        try:
            # Les outils MCP sont résolus lors de la première requête
            # Le cache sera utilisé automatiquement lors de la résolution
            from ai_core.mcp_cache import load_mcp_cache
            # Préchargement optionnel si nécessaire
        except Exception as e:
            log.debug(f"Erreur préchauffage MCP: {e}")

    def _prewarm_cache_manager(self):
        """Prépare tous les composants du CacheManager."""
        try:
            from features.CacheManager import GlobalCacheManager
            if GlobalCacheManager:
                GlobalCacheManager.prepare_content()
        except Exception as e:
            log.debug(f"Erreur préchauffage CacheManager: {e}")

    def _start_maintenance_thread(self):
        """Démarre le thread de maintenance asynchrone continue."""
        if self._maintenance_thread and self._maintenance_thread.is_alive():
            return  # Déjà démarré
        
        def maintenance_task():
            import time
            # Démarrer avec un délai plus long pour éviter la surcharge au démarrage
            time.sleep(300)  # Attendre 5 minutes avant la première vérification
            
            while True:
                try:
                    time.sleep(600)  # Vérification toutes les 10 minutes au lieu de 30 secondes
                    self._maintain_caches()
                except Exception as e:
                    log.debug(f"Erreur maintenance: {e}")
                    time.sleep(1200)  # Attendre 20 minutes en cas d'erreur
        
        self._maintenance_thread = threading.Thread(
            target=maintenance_task,
            daemon=True,
            name="CacheMaintenance"
        )
        self._maintenance_thread.start()
        log.debug("🔄 Thread de maintenance démarré (vérification toutes les 10 min)")

    def _maintain_caches(self):
        """Maintient les caches à jour de manière asynchrone."""
        try:
            from features.CacheManager import GlobalCacheManager
            
            # 1. Vérifier et invalider le cache de l'arborescence si nécessaire
            if GlobalCacheManager:
                with GlobalCacheManager._tree_lock:
                    current_hash = GlobalCacheManager._get_project_hash()
                    if GlobalCacheManager._tree_hash != current_hash:
                        log.debug("🔄 Invalidation cache arborescence (projet modifié)")
                        GlobalCacheManager._tree_cache = None
                        GlobalCacheManager._tree_hash = None
                        # Régénérer en arrière-plan
                        threading.Thread(
                            target=GlobalCacheManager.prepare_tree_only,
                            daemon=True,
                            name="TreeRegen"
                        ).start()
            
            # 2. Vérifier le cache Repo Map (déjà géré par get_cached_repo_map)
            # La régénération asynchrone est déjà implémentée
            
            # 3. Vérifier la base RAG (pas de maintenance nécessaire, déjà en mémoire)
            
        except Exception as e:
            log.debug(f"Erreur maintenance caches: {e}")

    def _save_prompt_history(self):
        """Sauvegarde les 50 dernières commandes."""
        try:
            hist_path = get_path("prompt_history.json")
            # On garde un buffer raisonnable
            to_save = self.prompt_history[:50]
            with open(hist_path, 'w', encoding='utf-8') as f:
                json.dump(to_save, f, ensure_ascii=False, indent=2)
        except Exception: pass
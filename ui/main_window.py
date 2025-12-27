import time
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
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
from ui.widgets import TextEditorWithLineNumbers, COLORS, ApiKeyStatusMenu, ReasoningModeSwitch
from ui.windows import (
    SettingsWindow, DbManagerWindow, 
    WaitingListWindow, BackupManagerWindow,
    ApiKeyManager
)
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
        self.windows = {} 
        self.prompt_history = []
        self.history_index = -1
        self.sidebar_visible = True
        
        # Init UI
        self._setup_layout()
        self._setup_bindings()
        self._setup_log_menu()
        
        # Worker
        self._init_worker()
        
        # Polling
        self.check_result_queue()

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
        
        self.tab_view.add("Chat Principal")
        self.chat1_txt = ctk.CTkTextbox(self.tab_view.tab("Chat Principal"), wrap="word", font=("Consolas", 12))
        self.chat1_txt.pack(fill="both", expand=True)
        self.chat1_txt.configure(state="disabled")
        
        self.tab_view.add("Chat Secondaire")
        self.chat2_txt = ctk.CTkTextbox(self.tab_view.tab("Chat Secondaire"), wrap="word", font=("Consolas", 12))
        self.chat2_txt.pack(fill="both", expand=True)
        self.chat2_txt.configure(state="disabled")
        
        self._configure_chat_tags(self.chat1_txt)
        self._configure_chat_tags(self.chat2_txt)

        # C. Input Zone (Bas)
        self.input_frame = ctk.CTkFrame(self.main_area, height=100)
        self.input_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        
        self.btn_mic = ctk.CTkButton(self.input_frame, text="🎤", width=40, height=40, 
                                     command=lambda: task_queue.put({'type': 'start_asr'}))
        self.btn_mic.pack(side="left", padx=5, pady=5)
        
        self.btn_speak = ctk.CTkButton(self.input_frame, text="🔊", width=40, height=40, 
                                       command=lambda: task_queue.put({'type': 'start_tts', 'text': self._get_last_response()}))
        self.btn_speak.pack(side="left", padx=5, pady=5)

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
                messagebox.showinfo("Info", "Impossible de sauvegarder le chat comme fichier code.")
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
                messagebox.showwarning("Erreur", "Impossible de trouver l'éditeur.")

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur sauvegarde : {e}")

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
        widget = self.chat2_txt if target == "Chat Secondaire" else self.chat1_txt
        self._log_chat(widget, f"Vous: {msg}", "user")
        
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
        
        editor = TextEditorWithLineNumbers(self.tab_view.tab(filename))
        editor.pack(fill="both", expand=True)
        editor.text_area.insert("1.0", content)
        syntax_highlighter.apply_highlighting_to_editor(editor, content, syntax_highlighter.get_lexer(filename, content))
        
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

    def _log_chat(self, widget, text, tag):
        widget.configure(state="normal")
        widget.insert("end", text + "\n\n", tag)
        widget.configure(state="disabled")
        widget.see("end")

    def _get_last_response(self):
        return self.chat1_txt.get("end-5l", "end")

    def _clear_chat(self):
        self.chat1_txt.configure(state="normal")
        self.chat1_txt.delete("1.0", "end")
        self.chat1_txt.configure(state="disabled")
        task_queue.put({'type': 'reset_memory'})
        self.status_var.set("🧹 Chat et Mémoire effacés.")

    def check_result_queue(self):
        try:
            while not result_queue.empty():
                res = result_queue.get_nowait()
                msg_type = res.get('type')

                if msg_type == 'chat_response':
                    self._stop_animation()
                    self._log_chat(self.chat1_txt, f"🤖 {res['text']}", "gemini")
                
                elif msg_type == 'ui_stream_chunk':
                    # [CORRECTION] Insertion directe sans saut de ligne forcé pour le streaming fluide
                    self.chat1_txt.configure(state="normal")
                    self.chat1_txt.insert("end", res['text'], "gemini")
                    self.chat1_txt.configure(state="disabled")
                    self.chat1_txt.see("end")
                
                elif msg_type == 'ui_stream_end':
                    self._stop_animation() 
                    # [CORRECTION] On ajoute juste le saut de ligne final (via l'argument vide, _log_chat mettra \n\n)
                    self._log_chat(self.chat1_txt, "", "gemini")
                    
                elif msg_type == 'ui_update':
                    if res.get('widget') == 'status': self.status_var.set(res['text'])
                    elif res.get('widget') == 'message': self._log_chat(self.chat1_txt, f"ℹ️ {res['text']}", "info")
                
                elif msg_type == 'error':
                    self._stop_animation()
                    self._log_chat(self.chat1_txt, f"❌ {res['text']}", "error")
                
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
        self._log_chat(self.chat1_txt, f"Action: {choice} sur {os.path.basename(self.current_file_path)}", "info")

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

    def _save_prompt_history(self):
        """Sauvegarde les 50 dernières commandes."""
        try:
            hist_path = get_path("prompt_history.json")
            # On garde un buffer raisonnable
            to_save = self.prompt_history[:50]
            with open(hist_path, 'w', encoding='utf-8') as f:
                json.dump(to_save, f, ensure_ascii=False, indent=2)
        except Exception: pass
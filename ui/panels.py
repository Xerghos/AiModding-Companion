import customtkinter as ctk
import tkinter as tk
import os
import ui.syntax as syntax_highlighter
from ui.widgets import TextEditorWithLineNumbers, COLORS, ApiKeyStatusMenu, ReasoningModeSwitch, add_tooltip
from ui.icons import IconProvider
from features.Decorators import trace_action

QUICK_PROMPTS = {
    "Audit Qualité": "Analyse la qualité et la sécurité de ce code : ",
    "Générer Tests": "Génère des tests unitaires pour ce fichier : ",
    "Refactoring": "Propose un plan de refactoring pour améliorer ce code : ",
    "Documentation": "Génère la documentation technique de ce fichier : ",
    "Expliquer": "Explique-moi comment fonctionne ce code : ",
    "Roadmap": "Mets à jour la roadmap du projet en fonction de l'historique récent.",
    "Synthèse": "Fais une synthèse de l'activité récente sur le projet.",
    "Backups": "Liste les sauvegardes disponibles.",
}

class MainPanel(ctk.CTkFrame):
    """
    Contient toute la zone droite : Toolbar, Onglets (Chat/Code), Input.
    """
    def __init__(self, master, task_queue, callbacks, prompt_history_ref, **kwargs):
        super().__init__(master, corner_radius=0, fg_color="transparent", **kwargs)
        self.task_queue = task_queue
        self.cb = callbacks
        self.prompt_history = prompt_history_ref # Référence partagée
        self.history_index = -1
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._setup_toolbar()
        self._setup_tabs()
        self._setup_input_area()
        
        self.status_var = tk.StringVar(value="Démarrage...")
        self.status_bar = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w", font=("Arial", 10), text_color="gray")
        self.status_bar.grid(row=3, column=0, sticky="ew")

    @trace_action(source="panels")
    def _setup_toolbar(self):
        self.toolbar = ctk.CTkFrame(self, height=40)
        self.toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        btn_settings = ctk.CTkButton(self.toolbar, text="⚙️ Paramètres", width=100, command=self.cb.get('open_settings'))
        btn_settings.pack(side="left", padx=2)
        add_tooltip(btn_settings, "Ouvrir les paramètres de l'application")
        
        self.btn_api = ctk.CTkButton(self.toolbar, text="🔑 Clés API", width=90, command=self.cb.get('toggle_api'))
        self.btn_api.pack(side="left", padx=2)
        add_tooltip(self.btn_api, "Gérer les clés API")
        
        try:
            self.api_status_menu = ApiKeyStatusMenu(self.winfo_toplevel(), task_queue=self.task_queue)
        except: self.api_status_menu = None

        btn_backups = ctk.CTkButton(self.toolbar, text="🕒 Backups", width=90, fg_color=COLORS["BG_SECONDARY"], command=self.cb.get('open_backups'))
        btn_backups.pack(side="left", padx=2)
        add_tooltip(btn_backups, "Gérer les sauvegardes")
        
        btn_rag = ctk.CTkButton(self.toolbar, text="🧠 RAG", width=70, command=self.cb.get('open_rag'))
        btn_rag.pack(side="left", padx=2)
        add_tooltip(btn_rag, "Gérer la base de connaissances (RAG)")
        
        btn_queue = ctk.CTkButton(self.toolbar, text="⏳ Queue", width=50, command=self.cb.get('open_queue'))
        btn_queue.pack(side="left", padx=2)
        add_tooltip(btn_queue, "Voir la file d'attente des tâches")
        
        btn_close = ctk.CTkButton(self.toolbar, text="❌ Fermer", width=60, fg_color=COLORS["ERROR"], command=self._close_current_tab)
        btn_close.pack(side="left", padx=10)
        add_tooltip(btn_close, "Fermer l'onglet actuel")

        self.cmd_menu = ctk.CTkOptionMenu(self.toolbar, values=list(QUICK_PROMPTS.keys()), command=self._on_quick_prompt, width=180)
        self.cmd_menu.set("✨ Prompts Rapides")
        self.cmd_menu.pack(side="right", padx=5)
        add_tooltip(self.cmd_menu, "Commandes rapides disponibles")

    @trace_action(source="panels")
    def _setup_tabs(self):
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=1, column=0, sticky="nsew")
        
        self.tab_view.add("Chat Principal")
        self.chat1_txt = ctk.CTkTextbox(self.tab_view.tab("Chat Principal"), state="disabled", wrap="word", font=("Consolas", 11))
        self.chat1_txt.pack(fill="both", expand=True)
        self._configure_chat_tags(self.chat1_txt)

        self.tab_view.add("Chat Secondaire")
        self.chat2_txt = ctk.CTkTextbox(self.tab_view.tab("Chat Secondaire"), state="disabled", wrap="word", font=("Consolas", 11))
        self.chat2_txt.pack(fill="both", expand=True)
        self._configure_chat_tags(self.chat2_txt)

    @trace_action(source="panels")
    def _setup_input_area(self):
        self.input_frame = ctk.CTkFrame(self, height=80)
        self.input_frame.grid(row=2, column=0, sticky="ew", pady=(5,0))
        
        try:
            self.reasoning_switch = ReasoningModeSwitch(self.input_frame)
            self.reasoning_switch.pack(side="right", padx=5, fill="y")
        except: pass

        self.btn_send = ctk.CTkButton(self.input_frame, text="Envoyer", width=80, command=self._on_send_press)
        self.btn_send.pack(side="right", padx=5, pady=5)
        add_tooltip(self.btn_send, "Envoyer le message (Ctrl+Enter)")
        
        btn_mic = ctk.CTkButton(self.input_frame, text="🎤", width=40, command=lambda: self.task_queue.put({'type': 'start_asr'}))
        btn_mic.pack(side="left", padx=5)
        add_tooltip(btn_mic, "Reconnaissance vocale")
        
        btn_speak = ctk.CTkButton(self.input_frame, text="🔊", width=40, command=lambda: self.task_queue.put({'type': 'start_tts'}))
        btn_speak.pack(side="left", padx=2)
        add_tooltip(btn_speak, "Synthèse vocale")
        
        self.input_txt = ctk.CTkTextbox(self.input_frame, height=60, font=("Arial", 11))
        self.input_txt.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        add_tooltip(self.input_txt, "Tapez votre message ici (Ctrl+Enter pour envoyer)")
        
        # BINDINGS HISTORIQUE (RESTAURÉS)
        self.input_txt.bind("<Return>", self._on_enter)
        self.input_txt.bind("<Shift-Return>", lambda e: None)
        self.input_txt.bind("<Control-l>", lambda e: self.input_txt.focus_force())
        self.input_txt.bind("<Up>", self._history_up)
        self.input_txt.bind("<Down>", self._history_down)

    @trace_action(source="panels")
    def _on_quick_prompt(self, choice):
        if choice in QUICK_PROMPTS:
            self.input_txt.delete("1.0", "end")
            self.input_txt.insert("end", QUICK_PROMPTS[choice])
            self.input_txt.focus()
        self.cmd_menu.set("✨ Prompts Rapides")

    @trace_action(source="panels")
    def _on_send_press(self):
        msg = self.input_txt.get("1.0", "end").strip()
        if msg and self.cb.get('send_message'):
            self.cb['send_message'](msg)
            self.input_txt.delete("1.0", "end")
            self.history_index = -1 # Reset historique position

    @trace_action(source="panels")
    def _on_enter(self, event):
        self._on_send_press()
        return "break"

    @trace_action(source="panels")
    def _history_up(self, event):
        if not self.prompt_history: return "break"
        if self.history_index < len(self.prompt_history) - 1:
            self.history_index += 1
            entry = self.prompt_history[self.history_index]
            text = entry.get("prompt", "")
            self.input_txt.delete("1.0", "end")
            self.input_txt.insert("end", text)
        return "break"

    @trace_action(source="panels")
    def _history_down(self, event):
        if self.history_index > 0:
            self.history_index -= 1
            entry = self.prompt_history[self.history_index]
            text = entry.get("prompt", "")
            self.input_txt.delete("1.0", "end")
            self.input_txt.insert("end", text)
        elif self.history_index == 0:
            self.history_index = -1
            self.input_txt.delete("1.0", "end")
        return "break"

    @trace_action(source="panels")
    def _close_current_tab(self):
        try:
            current = self.tab_view.get()
            if current not in ["Chat Principal", "Chat Secondaire"]:
                self.tab_view.delete(current)
        except: pass

    @trace_action(source="panels")
    def open_editor_tab(self, filepath, content=None):
        filename = os.path.basename(filepath)
        if filename in self.tab_view._tab_dict:
            self.tab_view.set(filename)
            return
        
        self.tab_view.add(filename)
        if content is None:
            try:
                with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
            except Exception as e: content = f"Erreur: {e}"

        editor = TextEditorWithLineNumbers(self.tab_view.tab(filename))
        editor.pack(fill="both", expand=True)
        lexer = syntax_highlighter.get_lexer(filename=filename, code_content=content)
        syntax_highlighter.apply_highlighting_to_editor(editor, content, lexer)
        self.tab_view.set(filename)

    @trace_action(source="panels")
    def log_chat(self, text, tag, target="Chat Principal"):
        widget = self.chat2_txt if target == "Chat Secondaire" else self.chat1_txt
        widget.configure(state="normal")
        widget.insert("end", text + "\n\n", tag)
        widget.configure(state="disabled")
        widget.see("end")

    @trace_action(source="panels")
    def _configure_chat_tags(self, widget):
        widget.tag_config("user", foreground=COLORS["ACCENT"])
        widget.tag_config("gemini", foreground=COLORS["FG_PRIMARY"])
        widget.tag_config("info", foreground=COLORS["INFO"])
        widget.tag_config("error", foreground=COLORS["ERROR"])
        syntax_highlighter.configure_tags(widget)
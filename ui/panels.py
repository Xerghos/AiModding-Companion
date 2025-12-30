import customtkinter as ctk
import tkinter as tk
import os
import logging
import ui.syntax as syntax_highlighter
from ui.widgets import TextEditorWithLineNumbers, MarkdownViewer, _is_markdown_content, _is_thinking_content, _parse_mixed_content, _group_thinking_and_response, ThinkingWidget, ResponseContainer, CollapsibleMarkdownWidget, COLORS, ApiKeyStatusMenu, ReasoningModeSwitch, add_tooltip
from ui.windows.markdown_viewer import MarkdownViewerWindow
from ui.icons import IconProvider
from features.Decorators import trace_action

log = logging.getLogger("ui.panels")

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
        
        # Chat Principal - Approche hybride avec affichage mixte
        self.tab_view.add("Chat Principal")
        chat1_container = ctk.CTkFrame(self.tab_view.tab("Chat Principal"), fg_color="transparent")
        chat1_container.pack(fill="both", expand=True)
        
        # ScrollableFrame principal qui contiendra toutes les textboxes et widgets
        self.chat1_scroll = ctk.CTkScrollableFrame(chat1_container, fg_color="transparent")
        self.chat1_scroll.pack(fill="both", expand=True)
        
        # Container pour widgets Markdown (sera ajouté dynamiquement)
        self.chat1_widgets_container = self.chat1_scroll

        # Chat Secondaire - Approche hybride avec affichage mixte
        self.tab_view.add("Chat Secondaire")
        chat2_container = ctk.CTkFrame(self.tab_view.tab("Chat Secondaire"), fg_color="transparent")
        chat2_container.pack(fill="both", expand=True)
        
        # ScrollableFrame principal qui contiendra toutes les textboxes et widgets
        self.chat2_scroll = ctk.CTkScrollableFrame(chat2_container, fg_color="transparent")
        self.chat2_scroll.pack(fill="both", expand=True)
        
        # Container pour widgets Markdown (sera ajouté dynamiquement)
        self.chat2_widgets_container = self.chat2_scroll

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

    def _create_message_textbox(self, container, tag="gemini", content=""):
        """Crée une nouvelle textbox pour un message avec hauteur adaptative."""
        # Calculer la hauteur approximative basée sur le contenu
        if content:
            # Compter les lignes réelles (avec wrap approximatif)
            lines = content.count('\n') + 1
            # Estimer les lignes avec wrap (environ 80 caractères par ligne)
            avg_chars_per_line = 80
            wrapped_lines = sum(len(line) // avg_chars_per_line + 1 for line in content.split('\n'))
            total_lines = max(lines, wrapped_lines)
            # Environ 20px par ligne (hauteur de ligne + espacement), minimum 50px, maximum 500px
            estimated_height = min(max(total_lines * 20, 50), 500)
        else:
            estimated_height = 50
        
        textbox = ctk.CTkTextbox(container, wrap="word", font=("Consolas", 11), height=estimated_height)
        textbox.pack(fill="x", padx=5, pady=0)
        textbox.configure(state="disabled")
        self._configure_chat_tags(textbox)
        return textbox

    @trace_action(source="panels")
    def log_chat(self, text, tag, target="Chat Principal"):
        # Nettoyer les séquences \n\n échappées
        text = text.replace('\\n\\n', '\n\n').replace('\\n', '\n')
        
        # Déterminer quel container utiliser
        if target == "Chat Secondaire":
            widgets_container = self.chat2_widgets_container
            scroll_container = self.chat2_scroll
        else:
            widgets_container = self.chat1_widgets_container
            scroll_container = self.chat1_scroll
        
        # Séparer thinking et réponse finale
        thinking_content, response_parts = _group_thinking_and_response(text)
        
        # Afficher le thinking (un seul widget regroupé, collapsed par défaut)
        if thinking_content:
            thinking_widget = ThinkingWidget(
                widgets_container,
                content=thinking_content
            )
            thinking_widget.pack(fill="x", padx=5, pady=0)
        
        # Créer le ResponseContainer pour la réponse finale
        if response_parts:
            response_container = ResponseContainer(widgets_container)
            response_container.pack(fill="both", expand=True, padx=5, pady=0)
            
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
            textbox = self._create_message_textbox(widgets_container, tag, text)
            textbox.configure(state="normal")
            textbox.insert("1.0", text + "\n\n", tag)
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

    @trace_action(source="panels")
    def _configure_chat_tags(self, widget):
        widget.tag_config("user", foreground=COLORS["ACCENT"])
        widget.tag_config("gemini", foreground=COLORS["FG_PRIMARY"])
        widget.tag_config("info", foreground=COLORS["INFO"])
        widget.tag_config("error", foreground=COLORS["ERROR"])
        syntax_highlighter.configure_tags(widget)
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import logging
import time
import re # Nécessaire pour la recherche/remplacement
import os

# --- MONKEYPATCH CTkScrollableFrame (Fix AttributeError: 'str' object has no attribute 'master') ---
from customtkinter.windows.widgets.ctk_scrollable_frame import CTkScrollableFrame

def _check_if_master_is_canvas_patched(self, widget):
    try:
        if widget == self._parent_canvas:
            return True
        
        # Si le widget est une chaîne (chemin Tkinter), essayer de récupérer l'objet
        if isinstance(widget, str):
            try:
                # On utilise nametowidget sur le canvas parent ou root
                widget = self._parent_canvas.nametowidget(widget)
            except Exception:
                return False

        if hasattr(widget, 'master') and widget.master is not None:
            return self.check_if_master_is_canvas(widget.master)
        else:
            return False
    except Exception:
        return False

# Appliquer le patch
CTkScrollableFrame.check_if_master_is_canvas = _check_if_master_is_canvas_patched
# ------------------------------------------------------------------------------------------------

# Import pour récupérer la taille de police depuis les settings
try:
    from config.settings import APP_SETTINGS
except ImportError:
    APP_SETTINGS = {}

log = logging.getLogger("ui.widgets")

# Import tkinterweb pour affichage HTML (remplace tkhtmlview)
try:
    from tkinterweb import HtmlFrame
    TKINTERWEB_AVAILABLE = True
except ImportError:
    TKINTERWEB_AVAILABLE = False
    HtmlFrame = None
    log.warning("tkinterweb non disponible - l'affichage Markdown/HTML sera limité")

# Import du convertisseur Markdown
try:
    from ui.markdown_converter import markdown_to_html
    MARKDOWN_CONVERTER_AVAILABLE = True
except ImportError:
    MARKDOWN_CONVERTER_AVAILABLE = False
    log.warning("Module markdown_converter non disponible")

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


def _is_thinking_content(text):
    """
    Détecte si un texte est un message de "thinking" (pensées internes de l'IA).
    
    Args:
        text: Texte à analyser
    
    Returns:
        True si c'est un message de thinking, False sinon
    """
    if not text or len(text.strip()) < 10:
        return False
    
    # Patterns typiques des messages de thinking
    thinking_patterns = [
        r'^\*\*Assessing\s+',      # **Assessing the...
        r'^\*\*Processing\s+',      # **Processing the...
        r'^\*\*Crafting\s+',        # **Crafting the...
        r'^\*\*Constructing\s+',    # **Constructing the...
        r'^\*\*Developing\s+',      # **Developing the...
        r"^I'm analyzing",          # I'm analyzing...
        r"^I've taken in",          # I've taken in...
        r"^I've crafted",           # I've crafted...
        r"^I registered",           # I registered...
        r"^My focus is now",        # My focus is now...
        r"^I'm considering",        # I'm considering...
        r"^Now, I'm",               # Now, I'm...
        r"^I'm focusing",           # I'm focusing...
        r"^I'm ready to",           # I'm ready to...
        r"^Protocol V4",            # Protocol V4...
        r"^My structure is",        # My structure is...
        r"^Ma structure est",        # Ma structure est... (français)
        r"^Je suis",                # Je suis... (français)
        r"^J'ai",                   # J'ai... (français)
    ]
    
    # Vérifier si le texte commence par un pattern de thinking
    for pattern in thinking_patterns:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            return True
    
    # Vérifier aussi si le texte contient plusieurs phrases de thinking
    thinking_phrases = [
        "I'm analyzing",
        "I've taken in",
        "I registered",
        "My focus is",
        "I'm considering",
        "I'm focusing",
        "I'm diving",
        "I'm examining",
        "I'm investigating",
        "I'm breaking down",
        "I'm currently focused",
        "I'm now",
        "Protocol V4",
        "tools are ready",
        "file system",
        "RAG are primed",
        "Analyzing",  # Avec majuscule
        "Investigating",
    ]
    
    phrase_count = sum(1 for phrase in thinking_phrases if phrase.lower() in text.lower())
    if phrase_count >= 1:  # Réduire à 1 pour détecter plus facilement
        return True
    
    # Détecter aussi les patterns français
    french_thinking_patterns = [
        r"^Je suis.*en train",
        r"^J'analyse",
        r"^Je me concentre",
        r"^Je vais",
    ]
    for pattern in french_thinking_patterns:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            return True
    
    return False


def _is_markdown_content(text):
    """
    Détecte si un texte contient du Markdown.
    Exclut les messages de thinking pour éviter les faux positifs.
    
    Args:
        text: Texte à analyser
    
    Returns:
        True si Markdown détecté, False sinon
    """
    if not text or len(text.strip()) < 10:
        return False
    
    # Ne pas considérer comme Markdown si c'est UNIQUEMENT du thinking
    # Mais si le texte contient à la fois du thinking ET du contenu normal, c'est OK
    # On vérifie seulement si le texte ENTIER est du thinking (sans éléments Markdown)
    is_only_thinking = _is_thinking_content(text)
    has_markdown_elements = any(
        re.search(pattern, text, re.MULTILINE) 
        for pattern in [r'\*\*[^*]+\*\*', r'`[^`]+`', r'^#{1,6}\s', r'^\s*[-*+]\s', r'^\s*\d+\.\s']
    )
    
    # Si c'est uniquement du thinking sans éléments Markdown, ne pas considérer comme Markdown
    if is_only_thinking and not has_markdown_elements:
        return False
    
    markdown_patterns = [
        r'\*\*[^*]+\*\*',      # Bold **text**
        r'\*[^*]+\*',          # Italic *text*
        r'^#{1,6}\s',          # Headings # Title
        r'```[\s\S]*?```',     # Code blocks ```
        r'`[^`]+`',            # Inline code `code`
        r'^\s*[-*+]\s',        # Lists - item
        r'^\s*\d+\.\s',        # Numbered lists 1. item
        r'\[.*?\]\(.*?\)',     # Links [text](url)
        r'^\s*>\s',            # Blockquotes > text
        r'^\s*\|.*\|',         # Tables | col1 | col2 |
    ]
    
    matches = sum(1 for pattern in markdown_patterns if re.search(pattern, text, re.MULTILINE))
    return matches >= 2  # Au moins 2 patterns différents


def _parse_mixed_content(text):
    """
    Parse un texte mixte et sépare les parties Thinking, Markdown et texte simple.
    
    Args:
        text: Texte à parser
    
    Returns:
        Liste de tuples (type, content) où type est 'thinking', 'text' ou 'markdown'
    """
    if not text:
        return []
    
    # D'abord, détecter si le texte entier est du thinking
    if _is_thinking_content(text):
        return [('thinking', text)]
    
    parts = []
    
    # Séparer le texte en blocs potentiels (séparés par des sauts de ligne multiples)
    blocks = re.split(r'\n\n+', text)
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        # Détecter le type de bloc
        if _is_thinking_content(block):
            parts.append(('thinking', block))
        elif _is_markdown_content(block):
            parts.append(('markdown', block))
        else:
            # Vérifier s'il y a des blocs de code dans le texte
            code_block_pattern = r'```[\s\S]*?```'
            code_blocks = list(re.finditer(code_block_pattern, block))
            
            if code_blocks:
                # Séparer autour des blocs de code
                last_pos = 0
                for match in code_blocks:
                    # Texte avant le bloc
                    before_text = block[last_pos:match.start()].strip()
                    if before_text:
                        if _is_thinking_content(before_text):
                            parts.append(('thinking', before_text))
                        elif _is_markdown_content(before_text):
                            parts.append(('markdown', before_text))
                        else:
                            parts.append(('text', before_text))
                    
                    # Le bloc de code lui-même
                    code_block = match.group(0)
                    parts.append(('markdown', code_block))
                    
                    last_pos = match.end()
                
                # Texte après le dernier bloc
                after_text = block[last_pos:].strip()
                if after_text:
                    if _is_thinking_content(after_text):
                        parts.append(('thinking', after_text))
                    elif _is_markdown_content(after_text):
                        parts.append(('markdown', after_text))
                    else:
                        parts.append(('text', after_text))
            else:
                # Pas de blocs de code, c'est du texte simple
                parts.append(('text', block))
    
    # Si aucune partie n'a été créée, retourner le texte entier comme texte
    if not parts:
        return [('text', text)]
    
    return parts


def _group_thinking_and_response(text):
    """
    Sépare le texte en deux groupes : thinking (tous regroupés) et réponse finale (texte + markdown).
    
    Args:
        text: Texte complet à analyser
    
    Returns:
        Tuple (thinking_content, response_parts) où:
        - thinking_content: str ou None (tous les thinking regroupés)
        - response_parts: Liste de tuples (type, content) pour la réponse finale
    """
    if not text:
        return None, []
    
    # Parser le contenu mixte
    parts = _parse_mixed_content(text)
    
    # Séparer thinking et réponse
    thinking_parts = [p[1] for p in parts if p[0] == 'thinking']
    response_parts = [p for p in parts if p[0] != 'thinking']
    
    # Regrouper tous les thinking en un seul bloc
    thinking_content = None
    if thinking_parts:
        # Joindre tous les thinking avec un séparateur
        thinking_content = "\n\n---\n\n".join(thinking_parts)
    
    return thinking_content, response_parts


class MarkdownViewer(ctk.CTkFrame):
    """
    Widget pour afficher du Markdown/HTML avec tkinterweb.
    """
    def __init__(self, master, content=None, is_markdown=True, **kwargs):
        super().__init__(master, **kwargs)
        self.pack_propagate(False)
        self.is_markdown = is_markdown
        
        if not TKINTERWEB_AVAILABLE:
            # Fallback vers un label d'erreur
            error_label = ctk.CTkLabel(
                self,
                text="tkinterweb n'est pas disponible.\nVeuillez installer: pip install tkinterweb",
                text_color=COLORS["ERROR"],
                font=("Arial", 12)
            )
            error_label.pack(fill="both", expand=True, padx=20, pady=20)
            return
        
        # Créer HtmlFrame directement (gère le scroll automatiquement)
        # HtmlFrame nécessite un Frame tkinter natif, pas un CTkFrame
        self.html_frame_container = tk.Frame(
            self,
            bg=COLORS.get("BG_MAIN", "#1E1E1E")
        )
        self.html_frame_container.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Créer HtmlFrame dans le container
        self.html_frame = HtmlFrame(
            self.html_frame_container,
            messages_enabled=False,  # Désactiver les messages de console
            vertical_scrollbar=False,    # Désactiver la scrollbar verticale
            horizontal_scrollbar=False    # Désactiver la scrollbar horizontale
        )
        self.html_frame.pack(fill="both", expand=True)

        # Propager les événements de scroll au parent de manière plus robuste
        # On utilise bind_all car les widgets internes de HtmlFrame peuvent capturer le focus/events
        # Mais on filtrera dans le handler pour ne réagir que si l'événement vient de ce widget
        self.html_frame.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.html_frame.bind_all("<Button-4>", self._on_mousewheel, add="+")
        self.html_frame.bind_all("<Button-5>", self._on_mousewheel, add="+")
        
        # Stocker le contenu pour ajustement de hauteur
        self.content = content if content else ""
        
        # Définir le contenu si fourni
        if content:
            self.set_content(content, is_markdown)

    def _on_mousewheel(self, event):
        """
        Gère le scroll de la molette pour propager au parent si nécessaire.
        """
        try:
            # Vérifier si l'événement vient de notre HtmlFrame ou de ses enfants
            if not str(event.widget).startswith(str(self.html_frame)):
                return

            # Trouver le CTkScrollableFrame parent (chat1_scroll)
            parent = self.master
            while parent and not isinstance(parent, CTkScrollableFrame):
                parent = parent.master
                if not parent:
                    break
            
            if parent and isinstance(parent, CTkScrollableFrame):
                # Récupérer les paramètres de scroll
                system_settings = APP_SETTINGS.get("system_settings", {})
                base_speed = system_settings.get("scroll_speed", 4)
                modifier_key = system_settings.get("scroll_modifier_key", "Alt_L")
                modifier_mult = system_settings.get("scroll_modifier_multiplier", 4)
                
                # Vérifier le modificateur
                is_mod_active = False
                state = getattr(event, "state", 0)
                
                # Mapping basique des modificateurs pour Windows/Linux
                # Alt: 131072 (Windows), 8 ou 24 (Linux Mod1)
                # Control: 4
                # Shift: 1
                
                if "Alt" in modifier_key:
                    is_mod_active = (state & 131072) or (state & 8)
                elif "Control" in modifier_key or "Ctrl" in modifier_key:
                    is_mod_active = (state & 4)
                elif "Shift" in modifier_key:
                    is_mod_active = (state & 1)
                
                # Calculer la vitesse finale
                scroll_amount = base_speed
                if is_mod_active:
                    scroll_amount *= modifier_mult
                
                # Appliquer le scroll (négatif = haut, positif = bas pour yview_scroll)
                # Mais delta est positif pour haut (120), négatif pour bas (-120) sur Windows
                # Button-4 = Haut, Button-5 = Bas sur Linux
                
                steps = int(scroll_amount)
                
                if event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
                    # Scroll bas
                    parent._parent_canvas.yview_scroll(steps, "units")
                elif event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
                    # Scroll haut
                    parent._parent_canvas.yview_scroll(-steps, "units")
                    
        except Exception:
            pass
    
    def set_content(self, content, is_markdown=None):
        """
        Définit le contenu à afficher.
        
        Args:
            content: Texte Markdown ou HTML
            is_markdown: Si True, convertir Markdown en HTML. Si None, utilise self.is_markdown
        """
        if not TKINTERWEB_AVAILABLE:
            return
        
        if is_markdown is None:
            is_markdown = self.is_markdown
        
        try:
            if is_markdown and MARKDOWN_CONVERTER_AVAILABLE:
                # Convertir Markdown en HTML
                html_content = markdown_to_html(content, theme="dark")
                # Injecter le CSS pour masquer la scrollbar dans le HTML généré
                scrollbar_css = """
        /* Masquer TOUTES les scrollbars de manière plus agressive */
        ::-webkit-scrollbar {
            width: 0px !important;
            height: 0px !important;
            display: none !important;
        }
        ::-webkit-scrollbar-track {
            display: none !important;
        }
        ::-webkit-scrollbar-thumb {
            display: none !important;
        }
        ::-webkit-scrollbar-corner {
            display: none !important;
        }
        /* Pour Firefox, IE, Edge */
        * {
            scrollbar-width: none !important;
            -ms-overflow-style: none !important;
        }
        /* Permettre le scroll avec la souris mais sans scrollbar visible */
        html, body {
            overflow: auto !important;
            overflow-y: auto !important;
            -ms-overflow-style: none !important;
            scrollbar-width: none !important;
        }
        html::-webkit-scrollbar, body::-webkit-scrollbar {
            display: none !important;
        }"""
                if '<style>' in html_content:
                    # Injecter le CSS dans le style existant
                    html_content = html_content.replace('</style>', scrollbar_css + '\n    </style>')
                elif '<head>' in html_content:
                    # Ajouter un style dans le head
                    scrollbar_style = f"""
    <style>{scrollbar_css}
    </style>"""
                    html_content = html_content.replace('</head>', scrollbar_style + '\n</head>')
            else:
                # Utiliser directement comme HTML
                html_content = content
            
            # tkinterweb HtmlFrame supporte mieux les balises <style> et <body>
            # On peut utiliser le HTML complet directement
            # Si le HTML n'a pas de structure complète, on l'emballe
            if not html_content.strip().startswith('<!DOCTYPE') and not html_content.strip().startswith('<html'):
                # Si c'est juste du contenu HTML sans structure, on l'emballe
                if '<body>' not in html_content and '<style>' not in html_content:
                    # Contenu simple, on ajoute juste les styles de base
                    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            background-color: #1E1E1E;
            color: #CCCCCC;
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            padding: 20px;
            margin: 0;
        }}
        /* Masquer TOUTES les scrollbars de manière plus agressive */
        ::-webkit-scrollbar {{
            width: 0px !important;
            height: 0px !important;
            display: none !important;
        }}
        ::-webkit-scrollbar-track {{
            display: none !important;
        }}
        ::-webkit-scrollbar-thumb {{
            display: none !important;
        }}
        ::-webkit-scrollbar-corner {{
            display: none !important;
        }}
        /* Pour Firefox, IE, Edge */
        * {{
            scrollbar-width: none !important;
            -ms-overflow-style: none !important;
        }}
        /* Permettre le scroll avec la souris mais sans scrollbar visible */
        html, body {{
            overflow: auto !important;
            overflow-y: auto !important;
            -ms-overflow-style: none !important;
            scrollbar-width: none !important;
        }}
        html::-webkit-scrollbar, body::-webkit-scrollbar {{
            display: none !important;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>'''
            
            # Stocker le contenu pour ajustement de hauteur
            self.content = content
            
            # Charger le HTML dans HtmlFrame
            self.html_frame.load_html(html_content)
            
            # Ajuster la hauteur après chargement
            self.after(100, self._adjust_html_height)
            
        except Exception as e:
            log.error(f"Erreur lors de l'affichage du contenu: {e}", exc_info=True)
            error_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            background-color: #1E1E1E;
            color: #F44336;
            font-family: 'Segoe UI', Arial, sans-serif;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <p>Erreur: {str(e)}</p>
</body>
</html>'''
            try:
                self.html_frame.load_html(error_html)
            except:
                pass
    
    def _adjust_html_height(self):
        """Ajuste la hauteur du widget HTML selon le contenu (limite ~100 lignes = ~2500px max)."""
        try:
            if not hasattr(self, 'content') or not self.content:
                return
            
            # Estimer la hauteur basée sur le contenu
            # Compter les lignes dans le contenu (approximatif avec wrapping)
            avg_chars_per_line = 80
            lines = 0
            if self.content:
                for line in self.content.split('\n'):
                    # Compter au moins 1 ligne, plus le wrapping
                    lines += max(1, (len(line) // avg_chars_per_line) + 1)
            else:
                lines = 1
            
            # Limite à ~100 lignes
            max_lines = 100
            lines = min(lines, max_lines)
            
            # Environ 25px par ligne (hauteur de ligne + padding)
            estimated_height = lines * 25
            # Limite minimale pour éviter les boîtes trop petites (6 lignes visibles)
            min_height = 150
            estimated_height = max(estimated_height, min_height)
            # Limite maximale à 2500px (100 lignes)
            estimated_height = min(estimated_height, 2500)
            
            # Configurer la hauteur du widget principal (MarkdownViewer)
            # pack_propagate(False) est activé, donc on doit définir la hauteur explicitement
            self.configure(height=estimated_height)
            
            # Le container interne suivra grâce à fill="both"
            self.html_frame_container.pack_configure(fill="both", expand=True)
            
            # Mettre à jour le widget
            self.update_idletasks()
            
            log.debug(f"📏 Hauteur HTML ajustée: {estimated_height}px pour {lines} lignes")
            
            # Essayer de masquer les scrollbars après ajustement de la hauteur
            self.after(200, self._hide_html_frame_scrollbars)
            
        except Exception as e:
            log.debug(f"Erreur ajustement hauteur HTML: {e}")
    
    def _hide_html_frame_scrollbars(self):
        """Tente de masquer les scrollbars du HtmlFrame si les paramètres ne suffisent pas."""
        try:
            if hasattr(self, 'html_frame'):
                # Essayer de masquer via configuration si disponible
                if hasattr(self.html_frame, 'configure'):
                    try:
                        self.html_frame.configure(vertical_scrollbar=False)
                    except Exception:
                        pass
                    try:
                        self.html_frame.configure(horizontal_scrollbar=False)
                    except Exception:
                        pass
        except Exception as e:
            log.debug(f"Impossible de masquer les scrollbars via configuration: {e}")


class ThinkingWidget(ctk.CTkFrame):
    """
    Widget pour afficher les messages de thinking (pensées internes), style Gemini.
    Header collapsible avec contenu texte. Peut accepter un seul contenu ou une liste de contenus.
    """
    def __init__(self, master, content=None, thinking_blocks=None, **kwargs):
        super().__init__(master, **kwargs)
        self.is_expanded = False  # Par défaut collapsed
        
        # Accepter soit content (string) soit thinking_blocks (list)
        if thinking_blocks is not None:
            self.thinking_blocks = thinking_blocks if isinstance(thinking_blocks, list) else [thinking_blocks]
        elif content is not None:
            self.thinking_blocks = [content]
        else:
            self.thinking_blocks = []
        
        # Combiner tous les thinking en un seul texte
        self.content = "\n\n---\n\n".join(self.thinking_blocks) if self.thinking_blocks else ""
        
        # Frame principal avec style subtil
        self.configure(fg_color=COLORS.get("BG_SECONDARY", "#252526"), corner_radius=5)
        
        # Permettre au widget de s'adapter à son contenu
        self.pack_propagate(True)
        
        # Header collapsible (style Gemini)
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=35)
        self.header.pack(fill="x", padx=5, pady=0)
        
        # Bouton expand/collapse
        self.btn_toggle = ctk.CTkButton(
            self.header,
            text="▶",
            width=20,
            height=20,
            command=self.toggle,
            fg_color="transparent",
            hover_color=COLORS.get("BG_WIDGET", "#2D2D30"),
            corner_radius=10,
            font=("Arial", 8)
        )
        self.btn_toggle.pack(side="left", padx=5)
        
        # Label "Thinking" ou "Pensées"
        self.title_label = ctk.CTkLabel(
            self.header,
            text="💭 Pensées",
            font=("Arial", 10, "bold"),
            text_color=COLORS.get("FG_SECONDARY", "#858585")
        )
        self.title_label.pack(side="left", padx=5)
        
        # Container pour le contenu (initialement caché)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Ne pas pack initialement
        
        # Textbox scrollable pour le contenu thinking
        self.thinking_textbox = ctk.CTkTextbox(
            self.content_frame,
            wrap="word",
            font=("Consolas", 10),
            height=100,
            fg_color=COLORS.get("BG_WIDGET", "#2D2D30"),
            corner_radius=0,      # Espacement minimal
            border_spacing=0       # Texte touche les bords
        )
        # pady=1 pour un léger espacement entre les box (scaled automatiquement par CustomTkinter)
        self.thinking_textbox.pack(fill="both", expand=True, padx=0, pady=1)
        self.thinking_textbox.configure(state="disabled")
        
        # Insérer le contenu combiné
        if self.content:
            self.thinking_textbox.configure(state="normal")
            self.thinking_textbox.insert("1.0", self.content)
            self.thinking_textbox.configure(state="disabled")
            
            # Calculer la hauteur adaptative et ajuster après insertion
            self.after(10, lambda: self._adjust_thinking_textbox_height())
        
        # Bind double-clic sur le header pour toggle
        self.header.bind("<Double-Button-1>", lambda e: self.toggle())
        self.title_label.bind("<Double-Button-1>", lambda e: self.toggle())
    
    def add_thinking_block(self, content):
        """Ajoute un bloc de thinking au widget."""
        if content:
            self.thinking_blocks.append(content)
            # Recombiner le contenu
            self.content = "\n\n---\n\n".join(self.thinking_blocks)
            # Mettre à jour la textbox
            self.thinking_textbox.configure(state="normal")
            self.thinking_textbox.delete("1.0", "end")
            self.thinking_textbox.insert("1.0", self.content)
            self.thinking_textbox.configure(state="disabled")
            # Recalculer la hauteur après insertion
            self.after(10, lambda: self._adjust_thinking_textbox_height())
    
    def _adjust_thinking_textbox_height(self):
        """Ajuste la hauteur de la textbox thinking pour qu'elle corresponde exactement au contenu."""
        try:
            self.thinking_textbox.update_idletasks()
            line_count = int(self.thinking_textbox.index("end-1c").split('.')[0])
            if line_count > 0:
                estimated_height = min(line_count * 18, 400)  # Pas de minimum
                self.thinking_textbox.configure(height=estimated_height)
                self.thinking_textbox.update_idletasks()
        except Exception as e:
            log.debug(f"Erreur ajustement hauteur thinking textbox: {e}")
    
    def toggle(self):
        """Bascule entre collapsed et expanded."""
        self.is_expanded = not self.is_expanded
        
        if self.is_expanded:
            self.btn_toggle.configure(text="▼")
            self.content_frame.pack(fill="both", expand=True, padx=5, pady=0)
        else:
            self.btn_toggle.configure(text="▶")
            self.content_frame.pack_forget()


class ResponseContainer(ctk.CTkFrame):
    """
    Container simple pour regrouper toutes les textboxes et widgets md de la réponse finale.
    Transformé en CTkFrame simple (au lieu de CTkScrollableFrame) pour éviter l'espace vide de 200px.
    Le scroll est géré par le parent chat1_scroll qui est déjà un CTkScrollableFrame.
    """
    def __init__(self, master, **kwargs):
        # Configurer corner_radius=0 et border_width=0 pour réduire les paddings internes
        super().__init__(
            master, 
            fg_color="transparent", 
            corner_radius=0, 
            border_width=0,
            **kwargs
        )
        self.widgets = []  # Liste des widgets ajoutés
        
        # Activer pack_propagate pour que le Frame s'adapte exactement au contenu
        self.pack_propagate(True)
    
    def add_textbox(self, text, tag="gemini", height=None):
        """Ajoute une textbox au container. Hauteur adaptative, pas de scrollbar."""
        # Récupérer la taille de police depuis les settings
        font_size = APP_SETTINGS.get("system_settings", {}).get("font_size", 12)
        
        if height is None:
            # Calculer la hauteur adaptative basée sur le contenu
            lines = text.count('\n') + 1
            avg_chars_per_line = 80
            wrapped_lines = sum(len(line) // avg_chars_per_line + 1 for line in text.split('\n'))
            total_lines = max(lines, wrapped_lines)
            # Calculer la hauteur en fonction de la taille de police
            line_height = max(int(font_size * 1.0), 13)  # Harmonisé avec main_window.py
            height = total_lines * line_height  # Pas de padding supplémentaire ni de minimum
        
        # Créer la textbox avec la taille de police configurée et SANS scrollbars ni scroll
        textbox = ctk.CTkTextbox(
            self, 
            wrap="word", 
            font=("Consolas", font_size), 
            height=height,
            activate_scrollbars=False,  # Désactiver les scrollbars
            yscrollcommand=None,  # Désactiver le scroll vertical
            xscrollcommand=None,   # Désactiver le scroll horizontal
            corner_radius=0,       # Espacement minimal
            border_spacing=0       # Texte touche les bords
        )
        # pady=1 pour un léger espacement entre les box (scaled automatiquement par CustomTkinter)
        textbox.pack(fill="x", padx=0, pady=1)
        textbox.configure(state="disabled")
        
        textbox.configure(state="normal")
        textbox.insert("1.0", text, tag)
        textbox.configure(state="disabled")
        
        # Ajuster la hauteur après insertion pour être plus précis
        self.after(10, lambda: self._adjust_textbox_height(textbox))
        
        self.widgets.append(textbox)
        
        # Ajuster la hauteur du container après ajout du widget
        
        return textbox
    
    def _adjust_textbox_height(self, textbox):
        """Ajuste la hauteur d'une textbox pour qu'elle corresponde exactement au contenu."""
        try:
            textbox.update_idletasks()
            # Obtenir le nombre de lignes réelles dans la textbox
            line_count = int(textbox.index("end-1c").split('.')[0])
            if line_count > 0:
                # Calculer la hauteur nécessaire (environ 1.1x la taille de police par ligne)
                font_size = APP_SETTINGS.get("system_settings", {}).get("font_size", 12)
                line_height = max(int(font_size * 1.0), 13)
                new_height = line_count * line_height  # Pas de minimum
                textbox.configure(height=new_height)
                textbox.update_idletasks()
        except Exception as e:
            log.debug(f"Erreur ajustement hauteur textbox: {e}")
    
    def add_markdown_widget(self, content, is_markdown=True, on_open_in_tab=None):
        """Ajoute un widget Markdown non-collapsible au container pour la réponse finale."""
        md_widget = NonCollapsibleMarkdownWidget(
            self,
            content=content,
            is_markdown=is_markdown,
            on_open_in_tab=on_open_in_tab
        )
        # pady=1 pour un léger espacement entre les box (scaled automatiquement par CustomTkinter)
        md_widget.pack(fill="x", padx=0, pady=1)
        self.widgets.append(md_widget)
        
        # Ajuster la hauteur du container après ajout du widget
        
        return md_widget


class CollapsibleMarkdownWidget(ctk.CTkFrame):
    """
    Widget Markdown collapsible pour le chat, style Cursor.
    Affichage direct du contenu avec bouton collapse intégré.
    """
    def __init__(self, master, content, is_markdown=True, on_open_in_tab=None, **kwargs):
        super().__init__(master, **kwargs)
        self.content = content
        self.is_markdown = is_markdown
        self.on_open_in_tab = on_open_in_tab
        self.is_expanded = True  # Par défaut expanded
        self._preview_label = None
        
        # Frame principal avec bordure subtile (style Cursor)
        self.configure(fg_color=COLORS.get("BG_SECONDARY", "#252526"), corner_radius=5, border_width=1, border_color=COLORS.get("BG_WIDGET", "#2D2D30"))
        
        # Container pour le contenu (toujours visible, taille adaptative)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=3, pady=3)
        
        # Utiliser MarkdownViewer pour l'affichage
        self._create_fallback_viewer()
        
        # Bouton collapse intégré en haut à droite (overlay style Cursor)
        self.btn_toggle = ctk.CTkButton(
            self,
            text="▼",
            width=24,
            height=24,
            command=self.toggle,
            fg_color=COLORS.get("BG_WIDGET", "#2D2D30"),
            hover_color=COLORS.get("ACCENT", "#007ACC"),
            corner_radius=12,
            font=("Arial", 9),
            text_color=COLORS.get("FG_PRIMARY", "#CCCCCC")
        )
        # Positionner le bouton en overlay (top-right)
        self.btn_toggle.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)
        
        # Bind double-clic pour toggle sur tout le widget
        self.bind("<Double-Button-1>", lambda e: self.toggle())
        self.content_frame.bind("<Double-Button-1>", lambda e: self.toggle())
        if hasattr(self, 'md_widget') and hasattr(self.md_widget, 'bind'):
            self.md_widget.bind("<Double-Button-1>", lambda e: self.toggle())
    
    def _create_fallback_viewer(self):
        """Crée un viewer Markdown/HTML pour l'affichage."""
        self.md_widget = MarkdownViewer(
            self.content_frame,
            content=self.content,
            is_markdown=self.is_markdown
        )
        # pady=1 pour un léger espacement entre les box (scaled automatiquement par CustomTkinter)
        self.md_widget.pack(fill="both", expand=True, padx=0, pady=1)
        
        # Calculer la hauteur approximative
        lines = self.content.count('\n') + 1
        estimated_height = min(lines * 25, 800)  # Pas de minimum
        # Note: MarkdownViewer utilise tkinterweb HtmlFrame qui gère automatiquement la taille
        # La hauteur sera gérée par le contenu
    
    def toggle(self):
        """Bascule entre collapsed et expanded."""
        self.is_expanded = not self.is_expanded
        
        if self.is_expanded:
            self.btn_toggle.configure(text="▼")
            # Afficher le contenu complet
            if self._preview_label:
                self._preview_label.pack_forget()
            self.content_frame.pack(fill="both", expand=True, padx=3, pady=3)
        else:
            self.btn_toggle.configure(text="▶")
            # En mode collapsed, cacher le contenu et afficher un aperçu
            self.content_frame.pack_forget()
            # Créer un label avec aperçu si pas déjà créé
            if not self._preview_label:
                preview_text = self.content.split('\n')[0][:80] + "..." if len(self.content.split('\n')[0]) > 80 else self.content.split('\n')[0]
                self._preview_label = ctk.CTkLabel(
                    self,
                    text=preview_text,
                    font=("Consolas", 10),
                    text_color=COLORS.get("FG_SECONDARY", "#858585"),
                    anchor="w",
                    justify="left",
                    wraplength=400
                )
            self._preview_label.pack(fill="x", padx=15, pady=15)
    
    def _open_in_tab(self):
        """Ouvre le contenu dans un onglet séparé."""
        if self.on_open_in_tab:
            self.on_open_in_tab(self.content, self.is_markdown)


class NonCollapsibleMarkdownWidget(ctk.CTkFrame):
    """
    Widget Markdown non-collapsible pour la réponse finale.
    Taille adaptative au contenu, scroll géré automatiquement par tkinterweb.
    """
    def __init__(self, master, content, is_markdown=True, on_open_in_tab=None, **kwargs):
        super().__init__(master, **kwargs)
        self.content = content
        self.is_markdown = is_markdown
        self.on_open_in_tab = on_open_in_tab
        
        # Frame principal sans bordure (style simple)
        self.configure(fg_color="transparent", corner_radius=0)
        
        # Permettre au widget de s'adapter à son contenu
        self.pack_propagate(True)
        
        # Container pour le contenu (toujours visible, taille adaptative)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Utiliser MarkdownViewer pour l'affichage
        self._create_fallback_viewer()
        
        # Ajuster la hauteur après création
        self.after(100, self._adjust_markdown_widget_height)
    
    def _create_fallback_viewer(self):
        """Crée un viewer Markdown/HTML pour l'affichage."""
        self.md_widget = MarkdownViewer(
            self.content_frame,
            content=self.content,
            is_markdown=self.is_markdown
        )
        # pady=1 pour un léger espacement entre les box (scaled automatiquement par CustomTkinter)
        self.md_widget.pack(fill="both", expand=True, padx=0, pady=1)
        
        # Masquer la scrollbar du MarkdownViewer après création
        self.after(200, self._hide_markdown_viewer_scrollbar)
    
    def _adjust_markdown_widget_height(self):
        """Ajuste la hauteur du widget markdown pour qu'il corresponde au contenu (limite ~100 lignes = ~2500px max)."""
        try:
            self.update_idletasks()
            # Calculer approximativement la hauteur basée sur le nombre de lignes
            lines = self.content.count('\n') + 1
            # Limite à ~100 lignes
            max_lines = 100
            lines = min(lines, max_lines)
            # Estimer environ 25px par ligne pour le markdown
            estimated_height = min(max(lines * 25, 150), 2500)  # Minimum 150px (6 lignes), maximum 2500px (100 lignes)
            # Note: MarkdownViewer avec tkinterweb gère la taille automatiquement
            # On peut juste s'assurer que le container s'adapte
            self.update_idletasks()
        except Exception as e:
            log.debug(f"Erreur ajustement hauteur markdown widget: {e}")
    
    def _hide_markdown_viewer_scrollbar(self):
        """Masque la scrollbar du MarkdownViewer (tkinterweb gère le scroll automatiquement)."""
        # tkinterweb HtmlFrame gère le scroll automatiquement, pas besoin de masquer de scrollbar
        # Cette méthode est conservée pour compatibilité mais ne fait rien
        pass


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
"""
Fenêtre popup pour afficher du Markdown/HTML rendu.
"""
import customtkinter as ctk
from ui.windows.base import BaseWindow
from ui.widgets import MarkdownViewer, COLORS
from features.Decorators import trace_action

class MarkdownViewerWindow(BaseWindow):
    """
    Fenêtre popup pour afficher du Markdown/HTML avec rendu complet.
    """
    def __init__(self, master, content, is_markdown=True, title="Aperçu Markdown"):
        super().__init__(master, title, 800, 600)
        self.content = content
        self.is_markdown = is_markdown
        self._build()
    
    @trace_action(source="markdown_viewer")
    def _build(self):
        try:
            # Créer le viewer
            viewer = MarkdownViewer(
                self,
                content=self.content,
                is_markdown=self.is_markdown
            )
            viewer.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Bouton fermer
            btn_frame = ctk.CTkFrame(self, fg_color="transparent")
            btn_frame.pack(fill="x", padx=10, pady=5)
            ctk.CTkButton(
                btn_frame,
                text="Fermer",
                command=self.destroy,
                fg_color=COLORS["BG_SECONDARY"]
            ).pack(side="right")
            
        except Exception as e:
            self.report_error("MarkdownViewer Init", e)

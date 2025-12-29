import customtkinter as ctk
import tkinter as tk
import traceback
import logging
from ui.widgets import COLORS, show_messagebox
from features.Decorators import trace_action

log = logging.getLogger("ui.windows.base")

class Tooltip:
    """Petit utilitaire pour afficher des info-bulles au survol (Ergonomie V16)."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    @trace_action(source="base")
    def show_tooltip(self, event=None):
        try:
            x, y, _, _ = self.widget.bbox("insert")
            x += self.widget.winfo_rootx() + 25
            y += self.widget.winfo_rooty() + 25
            self.tooltip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            label = tk.Label(tw, text=self.text, justify='left',
                             background="#ffffe0", relief='solid', borderwidth=1,
                             font=("tahoma", "8", "normal"), fg="black")
            label.pack(ipadx=1)
        except Exception: pass

    @trace_action(source="base")
    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class BaseWindow(ctk.CTkToplevel):
    """
    Classe de base pour toutes les fenêtres secondaires.
    """
    def __init__(self, master, title, width, height):
        super().__init__(master)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.configure(fg_color=COLORS["BG_MAIN"])
        self.transient(master)
        self.lift()
        
        self.after(200, lambda: self.focus_force())
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    @trace_action(source="base")
    def report_error(self, context, e):
        """Affiche une erreur bloquante à l'utilisateur (Fail Loud)."""
        msg = f"Erreur dans {context}: {str(e)}"
        log.error(f"{msg}\n{traceback.format_exc()}")
        show_messagebox("Erreur Application", f"{msg}\n\n(Voir logs pour traceback)", icon="error", parent=self)

class KeyCaptureDialog(BaseWindow):
    """
    Fenêtre modale pour capturer une combinaison de touches.
    """
    def __init__(self, master, title, callback):
        super().__init__(master, title, 400, 200)
        self.callback = callback
        self.unbind("<Escape>")
        
        self.lbl_instruction = ctk.CTkLabel(self, text="Appuyez sur la combinaison de touches...", font=("Arial", 14))
        self.lbl_instruction.pack(pady=20)
        
        self.lbl_current = ctk.CTkLabel(self, text="...", font=("Consolas", 16, "bold"), text_color=COLORS["ACCENT"])
        self.lbl_current.pack(pady=10)
        
        ctk.CTkButton(self, text="Annuler", command=self.destroy, fg_color=COLORS["ERROR"]).pack(side="bottom", pady=20)
        
        self.bind("<KeyPress>", self._on_key_press)
        self.bind("<Button-1>", self._check_click_outside)
        
        self.focus_force()
        self.grab_set()

    @trace_action(source="base")
    def _check_click_outside(self, event):
        x, y = event.x, event.y
        w, h = self.winfo_width(), self.winfo_height()
        if x < 0 or x > w or y < 0 or y > h:
            self.destroy()

    @trace_action(source="base")
    def _on_key_press(self, event):
        if event.keysym.lower() in ["control_l", "control_r", "alt_l", "alt_r", "shift_l", "shift_r", "caps_lock", "num_lock"]:
            return

        parts = []
        state = event.state
        
        is_ctrl = (state & 4) != 0
        is_alt = (state & 131072) != 0
        is_shift = (state & 1) != 0
        
        if is_ctrl: parts.append("Control")
        if is_alt: parts.append("Alt")
        if is_shift: parts.append("Shift")
        
        parts.append(event.keysym)
        final_string = f"<{'-'.join(parts)}>"
        
        self.lbl_current.configure(text=final_string)
        self.after(300, lambda: self._confirm(final_string))

    @trace_action(source="base")
    def _confirm(self, key_str):
        if self.callback:
            self.callback(key_str)
        self.destroy()
class ModelEditorWindow(BaseWindow):
    def __init__(self, master, current_data, on_save):
        super().__init__(master, "Éditeur JSON", 700, 600)
        self.on_save = on_save
        try:
            import customtkinter as ctk
            import json
            from ui.widgets import COLORS
            
            ctk.CTkLabel(self, text="Édition brute configuration.", text_color="gray").pack(pady=5)
            self.txt = ctk.CTkTextbox(self, font=("Consolas", 12), wrap="none")
            self.txt.pack(fill="both", expand=True, padx=10, pady=5)
            self.txt.insert("1.0", json.dumps(current_data, indent=4))
            btn_frame = ctk.CTkFrame(self, fg_color="transparent")
            btn_frame.pack(fill="x", padx=10, pady=10)
            ctk.CTkButton(btn_frame, text="Annuler", command=self.destroy, fg_color=COLORS["ERROR"]).pack(side="left")
            ctk.CTkButton(btn_frame, text="Sauvegarder", command=self._save, fg_color=COLORS["SUCCESS"]).pack(side="right")
        except Exception as e: self.report_error("Editor Init", e)

    @trace_action(source="base")
    def _save(self):
        import json
        try:
            self.on_save(json.loads(self.txt.get("1.0", "end").strip()))
            self.destroy()
        except Exception as e: self.report_error("Save JSON", e)
import customtkinter as ctk
from ui.windows.base import BaseWindow # Import relatif si possible, sinon absolu depuis le package
from features.Decorators import trace_action

class SecondaryChatWindow(BaseWindow):
    """
    Chat secondaire (préservé de l'original).
    """
    def __init__(self, master, task_queue):
        super().__init__(master, "Chat Secondaire", 600, 500)
        self.task_queue = task_queue
        self._build()

    @trace_action(source="chat")
    def _build(self):
        try:
            self.txt = ctk.CTkTextbox(self, state="disabled", font=("Consolas", 11))
            self.txt.pack(fill="both", expand=True, padx=10, pady=10)
            if hasattr(self.txt, "_textbox"): self.txt._textbox.bind("<Escape>", lambda e: self.destroy())
            
            self.entry = ctk.CTkTextbox(self, height=40)
            self.entry.pack(fill="x", padx=10, pady=5)
            if hasattr(self.entry, "_textbox"): self.entry._textbox.bind("<Escape>", lambda e: self.destroy())
            self.entry.bind("<Return>", self._send)
        except Exception as e:
            self.report_error("SecondaryChat", e)

    @trace_action(source="chat")
    def _send(self, event=None):
        try:
            msg = self.entry.get("1.0", "end").strip()
            if msg:
                self.txt.configure(state="normal"); self.txt.insert("end", f"Vous: {msg}\n\n"); self.txt.configure(state="disabled")
                self.task_queue.put({'type': 'secondary_user_prompt', 'prompt': msg})
                self.entry.delete("1.0", "end")
        except Exception as e:
            self.report_error("Send", e)
        return "break"
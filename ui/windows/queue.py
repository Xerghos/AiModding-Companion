import customtkinter as ctk
from ui.windows.base import BaseWindow
from features.Decorators import trace_action

class WaitingListWindow(BaseWindow):
    """
    Fenêtre de gestion de la file d'attente (Queue).
    Affiche la tâche active et les tâches futures.
    """
    def __init__(self, master, task_queue):
        super().__init__(master, "File d'attente & Processus", 500, 600)
        self.task_queue = task_queue
        
        # --- Section : EN COURS ---
        self.lbl_current = ctk.CTkLabel(self, text="▶️ Tâche en cours", font=("Arial", 14, "bold"), text_color="#4CAF50")
        self.lbl_current.pack(pady=(15, 5), padx=10, anchor="w")
        
        self.txt_current = ctk.CTkTextbox(self, height=60, fg_color="#2b2b2b", text_color="white")
        self.txt_current.pack(fill="x", padx=10, pady=5)
        self.txt_current.configure(state="disabled")
        
        # --- Section : EN ATTENTE ---
        self.lbl_waiting = ctk.CTkLabel(self, text="⏳ En attente", font=("Arial", 14, "bold"), text_color="#FF9800")
        self.lbl_waiting.pack(pady=(15, 5), padx=10, anchor="w")
        
        self.list_waiting = ctk.CTkTextbox(self, height=300)
        self.list_waiting.pack(fill="both", expand=True, padx=10, pady=5)
        self.list_waiting.configure(state="disabled")
        
        # Actions
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(btn_frame, text="Rafraîchir", command=self._refresh, width=100).pack(side="left")
        ctk.CTkButton(btn_frame, text="Vider la file", command=self._clear_queue, width=100, fg_color="#dc3545").pack(side="right")
        
        # Auto-refresh au démarrage
        self.after(500, self._refresh)

    def _refresh(self):
        """Boucle de rafraîchissement automatique."""
        # Vérifie si la fenêtre existe encore
        if not self.winfo_exists():
            return

        # Envoie une demande au worker
        if self.task_queue:
            self.task_queue.put({"type": "get_queue_status"}) 
            
        # [CORRECTION] Se relance automatiquement toutes les 1s (1000ms)
        self.after(1000, self._refresh)
    
    def _clear_queue(self):
        # Pour vider, on peut consommer la queue côté worker ou réinitialiser
        # Ici on envoie une commande spéciale si implémentée, sinon on prévient
        # self.task_queue.put({"type": "clear_queue"}) 
        pass # À implémenter côté worker si désiré

    @trace_action(source="queue")
    def update_list(self, data):
        """Reçoit {current: str, waiting: list}"""
        current = data.get("current", "Inactif")
        waiting = data.get("waiting", [])
        
        # Mise à jour En Cours
        self.txt_current.configure(state="normal")
        self.txt_current.delete("1.0", "end")
        self.txt_current.insert("1.0", current)
        self.txt_current.configure(state="disabled")
        
        # Mise à jour En Attente
        self.list_waiting.configure(state="normal")
        self.list_waiting.delete("1.0", "end")
        
        if not waiting:
            self.list_waiting.insert("end", "La file est vide.")
        else:
            for i, t in enumerate(waiting):
                self.list_waiting.insert("end", f"{i+1}. {t}\n")
                
        self.list_waiting.configure(state="disabled")
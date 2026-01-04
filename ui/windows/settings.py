from tkinter import filedialog as fd
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import json
import os
import logging
import threading
import traceback
import time

# --- IMPORTS CONFIGURATION MODULAIRE ---
from config.settings import APP_SETTINGS, save_app_settings, load_app_settings
from config.logs import get_logger

# --- IMPORTS UI BASE ---
from ui.windows.base import BaseWindow
from ui.widgets import show_messagebox, add_tooltip

# --- IMPORTS AI CORE (Pour Audit & Découverte) ---
from ai_core.factory import SessionFactory
from ai_core.keys import discover_models 
from features.Decorators import trace_action

log = get_logger("ui.windows.settings")

# --- CONSTANTES VISUELLES ---
COLORS = {
    "BG_PRIMARY": "#1e1e1e",
    "BG_SECONDARY": "#252525",
    "BG_WIDGET": "#2b2b2b",
    "FG_PRIMARY": "#E0E0E0",
    "FG_SECONDARY": "#A0A0A0",
    "ACCENT": "#007ACC",
    "SUCCESS": "#28a745",
    "ERROR": "#dc3545",
    "INFO": "#17a2b8",
    "WARNING": "#ffc107"
}

# --- CLASSES HELPERS ---

class Tooltip:
    """Petit utilitaire pour afficher des info-bulles au survol."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        try:
            if self.tooltip_window or not self.text: return
            x = self.widget.winfo_rootx() + 25
            y = self.widget.winfo_rooty() + 25
            self.tooltip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"{x}+{y}")
            label = tk.Label(tw, text=self.text, justify='left',
                             background="#ffffe0", relief='solid', borderwidth=1,
                             font=("tahoma", "8", "normal"), fg="black")
            label.pack(ipadx=1)
        except Exception: pass

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy(); self.tooltip_window = None

class KeyCaptureDialog(BaseWindow):
    """Dialogue modal pour capturer une combinaison de touches."""
    def __init__(self, master, title, callback):
        super().__init__(master, title, 400, 200)
        self.callback = callback
        self.unbind("<Escape>")
        self.lbl_instruction = ctk.CTkLabel(self, text="Appuyez sur la combinaison...", font=("Arial", 14))
        self.lbl_instruction.pack(pady=20)
        self.lbl_current = ctk.CTkLabel(self, text="...", font=("Consolas", 16, "bold"), text_color=COLORS["ACCENT"])
        self.lbl_current.pack(pady=10)
        ctk.CTkButton(self, text="Annuler", command=self.destroy, fg_color=COLORS["ERROR"]).pack(side="bottom", pady=20)
        self.bind("<KeyPress>", self._on_key_press)
        self.focus_force(); self.grab_set()

    def _on_key_press(self, event):
        if event.keysym.lower() in ["control_l", "control_r", "alt_l", "alt_r", "shift_l", "shift_r", "caps_lock", "num_lock"]: return
        parts = []
        if event.state & 4: parts.append("Control")
        if event.state & 131072: parts.append("Alt")
        if event.state & 1: parts.append("Shift")
        parts.append(event.keysym)
        final = f"<{'-'.join(parts)}>"
        self.lbl_current.configure(text=final)
        self.after(300, lambda: self._confirm(final))

    def _confirm(self, key):
        if self.callback: self.callback(key)
        self.destroy()

class ModelEditorWindow(BaseWindow):
    """Éditeur JSON brut pour les configurations avancées."""
    def __init__(self, master, current_data, on_save):
        super().__init__(master, "Éditeur JSON Avancé", 700, 600)
        self.on_save = on_save
        try:
            ctk.CTkLabel(self, text="⚠️ Édition brute de la configuration (Pour experts)", text_color="orange").pack(pady=5)
            self.txt = ctk.CTkTextbox(self, font=("Consolas", 12), wrap="none")
            self.txt.pack(fill="both", expand=True, padx=10, pady=5)
            self.txt.insert("1.0", json.dumps(current_data, indent=4))
            
            btn_frame = ctk.CTkFrame(self, fg_color="transparent")
            btn_frame.pack(fill="x", padx=10, pady=10)
            ctk.CTkButton(btn_frame, text="Annuler", command=self.destroy, fg_color=COLORS["ERROR"]).pack(side="left")
            ctk.CTkButton(btn_frame, text="Valider & Sauvegarder", command=self._save, fg_color=COLORS["SUCCESS"]).pack(side="right")
        except Exception as e:
            show_messagebox("Erreur Init Editor", str(e), icon="error", parent=self)

    def _save(self):
        try:
            data = json.loads(self.txt.get("1.0", "end").strip())
            self.on_save(data)
            self.destroy()
        except Exception as e:
            show_messagebox("Erreur JSON", f"Format invalide : {e}", icon="error", parent=self)

class PathListEditor(ctk.CTkFrame):
    """
    Widget réutilisable pour gérer une liste de chemins (fichiers/dossiers).
    Affiche une liste scrollable avec boutons de suppression et options d'ajout.
    """
    def __init__(self, master, initial_items=None, title="Liste des chemins"):
        super().__init__(master, fg_color="transparent")
        self.items = initial_items if initial_items else []
        
        # Titre
        ctk.CTkLabel(self, text=title, font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 5))
        
        # Zone de liste scrollable
        self.scroll_frame = ctk.CTkScrollableFrame(self, height=150, fg_color=COLORS["BG_WIDGET"])
        self.scroll_frame.pack(fill="x", expand=True, pady=(0, 5))
        
        # Zone d'ajout manuel
        self.entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.entry_frame.pack(fill="x")
        
        self.entry = ctk.CTkEntry(self.entry_frame, placeholder_text="Chemin relatif ou pattern (ex: *.log)")
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry.bind("<Return>", lambda e: self._add_manual())
        
        ctk.CTkButton(self.entry_frame, text="➕", width=30, command=self._add_manual).pack(side="right")
        
        # Boutons d'ajout rapide (Fichier / Dossier)
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(fill="x", pady=5)
        
        ctk.CTkButton(self.btn_frame, text="📄 Ajouter Fichier", command=self._add_file, 
                      fg_color=COLORS["BG_SECONDARY"], height=24).pack(side="left", padx=(0, 5), expand=True, fill="x")
        ctk.CTkButton(self.btn_frame, text="📁 Ajouter Dossier", command=self._add_folder, 
                      fg_color=COLORS["BG_SECONDARY"], height=24).pack(side="left", padx=5, expand=True, fill="x")

        self._refresh_list()

    def _refresh_list(self):
        # Vider la liste
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        # Repeupler
        for item in self.items:
            row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            
            lbl = ctk.CTkLabel(row, text=item, anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=5)
            
            del_btn = ctk.CTkButton(row, text="❌", width=25, height=20, 
                                    fg_color=COLORS["ERROR"], 
                                    command=lambda i=item: self._remove_item(i))
            del_btn.pack(side="right")

    def _remove_item(self, item):
        if item in self.items:
            self.items.remove(item)
            self._refresh_list()

    def _add_manual(self):
        txt = self.entry.get().strip()
        if txt and txt not in self.items:
            self.items.append(txt)
            self.entry.delete(0, "end")
            self._refresh_list()

    def _add_file(self):
        files = fd.askopenfilenames()
        if files:
            self._process_paths(files)

    def _add_folder(self):
        folder = fd.askdirectory()
        if folder:
            self._process_paths([folder])

    def _process_paths(self, paths):
        cwd = os.getcwd()
        for p in paths:
            try:
                # Tenter de rendre relatif
                rel = os.path.relpath(p, cwd).replace("\\", "/")
                if not rel.startswith(".."):
                    val = rel
                else:
                    val = p # Hors projet, on garde absolu
            except:
                val = p
            
            if val not in self.items:
                self.items.append(val)
        self._refresh_list()

    def get_data(self):
        return self.items


class IndexingStatusWidget(ctk.CTkFrame):
    """Widget affichant l'état dynamique de l'indexation (Inclus/Exclus/Exceptions)."""
    def __init__(self, master, root_path, settings):
        super().__init__(master, fg_color=COLORS["BG_WIDGET"], corner_radius=10)
        self.root_path = root_path
        self.settings = settings
        
        self.grid_columnconfigure((0, 1, 2), weight=1)
        self.lbl_inc = self._create_stat(0, "📄 Inclus", COLORS["SUCCESS"])
        self.lbl_exc = self._create_stat(1, "🚫 Exclus", COLORS["ERROR"])
        self.lbl_byp = self._create_stat(2, "🔓 Exceptions", "#9C27B0")
        
        self.btn_refresh = ctk.CTkButton(self, text="🔄 Actualiser l'analyse", width=140, height=28, 
                                         fg_color=COLORS["BG_SECONDARY"], command=self.refresh)
        self.btn_refresh.grid(row=1, column=0, columnspan=3, pady=(0, 10))
        self.after(500, self.refresh)

    def _create_stat(self, col, label, color):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid(row=0, column=col, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(f, text=label, font=("Arial", 11, "bold")).pack()
        val = ctk.CTkLabel(f, text="--", font=("Consolas", 18, "bold"), text_color=color)
        val.pack()
        return val

    def refresh(self):
        if not self.winfo_exists(): return
        self.btn_refresh.configure(state="disabled", text="⏳ Analyse...")
        threading.Thread(target=self._calculate, daemon=True).start()

    def _calculate(self):
        try:
            from features.context.database import calculate_indexing_stats
            stats = calculate_indexing_stats(self.root_path, self.settings)
            if self.winfo_exists():
                self.after(0, lambda: self._update_ui(stats))
        except Exception as e:
            log.error(f"Erreur calcul stats : {e}")
            if self.winfo_exists():
                self.after(0, lambda: self.btn_refresh.configure(state="normal", text="🔄 Erreur"))

    def _update_ui(self, stats):
        if not self.winfo_exists(): return
        self.lbl_inc.configure(text=str(stats["included"]))
        self.lbl_exc.configure(text=str(stats["excluded"]))
        self.lbl_byp.configure(text=str(stats["bypassed"]))
        self.btn_refresh.configure(state="normal", text="🔄 Actualiser l'analyse")

# --- FENÊTRE PRINCIPALE SETTINGS ---

class SettingsWindow(BaseWindow):
    def __init__(self, master, task_queue=None):
        super().__init__(master, "Centre de Contrôle & Paramètres", 1000, 800)
        self.task_queue = task_queue
        
        # 1. Chargement de la Configuration Fraîche
        self.settings = load_app_settings()

        # 2. Récupération des modèles DÉJÀ découverts
        self.available_models = self.settings.get("ai_engine", {}).get("available_models", [])
        if not self.available_models:
            self.available_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gpt-4o"]
            
        # Liste des profils abstraits (Registry Keys)
        self.registry_keys = ["fast", "smart", "coder", "architect", "writer", "reviewer", "compressor"]

        self.vars = {}
        self.model_selectors = [] 
        # Stockage des widgets complexes pour récupération des données
        self.custom_widgets = {}

        # UI Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.tab_gen = self.tab_view.add("⚙️ Général")
        self.tab_api = self.tab_view.add("🔑 Moteurs & API")
        self.tab_swarm = self.tab_view.add("🧠 Swarm & Rôles")
        self.tab_cli = self.tab_view.add("🌉 Hybride / CLI")
        self.tab_sys = self.tab_view.add("🛠️ Système & Code")
        self.tab_ui = self.tab_view.add("🎨 UI & Clés")

        self._build_general_tab()
        self._build_api_tab_dynamic()
        self._build_swarm_tab()
        self._build_cli_tab()
        self._build_system_code_tab()
        self._build_ui_keys_tab()

        # Barre d'actions
        btn_frame = ctk.CTkFrame(self, height=50, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        
        btn_json = ctk.CTkButton(btn_frame, text="🛠️ JSON Brut", command=self._open_json_editor, fg_color="gray", width=120)
        btn_json.pack(side="left", padx=10)
        add_tooltip(btn_json, "Ouvrir l'éditeur JSON brut pour modifier la configuration directement")
        
        btn_cancel = ctk.CTkButton(btn_frame, text="Annuler", command=self.destroy, fg_color=COLORS["BG_SECONDARY"], width=100)
        btn_cancel.pack(side="right", padx=10)
        add_tooltip(btn_cancel, "Annuler les modifications et fermer")
        
        btn_save = ctk.CTkButton(btn_frame, text="💾 Sauvegarder & Appliquer", command=self.save_all_settings, fg_color=COLORS["SUCCESS"], width=200, font=("Arial", 14, "bold"))
        btn_save.pack(side="right")
        add_tooltip(btn_save, "Sauvegarder toutes les modifications et les appliquer immédiatement")

        # [MODIF] Lancement différé de l'audit et de la découverte (SUR SettingsWindow, pas Tooltip !)
        self.after(1000, lambda: threading.Thread(target=self._startup_checks, daemon=True).start())

    def _refresh_combo_values(self):
        """Met à jour les menus déroulants avec la nouvelle liste."""
        if not self.winfo_exists(): return
        try:
            for role in self.registry_keys:
                widget_key = f"ai_engine.cloud_models_registry.{role}_WIDGET"
                if widget_key in self.vars:
                    widget = self.vars[widget_key]
                    if not widget.winfo_exists(): continue
                    current_val = widget.get()
                    
                    new_values = sorted(list(self.available_models))
                    if current_val and current_val not in new_values:
                        new_values.insert(0, current_val)
                        
                    widget.configure(values=new_values)
        except Exception as e:
            log.error(f"Erreur refresh combos: {e}")

    def destroy(self):
        super().destroy()

    def _startup_checks(self):
        """Lance l'audit et la découverte."""
        self._update_available_models() # <-- Découverte des modèles
        self._perform_update_cycle()    # <-- Vérification des clés

    def _update_available_models(self):
        """
        Scanne les clés pour découvrir les modèles disponibles.
        Utilise le nouveau système centralisé de keys.py (Appel unique).
        """
        try:
            found_models = set(self.available_models) # On garde les existants
            
            # [CORRECTION] Appel unique sans arguments (le KeyManager gère ses clés)
            # Retourne format: {"deepseek": ["model-a"], "groq": ["model-b"], ...}
            discovery_result = discover_models()
            
            if discovery_result:
                for provider, models in discovery_result.items():
                    if models:
                        for m in models: found_models.add(m)
                        log.info(f"Modèles trouvés pour {provider}: {len(models)}")
            
            # Mise à jour de la liste triée
            self.available_models = sorted(list(found_models))
            
            # Sauvegarde dans la config
            if "ai_engine" not in self.settings: self.settings["ai_engine"] = {}
            self.settings["ai_engine"]["available_models"] = self.available_models
            
            # Force la mise à jour visuelle des menus déroulants
            self.after(0, self._refresh_combo_values)
            
        except Exception as e:
            log.error(f"Erreur Globale Discovery: {e}")

    # --- HELPERS DE CONSTRUCTION UI ---
    
    def _add_header(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=("Arial", 14, "bold"), text_color=COLORS["ACCENT"]).pack(anchor="w", pady=(15, 5), padx=5)

    def _add_scroll_frame(self, parent):
        f = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True)
        return f

    def _add_combo(self, parent, key, label, options, default):
        frame = ctk.CTkFrame(parent, fg_color="transparent"); frame.pack(fill="x", pady=2)
        ctk.CTkLabel(frame, text=label, width=220, anchor="w").pack(side="left", padx=5)
        
        val = self._get_val(key, default)
        var = ctk.StringVar(value=str(val))
        self.vars[key] = var
        
        # Nettoyage et fusion des options
        clean_opts = sorted(list(set([str(o) for o in options if o])))
        if str(val) not in clean_opts and str(val):
            clean_opts.insert(0, str(val))
        
        cb = ctk.CTkComboBox(frame, values=clean_opts, variable=var)
        cb.pack(side="right", fill="x", expand=True, padx=5)
        self.vars[key + "_WIDGET"] = cb 

    def _add_slider(self, parent, key, label, min_val, max_val, default, is_float=False):
        frame = ctk.CTkFrame(parent, fg_color="transparent"); frame.pack(fill="x", pady=5)
        
        val = self._get_val(key, default)
        try: val = float(val)
        except: val = min_val
        
        var = tk.DoubleVar(value=val)
        self.vars[key] = var
        
        lbl_text = tk.StringVar(value=f"{label}: {val:.2f}" if is_float else f"{label}: {int(val)}")
        
        def update_lbl(v):
            lbl_text.set(f"{label}: {float(v):.2f}" if is_float else f"{label}: {int(float(v))}")

        ctk.CTkLabel(frame, textvariable=lbl_text, width=220, anchor="w").pack(side="left", padx=5)
        steps = 100 if is_float else (max_val - min_val)
        ctk.CTkSlider(frame, from_=min_val, to=max_val, variable=var, number_of_steps=steps, command=update_lbl).pack(side="right", fill="x", expand=True, padx=5)

    def _add_switch(self, parent, key, label, default):
        frame = ctk.CTkFrame(parent, fg_color="transparent"); frame.pack(fill="x", pady=2)
        val = self._get_val(key, default)
        var = ctk.BooleanVar(value=bool(val))
        self.vars[key] = var
        switch_widget = ctk.CTkSwitch(frame, text=label, variable=var)
        switch_widget.pack(anchor="w", padx=5)
        self.vars[key + "_WIDGET"] = switch_widget  # Stocker le widget pour Tooltip

    def _add_entry(self, parent, key, label, default):
        frame = ctk.CTkFrame(parent, fg_color="transparent"); frame.pack(fill="x", pady=2)
        ctk.CTkLabel(frame, text=label, width=220, anchor="w").pack(side="left", padx=5)
        val = self._get_val(key, default)
        var = tk.StringVar(value=str(val))
        self.vars[key] = var
        ctk.CTkEntry(frame, textvariable=var).pack(side="right", fill="x", expand=True, padx=5)
    
    def _add_text(self, parent, key, label, default):
        """Ajoute un widget de texte multi-lignes."""
        frame = ctk.CTkFrame(parent, fg_color="transparent"); frame.pack(fill="both", expand=True, pady=2)
        ctk.CTkLabel(frame, text=label, anchor="w").pack(anchor="w", padx=5, pady=(0, 5))
        val = self._get_val(key, default)
        text_widget = ctk.CTkTextbox(frame, height=100)
        text_widget.insert("1.0", str(val))
        text_widget.pack(fill="both", expand=True, padx=5)
        self.vars[key] = text_widget

    # --- CONSTRUCTION ONGLETS ---

    def _build_general_tab(self):
        scroll = self._add_scroll_frame(self.tab_gen)
        self._add_header(scroll, "Interface & Expérience")
        self._add_combo(scroll, "ui_settings.theme", "Thème Visuel", ["Dark", "Light", "System"], "Dark")
        self._add_combo(scroll, "ui_settings.language", "Langue", ["fr", "en"], "fr")
        self._add_slider(scroll, "ui_settings.font_size", "Taille Police", 8, 20, 12, False)
        self._add_switch(scroll, "ui_settings.streaming_text", "Effet Machine à écrire (Stream)", True)
        self._add_switch(scroll, "ui_settings.sidebar_visible", "Barre Latérale au démarrage", True)

        self._add_header(scroll, "Défilement & Navigation")
        self._add_slider(scroll, "system_settings.scroll_speed", "Vitesse de base", 1, 20, 4, False)
        
        # Modifier Key with Capture
        frame_mod = ctk.CTkFrame(scroll, fg_color="transparent"); frame_mod.pack(fill="x", pady=2)
        ctk.CTkLabel(frame_mod, text="Touche Accélérateur", width=220, anchor="w").pack(side="left", padx=5)
        
        var_mod = tk.StringVar(value=self._get_val("system_settings.scroll_modifier_key", "Alt_L"))
        self.vars["system_settings.scroll_modifier_key"] = var_mod
        
        e_mod = ctk.CTkEntry(frame_mod, textvariable=var_mod, width=150, state="readonly")
        e_mod.pack(side="left", padx=5, expand=True, fill="x")
        
        ctk.CTkButton(frame_mod, text="Modifier", width=80, 
                      command=lambda: self._capture_key("Accélérateur Scroll", var_mod)).pack(side="right", padx=5)
                      
        self._add_slider(scroll, "system_settings.scroll_modifier_multiplier", "Facteur Accélération", 1, 10, 4, False)

        self._add_header(scroll, "Gestion des Pools (Threads)")
        self._add_switch(scroll, "general_settings.dynamic_pool_management", "Gestion Dynamique des Pools", False)
        self._add_slider(scroll, "general_settings.chat_pool_size", "Pool Chat Principal", 1, 30, 4, False)
        self._add_slider(scroll, "general_settings.secondary_chat_pool_size", "Pool Tâches de Fond", 1, 10, 1, False)
        self._add_entry(scroll, "general_settings.api_cooldown_seconds", "Cooldown API (sec)", "60")
        self._add_entry(scroll, "general_settings.audit_interval_seconds", "Vitesse Audit (sec)", "0.1")
        
        # Section Repo Map Cache (TTL uniquement)
        # La liste des fichiers surveillés a été déplacée dans l'onglet Système
        self._add_header(scroll, "🗺️ Cache Repo Map")
        self._add_slider(scroll, "repo_map_cache.ttl_seconds", "TTL Cache (secondes)", 60, 3600, 300)
        
        # Bouton Invalider Cache
        invalidate_btn = ctk.CTkButton(scroll, text="🗑️ Invalider le Cache", 
                                      command=lambda: self._invalidate_repo_map_cache())
        invalidate_btn.pack(pady=5)

    def _build_api_tab_dynamic(self):
        scroll = self._add_scroll_frame(self.tab_api)
        
        self._add_header(scroll, "Fournisseur Principal")
        # [MODIF] Ajout de DeepSeek
        self._add_combo(scroll, "ai_engine.default_provider", "Provider par défaut", ["google_gemini", "deepseek", "openai", "anthropic", "mistral_api", "groq"], "google_gemini")
        self._add_switch(scroll, "ai_engine.fallback_enabled", "Activer Fallback (Secours Auto)", True)
        
        # [MODIF V8.9] Option Accélération ONNX pour l'indexation locale
        self._add_header(scroll, "Moteur d'Embeddings Local (RAG)")
        self._add_switch(scroll, "system_settings.use_onnx_acceleration", "🚀 Accélération ONNX (Ryzen optimized)", False)
        if "system_settings.use_onnx_acceleration_WIDGET" in self.vars:
            add_tooltip(self.vars["system_settings.use_onnx_acceleration_WIDGET"], 
                        "Active ONNX Runtime pour l'indexation massive.\nOFF = PyTorch (Config proven fast 15s).")
        
        # Phase 1 : Toggle LiteLLM (déplacé dans l'onglet CLI)
        # Le toggle LiteLLM est maintenant dans l'onglet "Hybride / CLI"
        
        # --- GESTION AVANCÉE CLÉS (Treeview) ---
        self._add_header(scroll, "Gestionnaire de Clés API (Multi-Comptes)")
        
        # [MODIF V8.5] Déplacement du toggle ONNX ici
        self._add_header(scroll, "Moteur d'Embeddings Local (RAG)")
        self._add_switch(scroll, "system_settings.use_onnx_acceleration", "🚀 Accélération ONNX (Expérimental)", False)
        if "system_settings.use_onnx_acceleration_WIDGET" in self.vars:
            add_tooltip(self.vars["system_settings.use_onnx_acceleration_WIDGET"], 
                        "Active ONNX Runtime pour l'indexation.\nOFF = PyTorch (Config proven fast 15s).")
        
        key_frame = ctk.CTkFrame(scroll)
        key_frame.pack(fill="x", padx=10, pady=5)
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.map("Treeview", background=[('selected', '#007ACC')])
        
        cols = ("Nom", "Provider", "Clé (Masquée)", "Statut")
        self.api_tree = ttk.Treeview(key_frame, columns=cols, show="headings", height=6)
        
        for c in cols: 
            self.api_tree.heading(c, text=c)
            self.api_tree.column(c, width=100 if c != "Clé (Masquée)" else 200)

        self.api_tree.pack(side="left", fill="x", expand=True)
        self._refresh_key_tree()
        
        # Boutons Clés
        btn_k_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_k_frame.pack(fill="x", padx=10, pady=5)
        
        btn_add_key = ctk.CTkButton(btn_k_frame, text="➕ Ajouter Clé", command=self._add_key_dialog, width=100, fg_color=COLORS["ACCENT"])
        btn_add_key.pack(side="left", padx=5)
        add_tooltip(btn_add_key, "Ajouter une nouvelle clé API")
        
        btn_delete_key = ctk.CTkButton(btn_k_frame, text="❌ Supprimer", command=self._delete_key, width=100, fg_color=COLORS["ERROR"])
        btn_delete_key.pack(side="left", padx=5)
        add_tooltip(btn_delete_key, "Supprimer la clé sélectionnée")
        
        # Le bouton appelle _manual_refresh qui lance _perform_update_cycle
        btn_audit = ctk.CTkButton(btn_k_frame, text="🔍 Audit Connexion", command=self._manual_refresh, width=120, fg_color="#9C27B0")
        btn_audit.pack(side="right", padx=5)
        add_tooltip(btn_audit, "Vérifier la connexion et découvrir les modèles disponibles")

        # --- SELECTION MODELES (ROLES COMPLETS) ---
        self._add_header(scroll, "Modèles par Rôle (Registry)")
        reg = self.settings.get("ai_engine", {}).get("cloud_models_registry", {})
        
        # REGISTRY : On mappe un Concept (FAST) vers un Modèle Réel (Gemini-Flash)
        for role in self.registry_keys:
            self._add_combo(scroll, f"ai_engine.cloud_models_registry.{role}", f"Profil '{role.upper()}'.", self.available_models, reg.get(role, ""))

    def _build_swarm_tab(self):
        scroll = self._add_scroll_frame(self.tab_swarm)
        
        self._add_header(scroll, "Configuration Swarm (Essaim)")
        self._add_combo(scroll, "swarm_settings.mode", "Topologie Swarm", ["duo", "trio", "full_swarm"], "duo")
        self._add_combo(scroll, "swarm_settings.autonomy_level", "Niveau Autonomie", ["supervised", "autonomous"], "supervised")
        Tooltip(self.vars["swarm_settings.autonomy_level_WIDGET"], "Supervisé: Demande validation. Autonome: Enchaîne les actions.")

        self._add_header(scroll, "Paramètres Cognitifs & Cloud")
        self._add_slider(scroll, "ai_engine.temperature", "Température (Créativité)", 0.0, 1.0, 0.7, True)
        self._add_entry(scroll, "ai_engine.max_output_tokens", "Max Output Tokens", 8192)
        self._add_slider(scroll, "agents_config.react_max_steps_cloud", "Max Steps Cloud (ReAct)", 1, 20, 10, False)
        
        self._add_header(scroll, "Affectation des Rôles (Mapping)")
        mapping = self.settings.get("swarm_settings", {}).get("role_mapping", {})
        # Agents : Manager, Coder, Architect, etc.
        roles = ["manager", "coder", "architect", "reviewer", "writer", "compressor"]
        
        for role in roles:
            # MAPPING : On mappe un Agent (Manager) vers un Concept (SMART)
            self._add_combo(scroll, f"swarm_settings.role_mapping.{role}", f"Agent {role.capitalize()}", self.registry_keys, mapping.get(role, role))

    def _build_cli_tab(self):
        """Onglet pour la configuration du Pont CLI (Hybride)."""
        scroll = self._add_scroll_frame(self.tab_cli)
        
        # Section LiteLLM avec Auth ADC
        self._add_header(scroll, "🚀 LiteLLM & Authentification Google")
        self._add_switch(scroll, "migration_flags.use_litellm", "Activer LiteLLM (Proxy Universel)", False)
        if "migration_flags.use_litellm_WIDGET" in self.vars:
            Tooltip(self.vars["migration_flags.use_litellm_WIDGET"], 
                    "LiteLLM permet d'utiliser un proxy universel pour toutes les APIs LLM.\n"
                    "Activez cette option pour utiliser LiteLLM au lieu des sessions legacy.\n"
                    "⚠️ Nécessite: pip install litellm")
        
        # Bouton pour configurer l'authentification Google ADC
        adc_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        adc_frame.pack(fill="x", padx=10, pady=5)
        
        btn_oauth = ctk.CTkButton(
            adc_frame, 
            text="🔐 Login with Google (OAuth)", 
            command=self._setup_google_adc_auth,
            fg_color=COLORS["ACCENT"],
            width=200
        )
        btn_oauth.pack(side="left", padx=5)
        add_tooltip(btn_oauth, "S'authentifier avec Google pour utiliser les tokens gratuits (60 req/min, 1000/jour)")
        
        self.adc_status_label = ctk.CTkLabel(adc_frame, text="", font=("Arial", 10))
        self.adc_status_label.pack(side="left", padx=10)
        
        # Vérifier le statut ADC au chargement
        self._check_adc_status()
        
        # Info sur OAuth
        adc_info_frame = ctk.CTkFrame(scroll, fg_color=COLORS["BG_WIDGET"])
        adc_info_frame.pack(fill="x", padx=10, pady=5)
        adc_info_text = (
            "Login with Google (OAuth) permet d'utiliser les tokens gratuits\n"
            "Google AI Pro (60 req/min, 1000/jour) sans API key.\n\n"
            "Cliquez sur le bouton pour ouvrir le navigateur et vous connecter avec votre compte Google."
        )
        ctk.CTkLabel(adc_info_frame, text=adc_info_text, justify="left", font=("Arial", 10), text_color=COLORS["FG_SECONDARY"])
        
        self._add_header(scroll, "🌉 Pont CLI (Bridge)")
        self._add_switch(scroll, "cli_bridge.enabled", "Activer le Mode Hybride CLI", False)
        
        # Info sur le CLI
        info_frame = ctk.CTkFrame(scroll, fg_color=COLORS["BG_WIDGET"])
        info_frame.pack(fill="x", padx=10, pady=5)
        info_text = (
            "Le Pont CLI permet d'utiliser le CLI officiel 'gemini' pour certains modèles,\n"
            "permettant l'utilisation gratuite au lieu de l'API payante.\n\n"
            "Installation: npm install -g @google/gemini-cli\n"
            "Authentification: gemini auth login"
        )
        ctk.CTkLabel(info_frame, text=info_text, justify="left", font=("Arial", 10), text_color=COLORS["FG_SECONDARY"])
        
        # Liste des modèles routés vers le CLI
        self._add_header(scroll, "Modèles Routés vers le CLI")
        cli_models = self.settings.get("cli_bridge", {}).get("models", [])
        if isinstance(cli_models, list):
            cli_models_str = ", ".join(cli_models)
        else:
            cli_models_str = str(cli_models) if cli_models else ""
        
        self._add_entry(scroll, "cli_bridge.models", "Liste des modèles (séparés par virgule)", cli_models_str)
        
        # Info sur le format
        format_frame = ctk.CTkFrame(scroll, fg_color=COLORS["BG_WIDGET"])
        format_frame.pack(fill="x", padx=10, pady=5)
        format_text = (
            "Exemple: gemini-3-flash, gemini-3-pro, gemini-exp-1206\n"
            "Les modèles listés seront automatiquement routés vers le CLI si activé."
        )
        ctk.CTkLabel(format_frame, text=format_text, justify="left", font=("Arial", 9), text_color=COLORS["FG_SECONDARY"])
        
        # Vérification du CLI
        check_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        check_frame.pack(fill="x", padx=10, pady=10)
        btn_check_cli = ctk.CTkButton(check_frame, text="🔍 Vérifier Installation CLI", command=self._check_cli_installation, fg_color=COLORS["INFO"])
        btn_check_cli.pack(side="left", padx=5)
        add_tooltip(btn_check_cli, "Vérifier si le CLI gemini est installé et accessible")
        self.cli_status_label = ctk.CTkLabel(check_frame, text="", font=("Arial", 10))
        self.cli_status_label.pack(side="left", padx=10)
    
    def _check_cli_installation(self):
        """Vérifie si le CLI gemini est installé et accessible."""
        import shutil
        import sys
        import os
        
        # Recherche avec gestion Windows (gemini.cmd, etc.)
        cli_path = None
        candidates = ["gemini"]
        if sys.platform == "win32":
            candidates.extend(["gemini.cmd", "gemini.exe", "gemini.ps1"])
        
        for cmd in candidates:
            path = shutil.which(cmd)
            if path:
                cli_path = path
                break
        
        # Fallback Windows : chemins npm standards
        if not cli_path and sys.platform == "win32":
            npm_paths = [
                os.path.join(os.environ.get("APPDATA", ""), "npm", "gemini.cmd"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "npm", "gemini.cmd"),
            ]
            for npm_path in npm_paths:
                if os.path.exists(npm_path):
                    cli_path = npm_path
                    break
        
        if cli_path:
            self.cli_status_label.configure(text=f"✅ CLI installé: {os.path.basename(cli_path)}", text_color=COLORS["SUCCESS"])
        else:
            self.cli_status_label.configure(text="❌ CLI non trouvé dans PATH", text_color=COLORS["ERROR"])
    
    def _check_adc_status(self):
        """Vérifie si l'authentification Google OAuth (Login with Google) est configurée."""
        try:
            from google.oauth2.credentials import Credentials
            import os
            
            # Vérifier si les tokens OAuth sont stockés (comme gemini-cli)
            token_path = os.path.join(os.path.expanduser("~"), ".config", "google", "gemini_oauth_token.json")
            
            if os.path.exists(token_path):
                try:
                    creds = Credentials.from_authorized_user_file(token_path)
                    # Vérifier que les credentials sont valides
                    if creds and creds.valid:
                        self.adc_status_label.configure(
                            text="✅ Auth Google configurée (OAuth)", 
                            text_color=COLORS["SUCCESS"]
                        )
                        return True
                    elif creds and hasattr(creds, 'refresh_token'):
                        # Tokens expirés mais refresh token disponible
                        try:
                            from google.auth.transport.requests import Request
                            creds.refresh(Request())
                            if creds.valid:
                                # Sauvegarder les tokens rafraîchis avec le validateur
                                from ai_core.oauth_validator import save_oauth_credentials
                                save_oauth_credentials(creds, token_path)
                                self.adc_status_label.configure(
                                    text="✅ Auth Google configurée (OAuth)", 
                                    text_color=COLORS["SUCCESS"]
                                )
                                return True
                        except Exception:
                            pass
                    
                    self.adc_status_label.configure(
                        text="⚠️ Tokens OAuth invalides", 
                        text_color=COLORS["WARNING"]
                    )
                    return False
                except Exception:
                    self.adc_status_label.configure(
                        text="⚠️ Erreur lecture tokens OAuth", 
                        text_color=COLORS["WARNING"]
                    )
                    return False
            else:
                self.adc_status_label.configure(
                    text="❌ Auth Google non configurée", 
                    text_color=COLORS["ERROR"]
                )
                return False
        except ImportError:
            self.adc_status_label.configure(
                text="⚠️ google-auth-oauthlib non installé", 
                text_color=COLORS["WARNING"]
            )
            return False
    
    def _setup_google_adc_auth(self):
        """Configure l'authentification Google OAuth (Login with Google) comme gemini-cli."""
        import threading
        import os
        import json
        
        def auth_thread():
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow
                from google.oauth2.credentials import Credentials
                
                # CRITIQUE: Désactiver la vérification stricte des scopes
                # Google ajoute automatiquement "openid" aux scopes, ce qui cause une exception
                # En définissant cette variable d'environnement, on accepte les scopes modifiés
                os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
                
                # Scopes nécessaires pour Gemini API (EXACTEMENT les mêmes que gemini-cli)
                # Référence: packages/core/src/code_assist/oauth2.ts:81-85 de gemini-cli
                # Note: Google ajoute automatiquement "openid" aux scopes, c'est normal
                # Ces scopes donnent accès à Gemini Code Assist, Cloud Code avec Gemini Code Assist, et Gemini CLI
                # L'application utilise maintenant un custom provider LiteLLM pour CodeAssist (comme gemini-cli)
                # qui utilise l'endpoint cloudcode-pa.googleapis.com via CodeAssistClient, permettant à LiteLLM
                # d'orchestrer (monitoring, fallback, routing) tout en utilisant l'authentification OAuth native
                SCOPES = [
                    'https://www.googleapis.com/auth/cloud-platform',
                    'https://www.googleapis.com/auth/userinfo.email',
                    'https://www.googleapis.com/auth/userinfo.profile'
                ]
                
                # Client ID/Secret OAuth pour Gemini (via variables d'environnement)
                # Référence: oauth2.ts ligne 69-78 de gemini-cli
                # Utiliser les mêmes fonctions que oauth_validator.py pour cohérence
                from ai_core.oauth_validator import _get_gemini_cli_client_id, _get_gemini_cli_client_secret, invalidate_oauth_cache
                
                # Invalider le cache pour utiliser les valeurs corrigées
                invalidate_oauth_cache()
                
                # Priorité : variables d'environnement GOOGLE_OAUTH_* > GEMINI_CLI_* > système de secrets > valeur par défaut
                # IMPORTANT: Utiliser directement _get_gemini_cli_client_id() pour éviter le cache
                client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or os.environ.get("GEMINI_CLI_CLIENT_ID")
                if not client_id:
                    # Utiliser directement la fonction sans cache (valeurs corrigées)
                    client_id = _get_gemini_cli_client_id()
                
                client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or os.environ.get("GEMINI_CLI_CLIENT_SECRET")
                if not client_secret:
                    # Utiliser directement la fonction sans cache (valeurs corrigées)
                    client_secret = _get_gemini_cli_client_secret()
                
                # Validation : vérifier que les credentials sont valides
                if not client_id or len(client_id) < 10:
                    raise ValueError(f"Client ID invalide: {client_id}")
                if not client_secret or len(client_secret) < 10:
                    raise ValueError(f"Client Secret invalide: {client_secret}")
                
                # Log pour déboguer (sans afficher le secret complet)
                try:
                    from features.UnifiedLogger import UnifiedLogger
                    UnifiedLogger.write(
                        "AI_CORE",
                        "DEBUG",
                        f"OAuth Client ID: {client_id[:30]}... (longueur: {len(client_id)})")
                    UnifiedLogger.write(
                        "AI_CORE",
                        "DEBUG",
                        f"OAuth Client Secret: {client_secret[:15]}... (longueur: {len(client_secret)})")
                    # Vérifier que le Client ID correspond à celui de gemini-cli
                    expected_id = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
                    if client_id == expected_id:
                        UnifiedLogger.write("AI_CORE", "DEBUG", "✅ Client ID correspond à gemini-cli")
                    else:
                        UnifiedLogger.write("AI_CORE", "WARNING", f"⚠️ Client ID différent de gemini-cli: {client_id[:30]}...")
                except:
                    pass
                
                if not client_id or not client_secret:
                    # Fallback vers gcloud auth application-default login
                    self.after(0, lambda: show_messagebox(
                        "Configuration OAuth manquante",
                        "Les variables d'environnement GOOGLE_OAUTH_CLIENT_ID/GEMINI_CLI_CLIENT_ID et\n"
                        "GOOGLE_OAUTH_CLIENT_SECRET/GEMINI_CLI_CLIENT_SECRET ne sont pas définies.\n"
                        "Utilisation de 'gcloud auth application-default login'\n"
                        "comme méthode d'authentification alternative.\n\n"
                        "Note: Les valeurs par défaut gemini-cli sont utilisées si disponibles.",
                        icon="warning",
                        parent=self
                    ))
                    # Utiliser gcloud auth application-default login
                    import subprocess
                    import shutil
                    
                    # Trouver gcloud dans le PATH ou chemins standards Windows
                    gcloud_path = shutil.which("gcloud")
                    if not gcloud_path:
                        # Chemins standards Windows pour gcloud
                        gcloud_candidates = [
                            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd"),
                            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd"),
                            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd"),
                        ]
                        for candidate in gcloud_candidates:
                            if os.path.exists(candidate):
                                gcloud_path = candidate
                                break
                    
                    if not gcloud_path:
                        self.after(0, lambda: show_messagebox(
                            "gcloud non trouvé",
                            "gcloud n'a pas été trouvé dans le PATH.\n\n"
                            "Solutions:\n"
                            "1. Installez Google Cloud SDK: https://cloud.google.com/sdk/docs/install\n"
                            "2. Ajoutez gcloud au PATH système\n"
                            "3. Ou définissez GOOGLE_OAUTH_CLIENT_ID et GOOGLE_OAUTH_CLIENT_SECRET",
                            icon="error",
                            parent=self
                        ))
                        return
                    
                    # Lancer gcloud avec shell=True pour Windows
                    subprocess.run([gcloud_path, "auth", "application-default", "login"], check=True, shell=True)
                    self.after(0, lambda: self._check_adc_status())
                    return
                
                # Vérifier que le Client ID correspond exactement à celui de gemini-cli
                expected_id = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
                if client_id != expected_id:
                    try:
                        from features.UnifiedLogger import UnifiedLogger
                        UnifiedLogger.write(
                            "AI_CORE",
                            "WARNING",
                            f"⚠️ Client ID différent de gemini-cli attendu. Reçu: {client_id}, Attendu: {expected_id}")
                    except:
                        pass
                
                client_config = {
                    "installed": {
                        "client_id": client_id.strip(),  # Nettoyer les espaces
                        "client_secret": client_secret.strip(),  # Nettoyer les espaces
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
                    }
                }
                
                # Log du client_config (sans le secret complet) pour déboguer
                try:
                    from features.UnifiedLogger import UnifiedLogger
                    UnifiedLogger.write(
                        "AI_CORE",
                        "DEBUG",
                        f"Client config créé avec Client ID: {client_config['installed']['client_id'][:30]}...")
                except:
                    pass
                
                # CRITIQUE: Supprimer l'ancien token s'il existe pour éviter les conflits de scopes
                # Si un ancien token existe avec des scopes différents, Google refusera la connexion
                token_path = os.path.join(os.path.expanduser("~"), ".config", "google", "gemini_oauth_token.json")
                if os.path.exists(token_path):
                    try:
                        os.remove(token_path)
                        # Logger via le système de logs si disponible
                        try:
                            from features.UnifiedLogger import UnifiedLogger
                            UnifiedLogger.write(
                                "AI_CORE",
                                "AUTH",
                                "Ancien token OAuth supprimé pour éviter les conflits de scopes")
                        except:
                            pass
                    except Exception as e:
                        try:
                            from features.UnifiedLogger import UnifiedLogger
                            UnifiedLogger.write(
                                "AI_CORE",
                                "DEBUG",
                                f"Impossible de supprimer l'ancien token: {e}")
                        except:
                            pass
                
                self.after(0, lambda: self.adc_status_label.configure(
                    text="⏳ Ouverture du navigateur...", 
                    text_color=COLORS["INFO"]
                ))
                
                # Lancer le flow OAuth (Login with Google)
                # Note: run_local_server() gère automatiquement le callback et attend la réponse
                # Avec OAUTHLIB_RELAX_TOKEN_SCOPE=1, Google peut ajouter "openid" aux scopes sans erreur
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                
                # Utiliser success_message pour afficher un message personnalisé après l'auth
                credentials = flow.run_local_server(
                    port=0, 
                    open_browser=True,
                    success_message="L'authentification a réussi. Les produits suivants sont désormais autorisés à accéder à votre compte :\n    Gemini Code Assist\n    Cloud Code avec Gemini Code Assist\n    Gemini CLI\n\nVous pouvez fermer cette fenêtre."
                )
                
                # Vérifier que les credentials ont été obtenus
                if not credentials:
                    raise Exception("Aucun credential n'a été retourné par le flux OAuth")
                
                # Log des scopes obtenus (pour debug - Google peut ajouter "openid")
                try:
                    from features.UnifiedLogger import UnifiedLogger
                    obtained_scopes = list(credentials.scopes) if credentials.scopes else []
                    UnifiedLogger.write(
                        "AI_CORE",
                        "AUTH",
                        f"✅ Credentials OAuth obtenus avec scopes: {', '.join(obtained_scopes)}")
                    
                    # Vérifier si le scope cloud-platform est présent
                    has_cloud_platform = any('cloud-platform' in scope for scope in obtained_scopes)
                    if not has_cloud_platform:
                        UnifiedLogger.write(
                            "AI_CORE",
                            "WARNING",
                            "⚠️ Le scope 'cloud-platform' n'est pas présent dans les credentials. L'accès à l'API Gemini peut échouer.")
                except:
                    pass
                
                # Sauvegarder les tokens OAuth (comme gemini-cli)
                credentials_dir = os.path.join(os.path.expanduser("~"), ".config", "google")
                os.makedirs(credentials_dir, exist_ok=True)
                token_path = os.path.join(credentials_dir, "gemini_oauth_token.json")
                
                # Sauvegarder au format Credentials normalisé (compatible avec google.oauth2.credentials)
                from ai_core.oauth_validator import save_oauth_credentials
                
                if not save_oauth_credentials(credentials, token_path):
                    raise Exception("Échec de la sauvegarde des credentials OAuth (format invalide)")
                
                # CRITIQUE: NE JAMAIS définir GOOGLE_APPLICATION_CREDENTIALS ici !
                # Cela déclencherait la détection Vertex AI dans LiteLLM
                
                # Mettre à jour le statut dans l'UI
                self.after(0, lambda: self.adc_status_label.configure(
                    text="✅ Auth Google configurée avec succès!", 
                    text_color=COLORS["SUCCESS"]
                ))
                self.after(0, lambda: self._check_adc_status())
                
                # Afficher un message avec des informations sur les scopes
                obtained_scopes_str = ", ".join(list(credentials.scopes) if credentials.scopes else [])
                self.after(0, lambda: show_messagebox(
                    "Authentification réussie",
                    f"L'authentification Google (Login with Google) a été configurée avec succès!\n\n"
                    f"Scopes obtenus: {obtained_scopes_str}\n\n"
                    "Vous pouvez maintenant utiliser les tokens gratuits Google AI Pro\n"
                    "(60 req/min, 1000/jour) sans API key.\n\n"
                    "L'application utilise maintenant CodeAssistClient (même mécanisme que gemini-cli)\n"
                    "qui utilise l'endpoint cloudcode-pa.googleapis.com pour l'authentification OAuth.",
                    icon="info",
                    parent=self
                ))
                
            except ImportError as e:
                self.after(0, lambda: show_messagebox(
                    "Erreur",
                    f"Bibliothèque manquante: {e}\n\n"
                    "Installez avec:\n"
                    "pip install google-auth-oauthlib google-auth-httplib2",
                    icon="error",
                    parent=self
                ))
            except Exception as e:
                self.after(0, lambda: self.adc_status_label.configure(
                    text="❌ Erreur d'authentification", 
                    text_color=COLORS["ERROR"]
                ))
                self.after(0, lambda: show_messagebox(
                    "Erreur d'authentification",
                    f"Échec de l'authentification: {e}\n\n"
                    "Assurez-vous d'avoir une connexion Internet et que le navigateur peut s'ouvrir.",
                    icon="error",
                    parent=self
                ))
                log.error(f"Erreur setup OAuth: {e}", exc_info=True)
        
        # Lancer dans un thread séparé pour ne pas bloquer l'UI
        thread = threading.Thread(target=auth_thread, daemon=True)
        thread.start()

    def _invalidate_repo_map_cache(self):
        """Invalide le cache Repo Map."""
        try:
            from features.context.repo_map import invalidate_repo_map_cache
            invalidate_repo_map_cache()
            # Afficher un message de confirmation
            show_messagebox("Cache invalidé", "Le cache Repo Map a été invalidé avec succès.", icon="info", parent=self)
        except Exception as e:
            show_messagebox("Erreur", f"Erreur lors de l'invalidation: {e}", icon="error", parent=self)

    def _build_system_code_tab(self):
        scroll = self._add_scroll_frame(self.tab_sys)
        
        # [MODIF V8.9] Widget de Statistiques Dynamiques (Version Unique et Corrigée)
        self._add_header(scroll, "📊 État de l'Indexation & Corpus")
        self.indexing_stats = IndexingStatusWidget(scroll, os.getcwd(), self.settings)
        self.indexing_stats.pack(fill="x", padx=10, pady=5)

        self._add_header(scroll, "Analyse de Code & Sécurité")
        self._add_switch(scroll, "code_analysis.backup_before_refactor", "Backup Auto avant Refactoring", True)
        self._add_combo(scroll, "code_analysis.security_scan_level", "Niveau Scan Sécurité", ["standard", "high", "paranoid"], "standard")
        
        # --- Exclusions (Fichiers & Dossiers) ---
        self._add_header(scroll, "Exclusions (Fichiers & Dossiers ignorés)")
        
        # Widget PathListEditor pour les exclusions
        ignored_list = self.settings.get("code_analysis", {}).get("ignored_folders", [])
        self.exclusion_editor = PathListEditor(scroll, initial_items=ignored_list, title="")
        self.exclusion_editor.pack(fill="x", padx=10, pady=5)
        # On enregistre une référence pour la sauvegarde
        self.custom_widgets["code_analysis.ignored_folders"] = self.exclusion_editor

        # --- Surveillance (Repo Map & Indexation) ---
        self._add_header(scroll, "Surveillance (Exceptions Prioritaires)")
        
        # Widget PathListEditor pour les fichiers à surveiller (Repo Map Cache)
        # On récupère depuis repo_map_cache.watch_files
        watch_list = self.settings.get("repo_map_cache", {}).get("watch_files", ["config/architecture_map.json"])
        self.watch_editor = PathListEditor(scroll, initial_items=watch_list, title="Fichiers/Dossiers à inclure (Outrepasse les exclusions)")
        self.watch_editor.pack(fill="x", padx=10, pady=5)
        self.custom_widgets["repo_map_cache.watch_files"] = self.watch_editor

        self._add_header(scroll, "Maintenance & Logs")
        self._add_switch(scroll, "system_settings.debug_mode", "Mode Debug Global", False)
        self._add_combo(scroll, "system_settings.log_level", "Niveau de Logs", ["INFO", "DEBUG", "WARNING", "ERROR"], "INFO")
        self._add_switch(scroll, "system_settings.check_updates_on_startup", "Vérifier Mises à jour", True)
        
        self._add_header(scroll, "Mémoire & RAG")
        self._add_entry(scroll, "system_settings.max_history_retention", "Mémoire Historique (Lignes)", "500")
        self._add_entry(scroll, "system_settings.rag_database_path", "Chemin DB Vectorielle", "db/knowledge_base_hybrid")

        self._add_header(scroll, "Compression Sémantique (Optimisation)")
        self._add_switch(scroll, "memory_optimization.enabled", "Activer le Compresseur", True)
        self._add_switch(scroll, "memory_optimization.force_archiviste_mode", "Mode Archiviste (Anti-Boucle)", True)
        
        self._add_slider(scroll, "memory_optimization.active_window", "Fenêtre Active (Messages)", 0, 20, 10)
        self._add_slider(scroll, "memory_optimization.compression_threshold", "Seuil Compression (Chars)", 0, 2000, 800)
        self._add_slider(scroll, "memory_optimization.max_active_tokens", "Plafond RAM (Caractères)", 1000, 200000, 50000, False)

    def _build_ui_keys_tab(self):
        scroll = self._add_scroll_frame(self.tab_ui)
        self._add_header(scroll, "Raccourcis Clavier")
        
        bindings = self.settings.get("key_bindings", {})
        for name, key_val in bindings.items():
            f = ctk.CTkFrame(scroll, fg_color="transparent")
            f.pack(fill="x", pady=2)
            ctk.CTkLabel(f, text=name, width=150, anchor="w").pack(side="left")
            
            var = tk.StringVar(value=key_val)
            self.vars[f"key_bindings.{name}"] = var
            
            e = ctk.CTkEntry(f, textvariable=var, width=150, state="readonly")
            e.pack(side="left", padx=5)
            
            ctk.CTkButton(f, text="Modifier", width=60, command=lambda n=name, v=var: self._capture_key(n, v)).pack(side="left")

    # --- LOGIQUE METIER ---

    def _get_val(self, key, default):
        parts = key.split(".")
        d = self.settings
        try:
            for p in parts[:-1]: d = d.get(p, {})
            return d.get(parts[-1], default)
        except: return default

    def _refresh_key_tree(self):
        for i in self.api_tree.get_children(): self.api_tree.delete(i)
        keys = self.settings.get("api_keys_list", [])
        
        # Migration Legacy automatique si liste vide
        if not keys and "api_keys" in self.settings:
            legacy = self.settings["api_keys"]
            for k, v in legacy.items():
                if v and isinstance(v, str): 
                    sub_keys = v.split(',')
                    for idx, sk in enumerate(sub_keys):
                        if sk.strip():
                            keys.append({"name": f"Import {k} {idx+1}", "provider": k, "key": sk.strip(), "id": f"leg_{k}_{idx}"})
                elif v and isinstance(v, list):
                    for idx, sk in enumerate(v):
                        keys.append({"name": f"Import {k} {idx+1}", "provider": k, "key": sk, "id": f"leg_{k}_{idx}"})
        
        for k in keys:
            val_key = k.get("key", "")
            mask = val_key[:6] + "..." if len(val_key) > 6 else "Vide"
            # Statut initial : Inconnu
            self.api_tree.insert("", "end", values=(k.get("name", "?"), k.get("provider", "?"), mask, "Inconnu"), iid=k.get("id"))

    def _add_key_dialog(self):
        d = ctk.CTkToplevel(self); d.geometry("300x250"); d.title("Ajouter Clé")
        d.transient(self); d.grab_set()
        
        ctk.CTkLabel(d, text="Nom:").pack(pady=5)
        n = ctk.CTkEntry(d); n.pack()
        ctk.CTkLabel(d, text="Provider:").pack(pady=5)
        # [MODIFICATION] Ajout de deepseek
        p = ctk.CTkOptionMenu(d, values=["google_gemini", "deepseek", "openai", "mistral", "groq"]); p.pack()
        ctk.CTkLabel(d, text="Clé API:").pack(pady=5)
        k = ctk.CTkEntry(d); k.pack()
        
        def valider():
            if "api_keys_list" not in self.settings: self.settings["api_keys_list"] = []
            new_id = f"key_{len(self.settings['api_keys_list'])+1}_{int(time.time())}"
            self.settings["api_keys_list"].append({"id": new_id, "name": n.get(), "provider": p.get(), "key": k.get()})
            self._refresh_key_tree()
            d.destroy()
            
        ctk.CTkButton(d, text="Sauvegarder", command=valider).pack(pady=20)

    def _delete_key(self):
        sel = self.api_tree.selection()
        if not sel: return
        if show_messagebox("Confirmer", "Supprimer la clé sélectionnée ?", icon="question", parent=self):
            remaining = [k for k in self.settings.get("api_keys_list", []) if k.get("id") not in sel]
            self.settings["api_keys_list"] = remaining
            self._refresh_key_tree()

    # --- [MODIF] LOGIQUE D'AUDIT SUR DEMANDE ---

    def _manual_refresh(self):
        """Action du bouton 'Audit Connexion'."""
        self.title("Audit & Découverte en cours...")
        # On lance les deux tâches : Audit santé + Découverte modèles
        threading.Thread(target=self._startup_checks, daemon=True).start()

    def _perform_update_cycle(self):
        """Interroge la Factory et met à jour l'UI."""
        try:
            reports = SessionFactory.audit_all_providers()
            self.after(0, lambda: self._update_tree_status(reports))
        except Exception as e:
            log.error(f"Audit Cycle Fail: {e}")

    def _update_tree_status(self, reports):
        """Met à jour la colonne Statut du Treeview avec les scores de santé."""
        self.title("Paramètres Globaux")
        
        # Mapping pour aligner les noms UI avec les clés du rapport factory
        prov_map = {"google_gemini": "google_gemini", "groq": "groq", "deepseek": "deepseek"}
        
        count_updated = 0
        
        for item_id in self.api_tree.get_children():
            current_values = self.api_tree.item(item_id, "values")
            if not current_values: continue
            
            nom, provider_ui, masked_key, _ = current_values
            
            # Recherche de la vraie clé dans les settings locaux
            real_entry = next((k for k in self.settings.get("api_keys_list", []) if k.get("id") == item_id), None)
            if not real_entry: continue
            
            full_key = real_entry.get("key", "")
            if len(full_key) < 6: continue
            
            search_suffix = full_key[-6:]
            
            # [CORRECTION] Gestion directe de la liste (plus de .get("details"))
            # reports = {'google_gemini': [ {stats}, {stats} ], ...}
            report_key = prov_map.get(provider_ui, provider_ui)
            provider_stats_list = reports.get(report_key, [])
            
            # Match via short_id
            found_data = next((d for d in provider_stats_list if d.get("short_id") == search_suffix), None)
            
            if found_data:
                health = found_data.get("health", 0)
                # Icônes basées sur la santé
                icon = "🟢" if health > 80 else "🟠" if health > 30 else "🔴"
                display_status = f"{icon} {health:.0f}%"
                
                self.api_tree.item(item_id, values=(nom, provider_ui, masked_key, display_status))
                count_updated += 1
            else:
                # Clé présente dans l'UI mais pas chargée dans le KeyManager (ex: ajoutée sans save)
                self.api_tree.item(item_id, values=(nom, provider_ui, masked_key, "⚪ Non chargé"))

    def _capture_key(self, name, var):
        KeyCaptureDialog(self, f"Touche pour {name}", lambda k: var.set(k))

    def _open_json_editor(self):
        ModelEditorWindow(self, self.settings, self.save_all_settings)
    
    # --- SAUVEGARDE FINALE ---

    def save_all_settings(self, new_data=None):
        try:
            # 1. Mise à jour depuis widgets (si pas de new_data JSON)
            if new_data:
                self.settings = new_data
            else:
                # Sauvegarde des widgets standards
                for key, var in self.vars.items():
                    if "_WIDGET" in key: continue
                    
                    # Gestion spéciale pour les widgets texte multi-lignes
                    if isinstance(var, ctk.CTkTextbox):
                        val_str = var.get("1.0", "end-1c")
                        if "watch_directories" in key: # watch_files est géré par PathListEditor
                            val_list = [x.strip() for x in val_str.split("\n") if x.strip()]
                            parts = key.split(".")
                            if len(parts) >= 2:
                                section = parts[0]
                                subkey = parts[1]
                                if section not in self.settings: self.settings[section] = {}
                                self.settings[section][subkey] = val_list
                            continue
                        else:
                            val = val_str
                    else:
                        val = var.get()
                    
                    # Typage
                    if isinstance(val, str):
                        if val.isdigit() and "pool" in key: val = int(val)
                        elif val.replace(".","",1).isdigit() and "." in val: val = float(val)

                    # Mise à jour nested dict
                    parts = key.split(".")
                    d = self.settings
                    for p in parts[:-1]:
                        if p not in d: d[p] = {}
                        d = d[p]
                    d[parts[-1]] = val
                
                # Sauvegarde des widgets custom (PathListEditor)
                if hasattr(self, 'custom_widgets'):
                    for key, widget in self.custom_widgets.items():
                        if hasattr(widget, 'get_data'):
                            val_list = widget.get_data()
                            parts = key.split(".")
                            d = self.settings
                            for p in parts[:-1]:
                                if p not in d: d[p] = {}
                                d = d[p]
                            d[parts[-1]] = val_list

            # Reconstruction du dictionnaire simple api_keys pour le backend (compatibilité)
            final_keys_map = {}
            for item in self.settings.get("api_keys_list", []):
                p = item.get("provider")
                k = item.get("key")
                if p and k:
                    if p not in final_keys_map: final_keys_map[p] = []
                    final_keys_map[p].append(k)
            self.settings["api_keys"] = final_keys_map

            # 2. Sauvegarde Disque
            if save_app_settings(self.settings):
                try: ctk.set_appearance_mode(self.settings.get("ui_settings", {}).get("theme", "Dark"))
                except: pass
                
                if self.task_queue:
                    self.task_queue.put({"type": "reload_system"})
                
                show_messagebox("Sauvegardé", "Configuration appliquée en temps réel !", icon="info", parent=self)
                self.destroy()
            else:
                show_messagebox("Erreur", "Impossible d'écrire le fichier settings.json", icon="error", parent=self)
        except Exception as e:
            log.error(f"Erreur Save: {e}")
            show_messagebox("Erreur Critique", str(e), icon="error", parent=self)
    
class ApiKeyManager(BaseWindow):
    """Classe Wrapper pour compatibilité ascendante."""
    def __init__(self, master, task_queue=None):
        super().__init__(master, "Gestion des Clés", 400, 200)
        ctk.CTkLabel(self, text="⚠️ Ce module est intégré aux Paramètres Globaux", font=("Arial", 12, "bold")).pack(pady=20)
        ctk.CTkButton(self, text="Ouvrir Paramètres > Clés", command=self._open_settings).pack(pady=10)
    
    def _open_settings(self):
        SettingsWindow(self.master, None)
        self.destroy()

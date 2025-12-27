import os
import sys
import customtkinter as ctk
import traceback
import ctypes

# 1. Configuration du Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 2. Gestion High-DPI (Pour éviter l'interface floue ou cassée sur Windows)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# 3. Initialisation du Logger
try:
    import config.logs
    from features.UnifiedLogger import UnifiedLogger
    UnifiedLogger.write("run", "START", "Lancement...")
except ImportError:
    pass

# 3.5. Démarrage du serveur MCP HTTP long-running
try:
    import time
    from ai_core.mcp_server_http import start_server_background
    mcp_server_thread = start_server_background()
    # Laisser un peu de temps au serveur pour s'initialiser
    time.sleep(0.5)
    if 'UnifiedLogger' in locals():
        UnifiedLogger.write("run", "INFO", "✅ Serveur MCP HTTP démarré en arrière-plan")
except Exception as e:
    if 'UnifiedLogger' in locals():
        UnifiedLogger.write("run", "WARNING", f"⚠️ Impossible de démarrer le serveur MCP HTTP: {e}")
    else:
        print(f"⚠️ Serveur MCP HTTP non démarré: {e}")

# 4. Import UI
try:
    from ui.main_window import GeminiApp
except ImportError as e:
    print(f"❌ Erreur Import UI : {e}")
    input("Entrée pour quitter...")
    sys.exit(1)

def main():
    try:
        # --- CONFIGURATION DE L'APPARENCE ---
        # On définit le thème AVANT de créer la fenêtre
        ctk.set_appearance_mode("Dark")  # ou "System"
        ctk.set_default_color_theme("blue")
        
        # Options de mise à l'échelle (Si l'interface est trop grosse/petite)
        ctk.set_widget_scaling(1.0)  # 1.0 = 100% (Standard)
        ctk.set_window_scaling(1.0)  # 1.0 = 100% (Standard)

        # Création de la fenêtre racine
        root = ctk.CTk()
        root.title("AiModding-Companion")
        
        # Taille par défaut (ajustable)
        root.geometry("1400x900")

        # Instanciation de l'App
        app = GeminiApp(root)
        
        if 'UnifiedLogger' in locals():
            UnifiedLogger.write("run", "SUCCESS", "--- APPLICATION DÉMARRÉE ---")
        
        root.mainloop()

    except Exception as e:
        print(f"\n❌ CRASH : {e}")
        traceback.print_exc()
        input("Appuyez sur Entrée...")

if __name__ == "__main__":
    main()
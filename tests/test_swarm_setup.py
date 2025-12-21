import sys
import os

# Ajout de la racine au path pour les imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Imports des modules modifiés
try:
    from agents.swarm_manager import create_agent
    from config.settings import load_app_settings
except ImportError as e:
    print(f"❌ Erreur d'import critique : {e}")
    sys.exit(1)

def test_swarm_initialization():
    print("--- 🧪 TEST DIAGNOSTIC SWARM V2 ---")
    
    # Chargement config pour éviter erreur SessionFactory
    load_app_settings()

    # TEST 1 : Agent avec Outils (CODER)
    print("\n🔹 [1] Test Initialisation 'CODER' (Expert + Outils)")
    try:
        coder = create_agent("CODER")
        print(f"✅ Instance créée avec succès.")
        print(f"ℹ️  Modèle Tier détecté : {coder.tier}")
        
        # Vérification du prompt (Whitelisting)
        sys_prompt = coder.system_instruction
        if "MANUEL DES OUTILS AUTORISÉS" in sys_prompt and "lire_fichier" in sys_prompt:
            print("✅ SUCCÈS : Le Prompt contient bien le manuel des outils.")
        else:
            print("❌ ÉCHEC : Le manuel des outils est absent du prompt.")
            print(f"🔍 Extrait Prompt : {sys_prompt[:100]}...")

    except Exception as e:
        print(f"❌ CRASH : Impossible de créer l'agent CODER. Détail : {e}")
        import traceback
        traceback.print_exc()

    # TEST 2 : Agent sans Outils (ROUTER)
    print("\n🔹 [2] Test Initialisation 'ROUTER' (Fast + Sans Outils)")
    try:
        router = create_agent("ROUTER")
        print(f"✅ Instance créée avec succès.")
        print(f"ℹ️  Modèle Tier détecté : {router.tier}")
        
        sys_prompt = router.system_instruction
        if "MANUEL DES OUTILS AUTORISÉS" not in sys_prompt:
            print("✅ SUCCÈS : Le Prompt est propre (pas d'outils).")
        else:
            print("⚠️ AVERTISSEMENT : Le Router a reçu des outils (Inattendu).")

    except Exception as e:
        print(f"❌ CRASH : Impossible de créer l'agent ROUTER. Détail : {e}")

if __name__ == "__main__":
    test_swarm_initialization()
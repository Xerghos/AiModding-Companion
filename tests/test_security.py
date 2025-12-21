import sys
import os

# Ajout racine projet
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import load_app_settings
from features.ai_helper import execute_native_tool

def test_security_middleware():
    print("--- 🛡️ TEST SECURITY MIDDLEWARE (SANITY CHECK) ---")
    
    # 1. Rechargement Settings (S'assurer que la section 'security' est prise en compte)
    load_app_settings()
    
    # Mock des objets session/queue (inutiles pour ce test qui doit bloquer AVANT)
    mock_args = {"session": None, "action_log_path": None, "result_queue": None, "task_queue": None}

    # --- TEST 1 : ACCÈS LÉGITIME ---
    print("\n🔹 [1] Test Lecture Légitime ('README.md')")
    res_ok = execute_native_tool("lire_fichier", {"chemin": "README.md"}, **mock_args)
    if "⛔ SÉCURITÉ" not in str(res_ok) and "❌" not in str(res_ok):
        print("✅ SUCCÈS : L'accès légitime est passé.")
    else:
        print(f"❌ ÉCHEC : L'accès légitime a été bloqué ou a échoué. ({str(res_ok)[:100]}...)")

    # --- TEST 2 : CONFINEMENT (JAIL) ---
    print("\n🔹 [2] Test Confinement ('../outside.txt')")
    # On tente de lire un fichier hors du dossier projet
    res_jail = execute_native_tool("lire_fichier", {"chemin": "../outside.txt"}, **mock_args)
    
    if "⛔ SÉCURITÉ" in str(res_jail) and "Accès interdit hors du projet" in str(res_jail):
        print("✅ SUCCÈS : La tentative de sortie du projet a été BLOQUÉE.")
    else:
        print(f"❌ ÉCHEC : Le confinement n'a pas fonctionné ! Résultat : {str(res_jail)[:100]}")

    # --- TEST 3 : PROTECTION FICHIERS CRITIQUES ---
    print("\n🔹 [3] Test Protection Critique ('config/settings.py')")
    # On tente d'écrire dans les settings (interdit)
    res_protect = execute_native_tool("ecrire_fichier", {"chemin": "config/settings.py", "contenu": "HACKED"}, **mock_args)
    
    if "⛔ SÉCURITÉ" in str(res_protect) and "protégé contre la modification" in str(res_protect):
        print("✅ SUCCÈS : L'écriture sur un fichier critique a été BLOQUÉE.")
    elif "security" not in str(res_protect) and "❌" not in str(res_protect):
        # Si ça passe (et échoue plus loin car mock session), c'est que le check n'a pas trigger
        print("❌ CRITIQUE : Le middleware a laissé passer l'écriture ! (Vérifiez config/settings.py)")
        print(f"   Réponse : {str(res_protect)[:100]}")
    else:
        print(f"⚠️ RÉSULTAT INATTENDU : {str(res_protect)[:100]}")

if __name__ == "__main__":
    test_security_middleware()
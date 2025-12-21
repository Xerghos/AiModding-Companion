import os
import sys
import shutil
import time

# Ajout racine projet
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.swarm_manager import create_agent
from config.paths import get_path

def setup_sandbox():
    """Crée un environnement de test avec dépendances."""
    sandbox_dir = get_path("sandbox_test_doc")
    if os.path.exists(sandbox_dir):
        shutil.rmtree(sandbox_dir)
    os.makedirs(sandbox_dir)

    # 1. Le Fichier de Dépendance (avec le secret)
    with open(os.path.join(sandbox_dir, "secret_utils.py"), "w", encoding="utf-8") as f:
        f.write('''
def operation_secrete(valeur):
    """
    Cette fonction effectue une opération critique :
    Elle multiplie la valeur par 999 et ajoute 1.
    """
    return (valeur * 999) + 1
''')

    # 2. Le Fichier Cible (qui utilise la dépendance)
    with open(os.path.join(sandbox_dir, "main_app.py"), "w", encoding="utf-8") as f:
        f.write('''
from secret_utils import operation_secrete

def process_data(data):
    # Appel de la fonction externe
    return operation_secrete(data)
''')
    
    print(f"✅ Sandbox créé : {sandbox_dir}")
    return sandbox_dir

def run_test():
    sandbox_dir = setup_sandbox()
    target_file = os.path.join(sandbox_dir, "main_app.py")
    
    print("\n🤖 Lancement de l'Agent WRITER (Mode Investigation)...")
    print("Instruction : Documente 'main_app.py'.")
    
    # Création de l'agent WRITER
    # Note : Assurez-vous que votre clé API est valide dans settings.json
    try:
        agent = create_agent("WRITER", reasoning_mode=False) # Mode normal (Fast) pour voir s'il utilise les outils
        
        prompt = (
            f"Documente le fichier '{target_file}'.\n"
            f"Explique PRÉCISÉMENT ce que fait la fonction 'process_data' en détail.\n"
            f"Si tu ne sais pas ce que fait 'operation_secrete', cherche la définition !"
        )
        
        # Exécution (La boucle autonome du Swarm va gérer les outils)
        response = agent.execute_task(prompt)
        
        # Affichage
        print("\n" + "="*50)
        print("📄 RÉSULTAT DE LA DOCUMENTATION :")
        print("="*50)
        final_text = response.text if hasattr(response, 'text') else str(response)
        print(final_text)
        print("="*50)
        
        # Vérification du succès
        if "999" in final_text or "multiplie" in final_text or "ajoute 1" in final_text:
            print("\n🎉 SUCCÈS : L'agent a lu 'secret_utils.py' et a trouvé la logique cachée !")
        else:
            print("\n⚠️ ÉCHEC : L'agent est resté en surface (pas de détails sur le calcul).")
            
    except Exception as e:
        print(f"\n❌ Erreur technique : {e}")

if __name__ == "__main__":
    run_test()
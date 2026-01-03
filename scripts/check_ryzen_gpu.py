import torch
import time
import sys
import os

# Ajouter le dossier parent au path pour importer ai_core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Utiliser le module d'init centralisé
try:
    from ai_core.hardware_init import init_hardware
    init_hardware()
except ImportError:
    # Fallback si lancé hors du repo
    if not hasattr(torch, 'int1'):
        torch.int1 = torch.int8
        torch.int2 = torch.int8
        torch.int4 = torch.int8

def check_hardware():
    print("="*50)
    print("🔍 DIAGNOSTIC MATÉRIEL RYZEN AI / GPU AMD")
    print("="*50)
    
    # 1. Vérification PyTorch standard
    print(f"🐍 Python version: {sys.version.split()[0]}")
    print(f"🔥 PyTorch version: {torch.__version__}")
    
    # 2. Vérification DirectML
    try:
        import torch_directml
        print("✅ Librairie 'torch-directml' détectée.")
        
        if torch_directml.is_available():
            device = torch_directml.device()
            device_name = torch_directml.device_name(0)
            print(f"🚀 ACCÉLÉRATION GPU ACTIVE : {device_name}")
            
            # Test de calcul
            print("\n🧪 Test de calcul sur GPU...")
            start = time.time()
            x = torch.ones((1000, 1000)).to(device)
            y = torch.matmul(x, x)
            _ = torch.sum(y).item()
            elapsed = time.time() - start
            print(f"✅ Test réussi en {elapsed:.4f}s")
            
        else:
            print("❌ DirectML est installé mais 'is_available()' retourne False.")
            print("💡 Vérifiez que vos drivers AMD Adrenalin sont à jour.")
            
    except ImportError:
        print("ℹ️ 'torch-directml' n'est pas installé.")
        device = torch.device("cpu")
        print(f"💻 Utilisation actuelle : CPU")

    # 3. Vérification TorchAO (Optimisation CPU)
    try:
        from torchao.quantization import quantize_
        print("\n✅ 'torchao' est maintenant compatible (via hardware_init).")
    except ImportError:
        print("\nℹ️ 'torchao' non installé.")
    except Exception as e:
        print(f"\n❌ Erreur TorchAO malgré le patch centralisé : {e}")

    # 4. Vérification Transformers
    try:
        from transformers import AutoConfig
        print("\n✅ 'transformers' est opérationnel.")
    except ImportError:
        print("\n❌ 'transformers' est MANQUANT ou CORROMPU.")

    print("\n" + "="*50)

if __name__ == "__main__":
    check_hardware()
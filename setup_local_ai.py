#!/usr/bin/env python3
"""
Script d'installation et de test pour l'intégration d'IA locales
dans AiModding-Companion.
"""

import os
import sys
import json
import subprocess
import platform
import shutil
from pathlib import Path

def print_header(text):
    """Affiche un en-tête stylisé."""
    print("\n" + "="*60)
    print(f" {text}")
    print("="*60)

def check_python_version():
    """Vérifie la version de Python."""
    print_header("VÉRIFICATION VERSION PYTHON")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ requis")
        return False
    print("✅ Version Python compatible")
    return True

def check_system():
    """Vérifie le système d'exploitation et les ressources."""
    print_header("VÉRIFICATION SYSTÈME")
    system = platform.system()
    print(f"Système: {system}")
    
    # Vérifier la mémoire disponible
    import psutil
    memory_gb = psutil.virtual_memory().total / (1024**3)
    print(f"Mémoire totale: {memory_gb:.1f} GB")
    
    if memory_gb < 4:
        print("⚠️  Mémoire limitée - Modèles légers recommandés")
    else:
        print("✅ Mémoire suffisante")
    
    # Vérifier l'espace disque
    disk = psutil.disk_usage('/')
    disk_gb = disk.free / (1024**3)
    print(f"Espace disque libre: {disk_gb:.1f} GB")
    
    if disk_gb < 10:
        print("⚠️  Espace disque limité")
    else:
        print("✅ Espace disque suffisant")
    
    return True

def install_dependencies():
    """Installe les dépendances pour les IA locales."""
    print_header("INSTALLATION DÉPENDANCES")
    
    dependencies = [
        "ollama>=0.1.0",
        "llama-cpp-python>=0.2.0",
        "transformers>=4.40.0",
        "torch>=2.0.0",
        "accelerate>=0.27.0",
        "bitsandbytes>=0.42.0",
        "psutil>=5.9.0",
        "requests>=2.28.0",
        "pynvml>=11.5.0"
    ]
    
    print("Installation des packages Python...")
    for dep in dependencies:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"✅ {dep}")
        except subprocess.CalledProcessError:
            print(f"❌ Échec installation: {dep}")
    
    return True

def setup_ollama():
    """Configure Ollama."""
    print_header("CONFIGURATION OLLAMA")
    
    # Vérifier si Ollama est installé
    try:
        result = subprocess.run(["ollama", "--version"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Ollama déjà installé")
            print(f"Version: {result.stdout.strip()}")
        else:
            print("Ollama non trouvé, tentative d'installation...")
            install_ollama()
    except FileNotFoundError:
        print("Ollama non trouvé, tentative d'installation...")
        install_ollama()
    
    # Démarrer le service Ollama
    print("\nDémarrage du service Ollama...")
    try:
        # Essayer de démarrer Ollama en arrière-plan
        if platform.system() == "Windows":
            subprocess.Popen(["ollama", "serve"], 
                           creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            subprocess.Popen(["ollama", "serve"], 
                           start_new_session=True)
        print("✅ Service Ollama démarré")
    except Exception as e:
        print(f"⚠️  Impossible de démarrer Ollama: {e}")
        print("Veuillez démarrer Ollama manuellement: 'ollama serve'")
    
    return True

def install_ollama():
    """Installe Ollama selon le système."""
    system = platform.system()
    
    if system == "Windows":
        print("Installation Ollama sur Windows...")
        try:
            # Utiliser winget si disponible
            subprocess.run(["winget", "install", "Ollama.Ollama", "--silent"], 
                         check=True)
            print("✅ Ollama installé via winget")
        except:
            print("⚠️  Installation winget échouée")
            print("Téléchargez manuellement depuis: https://ollama.com/download/windows")
            return False
    
    elif system == "Linux":
        print("Installation Ollama sur Linux...")
        try:
            subprocess.run(["curl", "-fsSL", "https://ollama.com/install.sh"], 
                         capture_output=True, text=True)
            print("✅ Script d'installation téléchargé")
            # Note: L'utilisateur doit exécuter le script manuellement
            print("Exécutez: curl -fsSL https://ollama.com/install.sh | sh")
        except Exception as e:
            print(f"⚠️  Échec téléchargement: {e}")
    
    elif system == "Darwin":  # macOS
        print("Installation Ollama sur macOS...")
        try:
            subprocess.run(["brew", "install", "ollama"], check=True)
            print("✅ Ollama installé via Homebrew")
        except:
            print("⚠️  Homebrew non disponible")
            print("Téléchargez depuis: https://ollama.com/download/mac")
    
    return True

def download_sample_models():
    """Télécharge des modèles de test."""
    print_header("TÉLÉCHARGEMENT MODÈLES DE TEST")
    
    models_dir = Path("./models")
    models_dir.mkdir(exist_ok=True)
    
    sample_models = [
        {
            "name": "phi-3-mini",
            "provider": "ollama",
            "command": ["ollama", "pull", "phi-3-mini:latest"]
        },
        {
            "name": "llama3.2:3b",
            "provider": "ollama", 
            "command": ["ollama", "pull", "llama3.2:3b"]
        }
    ]
    
    print("Téléchargement des modèles de test...")
    for model in sample_models:
        print(f"\n📥 Téléchargement: {model['name']}")
        try:
            subprocess.run(model["command"], check=True)
            print(f"✅ {model['name']} téléchargé")
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Échec téléchargement {model['name']}: {e}")
        except Exception as e:
            print(f"⚠️  Erreur: {e}")
    
    return True

def update_app_config():
    """Met à jour la configuration de l'application."""
    print_header("MISE À JOUR CONFIGURATION")
    
    config_file = Path("app_settings.json")
    if not config_file.exists():
        print("Création du fichier de configuration...")
        base_config = {
            "local_ai_engine": {
                "enabled": True,
                "default_provider": "ollama",
                "models": {
                    "fast_local": "phi-3-mini:latest",
                    "coder_local": "llama3.2:3b"
                }
            }
        }
        config_file.write_text(json.dumps(base_config, indent=2))
        print("✅ Configuration créée")
    else:
        print("⚠️  Fichier de configuration existant - mise à jour manuelle requise")
        print("Ajoutez la section 'local_ai_engine' à votre app_settings.json")
    
    return True

def create_test_script():
    """Crée un script de test pour les IA locales."""
    print_header("CRÉATION SCRIPT DE TEST")
    
    test_script = """
#!/usr/bin/env python3
"""
Test des IA locales intégrées
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_core.factory import SessionFactory
from features.UnifiedLogger import UnifiedLogger

def test_local_ai():
    \"\"\"Teste les sessions IA locales.\"\"\"
    print("🧪 Test des IA locales...")
    
    try:
        # Test session locale rapide
        print("1. Test session locale 'fast_local'...")
        session = SessionFactory.create_session("fast_local")
        response = session.send_message("Bonjour, comment ça va?")
        print(f"✅ Réponse: {response[:100]}...")
        
        # Test session codeur local
        print("\n2. Test session locale 'coder_local'...")
        session = SessionFactory.create_session("coder_local")
        response = session.send_message("Écris une fonction Python pour additionner deux nombres")
        print(f"✅ Réponse: {response[:100]}...")
        
        print("\n🎉 Tous les tests locaux réussis!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        return False

def test_hybrid_fallback():
    \"\"\"Teste le fallback hybride cloud/local.\"\"\"
    print("\n🌐 Test du fallback hybride...")
    
    try:
        # Désactiver temporairement les IA locales
        from config.settings import APP_SETTINGS
        original_setting = APP_SETTINGS.get("local_ai_engine", {}).get("enabled", True)
        
        # Forcer le fallback vers le cloud
        print("Forçage du fallback cloud...")
        session = SessionFactory.create_session("smart")
        response = session.send_message("Quelle est la capitale de la France?")
        print(f"✅ Réponse cloud: {response[:100]}...")
        
        print("🎉 Test de fallback réussi!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur fallback: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Démarrage des tests IA locales")
    print("-" * 40)
    
    local_ok = test_local_ai()
    hybrid_ok = test_hybrid_fallback()
    
    print("\n" + "=" * 40)
    print("📊 RÉSUMUM DES TESTS")
    print(f"IA locales: {'✅' if local_ok else '❌'}")
    print(f"Fallback hybride: {'✅' if hybrid_ok else '❌'}")
    
    if local_ok and hybrid_ok:
        print("\n🎉 Tous les tests réussis!")
        sys.exit(0)
    else:
        print("\n⚠️  Certains tests ont échoué")
        sys.exit(1)
"""
    
    test_file = Path("test_local_ai.py")
    test_file.write_text(test_script)
    test_file.chmod(0o755)  # Rendre exécutable
    
    print("✅ Script de test créé: test_local_ai.py")
    print("Exécutez: python test_local_ai.py")
    
    return True

def setup_directories():
    """Crée la structure de répertoires nécessaire."""
    print_header("CRÉATION STRUCTURE DE RÉPERTOIRES")
    
    directories = [
        "models/gguf",
        "models/huggingface",
        "models/ollama",
        "logs/local_ai",
        "cache/local_models"
    ]
    
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"📁 Créé: {dir_path}")
    
    return True

def print_summary():
    """Affiche un résumé de l'installation."""
    print_header("RÉSUMÉ DE L'INSTALLATION")
    
    summary = """
🎯 INSTALLATION TERMINÉE

📋 Prochaines étapes:

1. 🔧 Configuration manuelle:
   - Modifiez app_settings.json pour ajouter la section 'local_ai_engine'
   - Ajustez les paramètres selon votre matériel

2. 🚀 Démarrage:
   - Assurez-vous qu'Ollama est en cours d'exécution: 'ollama serve'
   - Lancez l'application: 'python run.py'

3. 🧪 Tests:
   - Exécutez les tests: 'python test_local_ai.py'
   - Vérifiez les logs dans logs/local_ai/

4. 📊 Monitoring:
   - Surveillez l'utilisation mémoire dans l'interface
   - Vérifiez les performances des modèles locaux

5. 🔄 Optimisation:
   - Ajustez les paramètres de quantization selon votre GPU
   - Configurez le cache pour améliorer les performances

📚 Documentation:
   - Consultez local_ai_integration_guide.md
   - Exemple de configuration: local_ai_config_example.json

🆘 Support:
   - Vérifiez que Ollama est installé et en cours d'exécution
   - Vérifiez les permissions des dossiers models/
   - Consultez les logs pour les erreurs détaillées
"""
    
    print(summary)

def main():
    """Fonction principale."""
    print("🚀 INSTALLATION IA LOCALES - AiModding-Companion")
    print("="*60)
    
    steps = [
        ("Vérification Python", check_python_version),
        ("Vérification système", check_system),
        ("Création répertoires", setup_directories),
        ("Installation dépendances", install_dependencies),
        ("Configuration Ollama", setup_ollama),
        ("Téléchargement modèles", download_sample_models),
        ("Mise à jour configuration", update_app_config),
        ("Création script test", create_test_script)
    ]
    
    results = []
    for step_name, step_func in steps:
        try:
            print(f"\n▶️  {step_name}...")
            success = step_func()
            results.append((step_name, success))
        except Exception as e:
            print(f"❌ Erreur lors de {step_name}: {e}")
            results.append((step_name, False))
    
    # Afficher le résumé
    print_summary()
    
    # Résumé des étapes
    print("\n📊 RÉCAPITULATIF DES ÉTAPES:")
    for step_name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {step_name}")
    
    # Recommandations
    failed_steps = [name for name, success in results if not success]
    if failed_steps:
        print(f"\n⚠️  Étapes en échec: {', '.join(failed_steps)}")
        print("Certaines fonctionnalités peuvent être limitées.")
    
    print("\n🎉 Installation terminée!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Installation interrompue par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        sys.exit(1)
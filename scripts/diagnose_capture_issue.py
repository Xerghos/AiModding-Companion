"""
Script de diagnostic pour identifier pourquoi les payloads ne sont pas capturés.

Usage:
    python scripts/diagnose_capture_issue.py
"""

import sys
import os
import subprocess
from pathlib import Path

# Fix encoding pour Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def check_mitmproxy_running():
    """Vérifie si mitmproxy est en cours d'exécution."""
    print("1. Vérification si mitmproxy est en cours d'exécution...")
    try:
        # Sur Windows, utiliser tasklist
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq mitmdump.exe"],
                capture_output=True,
                text=True
            )
            if "mitmdump.exe" in result.stdout:
                print("   [OK] mitmproxy (mitmdump) est en cours d'execution")
                return True
            else:
                print("   [ERREUR] mitmproxy (mitmdump) n'est PAS en cours d'execution")
                print("      Demarrez-le avec: mitmdump -s scripts/capture_gemini_cli_mitmproxy.py")
                return False
        else:
            # Linux/Mac
            result = subprocess.run(
                ["pgrep", "-f", "mitmdump"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("   [OK] mitmproxy (mitmdump) est en cours d'execution")
                return True
            else:
                print("   [ERREUR] mitmproxy (mitmdump) n'est PAS en cours d'execution")
                print("      Demarrez-le avec: mitmdump -s scripts/capture_gemini_cli_mitmproxy.py")
                return False
    except Exception as e:
        print(f"   [WARN] Impossible de verifier: {e}")
        return None

def check_environment_variables():
    """Vérifie les variables d'environnement du proxy."""
    print("\n2. Vérification des variables d'environnement...")
    
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    
    issues = []
    
    if not http_proxy:
        issues.append("HTTP_PROXY non defini")
        print("   [ERREUR] HTTP_PROXY n'est pas defini")
    else:
        print(f"   [OK] HTTP_PROXY={http_proxy}")
        if "localhost:8080" not in http_proxy and "127.0.0.1:8080" not in http_proxy:
            issues.append(f"HTTP_PROXY pointe vers {http_proxy} au lieu de localhost:8080")
            print(f"   [WARN] HTTP_PROXY pointe vers {http_proxy} (attendu: localhost:8080)")
    
    if not https_proxy:
        issues.append("HTTPS_PROXY non defini")
        print("   [ERREUR] HTTPS_PROXY n'est pas defini")
    else:
        print(f"   [OK] HTTPS_PROXY={https_proxy}")
        if "localhost:8080" not in https_proxy and "127.0.0.1:8080" not in https_proxy:
            issues.append(f"HTTPS_PROXY pointe vers {https_proxy} au lieu de localhost:8080")
            print(f"   [WARN] HTTPS_PROXY pointe vers {https_proxy} (attendu: localhost:8080)")
    
    if issues:
        print("\n   💡 Pour définir les variables (Windows):")
        print("      set HTTP_PROXY=http://localhost:8080")
        print("      set HTTPS_PROXY=http://localhost:8080")
        print("\n   💡 Pour définir les variables (Linux/Mac):")
        print("      export HTTP_PROXY=http://localhost:8080")
        print("      export HTTPS_PROXY=http://localhost:8080")
        print("\n   ⚠️  IMPORTANT: Définissez-les dans le MÊME terminal où vous exécutez gemini-cli")
    
    return len(issues) == 0

def check_gemini_cli():
    """Vérifie si gemini-cli est installé et accessible."""
    print("\n3. Vérification de gemini-cli...")
    
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["where", "gemini-cli"],
                capture_output=True,
                text=True
            )
        else:
            result = subprocess.run(
                ["which", "gemini-cli"],
                capture_output=True,
                text=True
            )
        
        if result.returncode == 0:
            path = result.stdout.strip().split('\n')[0]
            print(f"   [OK] gemini-cli trouve: {path}")
            
            # Vérifier la version
            try:
                version_result = subprocess.run(
                    ["gemini-cli", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if version_result.returncode == 0:
                    print(f"   [OK] Version: {version_result.stdout.strip()}")
                else:
                    print("   [WARN] Impossible d'obtenir la version")
            except Exception as e:
                print(f"   [WARN] Erreur lors de la verification de version: {e}")
            
            return True
        else:
            print("   [ERREUR] gemini-cli n'est pas trouve dans le PATH")
            print("      Verifiez qu'il est installe et accessible")
            return False
    except Exception as e:
        print(f"   [WARN] Erreur lors de la verification: {e}")
        return None

def check_logs_directory():
    """Vérifie le dossier logs et compte les fichiers capturés."""
    print("\n4. Vérification du dossier logs...")
    
    logs_dir = Path(__file__).parent.parent / "logs"
    
    if not logs_dir.exists():
        print(f"   [WARN] Dossier logs n'existe pas: {logs_dir}")
        logs_dir.mkdir(exist_ok=True)
        print(f"   [OK] Dossier logs cree")
        return False
    
    print(f"   [OK] Dossier logs existe: {logs_dir}")
    
    # Compter les fichiers
    tool_call_files = list(logs_dir.glob("gemini_cli_tool_call_*.json"))
    request_files = list(logs_dir.glob("gemini_cli_request_*.json"))
    all_files = list(logs_dir.glob("gemini_cli_*.json"))
    
    print(f"   📊 Fichiers capturés:")
    print(f"      - Tool calls: {len(tool_call_files)}")
    print(f"      - Autres requêtes: {len(request_files)}")
    print(f"      - Total: {len(all_files)}")
    
    if len(all_files) == 0:
        print("   [WARN] Aucun fichier capture - le proxy n'a peut-etre pas intercepte de requetes")
        return False
    
    # Afficher les fichiers les plus récents
    if all_files:
        all_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        print(f"\n   📄 Fichiers les plus récents:")
        for f in all_files[:3]:
            mtime = os.path.getmtime(f)
            from datetime import datetime
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            print(f"      - {f.name} ({mtime_str})")
    
    return True

def check_mitmproxy_installation():
    """Vérifie si mitmproxy est installé."""
    print("\n5. Vérification de l'installation mitmproxy...")
    
    try:
        import mitmproxy
        version = getattr(mitmproxy, '__version__', 'unknown')
        print(f"   [OK] mitmproxy est installe (version: {version})")
        return True
    except ImportError:
        print("   [ERREUR] mitmproxy n'est pas installe")
        print("      Installez-le avec: pip install mitmproxy")
        return False

def check_certificate():
    """Vérifie si le certificat mitmproxy est mentionné."""
    print("\n6. Verification du certificat mitmproxy...")
    print("   [INFO] Pour HTTPS, le certificat mitmproxy doit etre installe")
    print("      1. Ouvrir http://mitm.it dans votre navigateur")
    print("      2. Telecharger le certificat pour votre OS")
    print("      3. Installer le certificat (sur Windows: dans 'Autorites de certification racines')")
    print("      4. Redemarrer gemini-cli apres l'installation")
    print()
    print("   [INFO] Si vous utilisez seulement HTTP (pas HTTPS), le certificat n'est pas necessaire")

def main():
    """Fonction principale de diagnostic."""
    print("=" * 80)
    print("DIAGNOSTIC DE CAPTURE PAYLOADS GEMINI-CLI")
    print("=" * 80)
    print()
    
    results = {
        "mitmproxy_running": check_mitmproxy_running(),
        "environment_ok": check_environment_variables(),
        "gemini_cli_ok": check_gemini_cli(),
        "logs_ok": check_logs_directory(),
        "mitmproxy_installed": check_mitmproxy_installation()
    }
    
    check_certificate()
    
    print("\n" + "=" * 80)
    print("RÉSUMÉ DU DIAGNOSTIC")
    print("=" * 80)
    print()
    
    all_ok = all(v for v in results.values() if v is not None)
    
    if all_ok:
        print("[OK] Tous les tests passent!")
        print()
        print("[INFO] Si rien n'est toujours capture:")
        print("   1. Verifiez que gemini-cli est execute dans le MEME terminal ou les variables sont definies")
        print("   2. Verifiez que gemini-cli utilise bien le proxy (regardez les logs de mitmproxy)")
        print("   3. Essayez une commande simple: gemini-cli \"Hello\"")
        print("   4. Verifiez les logs de mitmproxy pour voir toutes les requetes interceptees")
    else:
        print("[ERREUR] Des problemes ont ete detectes:")
        print()
        for key, value in results.items():
            if value is False:
                print(f"   - {key.replace('_', ' ').title()}: PROBLEME")
            elif value is True:
                print(f"   - {key.replace('_', ' ').title()}: OK")
        
        print()
        print("[INFO] Corrigez les problemes ci-dessus et reessayez")
    
    print()
    print("=" * 80)
    print("📚 Documentation: scripts/README_capture_payloads.md")
    print("=" * 80)

if __name__ == "__main__":
    main()

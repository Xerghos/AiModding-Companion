"""
Test simple pour vérifier que mitmproxy fonctionne et capture les requêtes.

Usage:
    python scripts/test_proxy_mitmproxy.py
"""

import requests
import sys
import os

# Fix encoding pour Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def test_proxy():
    """Teste que le proxy mitmproxy fonctionne."""
    print("=" * 80)
    print("TEST DU PROXY MITMPROXY")
    print("=" * 80)
    print()
    
    proxy_url = "http://localhost:8080"
    
    print(f"1. Test sans proxy (requête directe)...")
    try:
        response = requests.get("http://httpbin.org/ip", timeout=5)
        print(f"   [OK] Requête directe réussie - IP: {response.json().get('origin', 'unknown')}")
    except Exception as e:
        print(f"   [ERREUR] Requête directe échouée: {e}")
        return False
    
    print()
    print(f"2. Test avec proxy {proxy_url}...")
    try:
        response = requests.get(
            "http://httpbin.org/ip",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=5
        )
        print(f"   [OK] Requête via proxy réussie - IP: {response.json().get('origin', 'unknown')}")
        print(f"   ✅ Le proxy fonctionne!")
        return True
    except requests.exceptions.ProxyError as e:
        print(f"   [ERREUR] Le proxy n'est pas accessible: {e}")
        print(f"   💡 Vérifiez que mitmproxy est démarré:")
        print(f"      mitmdump -s scripts/capture_gemini_cli_mitmproxy.py")
        return False
    except Exception as e:
        print(f"   [ERREUR] Erreur lors de la requête: {e}")
        return False

def test_https_proxy():
    """Teste le proxy avec HTTPS."""
    print()
    print(f"3. Test HTTPS avec proxy (nécessite le certificat mitmproxy)...")
    proxy_url = "http://localhost:8080"
    
    try:
        # Désactiver la vérification SSL pour le test (mitmproxy utilise son propre certificat)
        response = requests.get(
            "https://httpbin.org/ip",
            proxies={"http": proxy_url, "https": proxy_url},
            verify=False,  # Ignorer la vérification SSL car mitmproxy utilise son propre certificat
            timeout=5
        )
        print(f"   [OK] Requête HTTPS via proxy réussie - IP: {response.json().get('origin', 'unknown')}")
        print(f"   ✅ Le proxy HTTPS fonctionne!")
        return True
    except requests.exceptions.SSLError as e:
        print(f"   [ERREUR] Erreur SSL: {e}")
        print(f"   💡 Installez le certificat mitmproxy:")
        print(f"      1. Ouvrir http://mitm.it dans votre navigateur")
        print(f"      2. Télécharger et installer le certificat")
        return False
    except Exception as e:
        print(f"   [ERREUR] Erreur lors de la requête HTTPS: {e}")
        return False

def check_environment():
    """Vérifie les variables d'environnement."""
    print()
    print("4. Vérification des variables d'environnement...")
    
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    
    if http_proxy:
        print(f"   [OK] HTTP_PROXY={http_proxy}")
    else:
        print(f"   [WARN] HTTP_PROXY non défini")
    
    if https_proxy:
        print(f"   [OK] HTTPS_PROXY={https_proxy}")
    else:
        print(f"   [WARN] HTTPS_PROXY non défini")
    
    print()
    print("   💡 Pour définir les variables (Windows PowerShell):")
    print("      $env:HTTP_PROXY='http://localhost:8080'")
    print("      $env:HTTPS_PROXY='http://localhost:8080'")
    print()
    print("   💡 Pour définir les variables (Windows CMD):")
    print("      set HTTP_PROXY=http://localhost:8080")
    print("      set HTTPS_PROXY=http://localhost:8080")

if __name__ == "__main__":
    print()
    print("[IMPORTANT] Assurez-vous que mitmproxy est demarre avant de lancer ce test!")
    print("   mitmdump -s scripts/capture_gemini_cli_mitmproxy.py")
    print()
    try:
        input("Appuyez sur Entree pour continuer...")
    except:
        pass
    print()
    
    http_ok = test_proxy()
    https_ok = test_https_proxy()
    check_environment()
    
    print()
    print("=" * 80)
    print("RESUME")
    print("=" * 80)
    print()
    
    if http_ok and https_ok:
        print("[OK] Tous les tests passent! Le proxy fonctionne correctement.")
        print()
        print("[INFO] Si gemini-cli ne passe toujours pas par le proxy:")
        print("   1. Verifiez que gemini-cli est execute dans le MEME terminal ou les variables sont definies")
        print("   2. Verifiez que gemini-cli respecte les variables HTTP_PROXY/HTTPS_PROXY")
        print("   3. Essayez de redemarrer gemini-cli apres avoir defini les variables")
        print("   4. Utilisez le script PowerShell: .\\scripts\\verifier_proxy_gemini_cli.ps1")
    else:
        print("[ERREUR] Certains tests ont echoue.")
        print()
        print("[INFO] Solutions:")
        if not http_ok:
            print("   - Demarrer mitmproxy: mitmdump -s scripts/capture_gemini_cli_mitmproxy.py")
        if not https_ok:
            print("   - Installer le certificat mitmproxy depuis http://mitm.it")

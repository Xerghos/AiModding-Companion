"""
Script de test pour vérifier que le proxy fonctionne correctement.
Teste la connexion et affiche des informations de diagnostic.

Usage:
    python scripts/test_proxy_connection.py [proxy_url]
"""

import sys
import requests
from pathlib import Path

def test_proxy(proxy_url: str = "http://localhost:8080"):
    """Teste la connexion au proxy."""
    print("=" * 80)
    print("TEST DE CONNEXION PROXY")
    print("=" * 80)
    print()
    
    print(f"🔍 Test du proxy: {proxy_url}")
    print()
    
    # Test 1: Vérifier que le proxy répond
    print("1. Test de connexion au proxy...")
    try:
        response = requests.get("http://httpbin.org/ip", proxies={"http": proxy_url, "https": proxy_url}, timeout=5)
        print(f"   ✅ Proxy accessible - IP: {response.json().get('origin', 'unknown')}")
    except requests.exceptions.ProxyError:
        print(f"   ❌ Erreur: Le proxy n'est pas accessible sur {proxy_url}")
        print(f"      Vérifiez que mitmproxy est démarré:")
        print(f"      mitmdump -s scripts/capture_gemini_cli_mitmproxy.py")
        return False
    except requests.exceptions.Timeout:
        print(f"   ❌ Timeout: Le proxy ne répond pas")
        return False
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False
    
    print()
    
    # Test 2: Vérifier les variables d'environnement
    print("2. Vérification des variables d'environnement...")
    import os
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    
    if http_proxy:
        print(f"   ✅ HTTP_PROXY={http_proxy}")
    else:
        print(f"   ⚠️  HTTP_PROXY non défini")
        print(f"      Windows: set HTTP_PROXY={proxy_url}")
        print(f"      Linux/Mac: export HTTP_PROXY={proxy_url}")
    
    if https_proxy:
        print(f"   ✅ HTTPS_PROXY={https_proxy}")
    else:
        print(f"   ⚠️  HTTPS_PROXY non défini")
        print(f"      Windows: set HTTPS_PROXY={proxy_url}")
        print(f"      Linux/Mac: export HTTPS_PROXY={proxy_url}")
    
    print()
    
    # Test 3: Vérifier le dossier logs
    print("3. Vérification du dossier logs...")
    logs_dir = Path(__file__).parent.parent / "logs"
    if logs_dir.exists():
        print(f"   ✅ Dossier logs existe: {logs_dir}")
        
        # Compter les fichiers capturés
        tool_call_files = list(logs_dir.glob("gemini_cli_tool_call_*.json"))
        request_files = list(logs_dir.glob("gemini_cli_request_*.json"))
        print(f"   📊 Fichiers capturés: {len(tool_call_files)} tool calls, {len(request_files)} autres requêtes")
    else:
        print(f"   ⚠️  Dossier logs n'existe pas: {logs_dir}")
        logs_dir.mkdir(exist_ok=True)
        print(f"   ✅ Dossier logs créé")
    
    print()
    
    # Test 4: Vérifier mitmproxy
    print("4. Vérification de mitmproxy...")
    try:
        import mitmproxy
        print(f"   ✅ mitmproxy installé (version: {mitmproxy.__version__ if hasattr(mitmproxy, '__version__') else 'unknown'})")
    except ImportError:
        print(f"   ❌ mitmproxy n'est pas installé")
        print(f"      Installez-le avec: pip install mitmproxy")
        return False
    
    print()
    print("=" * 80)
    print("✅ TESTS TERMINÉS")
    print("=" * 80)
    print()
    print("💡 Si tous les tests passent mais rien n'est capturé:")
    print("   1. Vérifiez que gemini-cli utilise bien le proxy")
    print("   2. Vérifiez que le certificat mitmproxy est installé (pour HTTPS)")
    print("   3. Exécutez gemini-cli dans le même terminal où les variables sont définies")
    print("   4. Vérifiez les logs de mitmproxy pour voir les requêtes interceptées")
    print()
    
    return True


if __name__ == "__main__":
    proxy_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    test_proxy(proxy_url)

"""
Script d'aide pour configurer rapidement la capture de payloads gemini-cli.
Affiche les instructions et vérifie les prérequis.

Usage:
    python scripts/quick_capture_setup.py
"""

import sys
from pathlib import Path

def check_mitmproxy():
    """Vérifie si mitmproxy est installé."""
    try:
        import mitmproxy
        return True, None
    except ImportError:
        return False, "pip install mitmproxy"

def check_logs_dir():
    """Vérifie que le dossier logs existe."""
    logs_dir = Path(__file__).parent.parent / "logs"
    if logs_dir.exists():
        return True, str(logs_dir)
    else:
        logs_dir.mkdir(exist_ok=True)
        return True, str(logs_dir)

def main():
    """Affiche les instructions de configuration."""
    print("=" * 80)
    print("CONFIGURATION CAPTURE PAYLOADS GEMINI-CLI")
    print("=" * 80)
    print()
    
    # Vérifier mitmproxy
    mitm_installed, mitm_cmd = check_mitmproxy()
    logs_ok, logs_path = check_logs_dir()
    
    print("📋 VÉRIFICATION DES PRÉREQUIS")
    print("-" * 80)
    
    if mitm_installed:
        print("✅ mitmproxy est installé")
        method = "mitmproxy (recommandé)"
    else:
        print("❌ mitmproxy n'est pas installé")
        print(f"   Installez-le avec: {mitm_cmd}")
        method = "proxy HTTP simple (limité)"
    
    if logs_ok:
        print(f"✅ Dossier logs: {logs_path}")
    else:
        print(f"❌ Impossible de créer le dossier logs")
    
    print()
    print("=" * 80)
    print("INSTRUCTIONS DE CAPTURE")
    print("=" * 80)
    print()
    
    if mitm_installed:
        print("🚀 MÉTHODE RECOMMANDÉE: mitmproxy")
        print("-" * 80)
        print()
        print("1. Démarrer le proxy mitmproxy:")
        print("   mitmdump -s scripts/capture_gemini_cli_mitmproxy.py")
        print()
        print("2. Installer le certificat mitmproxy (pour HTTPS):")
        print("   - Ouvrir http://mitm.it dans votre navigateur")
        print("   - Télécharger le certificat pour votre OS")
        print("   - Installer le certificat (sur Windows: dans 'Autorités de certification racines')")
        print()
        print("3. Configurer gemini-cli:")
        print("   Windows:")
        print("     set HTTP_PROXY=http://localhost:8080")
        print("     set HTTPS_PROXY=http://localhost:8080")
        print()
        print("   Linux/Mac:")
        print("     export HTTP_PROXY=http://localhost:8080")
        print("     export HTTPS_PROXY=http://localhost:8080")
        print()
        print("4. Exécuter une commande avec tool call:")
        print("   gemini-cli \"Lis le fichier README.md et résume-le\"")
        print()
        print("5. Analyser les payloads capturés:")
        print("   python scripts/analyze_gemini_cli_tool_payloads.py --compare --detailed")
        print()
    else:
        print("⚠️  MÉTHODE ALTERNATIVE: Proxy HTTP simple")
        print("-" * 80)
        print()
        print("⚠️  LIMITATION: Cette méthode ne gère pas correctement HTTPS.")
        print("   Certaines requêtes peuvent échouer.")
        print()
        print("1. Démarrer le proxy:")
        print("   python scripts/capture_gemini_cli_http_proxy.py")
        print()
        print("2. Configurer gemini-cli:")
        print("   set HTTP_PROXY=http://localhost:8888")
        print()
        print("3. Exécuter une commande avec tool call")
        print()
    
    print("=" * 80)
    print("FICHIERS GÉNÉRÉS")
    print("=" * 80)
    print()
    print("Pendant la capture:")
    print(f"  - {logs_path}/gemini_cli_tool_call_*.json (tool calls)")
    print(f"  - {logs_path}/gemini_cli_request_*.json (autres requêtes)")
    print()
    print("Après l'analyse:")
    print(f"  - {logs_path}/analysis_reports/gemini_cli_analysis_*.json")
    print()
    
    print("=" * 80)
    print("POINTS À VÉRIFIER DANS LES PAYLOADS")
    print("=" * 80)
    print()
    print("1. IDs dans functionCall:")
    print("   - Sont-ils toujours présents ?")
    print("   - Format des IDs (UUID v4, autres)")
    print("   - Que se passe-t-il quand il n'y a pas d'ID ?")
    print()
    print("2. thoughtSignature:")
    print("   - Est-il présent dans les réponses de l'API ?")
    print("   - Est-il réinjecté dans les requêtes suivantes ?")
    print("   - Où se trouve-t-il exactement ?")
    print()
    print("3. Format functionResponse:")
    print("   - Utilise-t-il response.output ou response.content ?")
    print("   - Structure exacte de l'objet response")
    print()
    print("4. Séquence dans contents:")
    print("   - Ordre exact: user → model (functionCall) → function (functionResponse)")
    print()
    print("5. Corrélation ID:")
    print("   - Les IDs correspondent-ils toujours ?")
    print("   - Que se passe-t-il si l'un ou l'autre n'a pas d'ID ?")
    print()
    
    print("=" * 80)
    print("📚 Documentation complète: scripts/README_capture_payloads.md")
    print("=" * 80)

if __name__ == "__main__":
    main()

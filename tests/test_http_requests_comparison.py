"""
Tests pour comparer les requêtes HTTP directes avec google-auth.
Objectif: Vérifier si utiliser google-auth (comme gemini-cli) résout les problèmes.
"""

import os
import sys
import json
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_1_google_auth_import():
    """Test 1: Vérifier l'import de google-auth."""
    print("\n" + "="*80)
    print("TEST 1: Import google-auth")
    print("="*80)
    
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        print("[OK] google-auth importé avec succès")
        return True, Request, Credentials
    except ImportError as e:
        print(f"[FAIL] google-auth non installé: {e}")
        print("   Installation requise: pip install google-auth")
        return False, None, None

def test_2_load_credentials():
    """Test 2: Charger les credentials OAuth."""
    print("\n" + "="*80)
    print("TEST 2: Chargement credentials OAuth")
    print("="*80)
    
    token_path = os.path.join(
        os.path.expanduser("~"),
        ".config",
        "google",
        "gemini_oauth_token.json"
    )
    
    if not os.path.exists(token_path):
        print(f"[FAIL] Fichier de credentials non trouvé: {token_path}")
        return False, None
    
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        creds = Credentials.from_authorized_user_file(token_path)
        
        # Rafraîchir si nécessaire
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                print("[OK] Credentials rafraîchis")
        
        print("[OK] Credentials chargés et valides")
        return True, creds
        
    except Exception as e:
        print(f"[FAIL] Erreur: {e}")
        return False, None

def test_3_compare_headers():
    """Test 3: Comparer les headers générés par requests vs google-auth."""
    print("\n" + "="*80)
    print("TEST 3: Comparaison des headers")
    print("="*80)
    
    success, creds = test_2_load_credentials()
    if not success:
        print("[WARN] Impossible de tester sans credentials")
        return False
    
    # Méthode 1: requests (actuelle)
    import requests
    headers_requests = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json"
    }
    
    # Méthode 2: google-auth (comme gemini-cli)
    from google.auth.transport.requests import Request as AuthRequest
    headers_google_auth = {
        "Content-Type": "application/json"
    }
    creds.apply(headers_google_auth)
    
    print("Headers avec requests:")
    print(json.dumps(headers_requests, indent=2))
    
    print("\nHeaders avec google-auth:")
    print(json.dumps(headers_google_auth, indent=2))
    
    # Comparaison
    print("\nComparaison:")
    print(f"  Authorization présent (requests): {'Authorization' in headers_requests}")
    print(f"  Authorization présent (google-auth): {'Authorization' in headers_google_auth}")
    print(f"  Tokens identiques: {headers_requests.get('Authorization') == headers_google_auth.get('Authorization')}")
    
    # Vérifier si google-auth ajoute d'autres headers
    extra_headers = set(headers_google_auth.keys()) - set(headers_requests.keys())
    if extra_headers:
        print(f"  Headers additionnels (google-auth): {extra_headers}")
    else:
        print("  Aucun header additionnel détecté")
    
    return True

def test_4_test_request_structure():
    """Test 4: Tester la structure d'une requête complète."""
    print("\n" + "="*80)
    print("TEST 4: Structure de requête complète")
    print("="*80)
    
    success, creds = test_2_load_credentials()
    if not success:
        print("[WARN] Impossible de tester sans credentials")
        return False
    
    # Créer un payload de test
    from ai_core.code_assist_converter import to_generate_content_request
    
    payload = to_generate_content_request(
        model="gemini-3-flash-preview",
        messages=[{"role": "user", "content": "Test"}],
        user_prompt_id="test-http-123",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "test_func",
                    "description": "Test function",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ],
        temperature=0.7
    )
    
    print("Payload à envoyer:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    # Vérifier la structure
    request = payload.get("request", {})
    checks = {
        "toolConfig présent": "toolConfig" in request,
        "tools présent": "tools" in request,
    }
    
    print("\nVérifications:")
    for check, result in checks.items():
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {check}")
    
    # Note: On ne fait pas de vraie requête HTTP ici, juste la préparation
    print("\n[WARN] Note: Aucune requête HTTP réelle n'est effectuée")
    print("   Ce test vérifie uniquement la structure du payload")
    
    return True

def test_5_simulate_gemini_cli_request():
    """Test 5: Simuler exactement ce que fait gemini-cli."""
    print("\n" + "="*80)
    print("TEST 5: Simulation requête gemini-cli")
    print("="*80)
    
    success, creds = test_2_load_credentials()
    if not success:
        print("[WARN] Impossible de tester sans credentials")
        return False
    
    # Structure exacte selon server.ts de gemini-cli
    endpoint = "https://cloudcode-pa.googleapis.com"
    api_version = "v1internal"
    method = "generateContent"
    url = f"{endpoint}/{api_version}:{method}"
    
    # Payload
    from ai_core.code_assist_converter import to_generate_content_request
    
    payload = to_generate_content_request(
        model="gemini-3-flash-preview",
        messages=[{"role": "user", "content": "Test simulation"}],
        user_prompt_id="sim-test-123",
        session_id="sim-session-456",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "test",
                    "description": "Test",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
    )
    
    # Headers comme gemini-cli (via google-auth)
    from google.auth.transport.requests import Request as AuthRequest
    headers = {
        "Content-Type": "application/json"
    }
    creds.apply(headers)
    
    print("URL:")
    print(f"  {url}")
    
    print("\nHeaders (comme gemini-cli):")
    print(json.dumps(headers, indent=2))
    
    print("\nPayload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    # Vérifications critiques
    request = payload.get("request", {})
    critical_checks = {
        "toolConfig présent": "toolConfig" in request,
        "toolConfig.functionCallingConfig présent": (
            "toolConfig" in request and
            "functionCallingConfig" in request.get("toolConfig", {})
        ),
        "Authorization header présent": "Authorization" in headers or "authorization" in headers,
    }
    
    print("\nVérifications critiques:")
    all_ok = True
    for check, result in critical_checks.items():
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {check}")
        if not result:
            all_ok = False
    
    if not all_ok:
        print("\n[CRITICAL] PROBLÈMES DÉTECTÉS qui pourraient causer des erreurs 500!")
    
    return all_ok

def main():
    """Exécuter tous les tests."""
    print("\n" + "="*80)
    print("SUITE DE TESTS: Comparaison requêtes HTTP")
    print("="*80)
    
    results = {}
    
    # Test 1: Import
    results['import'] = test_1_google_auth_import()
    if not results['import'][0]:
        print("\n[FAIL] Arrêt: google-auth non disponible")
        return
    
    # Test 2: Credentials
    results['creds'] = test_2_load_credentials()
    
    # Test 3: Headers
    if results['creds'][0]:
        results['headers'] = test_3_compare_headers()
    
    # Test 4: Structure
    if results['creds'][0]:
        results['structure'] = test_4_test_request_structure()
    
    # Test 5: Simulation gemini-cli
    if results['creds'][0]:
        results['simulation'] = test_5_simulate_gemini_cli_request()
    
    # Résumé
    print("\n" + "="*80)
    print("RÉSUMÉ DES TESTS")
    print("="*80)
    for test_name, result in results.items():
        if isinstance(result, tuple):
            status = "[OK]" if result[0] else "[FAIL]"
        else:
            status = "[OK]" if result else "[FAIL]"
        print(f"{status} {test_name}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()


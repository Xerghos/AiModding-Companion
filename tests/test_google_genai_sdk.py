"""
Tests pour vérifier l'utilisation du SDK google-genai avec CodeAssist.
Objectif: Vérifier si le SDK supporte l'endpoint cloudcode-pa et les credentials OAuth.
"""

import os
import sys
import json
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_1_import_sdk():
    """Test 1: Vérifier si google-genai est installé et importable."""
    print("\n" + "="*80)
    print("TEST 1: Import du SDK google-genai")
    print("="*80)
    
    try:
        from google import genai
        from google.genai import types
        print("[OK] SDK google-genai importé avec succès")
        print(f"   Version disponible: {genai.__version__ if hasattr(genai, '__version__') else 'N/A'}")
        return True, genai, types
    except ImportError as e:
        print(f"[FAIL] SDK google-genai non installé: {e}")
        print("   Installation requise: pip install google-genai")
        return False, None, None

def test_2_check_client_initialization():
    """Test 2: Vérifier les options d'initialisation du Client."""
    print("\n" + "="*80)
    print("TEST 2: Options d'initialisation du Client")
    print("="*80)
    
    try:
        from google import genai
        import inspect
        
        # Inspecter la signature du constructeur Client
        sig = inspect.signature(genai.Client.__init__)
        print("Paramètres du constructeur Client:")
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            default = f" = {param.default}" if param.default != inspect.Parameter.empty else ""
            print(f"  - {param_name}: {param.annotation}{default}")
        
        # Vérifier si api_endpoint ou base_url existe
        params = list(sig.parameters.keys())
        has_endpoint = any('endpoint' in p.lower() or 'url' in p.lower() or 'base' in p.lower() 
                          for p in params if p != 'self')
        
        if has_endpoint:
            print("\n[OK] Paramètre d'endpoint personnalisé détecté")
        else:
            print("\n[WARN] Aucun paramètre d'endpoint personnalisé détecté")
            print("   Vérification de la documentation nécessaire")
        
        return True
    except Exception as e:
        print(f"[FAIL] Erreur lors de l'inspection: {e}")
        return False

def test_3_load_oauth_credentials():
    """Test 3: Charger les credentials OAuth existants."""
    print("\n" + "="*80)
    print("TEST 3: Chargement des credentials OAuth")
    print("="*80)
    
    token_path = os.path.join(
        os.path.expanduser("~"),
        ".config",
        "google",
        "gemini_oauth_token.json"
    )
    
    print(f"Chemin des credentials: {token_path}")
    
    if not os.path.exists(token_path):
        print(f"[FAIL] Fichier de credentials non trouvé: {token_path}")
        print("   Authentification OAuth requise d'abord")
        return False, None
    
    try:
        with open(token_path, 'r') as f:
            creds_data = json.load(f)
        
        print("[OK] Credentials chargés")
        print(f"   Type: {creds_data.get('type', 'N/A')}")
        print(f"   Client ID présent: {'client_id' in creds_data}")
        print(f"   Refresh token présent: {'refresh_token' in creds_data}")
        print(f"   Access token présent: {'access_token' in creds_data}")
        
        # Essayer de charger avec google.oauth2
        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file(token_path)
            print("[OK] Credentials convertis en objet Credentials")
            return True, creds
        except Exception as e:
            print(f"[WARN] Erreur conversion Credentials: {e}")
            return True, creds_data
        
    except Exception as e:
        print(f"[FAIL] Erreur lors du chargement: {e}")
        return False, None

def test_4_try_client_with_oauth():
    """Test 4: Essayer d'initialiser le Client avec credentials OAuth."""
    print("\n" + "="*80)
    print("TEST 4: Initialisation Client avec OAuth")
    print("="*80)
    
    success, creds = test_3_load_oauth_credentials()
    if not success or not creds:
        print("[WARN] Impossible de tester sans credentials OAuth")
        return False
    
    try:
        from google import genai
        
        # Test 1: Avec credentials directement
        print("\nTentative 1: Client(credentials=creds)")
        try:
            if isinstance(creds, dict):
                from google.oauth2.credentials import Credentials
                creds_obj = Credentials.from_authorized_user_file(
                    os.path.join(os.path.expanduser("~"), ".config", "google", "gemini_oauth_token.json")
                )
            else:
                creds_obj = creds
            
            client = genai.Client(credentials=creds_obj)
            print("[OK] Client initialisé avec credentials")
            return True, client
        except Exception as e:
            print(f"[FAIL] Échec: {e}")
        
        # Test 2: Avec GOOGLE_APPLICATION_CREDENTIALS
        print("\nTentative 2: Via GOOGLE_APPLICATION_CREDENTIALS")
        try:
            token_path = os.path.join(
                os.path.expanduser("~"),
                ".config",
                "google",
                "gemini_oauth_token.json"
            )
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = token_path
            client = genai.Client()
            print("[OK] Client initialisé via variable d'environnement")
            return True, client
        except Exception as e:
            print(f"[FAIL] Échec: {e}")
        
        return False, None
        
    except Exception as e:
        print(f"[FAIL] Erreur: {e}")
        return False, None

def test_5_check_endpoint_support():
    """Test 5: Vérifier si on peut spécifier un endpoint personnalisé."""
    print("\n" + "="*80)
    print("TEST 5: Support endpoint personnalisé (cloudcode-pa)")
    print("="*80)
    
    success, client = test_4_try_client_with_oauth()
    if not success:
        print("[WARN] Impossible de tester sans client initialisé")
        return False
    
    try:
        from google import genai
        import inspect
        
        # Vérifier les méthodes du client
        methods = [m for m in dir(client) if not m.startswith('_')]
        print("Méthodes disponibles sur le client:")
        for method in methods[:10]:  # Premières 10
            print(f"  - {method}")
        
        # Vérifier si on peut accéder à un attribut base_url ou api_endpoint
        if hasattr(client, '_base_url') or hasattr(client, '_api_endpoint') or hasattr(client, 'base_url'):
            print("\n[OK] Attribut d'endpoint détecté")
            endpoint = getattr(client, '_base_url', None) or getattr(client, '_api_endpoint', None) or getattr(client, 'base_url', None)
            print(f"   Endpoint actuel: {endpoint}")
        else:
            print("\n[WARN] Aucun attribut d'endpoint détecté")
        
        # Essayer de créer un client avec un endpoint personnalisé
        print("\nTentative: Client avec endpoint personnalisé")
        try:
            # Tester différentes signatures possibles
            test_configs = [
                {"api_endpoint": "https://cloudcode-pa.googleapis.com"},
                {"base_url": "https://cloudcode-pa.googleapis.com"},
                {"endpoint": "https://cloudcode-pa.googleapis.com"},
            ]
            
            for config in test_configs:
                try:
                    success, creds = test_3_load_oauth_credentials()
                    if success and creds and isinstance(creds, dict):
                        from google.oauth2.credentials import Credentials
                        creds_obj = Credentials.from_authorized_user_file(
                            os.path.join(os.path.expanduser("~"), ".config", "google", "gemini_oauth_token.json")
                        )
                    else:
                        continue
                    
                    # Essayer avec chaque config
                    test_client = genai.Client(credentials=creds_obj, **config)
                    print(f"[OK] Client créé avec config: {config}")
                    return True, test_client
                except TypeError:
                    continue
                except Exception as e:
                    print(f"   Échec avec {config}: {e}")
            
            print("[FAIL] Aucune configuration d'endpoint personnalisé n'a fonctionné")
            return False, None
            
        except Exception as e:
            print(f"[FAIL] Erreur: {e}")
            return False, None
        
    except Exception as e:
        print(f"[FAIL] Erreur: {e}")
        return False, None

def test_6_check_toolconfig_structure():
    """Test 6: Vérifier la structure ToolConfig dans le SDK."""
    print("\n" + "="*80)
    print("TEST 6: Structure ToolConfig dans google-genai")
    print("="*80)
    
    try:
        from google.genai import types
        import inspect
        
        # Vérifier si ToolConfig existe
        if hasattr(types, 'ToolConfig'):
            print("[OK] types.ToolConfig existe")
            sig = inspect.signature(types.ToolConfig.__init__)
            print("Paramètres de ToolConfig:")
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                default = f" = {param.default}" if param.default != inspect.Parameter.empty else ""
                print(f"  - {param_name}: {param.annotation}{default}")
        else:
            print("[FAIL] types.ToolConfig n'existe pas")
            return False
        
        # Vérifier FunctionCallingConfig
        if hasattr(types, 'FunctionCallingConfig'):
            print("\n[OK] types.FunctionCallingConfig existe")
            sig = inspect.signature(types.FunctionCallingConfig.__init__)
            print("Paramètres de FunctionCallingConfig:")
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                default = f" = {param.default}" if param.default != inspect.Parameter.empty else ""
                print(f"  - {param_name}: {param.annotation}{default}")
        else:
            print("\n[FAIL] types.FunctionCallingConfig n'existe pas")
            return False
        
        # Essayer de créer un ToolConfig
        try:
            tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode='AUTO')
            )
            print("\n[OK] ToolConfig créé avec succès")
            print(f"   Représentation: {tool_config}")
            return True
        except Exception as e:
            print(f"\n[FAIL] Erreur création ToolConfig: {e}")
            return False
        
    except Exception as e:
        print(f"[FAIL] Erreur: {e}")
        return False

def main():
    """Exécuter tous les tests."""
    print("\n" + "="*80)
    print("SUITE DE TESTS: SDK google-genai avec CodeAssist")
    print("="*80)
    
    results = {}
    
    # Test 1: Import
    results['import'] = test_1_import_sdk()
    if not results['import'][0]:
        print("\n[FAIL] Arrêt: SDK non disponible")
        return
    
    # Test 2: Initialisation
    results['init'] = test_2_check_client_initialization()
    
    # Test 3: Credentials
    results['creds'] = test_3_load_oauth_credentials()
    
    # Test 4: Client avec OAuth
    results['client_oauth'] = test_4_try_client_with_oauth()
    
    # Test 5: Endpoint personnalisé
    results['endpoint'] = test_5_check_endpoint_support()
    
    # Test 6: ToolConfig
    results['toolconfig'] = test_6_check_toolconfig_structure()
    
    # Résumé
    print("\n" + "="*80)
    print("RÉSUMÉ DES TESTS")
    print("="*80)
    for test_name, result in results.items():
        status = "[OK]" if result else "[FAIL]"
        if isinstance(result, tuple):
            status = "[OK]" if result[0] else "[FAIL]"
        print(f"{status} {test_name}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()


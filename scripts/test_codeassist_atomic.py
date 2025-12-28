#!/usr/bin/env python3
"""
Tests Atomiques pour l'API CodeAssist v1internal.

Ce script exécute des tests séquentiels pour isoler la cause des erreurs 500.
Chaque test ajoute une couche de complexité pour identifier le vecteur de défaillance.

Usage:
    python scripts/test_codeassist_atomic.py

Ordre d'exécution recommandé:
    1. Test Baseline (sans outils)
    2. Test avec 1 outil (types MAJUSCULES)
    3. Test avec toolConfig
    4. Test avec plusieurs outils
    5. Test avec array d'objets imbriqués (bug connu)
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any

# Ajouter le chemin du projet
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from ai_core.oauth_validator import load_and_validate_oauth_credentials
    from google.auth.transport.requests import Request
except ImportError as e:
    print(f"❌ Erreur import: {e}")
    print("   Exécutez depuis la racine du projet: python scripts/test_codeassist_atomic.py")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

CODEASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com/v1internal"
TOKEN_PATH = os.path.join(os.path.expanduser("~"), ".config", "google", "gemini_oauth_token.json")
MODEL = "gemini-3-flash-preview"  # Modèle utilisé par gemini-cli (sans préfixe "models/")


# =============================================================================
# HELPERS
# =============================================================================

def get_access_token() -> Optional[str]:
    """Récupère un access token valide."""
    creds, error = load_and_validate_oauth_credentials(TOKEN_PATH)
    if creds is None:
        print(f"❌ Impossible de charger les credentials: {error}")
        return None
    
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    
    return creds.token if creds.valid else None


def make_request(payload: Dict[str, Any], stream: bool = False) -> tuple:
    """
    Effectue une requête vers l'API CodeAssist.
    
    Returns:
        (success: bool, status_code: int, response_text: str)
    """
    token = get_access_token()
    if not token:
        return False, 0, "Pas de token disponible"
    
    method = "streamGenerateContent" if stream else "generateContent"
    url = f"{CODEASSIST_ENDPOINT}:{method}"
    if stream:
        url += "?alt=sse"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        # Headers de blindage (mimant gemini-cli)
        "User-Agent": "GeminiCLI/0.2.2 (linux; x64)",
        "X-Goog-Api-Client": "gl-python/0.0.1",
    }
    
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60,
            stream=stream
        )
        
        if stream:
            # Lire juste le début du flux
            content = ""
            for i, line in enumerate(response.iter_lines()):
                if line:
                    content += line.decode('utf-8') + "\n"
                if i > 5:  # Limiter à 5 lignes
                    break
            return response.status_code == 200, response.status_code, content[:500]
        else:
            return response.status_code == 200, response.status_code, response.text[:500]
            
    except Exception as e:
        return False, 0, str(e)


def print_result(test_name: str, success: bool, status: int, message: str):
    """Affiche le résultat d'un test."""
    emoji = "✅" if success else "❌"
    print(f"\n{emoji} {test_name}")
    print(f"   Status: {status}")
    print(f"   Réponse: {message[:200]}...")


# =============================================================================
# TESTS ATOMIQUES
# =============================================================================

def test_1_baseline():
    """Test 1: Hello World sans outils (baseline)."""
    print("\n" + "="*60)
    print("TEST 1: Baseline (sans outils)")
    print("="*60)
    
    payload = {
        "model": MODEL,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Dis juste 'OK' si tu reçois ce message."}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7
            }
        }
    }
    
    success, status, response = make_request(payload)
    print_result("Baseline sans outils", success, status, response)
    return success


def test_2a_tool_lowercase():
    """Test 2A: Un outil simple avec types MINUSCULES (devrait échouer)."""
    print("\n" + "="*60)
    print("TEST 2A: Outil avec types minuscules (devrait échouer)")
    print("="*60)
    
    payload = {
        "model": MODEL,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Quelle heure est-il?"}]
                }
            ],
            "tools": [{
                "functionDeclarations": [{
                    "name": "get_time",
                    "description": "Retourne l'heure actuelle",
                    "parameters": {
                        "type": "object",  # MINUSCULE - devrait causer erreur 500
                        "properties": {
                            "timezone": {
                                "type": "string",  # MINUSCULE
                                "description": "Fuseau horaire"
                            }
                        }
                    }
                }]
            }],
            "generationConfig": {
                "temperature": 0.7
            }
        }
    }
    
    success, status, response = make_request(payload)
    print_result("Outil avec types minuscules", success, status, response)
    return success


def test_2b_tool_uppercase():
    """Test 2B: Un outil simple avec types MAJUSCULES (devrait réussir)."""
    print("\n" + "="*60)
    print("TEST 2B: Outil avec types MAJUSCULES")
    print("="*60)
    
    payload = {
        "model": MODEL,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Quelle heure est-il?"}]
                }
            ],
            "tools": [{
                "functionDeclarations": [{
                    "name": "get_time",
                    "description": "Retourne l'heure actuelle",
                    "parameters": {
                        "type": "OBJECT",  # MAJUSCULE
                        "properties": {
                            "timezone": {
                                "type": "STRING",  # MAJUSCULE
                                "description": "Fuseau horaire"
                            }
                        }
                    }
                }]
            }],
            "generationConfig": {
                "temperature": 0.7
            }
        }
    }
    
    success, status, response = make_request(payload)
    print_result("Outil avec types MAJUSCULES", success, status, response)
    return success


def test_3_with_toolconfig():
    """Test 3: Avec toolConfig (mode AUTO)."""
    print("\n" + "="*60)
    print("TEST 3: Avec toolConfig")
    print("="*60)
    
    payload = {
        "model": MODEL,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Quelle heure est-il?"}]
                }
            ],
            "tools": [{
                "functionDeclarations": [{
                    "name": "get_time",
                    "description": "Retourne l'heure actuelle",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "timezone": {
                                "type": "STRING",
                                "description": "Fuseau horaire"
                            }
                        }
                    }
                }]
            }],
            "toolConfig": {
                "functionCallingConfig": {
                    "mode": "AUTO"
                }
            },
            "generationConfig": {
                "temperature": 0.7
            }
        }
    }
    
    success, status, response = make_request(payload)
    print_result("Avec toolConfig", success, status, response)
    return success


def test_4_multiple_tools():
    """Test 4: Plusieurs outils (5 outils)."""
    print("\n" + "="*60)
    print("TEST 4: Plusieurs outils (5)")
    print("="*60)
    
    tools = []
    for i in range(5):
        tools.append({
            "name": f"tool_{i}",
            "description": f"Outil de test numéro {i}",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "param": {
                        "type": "STRING",
                        "description": f"Paramètre de l'outil {i}"
                    }
                }
            }
        })
    
    payload = {
        "model": MODEL,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Test avec plusieurs outils"}]
                }
            ],
            "tools": [{"functionDeclarations": tools}],
            "toolConfig": {
                "functionCallingConfig": {
                    "mode": "AUTO"
                }
            },
            "generationConfig": {
                "temperature": 0.7
            }
        }
    }
    
    success, status, response = make_request(payload)
    print_result("5 outils", success, status, response)
    return success


def test_5_array_of_objects():
    """Test 5: Array d'objets imbriqués (bug connu Google)."""
    print("\n" + "="*60)
    print("TEST 5: Array d'objets imbriqués (BUG CONNU)")
    print("="*60)
    
    payload = {
        "model": MODEL,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Test avec array d'objets"}]
                }
            ],
            "tools": [{
                "functionDeclarations": [{
                    "name": "batch_process",
                    "description": "Traite plusieurs éléments",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "items": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",  # BUG: Array d'OBJECT imbriqué
                                    "properties": {
                                        "id": {"type": "STRING"},
                                        "value": {"type": "STRING"}
                                    }
                                }
                            }
                        }
                    }
                }]
            }],
            "toolConfig": {
                "functionCallingConfig": {
                    "mode": "AUTO"
                }
            },
            "generationConfig": {
                "temperature": 0.7
            }
        }
    }
    
    success, status, response = make_request(payload)
    print_result("Array d'objets imbriqués", success, status, response)
    
    if not success and status == 500:
        print("\n   ⚠️  CONFIRMATION: Le bug des arrays d'objets est présent!")
        print("   → Éviter les paramètres de type ARRAY avec items de type OBJECT")
    
    return success


def test_6_streaming():
    """Test 6: Mode streaming."""
    print("\n" + "="*60)
    print("TEST 6: Mode streaming (SSE)")
    print("="*60)
    
    payload = {
        "model": MODEL,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Compte de 1 à 5."}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7
            }
        }
    }
    
    success, status, response = make_request(payload, stream=True)
    print_result("Streaming SSE", success, status, response)
    return success


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*60)
    print("🔬 TESTS ATOMIQUES CODEASSIST v1internal")
    print("="*60)
    print(f"Endpoint: {CODEASSIST_ENDPOINT}")
    print(f"Model: {MODEL}")
    print(f"Token: {TOKEN_PATH}")
    
    # Vérifier le token
    token = get_access_token()
    if not token:
        print("\n❌ ERREUR: Impossible d'obtenir un token valide")
        print("   Exécutez 'gemini auth login' pour vous authentifier")
        sys.exit(1)
    
    print(f"\n✅ Token obtenu: {token[:20]}...")
    
    # Exécuter les tests
    results = {}
    
    results["1_baseline"] = test_1_baseline()
    time.sleep(1)  # Pause entre les tests
    
    results["2a_lowercase"] = test_2a_tool_lowercase()
    time.sleep(1)
    
    results["2b_uppercase"] = test_2b_tool_uppercase()
    time.sleep(1)
    
    results["3_toolconfig"] = test_3_with_toolconfig()
    time.sleep(1)
    
    results["4_multiple"] = test_4_multiple_tools()
    time.sleep(1)
    
    results["5_array_objects"] = test_5_array_of_objects()
    time.sleep(1)
    
    results["6_streaming"] = test_6_streaming()
    
    # Résumé
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, success in results.items():
        emoji = "✅" if success else "❌"
        print(f"   {emoji} {name}")
    
    print(f"\n   Total: {passed}/{total} tests réussis")
    
    # Diagnostic
    print("\n" + "="*60)
    print("🔍 DIAGNOSTIC")
    print("="*60)
    
    if not results["1_baseline"]:
        print("   ❌ Le baseline échoue → Problème d'auth ou de modèle")
    elif not results["2b_uppercase"] and results["2a_lowercase"]:
        print("   ⚠️  Les types en minuscules fonctionnent (inattendu)")
    elif results["2b_uppercase"] and not results["2a_lowercase"]:
        print("   ✅ CONFIRMATION: Les types doivent être en MAJUSCULES")
    
    if not results["5_array_objects"]:
        print("   ⚠️  Bug arrays d'objets confirmé → Éviter cette structure")
    
    if results["3_toolconfig"] and not results["2b_uppercase"]:
        print("   ✅ toolConfig est nécessaire pour les outils")


if __name__ == "__main__":
    main()

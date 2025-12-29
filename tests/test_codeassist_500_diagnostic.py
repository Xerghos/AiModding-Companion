"""
Test progressif pour diagnostiquer l'erreur 500 CodeAssist.
Teste différentes configurations minimales pour isoler la cause.
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Optional
from collections import OrderedDict

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_core.code_assist_client import CodeAssistClient
from ai_core.code_assist_converter import to_generate_content_request
from ai_core.oauth_validator import load_and_validate_oauth_credentials
from features.UnifiedLogger import UnifiedLogger
import uuid


class CodeAssist500Diagnostic:
    """Test progressif pour diagnostiquer l'erreur 500."""
    
    def __init__(self):
        self.client = None
        self.results = []
        
    def setup(self):
        """Initialise le client CodeAssist."""
        try:
            # Chemin par défaut du token OAuth
            token_path = os.path.join(
                os.path.expanduser("~"), ".config", "google", "gemini_oauth_token.json"
            )
            credentials = load_and_validate_oauth_credentials(token_path)
            if not credentials:
                print("ERREUR: Pas de credentials OAuth disponibles")
                return False
            
            self.client = CodeAssistClient(credentials)
            print("Client CodeAssist initialise")
            return True
        except Exception as e:
            print(f"ERREUR initialisation client: {e}")
            return False
    
    def test_case(self, name: str, payload: Dict[str, Any], description: str = ""):
        """
        Exécute un test avec un payload donné.
        
        Args:
            name: Nom du test
            payload: Payload à tester
            description: Description du test
        """
        print(f"\n{'='*80}")
        print(f"TEST: {name}")
        if description:
            print(f"Description: {description}")
        print(f"{'='*80}")
        
        # Sauvegarder le payload pour inspection
        test_dir = os.path.join(os.path.dirname(__file__), "..", "logs", "diagnostic_tests")
        os.makedirs(test_dir, exist_ok=True)
        payload_file = os.path.join(test_dir, f"test_{name}.json")
        
        with open(payload_file, "w", encoding="utf-8") as f:
            json.dump({
                "test_name": name,
                "description": description,
                "payload": payload
            }, f, indent=2, ensure_ascii=False)
        
        print(f"Payload sauvegarde: {payload_file}")
        
        # Afficher les informations du payload
        request_data = payload.get("request", {})
        request_keys = list(request_data.keys()) if isinstance(request_data, dict) else []
        print(f"Ordre des cles dans request: {request_keys}")
        
        # Afficher la taille
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        payload_size = len(payload_json.encode('utf-8'))
        print(f"Taille du payload: {payload_size} bytes ({payload_size/1024:.2f} KB)")
        
        # Tester l'appel API
        try:
            print(f"\nEnvoi de la requete...")
            response = self.client._request_post("streamGenerateContent", payload)
            
            print(f"SUCCES! Reponse recue")
            print(f"Type de reponse: {type(response)}")
            if isinstance(response, dict):
                print(f"Cles de la reponse: {list(response.keys())}")
                # Afficher un aperçu de la réponse
                response_preview = json.dumps(response, ensure_ascii=False, indent=2)[:500]
                print(f"Apercu reponse (500 chars):\n{response_preview}...")
            
            self.results.append({
                "test": name,
                "status": "SUCCESS",
                "payload_size": payload_size,
                "request_keys": request_keys
            })
            return True
            
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            print(f"ECHEC: {error_type}: {error_msg}")
            
            # Extraire le code d'erreur si disponible
            error_code = None
            error_details = {}
            
            # Si c'est une erreur HTTP, extraire plus de détails
            if hasattr(e, 'response'):
                try:
                    if hasattr(e.response, 'status_code'):
                        error_code = e.response.status_code
                    if hasattr(e.response, 'text'):
                        error_text = e.response.text
                        print(f"Reponse serveur: {error_text[:500]}")
                        try:
                            error_details = json.loads(error_text)
                        except:
                            error_details = {"raw": error_text[:500]}
                except:
                    pass
            elif "500" in error_msg:
                error_code = 500
            elif "400" in error_msg:
                error_code = 400
            
            print(f"Code d'erreur: {error_code}")
            if error_details:
                print(f"Details: {json.dumps(error_details, indent=2, ensure_ascii=False)[:500]}")
            
            self.results.append({
                "test": name,
                "status": "FAILED",
                "error": error_msg,
                "error_type": error_type,
                "error_code": error_code,
                "error_details": error_details,
                "payload_size": payload_size,
                "request_keys": request_keys
            })
            return False
    
    def test_1_minimal_no_tools(self):
        """Test 1: Payload minimal sans outils."""
        payload = to_generate_content_request(
            model="gemini-3-flash-preview",
            messages=[],
            system_instruction="Test minimal",
            temperature=0.7
        )
        return self.test_case(
            "1_minimal_no_tools",
            payload,
            "Payload minimal avec seulement systemInstruction, sans outils"
        )
    
    def test_2_minimal_one_simple_tool(self):
        """Test 2: Payload avec un seul outil simple."""
        simple_tool = {
            "functionDeclarations": [{
                "name": "test_tool",
                "description": "Un outil de test simple",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "message": {
                            "type": "STRING",
                            "description": "Message de test"
                        }
                    },
                    "required": ["message"]
                }
            }]
        }
        
        payload = to_generate_content_request(
            model="gemini-3-flash-preview",
            messages=[],
            system_instruction="Test avec un outil simple",
            tools=[simple_tool],
            temperature=0.7
        )
        return self.test_case(
            "2_minimal_one_simple_tool",
            payload,
            "Payload avec un seul outil simple (sans structures complexes)"
        )
    
    def test_3_minimal_with_toolconfig(self):
        """Test 3: Payload avec toolConfig explicite."""
        simple_tool = {
            "functionDeclarations": [{
                "name": "test_tool",
                "description": "Un outil de test simple",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "message": {
                            "type": "STRING",
                            "description": "Message de test"
                        }
                    },
                    "required": ["message"]
                }
            }]
        }
        
        payload = to_generate_content_request(
            model="gemini-3-flash-preview",
            messages=[],
            system_instruction="Test avec toolConfig",
            tools=[simple_tool],
            temperature=0.7
        )
        
        # Vérifier que toolConfig est présent
        if "request" in payload and "tools" in payload["request"]:
            print("toolConfig devrait etre present automatiquement")
        
        return self.test_case(
            "3_minimal_with_toolconfig",
            payload,
            "Payload avec toolConfig explicite (mode AUTO)"
        )
    
    def test_4_exact_working_structure(self):
        """Test 4: Utiliser exactement la même structure que le payload fonctionnel."""
        # Créer un payload avec exactement la même structure que le payload fonctionnel
        # mais avec un systemInstruction minimal
        payload = {
            "model": "gemini-3-flash-preview",
            "request": OrderedDict([
                ("contents", []),
                ("systemInstruction", OrderedDict([
                    ("role", "system"),
                    ("parts", [OrderedDict([("text", "Test minimal")])])
                ])),
                ("generationConfig", OrderedDict([
                    ("temperature", 0.7)
                ]))
            ]),
            "user_prompt_id": str(uuid.uuid4())
        }
        
        return self.test_case(
            "4_exact_working_structure",
            payload,
            "Payload avec exactement la meme structure OrderedDict que le payload fonctionnel"
        )
    
    def test_4_compare_with_working_payload(self):
        """Test 4: Comparer avec le payload fonctionnel."""
        # Charger le payload fonctionnel
        working_payload_file = os.path.join(
            os.path.dirname(__file__), "..", "logs", "payload final fonctionnel geminiCLI.json"
        )
        
        if not os.path.exists(working_payload_file):
            print(f"ATTENTION: Fichier payload fonctionnel non trouve: {working_payload_file}")
            return False
        
        try:
            with open(working_payload_file, "r", encoding="utf-8") as f:
                working_data = json.load(f)
            
            working_payload = working_data.get("payload", {})
            
            # Extraire seulement la structure request pour comparaison
            if "request" in working_payload:
                # Créer un payload minimal basé sur la structure fonctionnelle
                minimal_working = {
                    "model": working_payload.get("model", "gemini-3-flash-preview"),
                    "request": {
                        "contents": [],
                        "systemInstruction": {
                            "role": "system",
                            "parts": [{"text": "Test minimal basé sur payload fonctionnel"}]
                        }
                    }
                }
                
                # Ajouter seulement le premier outil pour tester
                if "tools" in working_payload["request"] and len(working_payload["request"]["tools"]) > 0:
                    first_tool = working_payload["request"]["tools"][0]
                    minimal_working["request"]["tools"] = [first_tool]
                    minimal_working["request"]["toolConfig"] = working_payload["request"].get("toolConfig", {
                        "functionCallingConfig": {"mode": "AUTO"}
                    })
                    minimal_working["request"]["generationConfig"] = working_payload["request"].get("generationConfig", {
                        "temperature": 0.7
                    })
                
                if "user_prompt_id" in working_payload:
                    minimal_working["user_prompt_id"] = working_payload["user_prompt_id"]
                
                return self.test_case(
                    "4_compare_with_working_payload",
                    minimal_working,
                    "Payload minimal basé sur la structure du payload fonctionnel (premier outil seulement)"
                )
        except Exception as e:
            print(f"ERREUR lors du chargement du payload fonctionnel: {e}")
            return False
    
    def test_5_order_verification(self):
        """Test 5: Vérifier l'ordre exact des clés après sérialisation."""
        simple_tool = {
            "functionDeclarations": [{
                "name": "test_tool",
                "description": "Test",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {},
                    "required": []
                }
            }]
        }
        
        payload = to_generate_content_request(
            model="gemini-3-flash-preview",
            messages=[],
            system_instruction="Test ordre",
            tools=[simple_tool],
            temperature=0.7
        )
        
        # Sérialiser et désérialiser pour vérifier l'ordre
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        payload_parsed = json.loads(payload_json)
        
        # Vérifier l'ordre dans request
        request_keys = list(payload_parsed.get("request", {}).keys())
        expected_order = ["contents", "systemInstruction", "tools", "toolConfig", "generationConfig"]
        
        print(f"\nVerification de l'ordre des cles:")
        print(f"   Attendu: {expected_order}")
        print(f"   Obtenu:  {request_keys}")
        
        if request_keys == expected_order:
            print("   Ordre correct!")
        else:
            print("   Ordre different!")
        
        return self.test_case(
            "5_order_verification",
            payload,
            "Vérification de l'ordre des clés après sérialisation JSON"
        )
    
    def test_6_empty_contents(self):
        """Test 6: Vérifier que contents est bien vide."""
        payload = to_generate_content_request(
            model="gemini-3-flash-preview",
            messages=[],
            system_instruction="Test contents vide",
            temperature=0.7
        )
        
        contents = payload.get("request", {}).get("contents", None)
        print(f"\nVerification de contents:")
        print(f"   Type: {type(contents)}")
        print(f"   Valeur: {contents}")
        
        if contents == []:
            print("   contents est bien vide (liste vide)")
        else:
            print("   contents n'est pas vide!")
        
        return self.test_case(
            "6_empty_contents",
            payload,
            "Vérification que contents est bien une liste vide"
        )
    
    def test_7_generateContent_non_streaming(self):
        """Test 7: Tester avec generateContent (non-streaming) au lieu de streamGenerateContent."""
        payload = to_generate_content_request(
            model="gemini-3-flash-preview",
            messages=[],
            system_instruction="Test generateContent non-streaming",
            temperature=0.7
        )
        
        # Utiliser generateContent au lieu de streamGenerateContent
        try:
            print(f"\nEnvoi de la requete avec generateContent (non-streaming)...")
            response = self.client._request_post("generateContent", payload)
            
            print(f"SUCCES! Reponse recue")
            print(f"Type de reponse: {type(response)}")
            if isinstance(response, dict):
                print(f"Cles de la reponse: {list(response.keys())}")
            
            self.results.append({
                "test": "7_generateContent_non_streaming",
                "status": "SUCCESS",
                "payload_size": len(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            })
            return True
        except Exception as e:
            error_msg = str(e)
            print(f"ECHEC: {error_msg}")
            error_code = None
            if "500" in error_msg:
                error_code = 500
            elif "400" in error_msg:
                error_code = 400
            
            self.results.append({
                "test": "7_generateContent_non_streaming",
                "status": "FAILED",
                "error": error_msg,
                "error_code": error_code
            })
            return False
    
    def test_8_exact_gemini_cli_structure(self):
        """Test 8: Utiliser exactement la même structure que gemini-cli (sans champs undefined)."""
        # Structure exacte comme dans gemini-cli converter.ts
        # gemini-cli ne met pas les champs undefined dans l'objet
        # Mais l'ordre dans toVertexGenerateContentRequest est :
        # contents, systemInstruction, cachedContent, tools, toolConfig, labels, safetySettings, generationConfig, session_id
        payload = {
            "model": "gemini-3-flash-preview",
            "request": OrderedDict([
                ("contents", []),
                ("systemInstruction", OrderedDict([
                    ("role", "system"),
                    ("parts", [OrderedDict([("text", "Test minimal")])])
                ])),
                # Pas de cachedContent, tools, toolConfig, labels, safetySettings, session_id
                # car ils sont undefined dans gemini-cli
                ("generationConfig", OrderedDict([
                    ("temperature", 0.7)
                ]))
            ]),
            "user_prompt_id": str(uuid.uuid4())
        }
        
        return self.test_case(
            "8_exact_gemini_cli_structure",
            payload,
            "Payload avec exactement la meme structure que gemini-cli (sans champs undefined)"
        )
    
    def test_10_without_user_prompt_id(self):
        """Test 10: Tester sans user_prompt_id (peut-être que c'est optionnel)."""
        payload = {
            "model": "gemini-3-flash-preview",
            "request": OrderedDict([
                ("contents", []),
                ("systemInstruction", OrderedDict([
                    ("role", "system"),
                    ("parts", [OrderedDict([("text", "Test sans user_prompt_id")])])
                ])),
                ("generationConfig", OrderedDict([
                    ("temperature", 0.7)
                ]))
            ])
        }
        
        return self.test_case(
            "10_without_user_prompt_id",
            payload,
            "Payload sans user_prompt_id (peut-etre que c'est optionnel)"
        )
    
    def test_11_exact_gemini_cli_json_stringify(self):
        """Test 11: Reproduire exactement ce que fait JSON.stringify() de gemini-cli."""
        # Dans gemini-cli, JSON.stringify() préserve l'ordre d'insertion
        # Créons un payload exactement comme gemini-cli le ferait
        import json
        
        # Simuler exactement la structure de gemini-cli
        request_obj = {}
        request_obj["contents"] = []
        request_obj["systemInstruction"] = {
            "role": "system",
            "parts": [{"text": "Test exact gemini-cli"}]
        }
        # Pas de cachedContent, tools, toolConfig, etc. car undefined
        request_obj["generationConfig"] = {
            "temperature": 0.7
        }
        
        payload_obj = {}
        payload_obj["model"] = "gemini-3-flash-preview"
        # Pas de project car undefined
        payload_obj["user_prompt_id"] = str(uuid.uuid4())
        payload_obj["request"] = request_obj
        
        # Sérialiser exactement comme gemini-cli (JSON.stringify)
        payload_json = json.dumps(payload_obj, ensure_ascii=False, separators=(',', ':'))
        payload_parsed = json.loads(payload_json)
        
        print(f"\nVerification structure exacte gemini-cli:")
        print(f"   Ordre cles racine: {list(payload_parsed.keys())}")
        print(f"   Ordre cles request: {list(payload_parsed.get('request', {}).keys())}")
        print(f"   JSON (200 chars): {payload_json[:200]}")
        
        return self.test_case(
            "11_exact_gemini_cli_json_stringify",
            payload_parsed,
            "Payload cree exactement comme gemini-cli avec JSON.stringify()"
        )
    
    def test_9_compare_byte_by_byte(self):
        """Test 9: Comparer byte-par-byte avec le payload fonctionnel."""
        # Charger le payload fonctionnel
        working_payload_file = os.path.join(
            os.path.dirname(__file__), "..", "logs", "payload final fonctionnel geminiCLI.json"
        )
        
        if not os.path.exists(working_payload_file):
            print(f"ATTENTION: Fichier payload fonctionnel non trouve: {working_payload_file}")
            return False
        
        try:
            with open(working_payload_file, "r", encoding="utf-8") as f:
                working_data = json.load(f)
            
            working_payload = working_data.get("payload", {})
            
            # Sérialiser les deux payloads de la même manière
            our_payload = to_generate_content_request(
                model="gemini-3-flash-preview",
                messages=[],
                system_instruction="Test",
                temperature=0.7
            )
            
            our_json = json.dumps(our_payload, ensure_ascii=False, separators=(',', ':'))
            working_json = json.dumps(working_payload, ensure_ascii=False, separators=(',', ':'))
            
            print(f"\nComparaison byte-par-byte:")
            print(f"   Notre payload: {len(our_json)} bytes")
            print(f"   Payload fonctionnel: {len(working_json)} bytes")
            
            # Comparer les premières lignes pour voir les différences
            our_lines = our_json.split('\n')[:5] if '\n' in our_json else [our_json[:200]]
            working_lines = working_json.split('\n')[:5] if '\n' in working_json else [working_json[:200]]
            
            print(f"\n   Apercu notre payload (200 chars): {our_json[:200]}")
            print(f"   Apercu payload fonctionnel (200 chars): {working_json[:200]}")
            
            # Tester notre payload
            return self.test_case(
                "9_compare_byte_by_byte",
                our_payload,
                "Comparaison byte-par-byte avec payload fonctionnel"
            )
        except Exception as e:
            print(f"ERREUR lors de la comparaison: {e}")
            return False
    
    def run_all_tests(self):
        """Exécute tous les tests dans l'ordre."""
        print("\n" + "="*80)
        print("DIAGNOSTIC ERREUR 500 - CodeAssist API")
        print("="*80)
        
        if not self.setup():
            print("\nImpossible d'initialiser le client. Arret des tests.")
            return
        
        tests = [
            ("Test 1: Minimal sans outils", self.test_1_minimal_no_tools),
            ("Test 2: Minimal avec un outil simple", self.test_2_minimal_one_simple_tool),
            ("Test 3: Avec toolConfig", self.test_3_minimal_with_toolconfig),
            ("Test 4: Structure exacte OrderedDict", self.test_4_exact_working_structure),
            ("Test 5: Comparaison avec payload fonctionnel", self.test_4_compare_with_working_payload),
            ("Test 6: Vérification ordre", self.test_5_order_verification),
            ("Test 7: Vérification contents vide", self.test_6_empty_contents),
            ("Test 8: generateContent non-streaming", self.test_7_generateContent_non_streaming),
            ("Test 9: Structure exacte gemini-cli", self.test_8_exact_gemini_cli_structure),
            ("Test 10: Comparaison byte-par-byte", self.test_9_compare_byte_by_byte),
            ("Test 11: Sans user_prompt_id", self.test_10_without_user_prompt_id),
            ("Test 12: Exact gemini-cli JSON.stringify", self.test_11_exact_gemini_cli_json_stringify),
        ]
        
        for test_name, test_func in tests:
            try:
                test_func()
                time.sleep(1)  # Pause entre les tests
            except Exception as e:
                print(f"\nERREUR lors de l'execution de {test_name}: {e}")
                import traceback
                traceback.print_exc()
        
        # Résumé
        self.print_summary()
    
    def print_summary(self):
        """Affiche un résumé des résultats."""
        print("\n" + "="*80)
        print("RESUME DES TESTS")
        print("="*80)
        
        success_count = sum(1 for r in self.results if r["status"] == "SUCCESS")
        failed_count = sum(1 for r in self.results if r["status"] == "FAILED")
        
        print(f"\nSucces: {success_count}")
        print(f"Echecs: {failed_count}")
        print(f"Total: {len(self.results)}")
        
        print("\nDetails:")
        for result in self.results:
            status_icon = "[OK]" if result["status"] == "SUCCESS" else "[FAIL]"
            print(f"  {status_icon} {result['test']}: {result['status']}")
            if result["status"] == "FAILED" and "error_code" in result:
                print(f"     Code erreur: {result['error_code']}")
        
        # Sauvegarder le résumé
        summary_file = os.path.join(
            os.path.dirname(__file__), "..", "logs", "diagnostic_tests", "summary.json"
        )
        os.makedirs(os.path.dirname(summary_file), exist_ok=True)
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump({
                "summary": {
                    "success": success_count,
                    "failed": failed_count,
                    "total": len(self.results)
                },
                "results": self.results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\nResume sauvegarde: {summary_file}")


if __name__ == "__main__":
    import time
    
    diagnostic = CodeAssist500Diagnostic()
    diagnostic.run_all_tests()

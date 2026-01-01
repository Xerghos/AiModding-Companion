"""
Script mitmproxy pour capturer les payloads gemini-cli lors des tool calls.
Utilise mitmproxy pour intercepter HTTPS sans configuration complexe.

Ce script capture et analyse en temps réel tous les payloads envoyés par gemini-cli
vers l'API CodeAssist, avec un focus particulier sur les tool calls (functionCall/functionResponse).

Usage:
1. Installer mitmproxy: pip install mitmproxy
2. Démarrer: mitmdump -s scripts/capture_gemini_cli_mitmproxy.py
3. Configurer gemini-cli pour utiliser le proxy:
   - Windows: set HTTP_PROXY=http://localhost:8080 && set HTTPS_PROXY=http://localhost:8080
   - Linux/Mac: export HTTP_PROXY=http://localhost:8080 && export HTTPS_PROXY=http://localhost:8080
4. Installer le certificat mitmproxy (pour HTTPS):
   - Ouvrir http://mitm.it dans le navigateur
   - Télécharger et installer le certificat pour votre OS
5. Exécuter une commande avec tool call dans gemini-cli:
   gemini-cli "Lis le fichier README.md et résume-le"
6. Les payloads seront sauvegardés dans logs/gemini_cli_tool_call_*.json

Analyse automatique:
- Détection des functionCall et functionResponse
- Analyse des IDs et corrélation
- Détection des thoughtSignature
- Comparaison avec nos payloads (si disponibles)
"""

from mitmproxy import http
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import sys

# Configuration
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Statistiques globales
stats = {
    "total_requests": 0,
    "codeassist_requests": 0,
    "tool_call_requests": 0,
    "functionCall_count": 0,
    "functionResponse_count": 0,
    "thoughtSignature_detected": 0,
    "id_correlations": {"matches": 0, "mismatches": 0, "missing": 0}
}


def log_info(message: str, level: str = "INFO") -> None:
    """Log avec timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def has_tool_call(payload: dict) -> bool:
    """Détecte si le payload contient un functionCall ou functionResponse."""
    try:
        request_data = payload.get("request", {})
        contents = request_data.get("contents", [])
        
        for msg in contents:
            parts = msg.get("parts", [])
            for part in parts:
                if "functionCall" in part or "functionResponse" in part:
                    return True
        return False
    except Exception:
        return False


def analyze_payload_structure(payload: dict) -> Dict[str, Any]:
    """Analyse approfondie de la structure du payload."""
    analysis = {
        "has_functionCall": False,
        "has_functionResponse": False,
        "functionCall_details": [],
        "functionResponse_details": [],
        "has_thoughtSignature": False,
        "thoughtSignature_locations": [],
        "id_correlations": [],
        "contents_structure": [],
        "session_id": payload.get("request", {}).get("session_id"),
        "model": payload.get("model"),
        "project": payload.get("project"),
        "user_prompt_id": payload.get("user_prompt_id"),
        "contents_count": 0,
        "sequence_valid": False
    }
    
    try:
        request_data = payload.get("request", {})
        contents = request_data.get("contents", [])
        analysis["contents_count"] = len(contents)
        
        # Analyser chaque message dans contents
        for idx, msg in enumerate(contents):
            role = msg.get("role", "unknown")
            parts = msg.get("parts", [])
            
            msg_analysis = {
                "index": idx,
                "role": role,
                "parts_count": len(parts),
                "has_functionCall": False,
                "has_functionResponse": False,
                "has_text": False
            }
            
            for part_idx, part in enumerate(parts):
                # Analyser functionCall
                if "functionCall" in part:
                    analysis["has_functionCall"] = True
                    msg_analysis["has_functionCall"] = True
                    stats["functionCall_count"] += 1
                    
                    func_call = part["functionCall"]
                    func_call_detail = {
                        "message_index": idx,
                        "part_index": part_idx,
                        "name": func_call.get("name"),
                        "id": func_call.get("id"),
                        "has_id": bool(func_call.get("id")),
                        "args_keys": list(func_call.get("args", {}).keys()) if isinstance(func_call.get("args"), dict) else [],
                        "has_thoughtSignature": "thoughtSignature" in func_call or "thought_signature" in func_call,
                        "all_keys": list(func_call.keys()),
                        "raw": func_call
                    }
                    
                    if func_call_detail["has_thoughtSignature"]:
                        analysis["has_thoughtSignature"] = True
                        analysis["thoughtSignature_locations"].append(f"functionCall[{idx}][{part_idx}]")
                        stats["thoughtSignature_detected"] += 1
                    
                    analysis["functionCall_details"].append(func_call_detail)
                
                # Analyser functionResponse
                if "functionResponse" in part:
                    analysis["has_functionResponse"] = True
                    msg_analysis["has_functionResponse"] = True
                    stats["functionResponse_count"] += 1
                    
                    func_resp = part["functionResponse"]
                    response_obj = func_resp.get("response", {})
                    
                    func_resp_detail = {
                        "message_index": idx,
                        "part_index": part_idx,
                        "name": func_resp.get("name"),
                        "id": func_resp.get("id"),
                        "has_id": bool(func_resp.get("id")),
                        "response_type": type(response_obj).__name__,
                        "response_keys": list(response_obj.keys()) if isinstance(response_obj, dict) else [],
                        "has_output": "output" in response_obj,
                        "has_content": "content" in response_obj,
                        "has_result": "result" in response_obj,
                        "output_type": type(response_obj.get("output")).__name__ if "output" in response_obj else None,
                        "output_length": len(str(response_obj.get("output", ""))) if "output" in response_obj else 0,
                        "all_keys": list(func_resp.keys()),
                        "raw": func_resp
                    }
                    
                    analysis["functionResponse_details"].append(func_resp_detail)
                    
                    # Vérifier la corrélation ID avec le functionCall précédent
                    if idx > 0:
                        prev_msg = contents[idx - 1]
                        if prev_msg.get("role") == "model":
                            prev_parts = prev_msg.get("parts", [])
                            for prev_part in prev_parts:
                                if "functionCall" in prev_part:
                                    prev_func_call = prev_part["functionCall"]
                                    prev_id = prev_func_call.get("id")
                                    resp_id = func_resp.get("id")
                                    
                                    correlation = {
                                        "functionCall_id": prev_id,
                                        "functionResponse_id": resp_id,
                                        "match": prev_id == resp_id if (prev_id and resp_id) else None,
                                        "both_present": bool(prev_id and resp_id),
                                        "both_absent": bool(not prev_id and not resp_id),
                                        "only_functionCall": bool(prev_id and not resp_id),
                                        "only_functionResponse": bool(not prev_id and resp_id)
                                    }
                                    
                                    analysis["id_correlations"].append(correlation)
                                    
                                    if correlation["match"] is True:
                                        stats["id_correlations"]["matches"] += 1
                                    elif correlation["match"] is False:
                                        stats["id_correlations"]["mismatches"] += 1
                                    else:
                                        stats["id_correlations"]["missing"] += 1
                
                # Détecter texte
                if "text" in part:
                    msg_analysis["has_text"] = True
            
            analysis["contents_structure"].append(msg_analysis)
        
        # Valider la séquence attendue
        roles = [msg.get("role") for msg in contents]
        analysis["sequence_valid"] = validate_sequence(roles)
        
    except Exception as e:
        analysis["error"] = str(e)
        log_info(f"Erreur analyse payload: {e}", "ERROR")
    
    return analysis


def validate_sequence(roles: List[str]) -> bool:
    """Valide que la séquence des rôles est correcte."""
    # Séquence attendue pour tool call: user -> model (functionCall) -> function (functionResponse)
    # On accepte plusieurs messages user/model/function consécutifs
    valid_patterns = [
        ["user", "model", "function"],  # Pattern classique
        ["user", "model"],  # Juste functionCall, pas encore de réponse
        ["model", "function"],  # Continuation après tool call
    ]
    
    if len(roles) < 2:
        return False
    
    # Vérifier si la séquence correspond à un pattern valide
    for pattern in valid_patterns:
        if roles[:len(pattern)] == pattern:
            return True
    
    return False


def compare_with_our_payloads(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Compare avec nos payloads capturés précédemment."""
    comparison = {
        "our_payloads_found": False,
        "differences": []
    }
    
    try:
        # Chercher nos payloads d'erreur 400
        our_payloads_dir = LOGS_DIR
        our_payload_files = list(our_payloads_dir.glob("error_400_payload_*.json"))
        
        if not our_payload_files:
            return comparison
        
        comparison["our_payloads_found"] = True
        latest_our_payload = max(our_payload_files, key=lambda p: p.stat().st_mtime)
        
        with open(latest_our_payload, 'r', encoding='utf-8') as f:
            our_data = json.load(f)
        
        our_payload = our_data.get("payload", {})
        our_request = our_payload.get("request", {})
        our_contents = our_request.get("contents", [])
        
        # Comparer les structures
        if len(our_contents) != analysis["contents_count"]:
            comparison["differences"].append(
                f"Nombre de messages différent: nous={len(our_contents)}, gemini-cli={analysis['contents_count']}"
            )
        
        # Comparer les functionCall
        our_functionCalls = []
        for msg in our_contents:
            if msg.get("role") == "model":
                for part in msg.get("parts", []):
                    if "functionCall" in part:
                        our_functionCalls.append(part["functionCall"])
        
        if len(our_functionCalls) != len(analysis["functionCall_details"]):
            comparison["differences"].append(
                f"Nombre de functionCall différent: nous={len(our_functionCalls)}, gemini-cli={len(analysis['functionCall_details'])}"
            )
        
        # Comparer la présence d'IDs
        our_has_ids = all(fc.get("id") for fc in our_functionCalls)
        cli_has_ids = all(fc["has_id"] for fc in analysis["functionCall_details"])
        
        if our_has_ids != cli_has_ids:
            comparison["differences"].append(
                f"Présence d'IDs dans functionCall: nous={our_has_ids}, gemini-cli={cli_has_ids}"
            )
        
        # Comparer thoughtSignature
        our_has_thoughtSig = any("thoughtSignature" in fc for fc in our_functionCalls)
        if our_has_thoughtSig != analysis["has_thoughtSignature"]:
            comparison["differences"].append(
                f"Présence thoughtSignature: nous={our_has_thoughtSig}, gemini-cli={analysis['has_thoughtSignature']}"
            )
        
    except Exception as e:
        comparison["error"] = str(e)
        log_info(f"Erreur comparaison: {e}", "WARN")
    
    return comparison


def request(flow: http.HTTPFlow) -> None:
    """Intercepte les requêtes vers CodeAssist."""
    stats["total_requests"] += 1
    
    # Log toutes les requêtes pour diagnostic
    log_info(f"Requête #{stats['total_requests']}: {flow.request.pretty_host}{flow.request.path}", "DEBUG")
    
    # Filtrer uniquement les requêtes vers CodeAssist
    if "cloudcode-pa.googleapis.com" not in flow.request.pretty_host:
        # Log les autres requêtes pour voir ce qui passe
        if stats["total_requests"] <= 5:  # Log les 5 premières pour diagnostic
            log_info(f"  (Ignoré - pas CodeAssist)", "DEBUG")
        return
    
    stats["codeassist_requests"] += 1
    log_info(f"✅ Requête CodeAssist détectée: {flow.request.path}", "INFO")
    
    # Filtrer uniquement streamGenerateContent
    if "streamGenerateContent" not in flow.request.path:
        log_info(f"  (Ignoré - pas streamGenerateContent: {flow.request.path})", "DEBUG")
        return
    
    log_info(f"🎯 streamGenerateContent détecté!", "INFO")
    
    # Extraire le payload
    try:
        if not flow.request.content:
            log_info("⚠️  Requête sans contenu (peut être une requête GET ou vide)", "WARN")
            return
        
        log_info(f"📦 Contenu de la requête: {len(flow.request.content)} bytes", "DEBUG")
        
        try:
            payload = json.loads(flow.request.content.decode('utf-8'))
        except json.JSONDecodeError as e:
            log_info(f"❌ Erreur parsing JSON: {e}", "ERROR")
            log_info(f"   Premiers 200 chars: {flow.request.content[:200]}", "ERROR")
            return
        
        log_info(f"✅ Payload JSON parsé avec succès", "DEBUG")
        
        # Vérifier si c'est un tool call
        is_tool_call = has_tool_call(payload)
        log_info(f"🔍 Tool call détecté: {is_tool_call}", "DEBUG")
        
        if is_tool_call:
            stats["tool_call_requests"] += 1
            log_info("=" * 80, "TOOL_CALL")
            log_info(f"TOOL CALL DÉTECTÉ - URL: {flow.request.path}", "TOOL_CALL")
        
        # Analyser le payload
        analysis = analyze_payload_structure(payload)
        
        # Comparer avec nos payloads si c'est un tool call
        comparison = {}
        if is_tool_call:
            comparison = compare_with_our_payloads(analysis)
        
        # Sauvegarder le payload (toujours pour tool calls, optionnel pour autres)
        if is_tool_call or True:  # Sauvegarder toutes les requêtes CodeAssist
            timestamp = datetime.now().strftime("%d-%b_%Hh%M_%S")
            prefix = "gemini_cli_tool_call" if is_tool_call else "gemini_cli_request"
            filename = LOGS_DIR / f"{prefix}_{timestamp}.json"
            
            capture_data = {
                "timestamp": datetime.now().isoformat(),
                "url": flow.request.pretty_url,
                "method": flow.request.method,
                "path": flow.request.path,
                "headers": dict(flow.request.headers),
                "payload": payload,
                "analysis": analysis,
                "comparison": comparison if is_tool_call else None,
                "is_tool_call": is_tool_call
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(capture_data, f, indent=2, ensure_ascii=False)
            
            # Log détaillé pour tool calls
            if is_tool_call:
                log_info(f"Payload sauvegardé: {filename.name}", "TOOL_CALL")
                log_info(f"  - Model: {analysis.get('model')}", "TOOL_CALL")
                log_info(f"  - Session ID: {analysis.get('session_id', 'ABSENT')}", "TOOL_CALL")
                log_info(f"  - Contents: {analysis.get('contents_count')} messages", "TOOL_CALL")
                log_info(f"  - functionCall: {analysis.get('has_functionCall')} ({len(analysis.get('functionCall_details', []))} détecté(s))", "TOOL_CALL")
                log_info(f"  - functionResponse: {analysis.get('has_functionResponse')} ({len(analysis.get('functionResponse_details', []))} détecté(s))", "TOOL_CALL")
                log_info(f"  - thoughtSignature: {analysis.get('has_thoughtSignature')}", "TOOL_CALL")
                log_info(f"  - Séquence valide: {analysis.get('sequence_valid')}", "TOOL_CALL")
                
                # Détails des functionCall
                for fc in analysis.get("functionCall_details", []):
                    id_status = f"id={fc['id']}" if fc['has_id'] else "SANS ID"
                    thought_status = "avec thoughtSignature" if fc['has_thoughtSignature'] else "sans thoughtSignature"
                    log_info(f"    functionCall: {fc['name']} - {id_status} - {thought_status}", "TOOL_CALL")
                
                # Détails des functionResponse
                for fr in analysis.get("functionResponse_details", []):
                    id_status = f"id={fr['id']}" if fr['has_id'] else "SANS ID"
                    output_format = "output" if fr['has_output'] else ("content" if fr['has_content'] else "result" if fr['has_result'] else "UNKNOWN")
                    log_info(f"    functionResponse: {fr['name']} - {id_status} - format={output_format}", "TOOL_CALL")
                
                # Corrélations ID
                for corr in analysis.get("id_correlations", []):
                    if corr.get('match') is True:
                        log_info(f"    ✅ ID corrélé: {corr.get('functionCall_id')}", "TOOL_CALL")
                    elif corr.get('match') is False:
                        log_info(f"    ❌ ID mismatch: {corr.get('functionCall_id')} != {corr.get('functionResponse_id')}", "TOOL_CALL")
                    else:
                        log_info(f"    ⚠️  ID manquant: functionCall={corr.get('functionCall_id')}, functionResponse={corr.get('functionResponse_id')}", "TOOL_CALL")
                
                # Comparaisons
                if comparison.get("our_payloads_found"):
                    if comparison.get("differences"):
                        log_info("  DIFFÉRENCES avec nos payloads:", "TOOL_CALL")
                        for diff in comparison["differences"]:
                            log_info(f"    - {diff}", "TOOL_CALL")
                    else:
                        log_info("  ✅ Structure similaire à nos payloads", "TOOL_CALL")
                
                log_info("=" * 80, "TOOL_CALL")
        
    except json.JSONDecodeError as e:
        log_info(f"Erreur parsing JSON: {e}", "ERROR")
    except Exception as e:
        log_info(f"Erreur capture: {e}", "ERROR")
        import traceback
        log_info(traceback.format_exc(), "ERROR")


def start():
    """Appelé au démarrage de mitmproxy."""
    log_info("=" * 80, "START")
    log_info("PROXY MITMPROXY DEMARRE", "START")
    log_info(f"Dossier logs: {LOGS_DIR}", "START")
    log_info("En attente de requetes...", "START")
    log_info("", "START")
    log_info("INSTRUCTIONS IMPORTANTES:", "START")
    log_info("1. Dans un NOUVEAU terminal PowerShell, executez:", "START")
    log_info("   .\\scripts\\verifier_proxy_gemini_cli.ps1", "START")
    log_info("", "START")
    log_info("2. OU configurez manuellement les variables:", "START")
    log_info("   Windows PowerShell:", "START")
    log_info("     $env:HTTP_PROXY='http://localhost:8080'", "START")
    log_info("     $env:HTTPS_PROXY='http://localhost:8080'", "START")
    log_info("", "START")
    log_info("3. Executez gemini-cli dans le MEME terminal", "START")
    log_info("", "START")
    log_info("4. Testez le proxy avec:", "START")
    log_info("   python scripts/test_proxy_mitmproxy.py", "START")
    log_info("=" * 80, "START")


def done():
    """Appelé à la fin de la session mitmproxy."""
    log_info("=" * 80, "STATS")
    log_info("📊 STATISTIQUES FINALES:", "STATS")
    log_info(f"  Total requêtes interceptées: {stats['total_requests']}", "STATS")
    log_info(f"  Requêtes CodeAssist: {stats['codeassist_requests']}", "STATS")
    log_info(f"  Requêtes tool call: {stats['tool_call_requests']}", "STATS")
    log_info(f"  functionCall détectés: {stats['functionCall_count']}", "STATS")
    log_info(f"  functionResponse détectés: {stats['functionResponse_count']}", "STATS")
    log_info(f"  thoughtSignature détectés: {stats['thoughtSignature_detected']}", "STATS")
    log_info(f"  Corrélations ID - Matches: {stats['id_correlations']['matches']}, "
              f"Mismatches: {stats['id_correlations']['mismatches']}, "
              f"Missing: {stats['id_correlations']['missing']}", "STATS")
    
    if stats['total_requests'] == 0:
        log_info("⚠️  AUCUNE REQUÊTE INTERCEPTÉE!", "STATS")
        log_info("   Vérifiez que:", "STATS")
        log_info("   1. gemini-cli est configuré pour utiliser le proxy", "STATS")
        log_info("   2. Le certificat mitmproxy est installé (pour HTTPS)", "STATS")
        log_info("   3. gemini-cli est bien exécuté", "STATS")
    elif stats['codeassist_requests'] == 0:
        log_info("⚠️  Aucune requête CodeAssist interceptée!", "STATS")
        log_info("   Les requêtes vont peut-être vers un autre endpoint", "STATS")
    
    log_info("=" * 80, "STATS")

"""
Proxy HTTP local pour capturer les requêtes réelles envoyées par gemini-cli à CodeAssist.
Utilise un serveur HTTP simple qui intercepte les requêtes vers cloudcode-pa.googleapis.com.

⚠️  LIMITATION: Ce proxy a des limitations pour HTTPS. Pour une capture complète, utilisez plutôt:
   mitmdump -s scripts/capture_gemini_cli_mitmproxy.py

Usage:
1. Démarrer le proxy: python scripts/capture_gemini_cli_http_proxy.py [port]
2. Configurer gemini-cli pour utiliser le proxy (via variables d'environnement HTTP_PROXY)
3. Exécuter une requête avec gemini-cli
4. Le payload sera sauvegardé dans logs/gemini_cli_real_payload_*.json

Analyse automatique:
- Détection des functionCall et functionResponse
- Analyse des IDs et corrélation
- Détection des thoughtSignature
- Statistiques en temps réel
"""

import json
import http.server
import socketserver
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import threading
import sys
from collections import defaultdict


# Statistiques globales
stats = {
    "total_requests": 0,
    "codeassist_requests": 0,
    "tool_call_requests": 0,
    "functionCall_count": 0,
    "functionResponse_count": 0,
    "thoughtSignature_detected": 0
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


def analyze_payload(payload: dict) -> Dict[str, Any]:
    """Analyse le payload pour extraire les informations importantes."""
    analysis = {
        "has_functionCall": False,
        "has_functionResponse": False,
        "functionCall_details": [],
        "functionResponse_details": [],
        "has_thoughtSignature": False,
        "id_correlations": [],
        "contents_count": 0,
        "model": payload.get("model"),
        "session_id": payload.get("request", {}).get("session_id")
    }
    
    try:
        request_data = payload.get("request", {})
        contents = request_data.get("contents", [])
        analysis["contents_count"] = len(contents)
        
        for idx, msg in enumerate(contents):
            parts = msg.get("parts", [])
            
            for part_idx, part in enumerate(parts):
                if "functionCall" in part:
                    analysis["has_functionCall"] = True
                    stats["functionCall_count"] += 1
                    
                    func_call = part["functionCall"]
                    detail = {
                        "name": func_call.get("name"),
                        "id": func_call.get("id"),
                        "has_id": bool(func_call.get("id")),
                        "has_thoughtSignature": "thoughtSignature" in func_call,
                        "all_keys": list(func_call.keys())
                    }
                    
                    if detail["has_thoughtSignature"]:
                        analysis["has_thoughtSignature"] = True
                        stats["thoughtSignature_detected"] += 1
                    
                    analysis["functionCall_details"].append(detail)
                
                if "functionResponse" in part:
                    analysis["has_functionResponse"] = True
                    stats["functionResponse_count"] += 1
                    
                    func_resp = part["functionResponse"]
                    response_obj = func_resp.get("response", {})
                    
                    detail = {
                        "name": func_resp.get("name"),
                        "id": func_resp.get("id"),
                        "has_id": bool(func_resp.get("id")),
                        "has_output": "output" in response_obj,
                        "has_content": "content" in response_obj,
                        "output_length": len(str(response_obj.get("output", ""))) if "output" in response_obj else 0,
                        "all_keys": list(func_resp.keys())
                    }
                    
                    analysis["functionResponse_details"].append(detail)
                    
                    # Vérifier corrélation ID
                    if idx > 0:
                        prev_msg = contents[idx - 1]
                        if prev_msg.get("role") == "model":
                            for prev_part in prev_msg.get("parts", []):
                                if "functionCall" in prev_part:
                                    prev_id = prev_part["functionCall"].get("id")
                                    resp_id = func_resp.get("id")
                                    analysis["id_correlations"].append({
                                        "functionCall_id": prev_id,
                                        "functionResponse_id": resp_id,
                                        "match": prev_id == resp_id if (prev_id and resp_id) else None
                                    })
    
    except Exception as e:
        analysis["error"] = str(e)
    
    return analysis


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    """Handler pour intercepter les requêtes HTTP."""
    
    def log_message(self, format, *args):
        """Désactiver les logs par défaut."""
        pass
    
    def do_CONNECT(self):
        """Gérer les connexions HTTPS (tunnel)."""
        # Pour HTTPS, on doit créer un tunnel
        # Pour simplifier, on redirige vers le vrai serveur
        host, port = self.path.split(':', 1) if ':' in self.path else (self.path, '443')
        
        try:
            import socket
            dest_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            dest_sock.connect((host, int(port)))
            
            self.send_response(200, 'Connection Established')
            self.end_headers()
            
            # Tunnel bidirectionnel
            self._tunnel(dest_sock)
        except Exception as e:
            self.send_error(502, f"Proxy Error: {e}")
    
    def do_POST(self):
        """Intercepter les requêtes POST."""
        stats["total_requests"] += 1
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        # Vérifier si c'est une requête vers CodeAssist
        if 'cloudcode-pa.googleapis.com' in self.path or 'v1internal' in self.path:
            stats["codeassist_requests"] += 1
            log_info(f"Requête CodeAssist: {self.path}", "DEBUG")
            
            try:
                payload = json.loads(body.decode('utf-8'))
                
                # Analyser le payload
                is_tool_call = has_tool_call(payload)
                if is_tool_call:
                    stats["tool_call_requests"] += 1
                    log_info("=" * 80, "TOOL_CALL")
                    log_info("TOOL CALL DÉTECTÉ", "TOOL_CALL")
                
                analysis = analyze_payload(payload)
                
                # Sauvegarder le payload
                logs_dir = Path(__file__).parent.parent / "logs"
                logs_dir.mkdir(exist_ok=True)
                
                timestamp = datetime.now().strftime("%d-%b_%Hh%M_%S")
                prefix = "gemini_cli_tool_call" if is_tool_call else "gemini_cli_request"
                filename = logs_dir / f"{prefix}_{timestamp}.json"
                
                capture_data = {
                    "timestamp": datetime.now().isoformat(),
                    "url": self.path,
                    "method": "POST",
                    "headers": dict(self.headers),
                    "payload": payload,
                    "analysis": analysis,
                    "is_tool_call": is_tool_call
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(capture_data, f, indent=2, ensure_ascii=False)
                
                if is_tool_call:
                    log_info(f"Payload sauvegardé: {filename.name}", "TOOL_CALL")
                    log_info(f"  - Model: {analysis.get('model')}", "TOOL_CALL")
                    log_info(f"  - Session ID: {analysis.get('session_id', 'ABSENT')}", "TOOL_CALL")
                    log_info(f"  - functionCall: {analysis.get('has_functionCall')} ({len(analysis.get('functionCall_details', []))})", "TOOL_CALL")
                    log_info(f"  - functionResponse: {analysis.get('has_functionResponse')} ({len(analysis.get('functionResponse_details', []))})", "TOOL_CALL")
                    log_info(f"  - thoughtSignature: {analysis.get('has_thoughtSignature')}", "TOOL_CALL")
                    
                    for fc in analysis.get("functionCall_details", []):
                        id_status = f"id={fc['id']}" if fc['has_id'] else "SANS ID"
                        log_info(f"    functionCall: {fc['name']} - {id_status}", "TOOL_CALL")
                    
                    for fr in analysis.get("functionResponse_details", []):
                        id_status = f"id={fr['id']}" if fr['has_id'] else "SANS ID"
                        log_info(f"    functionResponse: {fr['name']} - {id_status}", "TOOL_CALL")
                    
                    log_info("=" * 80, "TOOL_CALL")
                else:
                    log_info(f"Payload sauvegardé: {filename.name} ({len(body)} bytes)", "INFO")
                
            except Exception as e:
                log_info(f"Erreur capture payload: {e}", "ERROR")
                import traceback
                log_info(traceback.format_exc(), "ERROR")
        
        # Forwarder la requête vers le vrai serveur
        self._forward_request()
    
    def do_GET(self):
        """Intercepter les requêtes GET."""
        self._forward_request()
    
    def _forward_request(self):
        """Forwarder la requête vers le vrai serveur."""
        try:
            import urllib.request
            import urllib.parse
            
            # Extraire l'URL de destination
            url = f"https://{self.headers.get('Host', 'cloudcode-pa.googleapis.com')}{self.path}"
            
            # Reconstruire la requête
            req = urllib.request.Request(url)
            
            # Copier les headers
            for header, value in self.headers.items():
                if header.lower() not in ['host', 'connection']:
                    req.add_header(header, value)
            
            # Si c'est une requête POST, ajouter le body
            if self.command == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                req.data = body
            
            # Envoyer la requête
            try:
                response = urllib.request.urlopen(req, timeout=30)
                
                # Lire la réponse
                response_data = response.read()
                
                # Envoyer la réponse au client
                self.send_response(response.getcode())
                
                # Copier les headers de réponse
                for header, value in response.headers.items():
                    self.send_header(header, value)
                self.end_headers()
                
                # Envoyer le body
                self.wfile.write(response_data)
                
            except urllib.error.HTTPError as e:
                # Gérer les erreurs HTTP
                self.send_response(e.code)
                for header, value in e.headers.items():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(e.read())
                
        except Exception as e:
            self.send_error(502, f"Proxy Error: {e}")
    
    def _tunnel(self, dest_sock):
        """Créer un tunnel bidirectionnel pour HTTPS."""
        # Implémentation simplifiée - pour une vraie implémentation,
        # il faudrait gérer le SSL/TLS
        pass


def run_proxy(port: int = 8888):
    """Démarrer le proxy HTTP."""
    handler = ProxyHandler
    
    print("=" * 80)
    print("PROXY HTTP POUR CAPTURE GEMINI-CLI")
    print("=" * 80)
    print()
    print("⚠️  ATTENTION: Ce proxy a des limitations pour HTTPS.")
    print("   Pour une capture complète, utilisez plutôt:")
    print("   mitmdump -s scripts/capture_gemini_cli_mitmproxy.py")
    print()
    print(f"🌐 Serveur proxy démarré sur le port {port}")
    print(f"📋 Configurez gemini-cli pour utiliser: http://localhost:{port}")
    print(f"   Windows: set HTTP_PROXY=http://localhost:{port}")
    print(f"   Linux/Mac: export HTTP_PROXY=http://localhost:{port}")
    print()
    print("📊 Les payloads seront sauvegardés dans logs/")
    print("   - gemini_cli_tool_call_*.json (tool calls)")
    print("   - gemini_cli_request_*.json (autres requêtes)")
    print()
    print("⏹️  Appuyez sur Ctrl+C pour arrêter")
    print("=" * 80)
    print()
    
    with socketserver.TCPServer(("", port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n" + "=" * 80)
            print("ARRÊT DU PROXY")
            print("=" * 80)
            print(f"📊 Statistiques finales:")
            print(f"  - Total requêtes: {stats['total_requests']}")
            print(f"  - Requêtes CodeAssist: {stats['codeassist_requests']}")
            print(f"  - Requêtes tool call: {stats['tool_call_requests']}")
            print(f"  - functionCall détectés: {stats['functionCall_count']}")
            print(f"  - functionResponse détectés: {stats['functionResponse_count']}")
            print(f"  - thoughtSignature détectés: {stats['thoughtSignature_detected']}")
            print("=" * 80)


if __name__ == "__main__":
    port = 8888
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"[ERROR] Port invalide: {sys.argv[1]}")
            sys.exit(1)
    
    run_proxy(port)


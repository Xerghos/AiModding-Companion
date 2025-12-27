"""
Proxy HTTP local pour capturer les requêtes réelles envoyées par gemini-cli à CodeAssist.
Utilise un serveur HTTP simple qui intercepte les requêtes vers cloudcode-pa.googleapis.com.

Usage:
1. Démarrer le proxy: python scripts/capture_gemini_cli_http_proxy.py
2. Configurer gemini-cli pour utiliser le proxy (via variables d'environnement HTTP_PROXY)
3. Exécuter une requête avec gemini-cli
4. Le payload sera sauvegardé dans logs/gemini_cli_real_payload_*.json
"""

import json
import http.server
import socketserver
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional
import threading
import sys


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
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        # Vérifier si c'est une requête vers CodeAssist
        if 'cloudcode-pa.googleapis.com' in self.path or 'v1internal' in self.path:
            try:
                payload = json.loads(body.decode('utf-8'))
                
                # Sauvegarder le payload
                logs_dir = Path(__file__).parent.parent / "logs"
                logs_dir.mkdir(exist_ok=True)
                
                timestamp = datetime.now().strftime("%d-%b_%Hh%M_%S")
                filename = logs_dir / f"gemini_cli_real_payload_{timestamp}.json"
                
                capture_data = {
                    "timestamp": datetime.now().isoformat(),
                    "url": self.path,
                    "method": "POST",
                    "headers": dict(self.headers),
                    "payload": payload
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(capture_data, f, indent=2, ensure_ascii=False)
                
                print(f"[CAPTURED] Payload sauvegarde: {filename}")
                print(f"[INFO] URL: {self.path}")
                print(f"[INFO] Payload size: {len(body)} bytes")
                
            except Exception as e:
                print(f"[ERROR] Erreur capture payload: {e}")
        
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
    
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"[PROXY] Serveur proxy demarre sur le port {port}")
        print(f"[INFO] Configurez gemini-cli pour utiliser: http://localhost:{port}")
        print(f"[INFO] Exemple: set HTTP_PROXY=http://localhost:{port}")
        print(f"[INFO] Appuyez sur Ctrl+C pour arreter")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[PROXY] Arret du serveur proxy...")


if __name__ == "__main__":
    port = 8888
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"[ERROR] Port invalide: {sys.argv[1]}")
            sys.exit(1)
    
    run_proxy(port)


"""
Serveur MCP HTTP long-running pour partager les outils entre gemini-cli et CodeAssistClient.
Utilise aiohttp pour exposer les outils MCP via HTTP/SSE.

Usage:
    Le serveur démarre automatiquement au lancement de l'application.
    Port par défaut: 8765 (configurable via MCP_HTTP_PORT)
"""
import asyncio
import json
import sys
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

# Ajouter le chemin du projet au PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from aiohttp import web
    from aiohttp.web import Response
except ImportError:
    print("❌ Erreur: Package 'aiohttp' non installé. Installez-le avec: pip install aiohttp")
    sys.exit(1)

from features.UnifiedLogger import UnifiedLogger

# Import des fonctions du serveur MCP stdio
from ai_core.mcp_server import (
    _get_tools_schema,
    _convert_tools_to_mcp_format,
    get_mcp_tools_for_cache,
    set_session_context,
    _active_session,
    _action_log_path,
    _result_queue,
    _task_queue
)

# Configuration du serveur
MCP_HTTP_PORT = int(os.environ.get("MCP_HTTP_PORT", "8765"))
MCP_HTTP_HOST = os.environ.get("MCP_HTTP_HOST", "127.0.0.1")

# Serveur HTTP global
_app: Optional[web.Application] = None
_runner: Optional[web.AppRunner] = None
_site: Optional[web.TCPSite] = None


def get_tools_list() -> List[Dict[str, Any]]:
    """
    Retourne la liste des outils au format MCP.
    Utilise le cache du serveur MCP stdio.
    """
    tools_schema = _get_tools_schema()
    mcp_tools = _convert_tools_to_mcp_format(tools_schema)
    
    # Convertir les objets Tool en dict
    tools_dict = []
    for tool in mcp_tools:
        tools_dict.append({
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.inputSchema
        })
    
    return tools_dict


async def handle_list_tools(request: web.Request) -> Response:
    """
    Endpoint MCP: Liste tous les outils disponibles.
    Compatible avec le protocole MCP.
    """
    try:
        tools = get_tools_list()
        
        # Format de réponse MCP
        response_data = {
            "tools": tools,
            "count": len(tools)
        }
        
        UnifiedLogger.write(
            "MCP_HTTP",
            "INFO",
            f"📋 Liste outils demandée: {len(tools)} outils retournés"
        )
        
        return web.json_response(response_data)
        
    except Exception as e:
        UnifiedLogger.write(
            "MCP_HTTP",
            "ERROR",
            f"❌ Erreur lors de la liste des outils: {e}"
        )
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def handle_call_tool(request: web.Request) -> Response:
    """
    Endpoint MCP: Exécute un outil.
    Compatible avec le protocole MCP.
    """
    try:
        data = await request.json()
        tool_name = data.get("name")
        arguments = data.get("arguments", {})
        
        if not tool_name:
            return web.json_response(
                {"error": "Le nom de l'outil est requis"},
                status=400
            )
        
        UnifiedLogger.write(
            "MCP_HTTP",
            "INFO",
            f"🔧 Appel outil HTTP: {tool_name} avec args: {json.dumps(arguments, ensure_ascii=False)}"
        )
        
        # Importer execute_native_tool
        from features.ai_helper import execute_native_tool
        
        # Exécuter l'outil
        result = execute_native_tool(
            name=tool_name,
            args=arguments,
            session=_active_session,
            action_log_path=_action_log_path,
            result_queue=_result_queue,
            task_queue=_task_queue
        )
        
        # Convertir le résultat en format MCP
        result_text = str(result) if result is not None else "✅ Opération terminée"
        
        # Format de réponse MCP
        response_data = {
            "content": [
                {
                    "type": "text",
                    "text": result_text
                }
            ]
        }
        
        UnifiedLogger.write(
            "MCP_HTTP",
            "SUCCESS",
            f"✅ Outil {tool_name} exécuté avec succès"
        )
        
        return web.json_response(response_data)
        
    except Exception as e:
        error_msg = f"❌ Erreur lors de l'exécution de l'outil '{tool_name}': {str(e)}"
        UnifiedLogger.write(
            "MCP_HTTP",
            "ERROR",
            error_msg
        )
        return web.json_response(
            {
                "content": [
                    {
                        "type": "text",
                        "text": error_msg
                    }
                ]
            },
            status=500
        )


async def handle_health(request: web.Request) -> Response:
    """Endpoint de santé pour vérifier que le serveur est actif."""
    return web.json_response({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "tools_count": len(get_tools_list())
    })


async def handle_sse(request: web.Request) -> Response:
    """
    Endpoint SSE pour le transport Server-Sent Events.
    Compatible avec gemini-cli SSE transport.
    
    Note: gemini-cli peut fermer la connexion après la découverte des outils,
    donc on gère gracieusement la fermeture de connexion.
    
    IMPORTANT: Pour POST, gemini-cli peut envoyer des requêtes MCP dans le body.
    Pour GET, c'est juste une connexion SSE pour recevoir des événements.
    """
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    
    await response.prepare(request)
    
    # Logger la méthode HTTP et les headers pour diagnostic
    UnifiedLogger.write(
        "MCP_HTTP",
        "INFO",
        f"🔗 Connexion SSE: {request.method} {request.path_qs} depuis {request.remote}"
    )
    UnifiedLogger.write(
        "MCP_HTTP",
        "DEBUG",
        f"Headers SSE: {dict(request.headers)}"
    )
    
    # Pour POST, lire le body si présent (gemini-cli peut envoyer des requêtes MCP)
    request_body = None
    if request.method == 'POST':
        try:
            request_body = await request.read()
            if request_body:
                UnifiedLogger.write(
                    "MCP_HTTP",
                    "INFO",
                    f"📦 Body POST reçu ({len(request_body)} bytes): {request_body[:500].decode('utf-8', errors='replace')}"
                )
            else:
                UnifiedLogger.write(
                    "MCP_HTTP",
                    "DEBUG",
                    "Body POST vide"
                )
        except Exception as e:
            UnifiedLogger.write(
                "MCP_HTTP",
                "ERROR",
                f"❌ Erreur lecture body POST: {e}"
            )
    
    try:
        # Envoyer un événement initial de connexion
        UnifiedLogger.write(
            "MCP_HTTP",
            "INFO",
            "✅ Envoi événement de connexion SSE"
        )
        await response.write(b'data: {"type": "connection", "status": "connected"}\n\n')
        
        # Maintenir la connexion ouverte avec des heartbeats
        # gemini-cli peut fermer la connexion à tout moment, donc on gère les exceptions
        heartbeat_count = 0
        while True:
            await asyncio.sleep(1)
            try:
                # Vérifier si la connexion est toujours ouverte avant d'écrire
                transport_closing = False
                try:
                    if hasattr(request, 'transport') and request.transport is not None:
                        transport_closing = request.transport.is_closing()
                except (AttributeError, RuntimeError, OSError):
                    transport_closing = True
                
                if transport_closing:
                    UnifiedLogger.write(
                        "MCP_HTTP",
                        "INFO",
                        f"🔌 Connexion SSE fermée par le client (heartbeat #{heartbeat_count})"
                    )
                    break
                # Envoyer un heartbeat périodique
                heartbeat_count += 1
                if heartbeat_count % 10 == 0:  # Logger tous les 10 heartbeats
                    UnifiedLogger.write(
                        "MCP_HTTP",
                        "DEBUG",
                        f"💓 Heartbeat SSE #{heartbeat_count}"
                    )
                await response.write(b'data: {"type": "heartbeat", "count": ' + str(heartbeat_count).encode() + b'}\n\n')
            except (ConnectionResetError, OSError, asyncio.CancelledError) as e:
                # Connexion fermée par le client - c'est normal
                UnifiedLogger.write(
                    "MCP_HTTP",
                    "INFO",
                    f"🔌 Connexion SSE fermée par le client (heartbeat #{heartbeat_count}): {type(e).__name__}"
                )
                break
            
    except asyncio.CancelledError:
        # Connexion annulée - c'est normal
        UnifiedLogger.write(
            "MCP_HTTP",
            "DEBUG",
            f"Connexion SSE annulée (heartbeat #{heartbeat_count})"
        )
    except Exception as e:
        UnifiedLogger.write(
            "MCP_HTTP",
            "ERROR",
            f"❌ Erreur SSE (heartbeat #{heartbeat_count}): {e}"
        )
    finally:
        # Fermer proprement la connexion si elle n'est pas déjà fermée
        try:
            # Vérifier si le transport existe et n'est pas fermé
            transport_closing = False
            try:
                if hasattr(request, 'transport') and request.transport is not None:
                    transport_closing = request.transport.is_closing()
            except (AttributeError, RuntimeError, OSError):
                # Transport déjà fermé ou invalide
                transport_closing = True
            
            if not transport_closing:
                await response.write_eof()
        except (ConnectionResetError, OSError, RuntimeError, AttributeError) as e:
            # Connexion déjà fermée - c'est normal, on ignore l'erreur
            UnifiedLogger.write(
                "MCP_HTTP",
                "DEBUG",
                f"Connexion SSE déjà fermée lors de write_eof: {type(e).__name__}"
            )
    
    return response


@web.middleware
async def logging_middleware(request: web.Request, handler):
    """Middleware pour logger toutes les requêtes HTTP entrantes."""
    start_time = time.time()
    
    # Logger la requête entrante
    UnifiedLogger.write(
        "MCP_HTTP",
        "DEBUG",
        f"Requête HTTP: {request.method} {request.path_qs} depuis {request.remote} (headers: {dict(request.headers)})"
    )
    
    try:
        response = await handler(request)
        duration = (time.time() - start_time) * 1000
        UnifiedLogger.write(
            "MCP_HTTP",
            "DEBUG",
            f"Réponse HTTP: {request.method} {request.path_qs} -> {response.status} ({duration:.0f}ms)"
        )
        return response
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        UnifiedLogger.write(
            "MCP_HTTP",
            "ERROR",
            f"Erreur HTTP: {request.method} {request.path_qs} -> {type(e).__name__}: {e} ({duration:.0f}ms)"
        )
        raise


def create_app() -> web.Application:
    """Crée l'application aiohttp avec les routes MCP."""
    app = web.Application(middlewares=[logging_middleware])
    
    # Routes MCP
    app.router.add_get('/mcp/tools', handle_list_tools)
    app.router.add_post('/mcp/tools/call', handle_call_tool)
    # SSE doit accepter GET et POST (gemini-cli utilise POST pour initialiser la connexion)
    app.router.add_get('/mcp/sse', handle_sse)
    app.router.add_post('/mcp/sse', handle_sse)
    app.router.add_get('/health', handle_health)
    
    # Route racine pour compatibilité
    app.router.add_get('/', handle_health)
    
    return app


async def start_server(host: str = MCP_HTTP_HOST, port: int = MCP_HTTP_PORT) -> None:
    """
    Démarre le serveur MCP HTTP en arrière-plan.
    """
    global _app, _runner, _site
    
    # Vérifier si le port est déjà utilisé (serveur précédent peut-être encore actif)
    import socket
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1)
        result = test_socket.connect_ex((host, port))
        test_socket.close()
        if result == 0:
            # Le port est déjà utilisé - vérifier si c'est notre serveur
            UnifiedLogger.write(
                "MCP_HTTP",
                "WARNING",
                f"⚠️ Port {port} déjà utilisé. Vérification si le serveur MCP HTTP est déjà actif..."
            )
            try:
                import requests
                health_url = f"http://{host}:{port}/health"
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    UnifiedLogger.write(
                        "MCP_HTTP",
                        "INFO",
                        f"✅ Serveur MCP HTTP déjà actif sur {health_url} ({response.json().get('tools_count', 0)} outils)"
                    )
                    return  # Le serveur est déjà actif, pas besoin d'en démarrer un nouveau
            except Exception:
                pass
            UnifiedLogger.write(
                "MCP_HTTP",
                "WARNING",
                f"⚠️ Port {port} utilisé par un autre processus. Tentative de démarrage quand même..."
            )
    except Exception as e:
        UnifiedLogger.write(
            "MCP_HTTP",
            "DEBUG",
            f"Vérification port échouée: {e}"
        )
    
    try:
        _app = create_app()
        _runner = web.AppRunner(_app)
        await _runner.setup()
        
        _site = web.TCPSite(_runner, host, port)
        await _site.start()
        
        UnifiedLogger.write(
            "MCP_HTTP",
            "START",
            f"🚀 Serveur MCP HTTP démarré sur http://{host}:{port}"
        )
        UnifiedLogger.write(
            "MCP_HTTP",
            "INFO",
            f"📋 Endpoints disponibles: /mcp/tools, /mcp/tools/call, /mcp/sse, /health"
        )
        
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            UnifiedLogger.write(
                "MCP_HTTP",
                "WARNING",
                f"⚠️ Port {port} déjà utilisé. Le serveur MCP HTTP est peut-être déjà démarré. Vérification..."
            )
            # Vérifier si le serveur répond
            try:
                import requests
                health_url = f"http://{host}:{port}/health"
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    UnifiedLogger.write(
                        "MCP_HTTP",
                        "INFO",
                        f"✅ Serveur MCP HTTP déjà actif sur {health_url} ({response.json().get('tools_count', 0)} outils) - Réutilisation du serveur existant"
                    )
                    return  # Le serveur est déjà actif
            except Exception:
                pass
            UnifiedLogger.write(
                "MCP_HTTP",
                "ERROR",
                f"❌ Impossible de démarrer le serveur MCP HTTP: port {port} utilisé et serveur non accessible"
            )
        else:
            UnifiedLogger.write(
                "MCP_HTTP",
                "ERROR",
                f"❌ Erreur démarrage serveur MCP HTTP: {e}"
            )
        raise
    except Exception as e:
        UnifiedLogger.write(
            "MCP_HTTP",
            "ERROR",
            f"❌ Erreur démarrage serveur MCP HTTP: {e}"
        )
        raise


async def stop_server() -> None:
    """Arrête le serveur MCP HTTP."""
    global _runner, _site
    
    try:
        if _site:
            await _site.stop()
        if _runner:
            await _runner.cleanup()
        
        UnifiedLogger.write(
            "MCP_HTTP",
            "INFO",
            "🛑 Serveur MCP HTTP arrêté"
        )
    except Exception as e:
        UnifiedLogger.write(
            "MCP_HTTP",
            "ERROR",
            f"❌ Erreur arrêt serveur MCP HTTP: {e}"
        )


def start_server_background(host: str = MCP_HTTP_HOST, port: int = MCP_HTTP_PORT) -> threading.Thread:
    """
    Démarre le serveur MCP HTTP dans un thread séparé avec une event loop dédiée.
    Retourne le thread pour pouvoir l'arrêter plus tard.
    """
    def run_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Démarrer le serveur
            loop.run_until_complete(start_server(host, port))
            
            # Maintenir la boucle en vie avec une tâche qui ne se termine jamais
            async def keep_alive():
                while True:
                    await asyncio.sleep(1)
            
            loop.create_task(keep_alive())
            # Maintenir la boucle en vie
            loop.run_forever()
        except Exception as e:
            UnifiedLogger.write(
                "MCP_HTTP",
                "ERROR",
                f"Erreur dans la boucle serveur: {e}"
            )
            import traceback
            traceback.print_exc()
        finally:
            try:
                # Arrêter proprement le serveur
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            finally:
                loop.close()
    
    server_thread = threading.Thread(target=run_server, daemon=True, name="MCP-HTTP-Server")
    server_thread.start()
    
    # Attendre un peu pour vérifier que le serveur démarre correctement
    import time
    time.sleep(0.5)
    
    UnifiedLogger.write(
        "MCP_HTTP",
        "INFO",
        f"Thread serveur MCP HTTP demarre (daemon)"
    )
    
    return server_thread


if __name__ == "__main__":
    # Mode standalone pour tests
    async def main():
        await start_server()
        try:
            # Maintenir le serveur en vie
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            await stop_server()
    
    asyncio.run(main())


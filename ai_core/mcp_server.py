"""
Serveur MCP pour exposer nos 41 outils.
Utilise le SDK MCP Python pour créer un serveur stdio qui expose les outils
depuis config/tools_schema.py.

Usage:
    python -m ai_core.mcp_server
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List

# Ajouter le chemin du projet au PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("❌ Erreur: Package 'mcp' non installé. Installez-le avec: pip install mcp")
    sys.exit(1)

from config.tools_schema import TOOLS_SCHEMA
from features.UnifiedLogger import UnifiedLogger

# Créer le serveur MCP
server = Server("aimodding-tools")

# Cache pour stocker la session active (sera injectée par le client)
_active_session = None
_action_log_path = "action_log.json"
_result_queue = None
_task_queue = None


def set_session_context(session, action_log_path="action_log.json", result_queue=None, task_queue=None):
    """Définit le contexte de session pour l'exécution des outils."""
    global _active_session, _action_log_path, _result_queue, _task_queue
    _active_session = session
    _action_log_path = action_log_path
    _result_queue = result_queue
    _task_queue = task_queue


@server.list_tools()
async def list_tools() -> List[Tool]:
    """
    Liste tous nos outils depuis TOOLS_SCHEMA.
    Convertit le format OpenAI/Gemini vers le format MCP Tool.
    """
    mcp_tools = []
    
    for tool_def in TOOLS_SCHEMA:
        # TOOLS_SCHEMA est au format OpenAI: {"name": "...", "description": "...", "parameters": {...}}
        # Convertir vers MCP Tool
        name = tool_def.get("name")
        description = tool_def.get("description", "")
        parameters = tool_def.get("parameters", {})
        
        # Convertir les types en minuscules pour MCP (MCP utilise lowercase)
        def convert_types_to_lowercase(obj):
            """Convertit récursivement les types en minuscules."""
            if isinstance(obj, dict):
                result = {}
                for k, v in obj.items():
                    if k == "type" and isinstance(v, str):
                        result[k] = v.lower()
                    else:
                        result[k] = convert_types_to_lowercase(v)
                return result
            elif isinstance(obj, list):
                return [convert_types_to_lowercase(item) for item in obj]
            else:
                return obj
        
        # Convertir le schéma de paramètres
        mcp_schema = convert_types_to_lowercase(parameters)
        
        mcp_tools.append(Tool(
            name=name,
            description=description,
            inputSchema=mcp_schema
        ))
    
    UnifiedLogger.write(
        "MCP_SERVER",
        "INFO",
        f"📋 {len(mcp_tools)} outils exposés via MCP"
    )
    
    return mcp_tools


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Exécute un outil par son nom.
    Route vers execute_native_tool pour l'exécution réelle.
    """
    try:
        # Importer execute_native_tool
        from features.ai_helper import execute_native_tool
        
        UnifiedLogger.write(
            "MCP_SERVER",
            "INFO",
            f"🔧 Appel outil MCP: {name} avec args: {json.dumps(arguments, ensure_ascii=False)}"
        )
        
        # Exécuter l'outil via execute_native_tool
        result = execute_native_tool(
            name=name,
            args=arguments,
            session=_active_session,
            action_log_path=_action_log_path,
            result_queue=_result_queue,
            task_queue=_task_queue
        )
        
        # Convertir le résultat en TextContent
        result_text = str(result) if result is not None else "✅ Opération terminée"
        
        UnifiedLogger.write(
            "MCP_SERVER",
            "SUCCESS",
            f"✅ Outil {name} exécuté avec succès"
        )
        
        return [TextContent(type="text", text=result_text)]
        
    except Exception as e:
        error_msg = f"❌ Erreur lors de l'exécution de l'outil '{name}': {str(e)}"
        UnifiedLogger.write(
            "MCP_SERVER",
            "ERROR",
            error_msg
        )
        return [TextContent(type="text", text=error_msg)]


async def main():
    """Point d'entrée principal du serveur MCP."""
    UnifiedLogger.write(
        "MCP_SERVER",
        "START",
        "🚀 Démarrage serveur MCP AiModding-Tools"
    )
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except Exception as e:
        UnifiedLogger.write(
            "MCP_SERVER",
            "ERROR",
            f"❌ Erreur serveur MCP: {e}"
        )
        raise


if __name__ == "__main__":
    asyncio.run(main())


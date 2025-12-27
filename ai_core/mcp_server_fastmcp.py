"""
Serveur MCP FastMCP pour exposer nos 41 outils via HTTP/SSE.
Utilise FastMCP pour simplifier l'implémentation et gérer automatiquement JSON-RPC.

Usage:
    Le serveur démarre automatiquement au lancement de l'application via mcp_server_http.py.
    Port par défaut: 8765 (configurable via MCP_HTTP_PORT)
"""
import sys
import os
import inspect
import functools
import types
from pathlib import Path
from typing import Any, Dict, List

# Ajouter le chemin du projet au PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from fastmcp import FastMCP
except ImportError:
    print("❌ Erreur: Package 'fastmcp' non installé. Installez-le avec: pip install fastmcp")
    sys.exit(1)

# Imports optionnels pour éviter les erreurs si les dépendances manquent
try:
    from features.UnifiedLogger import UnifiedLogger
except ImportError:
    # Fallback minimal si UnifiedLogger n'est pas disponible
    class UnifiedLogger:
        @staticmethod
        def write(source, level, message):
            print(f"[{source}] {level}: {message}")

try:
    from features.ai_helper import execute_native_tool
except ImportError:
    execute_native_tool = None

try:
    from config.tools_schema import TOOLS_SCHEMA
except ImportError:
    TOOLS_SCHEMA = []

# Variables de contexte pour l'exécution des outils
# Définies localement pour éviter d'importer ai_core.mcp_server qui dépend de google.generativeai
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

# Créer le serveur FastMCP
mcp = FastMCP(
    name="aimodding-tools",
    instructions="""Serveur MCP pour les outils AiModding-Companion.
    
Expose 41 outils pour :
- Gestion de fichiers (lire, écrire, comparer, créer dossiers)
- Actions Git (commit, push, pull, status, diff)
- Qualité de code (analyse, vérification, refactoring)
- Documentation (génération, mise à jour)
- Recherche sémantique et base de connaissances
- Gestion de projet (roadmap, tâches)
- Et bien plus...

Tous les outils utilisent le contexte de session actif pour l'exécution.
"""
)


def _create_tool_wrapper(tool_name: str, tool_schema: dict):
    """
    Crée dynamiquement une fonction wrapper pour un outil MCP avec des paramètres nommés explicites.
    FastMCP ne supporte pas **kwargs, donc on doit créer des fonctions avec des paramètres nommés.
    
    Args:
        tool_name: Nom de l'outil (ex: "lire_fichier")
        tool_schema: Schéma de l'outil depuis TOOLS_SCHEMA
    
    Returns:
        Fonction async qui peut être enregistrée avec @mcp.tool
    """
    description = tool_schema.get("description", f"Outil {tool_name}")
    parameters = tool_schema.get("parameters", {})
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])
    
    # Créer les annotations de type pour les paramètres
    annotations = {"return": dict}
    defaults = {}
    
    for param_name, param_schema in properties.items():
        param_type = param_schema.get("type", "STRING")
        # Convertir le type MCP en type Python
        if param_type == "STRING":
            annotations[param_name] = str
        elif param_type == "INTEGER" or param_type == "NUMBER":
            annotations[param_name] = int
        elif param_type == "BOOLEAN":
            annotations[param_name] = bool
        elif param_type == "ARRAY":
            annotations[param_name] = list
        elif param_type == "OBJECT":
            annotations[param_name] = dict
        else:
            annotations[param_name] = Any
        
        # Si le paramètre n'est pas requis, lui donner une valeur par défaut
        if param_name not in required:
            if param_type == "STRING":
                defaults[param_name] = ""
            elif param_type == "INTEGER" or param_type == "NUMBER":
                defaults[param_name] = 0
            elif param_type == "BOOLEAN":
                defaults[param_name] = False
            elif param_type == "ARRAY":
                defaults[param_name] = []
            elif param_type == "OBJECT":
                defaults[param_name] = {}
            else:
                defaults[param_name] = None
    
    # Créer le code source de la fonction dynamiquement
    param_list = []
    for param_name in properties.keys():
        if param_name in defaults:
            param_list.append(f"{param_name}: {annotations[param_name].__name__} = {repr(defaults[param_name])}")
        else:
            param_list.append(f"{param_name}: {annotations[param_name].__name__}")
    
    param_str = ", ".join(param_list)
    
    # Code source de la fonction
    func_code = f"""
async def {tool_name}({param_str}) -> dict:
    \"\"\"{description}\"\"\"
    try:
        # Import lazy pour éviter les dépendances au niveau du module
        from ai_core.mcp_server_fastmcp import _active_session, _action_log_path, _result_queue, _task_queue, UnifiedLogger
        
        # Construire le dict des arguments
        args = {{"""
    
    for param_name in properties.keys():
        func_code += f'"{param_name}": {param_name}, '
    
    func_code = func_code.rstrip(", ") + "}\n"
    
    func_code += f"""
        UnifiedLogger.write(
            "MCP_FASTMCP",
            "INFO",
            f"🔧 Appel outil FastMCP: {tool_name} avec args: {{args}}"
        )
        
        # Exécuter l'outil via execute_native_tool si disponible
        try:
            from features.ai_helper import execute_native_tool as _execute_native_tool
            if _execute_native_tool:
                result = _execute_native_tool(
                    name="{tool_name}",
                    args=args,
                    session=_active_session,
                    action_log_path=_action_log_path,
                    result_queue=_result_queue,
                    task_queue=_task_queue
                )
                # Convertir le résultat en format dict pour FastMCP
                result_text = str(result) if result is not None else "✅ Opération terminée"
            else:
                result_text = f"⚠️ Outil '{tool_name}' non disponible (execute_native_tool non disponible)"
        except ImportError:
            result_text = f"⚠️ Outil '{tool_name}' non disponible (dépendances manquantes: google.generativeai). Args: {{args}}"
        except Exception as e:
            result_text = f"⚠️ Erreur lors de l'exécution de l'outil '{tool_name}': {{str(e)}}"
        
        UnifiedLogger.write(
            "MCP_FASTMCP",
            "SUCCESS",
            f"✅ Outil {tool_name} exécuté"
        )
        
        return {{"result": "success", "content": result_text}}
        
    except Exception as e:
        error_msg = f"❌ Erreur lors de l'exécution de l'outil '{tool_name}': {{str(e)}}"
        try:
            from ai_core.mcp_server_fastmcp import UnifiedLogger
            UnifiedLogger.write(
                "MCP_FASTMCP",
                "ERROR",
                error_msg
            )
        except:
            print(error_msg)
        return {{"result": "error", "content": error_msg}}
"""
    
    # Compiler et exécuter le code pour créer la fonction
    namespace = {
        "Any": Any,
        "dict": dict,
        "str": str,
        "int": int,
        "bool": bool,
        "list": list,
    }
    exec(func_code, namespace)
    
    # Récupérer la fonction créée
    tool_func = namespace[tool_name]
    
    # Définir les annotations
    tool_func.__annotations__ = annotations
    
    return tool_func


# Enregistrer dynamiquement tous les outils depuis TOOLS_SCHEMA
def _register_all_tools():
    """Enregistre tous les outils depuis TOOLS_SCHEMA avec FastMCP."""
    tools_registered = 0
    
    for tool_schema in TOOLS_SCHEMA:
        tool_name = tool_schema.get("name")
        if not tool_name:
            continue
        
        try:
            # Créer le wrapper pour cet outil
            wrapper_func = _create_tool_wrapper(tool_name, tool_schema)
            
            # Enregistrer l'outil avec FastMCP
            mcp.tool()(wrapper_func)
            
            tools_registered += 1
            
        except Exception as e:
            UnifiedLogger.write(
                "MCP_FASTMCP",
                "ERROR",
                f"❌ Erreur lors de l'enregistrement de l'outil '{tool_name}': {e}"
            )
    
    UnifiedLogger.write(
        "MCP_FASTMCP",
        "INFO",
        f"📋 {tools_registered} outils enregistrés avec FastMCP"
    )
    
    return tools_registered


# Enregistrer tous les outils au chargement du module
_register_all_tools()


# Route de santé personnalisée (optionnelle, FastMCP en a déjà une)
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request=None):
    """Endpoint de santé pour vérifier que le serveur est actif."""
    from datetime import datetime
    from starlette.responses import JSONResponse
    return JSONResponse({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "server": "aimodding-tools",
        "tools_count": len(TOOLS_SCHEMA)
    })


if __name__ == "__main__":
    # Pour les tests directs du serveur FastMCP
    UnifiedLogger.write("MCP_FASTMCP", "START", "Démarrage direct du serveur FastMCP HTTP...")
    
    # Démarrer le serveur FastMCP avec transport HTTP
    mcp.run(transport="http", host="127.0.0.1", port=8765)


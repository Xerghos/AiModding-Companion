"""
Point d'entrée FastMCP pour le déploiement web.
Réexpose le serveur MCP depuis ai_core.mcp_server_fastmcp
"""
from ai_core.mcp_server_fastmcp import mcp

# L'objet mcp est maintenant accessible depuis la racine
# FastMCP le détectera automatiquement


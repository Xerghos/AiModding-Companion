"""
Point d'entrée FastMCP pour le déploiement web.
Réexpose le serveur MCP depuis ai_core.mcp_server_fastmcp

Gère les dépendances optionnelles pour éviter les erreurs d'import.
"""
import sys
from unittest.mock import MagicMock

# Mock les modules Google qui ne sont pas disponibles sur FastMCP.cloud
# avant qu'ils ne soient importés par les autres modules
if 'google' not in sys.modules:
    sys.modules['google'] = MagicMock()
    sys.modules['google.generativeai'] = MagicMock()
    sys.modules['google.generativeai.caching'] = MagicMock()

# Rendre les imports optionnels pour les autres dépendances qui pourraient manquer
try:
    from ai_core.mcp_server_fastmcp import mcp
except ImportError as e:
    # Si l'import échoue, on essaie de créer un serveur minimal
    print(f"⚠️  Import partiel échoué: {e}")
    print("🔧 Création d'un serveur FastMCP minimal...")
    
    from fastmcp import FastMCP
    
    mcp = FastMCP(
        name="aimodding-tools",
        instructions="Serveur MCP pour les outils AiModding-Companion (mode minimal)"
    )
    
    @mcp.tool()
    async def test_tool() -> dict:
        """Outil de test."""
        return {"result": "success", "message": "Serveur en mode minimal"}

# L'objet mcp est maintenant accessible depuis la racine
# FastMCP le détectera automatiquement


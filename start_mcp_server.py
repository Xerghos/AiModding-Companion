#!/usr/bin/env python
"""
Script pour démarrer le serveur MCP FastMCP localement.
Selon la documentation FastMCP 2.0, le serveur doit être lancé dans un terminal séparé.
"""
import os
import sys
from pathlib import Path

# Ajouter le chemin du projet au PYTHONPATH
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Démarrage du serveur MCP FastMCP")
    print("="*60)
    print("\nLe serveur sera accessible à: http://localhost:8000/mcp")
    print("Appuyez sur Ctrl+C pour arrêter le serveur\n")
    print("="*60 + "\n")
    
    # Importer et lancer le serveur
    try:
        from ai_core.mcp_server_fastmcp import mcp
        import os
        
        # Configuration selon la documentation FastMCP 2.0
        port = int(os.environ.get("MCP_HTTP_PORT", 8000))
        host = os.environ.get("MCP_HTTP_HOST", "127.0.0.1")
        
        mcp.run(transport="http", host=host, port=port)
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt du serveur...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


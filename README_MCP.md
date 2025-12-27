# Guide de démarrage du serveur MCP FastMCP

Ce guide explique comment démarrer le serveur MCP FastMCP localement selon la documentation FastMCP 2.0.

## 🚀 Démarrage rapide

### Option 1: Serveur MCP seul (terminal séparé)

Pour lancer uniquement le serveur MCP dans un terminal séparé :

```batch
start_mcp_server.bat
```

Ou directement avec Python :

```bash
python start_mcp_server.py
```

Le serveur sera accessible à : **http://localhost:8000/mcp**

### Option 2: Application complète avec serveur MCP (deux onglets)

Pour lancer l'application avec le serveur MCP dans deux onglets séparés :

```batch
start_with_mcp.bat
```

Ce script lance :
- **Onglet 1** : Serveur MCP FastMCP (http://localhost:8000/mcp)
- **Onglet 2** : Application principale (run.py)

## 📋 Configuration

Le serveur utilise le port **8000** par défaut (compatible avec FastMCP 2.0).

Vous pouvez modifier le port via les variables d'environnement :

```batch
set MCP_HTTP_PORT=8000
set MCP_HTTP_HOST=127.0.0.1
python start_mcp_server.py
```

**Note** : Le port 8000 est le port par défaut et recommandé (compatible FastMCP 2.0). Vous pouvez utiliser un autre port si nécessaire.

## 🔧 Dépannage

### Le serveur ne démarre pas

1. Vérifiez que toutes les dépendances sont installées :
   ```bash
   pip install -r requirements.txt
   ```

2. Vérifiez que le port 8000 n'est pas déjà utilisé :
   ```bash
   netstat -ano | findstr :8000
   ```

### Erreur "No module named 'google'"

Assurez-vous que `google-generativeai` est installé :
```bash
pip install google-generativeai
```

## 📚 Documentation

Pour plus d'informations sur FastMCP 2.0, consultez la documentation officielle :
- [FastMCP GitHub](https://github.com/jlowin/fastmcp)
- Documentation FastMCP 2.0 (fichier fourni)

## 🛠️ Intégration avec Cursor AI

Pour intégrer le serveur MCP dans Cursor AI, ajoutez dans les paramètres MCP :

```json
{
  "mcpServers": {
    "AiModding-Companion": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```


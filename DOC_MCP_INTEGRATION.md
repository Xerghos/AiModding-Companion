# Intégration MCP pour CodeAssist

## Dépendances

Pour utiliser le filtrage `.gitignore` dans les blocs de contexte, installez `pathspec` :
```bash
pip install pathspec>=0.11.0
```

## Vue d'ensemble

Cette intégration utilise **MCP (Model Context Protocol)** pour exposer nos 41 outils via un serveur MCP, ce qui permet de :

1. **Réduire la taille du payload** : Les outils ne sont plus passés directement dans le payload
2. **Réduire le systemInstruction** : Pas besoin de manuel d'outils dans le system prompt
3. **Éviter les erreurs 500** : Le payload est plus léger et respecte les limites de CodeAssist
4. **Découverte dynamique** : Les outils sont découverts automatiquement par LiteLLM

## Architecture

```
┌─────────────────┐
│  LiteLLMSession │
│  (litellm)      │
└────────┬────────┘
         │
         ├─► CodeAssistClient ──► cloudcode-pa.googleapis.com
         │
         └─► Serveur MCP (stdio) ──► 41 outils natifs
```

## Configuration

### 1. Serveur MCP

Le serveur MCP est dans `ai_core/mcp_server.py`. Il expose nos 41 outils depuis `config/tools_schema.py`.

**Démarrer le serveur MCP manuellement (pour test) :**
```bash
python -m ai_core.mcp_server
```

### 2. Configuration LiteLLM

Le fichier `litellm_config_mcp.yaml` contient la configuration pour LiteLLM Proxy.

**Pour utiliser avec LiteLLM Proxy :**
```bash
litellm --config litellm_config_mcp.yaml
```

**Ou dans votre code Python :**
```python
import litellm

# LiteLLM découvrira automatiquement les outils MCP depuis la config
response = litellm.completion(
    model="codeassist/gemini-3-pro-preview",
    messages=[{"role": "user", "content": "Liste les fichiers du projet"}],
    # Les outils MCP seront automatiquement découverts
)
```

### 3. Intégration dans LiteLLMSession

`LiteLLMSession` utilise automatiquement MCP pour CodeAssist (OAuth) :

- Si `_use_oauth = True` (CodeAssist) → Utilise MCP
- Sinon → Utilise les outils directement (compatibilité)

## Avantages

### Avant (sans MCP)
- Payload avec 41 outils dans `tools` array (~50k+ caractères)
- `systemInstruction` avec manuel d'outils (~274k caractères)
- **Erreur 500** : Payload trop volumineux

### Après (avec MCP)
- Payload léger : Outils découverts via MCP
- `systemInstruction` réduit : Pas de manuel d'outils
- **Pas d'erreur 500** : Payload respecte les limites

## Réduction du systemInstruction

Les modifications dans `litellm_session.py` :

1. **Nettoyage du system_instruction** : Retire le manuel d'outils
2. **Limites réduites** :
   - `LIMIT_ARCH`: 10000 → 5000
   - `LIMIT_TREE`: 10000 → 5000
   - `LIMIT_LTM`: 6000 → 3000

## Test

### Test du serveur MCP

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio

async def test_mcp_server():
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "ai_core.mcp_server"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Lister les outils
            tools_result = await session.list_tools()
            print(f"Outils disponibles: {len(tools_result.tools)}")
            for tool in tools_result.tools[:5]:  # Afficher les 5 premiers
                print(f"  - {tool.name}: {tool.description[:50]}...")
            
            # Tester un outil
            result = await session.call_tool(
                "lister_arborescence",
                {"chemin_relatif": "."}
            )
            print(f"\nRésultat: {result.content[0].text[:200]}...")

asyncio.run(test_mcp_server())
```

### Test avec LiteLLM

```python
import litellm
import os

# Configurer LiteLLM pour utiliser MCP
os.environ["LITELLM_CONFIG_PATH"] = "litellm_config_mcp.yaml"

response = litellm.completion(
    model="codeassist/gemini-3-pro-preview",
    messages=[{"role": "user", "content": "Liste les fichiers du projet"}],
    # Les outils MCP seront automatiquement découverts et utilisés
)

print(response.choices[0].message.content)
```

## Dépannage

### Le serveur MCP ne démarre pas

1. Vérifier que `mcp` est installé : `pip install mcp`
2. Vérifier que le chemin Python est correct dans la config
3. Vérifier les logs dans `logs/global_debug_*.log`

### Les outils MCP ne sont pas découverts

1. Vérifier que LiteLLM Proxy est configuré avec `store_model_in_db: true`
2. Vérifier que le serveur MCP est démarré
3. Vérifier les logs LiteLLM pour les erreurs de connexion MCP

### Erreur 500 persiste

1. Vérifier que MCP est bien utilisé (logs "🔧 Utilisation des outils MCP")
2. Vérifier que le `systemInstruction` est bien réduit (logs payload)
3. Vérifier les limites dans `litellm_session.py`

## Notes

- Le serveur MCP utilise `stdio` (standard input/output) pour la communication
- Les outils sont exécutés via `execute_native_tool` (même logique que avant)
- La session est injectée dans le serveur MCP via `set_session_context()` (à implémenter si nécessaire)


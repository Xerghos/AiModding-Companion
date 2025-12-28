"""
Script pour configurer les secrets OAuth gemini-cli dans le système de secrets.
Facilite la configuration des secrets OAuth pour éviter les warnings au démarrage.
"""

import sys
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_core.keys import KeyManager
from features.UnifiedLogger import UnifiedLogger

def main():
    """Configure les secrets OAuth gemini-cli dans le système de secrets."""
    print("🔧 Configuration des secrets OAuth gemini-cli...")
    
    try:
        key_mgr = KeyManager()
        
        # Valeurs par défaut (publiques dans repo gemini-cli officiel)
        # Source: https://github.com/google-gemini/gemini-cli
        client_id = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
        client_secret = "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"
        
        # Vérifier si déjà configurés
        already_configured = False
        for key, stats in key_mgr.keys.items():
            if stats.provider == "oauth_gemini_cli":
                if "client_id" in stats.alias.lower():
                    print(f"✅ Client ID déjà configuré: {stats.alias}")
                    already_configured = True
                elif "client_secret" in stats.alias.lower():
                    print(f"✅ Client Secret déjà configuré: {stats.alias}")
                    already_configured = True
        
        if not already_configured:
            # Ajouter les secrets
            key_mgr.add_key("oauth_gemini_cli", client_id, "Gemini CLI Client ID")
            key_mgr.add_key("oauth_gemini_cli", client_secret, "Gemini CLI Client Secret")
            print("✅ Secrets OAuth gemini-cli configurés dans le système de secrets")
        else:
            print("ℹ️  Secrets OAuth gemini-cli déjà configurés")
        
        print("\n💡 Note: Ces valeurs sont publiques dans le repo gemini-cli officiel.")
        print("   Elles sont stockées dans secrets.enc (chiffré) pour éviter les warnings.")
        
    except Exception as e:
        print(f"❌ Erreur lors de la configuration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

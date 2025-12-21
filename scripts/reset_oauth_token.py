"""
Script pour supprimer l'ancien token OAuth et forcer une nouvelle authentification
avec les credentials gemini-cli.
"""

import os
import sys

def main():
    token_path = os.path.join(
        os.path.expanduser("~"), 
        ".config", 
        "google", 
        "gemini_oauth_token.json"
    )
    
    if os.path.exists(token_path):
        try:
            os.remove(token_path)
            print(f"[OK] Ancien token OAuth supprime: {token_path}")
            print("\nProchaines etapes:")
            print("1. Ouvrez les Settings de l'application")
            print("2. Allez dans l'onglet 'Hybride / CLI'")
            print("3. Cliquez sur 'Login with Google (OAuth)'")
            print("4. Autorisez l'application dans le navigateur")
            print("\nLes nouveaux tokens utiliseront les credentials gemini-cli avec les bons scopes.")
            return 0
        except Exception as e:
            print(f"[ERREUR] Erreur lors de la suppression du token: {e}")
            return 1
    else:
        print(f"[INFO] Aucun token OAuth trouve a: {token_path}")
        print("Vous pouvez directement vous connecter via le bouton dans les Settings.")
        return 0

if __name__ == "__main__":
    sys.exit(main())


"""
Script pour supprimer l'ancien token OAuth et forcer une nouvelle authentification
avec les credentials gemini-cli.
Supprime depuis keyring (sécurisé) et le fichier legacy si présent.
"""

import os
import sys
import keyring

def main():
    # Supprimer depuis keyring (sécurisé)
    try:
        from ai_core.oauth_validator import SERVICE_ID, OAUTH_KEYRING_NAME
        keyring.delete_password(SERVICE_ID, OAUTH_KEYRING_NAME)
        print("[OK] Ancien token OAuth supprimé depuis keyring (sécurisé)")
    except Exception as e:
        print(f"[INFO] Aucun token OAuth dans keyring: {e}")
    
    # Supprimer aussi le fichier legacy si présent
    token_path = os.path.join(
        os.path.expanduser("~"), 
        ".config", 
        "google", 
        "gemini_oauth_token.json"
    )
    
    if os.path.exists(token_path):
        try:
            os.remove(token_path)
            print(f"[OK] Ancien fichier token OAuth supprimé: {token_path}")
        except Exception as e:
            print(f"[WARNING] Erreur lors de la suppression du fichier: {e}")
    
    print("\nProchaines étapes:")
    print("1. Ouvrez les Settings de l'application")
    print("2. Allez dans l'onglet 'Hybride / CLI'")
    print("3. Cliquez sur 'Login with Google (OAuth)'")
    print("4. Autorisez l'application dans le navigateur")
    print("\nLes nouveaux tokens seront stockés de manière sécurisée dans keyring.")
    return 0

if __name__ == "__main__":
    sys.exit(main())


# Documentation Technique - `features\TokenManager.py`

## 1. En-tête

*   **Titre**: Gestionnaire de Consommation de Tokens
*   **Description concise**: Ce module implémente un gestionnaire centralisé et thread-safe pour le suivi et la persistance de la consommation de tokens des modèles de langage, ventilée par modèle et par clé API. Les statistiques sont chargées au démarrage et sauvegardées après chaque mise à jour.
*   **Dépendances**:
    *   `os`: Pour les opérations de vérification d'existence de fichier.
    *   `json`: Pour la sérialisation et désérialisation des statistiques au format JSON.
    *   `threading`: Pour la gestion des verrous (`threading.Lock`) afin d'assurer la sécurité des opérations concurrentes sur les statistiques.
    *   `config.settings.TOKEN_USAGE_FILE`: Variable de configuration spécifiant le chemin du fichier où les statistiques de tokens sont persistées.
    *   `features.UnifiedLogger.UnifiedLogger`: Utilisé pour enregistrer les erreurs lors du chargement ou de la sauvegarde des statistiques.
    *   `features.Decorators.trace_action`: Importé mais non utilisé directement au sein de la classe `TokenManager` elle-même.

## 2. Classes & Fonctions

### Classe: `TokenManager`

*   **Description**: `TokenManager` est une classe statique conçue pour centraliser la gestion des statistiques de consommation de tokens. Elle gère le chargement, la sauvegarde et la mise à jour incrémentielle des tokens consommés. Elle est conçue pour être thread-safe grâce à l'utilisation d'un verrou (`_lock`).

*   **Attributs de classe**:
    *   `_lock`: `threading.Lock`
        *   **Description**: Un objet verrou qui garantit qu'une seule thread à la fois peut accéder ou modifier les statistiques (`_stats`), prévenant ainsi les courses concurrentielles (race conditions).
    *   `_stats`: `dict`
        *   **Description**: Dictionnaire interne qui stocke toutes les statistiques de consommation de tokens.
            *   `"total_global"`: Dictionnaire avec `"in"` (tokens d'entrée) et `"out"` (tokens de sortie) pour la consommation globale.
            *   `"by_model"`: Dictionnaire où les clés sont les noms de modèles (ex: "gemini-pro") et les valeurs sont des dictionnaires avec `"in"`, `"out"` et `"calls"`.
            *   `"by_key"`: Dictionnaire où les clés sont des identifiants masqués de clés API (ex: "abcdef") et les valeurs sont des dictionnaires avec `"in"`, `"out"` et `"provider"`.

#### Méthode statique: `load()`

*   **Signature**: `def load()`
*   **Arguments**: `N/A`
*   **Retours**: `None`
*   **Logique interne**:
    1.  Acquiert le verrou de la classe (`_lock`) pour assurer l'atomicité de l'opération.
    2.  Vérifie si le fichier spécifié par `TOKEN_USAGE_FILE` existe.
    3.  Si le fichier existe, tente de l'ouvrir en mode lecture (`'r'`) et de désérialiser son contenu JSON dans l'attribut de classe `_stats`.
    4.  En cas d'erreur (ex: fichier corrompu, permission), un message d'erreur est enregistré via `UnifiedLogger`.
    5.  Relâche le verrou.

#### Méthode statique: `save()`

*   **Signature**: `def save()`
*   **Arguments**: `N/A`
*   **Retours**: `None`
*   **Logique interne**:
    1.  Acquiert le verrou de la classe (`_lock`) pour assurer l'atomicité de l'opération.
    2.  Tente d'ouvrir le fichier spécifié par `TOKEN_USAGE_FILE` en mode écriture (`'w'`).
    3.  Sérialise l'attribut de classe `_stats` en JSON, avec une indentation de 2 espaces et sans caractères ASCII non garantis, puis écrit le résultat dans le fichier.
    4.  En cas d'erreur (ex: permission d'écriture, problème de sérialisation), un message d'erreur est enregistré via `UnifiedLogger`.
    5.  Relâche le verrou.

#### Méthode statique: `add_usage(model, api_key_mask, input_tokens, output_tokens)`

*   **Description**: Enregistre une nouvelle consommation de tokens, en la ventilant par modèle et par clé API, et met à jour les totaux globaux.
*   **Signature**: `def add_usage(model: str, api_key_mask: str, input_tokens: int, output_tokens: int)`
*   **Arguments**:
    *   `model` (Type: `str`): Le nom du modèle de langage pour lequel la consommation est enregistrée (ex: "gemini-pro").
    *   `api_key_mask` (Type: `str`): Une chaîne de caractères représentant une version masquée ou partielle de la clé API utilisée. Les 6 derniers caractères sont utilisés comme identifiant.
    *   `input_tokens` (Type: `int`): Le nombre de tokens consommés en entrée pour cette opération.
    *   `output_tokens` (Type: `int`): Le nombre de tokens générés en sortie pour cette opération.
*   **Retours**: `None`
*   **Logique interne**:
    1.  Appelle `TokenManager.load()` pour s'assurer que les statistiques sont à jour avec la dernière version persistée sur le disque, essentiel dans les environnements multi-thread ou multi-processus.
    2.  Acquiert le verrou de la classe (`_lock`) pour protéger les modifications des statistiques.
    3.  **Met à jour les totaux globaux**: Ajoute `input_tokens` et `output_tokens` aux compteurs `total_global["in"]` et `total_global["out"]`.
    4.  **Met à jour les statistiques par modèle**:
        *   Si le `model` n'existe pas encore dans `_stats["by_model"]`, une nouvelle entrée est créée avec des compteurs à zéro.
        *   Les `input_tokens`, `output_tokens` et le nombre d'appels (`calls`) sont ajoutés/incrémentés pour ce modèle.
    5.  **Met à jour les statistiques par clé API**:
        *   Un identifiant `key_id` est extrait des 6 derniers caractères de `api_key_mask`. Si `api_key_mask` est trop court, "unknown" est utilisé.
        *   Si `key_id` n'existe pas encore dans `_stats["by_key"]`, une nouvelle entrée est créée (avec un fournisseur par défaut comme "gemini").
        *   Les `input_tokens` et `output_tokens` sont ajoutés pour cette clé.
    6.  Relâche le verrou.
    7.  Appelle `TokenManager.save()` pour persister les statistiques mises à jour sur le disque.

## 3. Exemple d'usage

```python
import os
import threading
import json
from config.settings import TOKEN_USAGE_FILE
from features.UnifiedLogger import UnifiedLogger
# from features.Decorators import trace_action # Non utilisé directement dans TokenManager

# Simulate TOKEN_USAGE_FILE for example
TOKEN_USAGE_FILE = "token_usage_test.json"

# --- Code source du TokenManager (pour l'exemple) ---
class TokenManager:
    _lock = threading.Lock()
    _stats = {
        "total_global": {"in": 0, "out": 0},
        "by_model": {},
        "by_key": {}
    }

    @staticmethod
    def load():
        with TokenManager._lock:
            if os.path.exists(TOKEN_USAGE_FILE):
                try:
                    with open(TOKEN_USAGE_FILE, 'r', encoding='utf-8') as f:
                        TokenManager._stats = json.load(f)
                except Exception as e:
                    UnifiedLogger.write("TokenManager", "ERROR", f"Erreur chargement stats: {e}")

    @staticmethod
    def save():
        with TokenManager._lock:
            try:
                with open(TOKEN_USAGE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(TokenManager._stats, f, indent=2, ensure_ascii=False)
            except Exception as e:
                UnifiedLogger.write("TokenManager", "ERROR", f"Erreur sauvegarde stats: {e}")

    @staticmethod
    def add_usage(model, api_key_mask, input_tokens, output_tokens):
        TokenManager.load() 
        
        with TokenManager._lock:
            stats = TokenManager._stats
            
            # 1. Total Global
            stats["total_global"]["in"] += input_tokens
            stats["total_global"]["out"] += output_tokens
            
            # 2. Par Modèle
            if model not in stats["by_model"]:
                stats["by_model"][model] = {"in": 0, "out": 0, "calls": 0}
            stats["by_model"][model]["in"] += input_tokens
            stats["by_model"][model]["out"] += output_tokens
            stats["by_model"][model]["calls"] += 1
            
            # 3. Par Clé (Masquée)
            key_id = api_key_mask[-6:] if len(api_key_mask) > 6 else "unknown"
            if key_id not in stats["by_key"]:
                stats["by_key"][key_id] = {"in": 0, "out": 0, "provider": "gemini"} 
            stats["by_key"][key_id]["in"] += input_tokens
            stats["by_key"][key_id]["out"] += output_tokens
            
        TokenManager.save()

# --- Fin du code source ---

# Initialisation (comme dans le script original)
TokenManager.load()

# Exemple d'enregistrement de consommation de tokens
print("Enregistrement de la première consommation...")
TokenManager.add_usage(
    model="gemini-pro-1.5",
    api_key_mask="sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxyxZAB123",
    input_tokens=150,
    output_tokens=30
)
print("Statistiques après la première opération:")
print(json.dumps(TokenManager._stats, indent=2, ensure_ascii=False))

print("\nEnregistrement d'une deuxième consommation avec le même modèle/clé...")
TokenManager.add_usage(
    model="gemini-pro-1.5",
    api_key_mask="sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxyxZAB123",
    input_tokens=200,
    output_tokens=50
)
print("Statistiques après la deuxième opération:")
print(json.dumps(TokenManager._stats, indent=2, ensure_ascii=False))

print("\nEnregistrement d'une consommation avec un nouveau modèle et une nouvelle clé...")
TokenManager.add_usage(
    model="claude-3-opus",
    api_key_mask="sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxXYZ456",
    input_tokens=500,
    output_tokens=120
)
print("Statistiques après la troisième opération:")
print(json.dumps(TokenManager._stats, indent=2, ensure_ascii=False))

# Vérifier le contenu du fichier de persistance
if os.path.exists(TOKEN_USAGE_FILE):
    with open(TOKEN_USAGE_FILE, 'r', encoding='utf-8') as f:
        persisted_stats = json.load(f)
    print(f"\nContenu du fichier '{TOKEN_USAGE_FILE}':")
    print(json.dumps(persisted_stats, indent=2, ensure_ascii=False))

# Nettoyage du fichier de test
os.remove(TOKEN_USAGE_FILE)
print(f"\nFichier de test '{TOKEN_USAGE_FILE}' supprimé.")
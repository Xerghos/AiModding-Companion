# Documentation Technique - `ai_core/factory.py`

## 1. En-tête

*   **Titre**: Fabrique de Sessions IA Intelligente
*   **Description concise**: Ce module implémente une fabrique de sessions IA (`SmartSessionFactory`) centralisée, responsable de l'initialisation dynamique et de la configuration des sessions d'IA (Gemini, Groq, DeepSeek, etc.) en fonction des paramètres de l'application et des requêtes des agents. Elle s'appuie sur un `KeyManager` unique pour la gestion sécurisée des clés d'API et intègre des logiques de routage avancées (ex: CLI Bridge) et de fallback de modèles.
*   **Dépendances**:
    *   `google.generativeai`: Client Python officiel pour l'API Gemini.
    *   `config.settings.APP_SETTINGS`: Paramètres de configuration globaux de l'application.
    *   `config.logs.get_logger`: Utilitaire pour l'initialisation des loggers.
    *   `ai_core.keys.KeyManager`: Gestionnaire centralisé pour toutes les clés d'API.
    *   `ai_core.sessions.GeminiSession`: Classe pour les interactions avec l'API Gemini.
    *   `ai_core.sessions.GroqSession`: Classe pour les interactions avec l'API Groq.
    *   `ai_core.sessions.DeepSeekSession`: Classe pour les interactions avec l'API DeepSeek.
    *   `ai_core.sessions.GeminiCliSession`: Classe pour les interactions via l'outil CLI Gemini.
    *   `ai_core.sessions.UniversalResponseWrapper`: Wrapper pour les réponses non implémentées.
    *   `features.Decorators.trace_action`: Décorateur pour le traçage des appels de fonctions.
    *   `features.UnifiedLogger.UnifiedLogger`: Système de journalisation unifié de l'application.

## 2. Classes & Fonctions

### Classe `SmartSessionFactory`

```python
class SmartSessionFactory:
    """
    Fabrique centrale pour les sessions IA (V3.2 - Clean Init).
    Délègue l'entière responsabilité de l'initialisation à la Session elle-même.
    Mise à jour pour utiliser le KeyManager centralisé (Global Keyring).
    """
    # ... (méthodes)
```

**Description**: Cette classe est une implémentation du patron de conception "Factory" pour la création de sessions d'IA. Elle centralise la logique de sélection du fournisseur, la résolution des modèles, la gestion des clés d'API via `KeyManager`, et l'application des configurations spécifiques (instructions système, outils, etc.).

#### Méthodes

---

#### `__init__(self)`

```python
    def __init__(self):
```

*   **Arguments**:
    *   `self`: L'instance de la classe.
*   **Retours**: `None`
*   **Logique interne**:
    *   Initialise un dictionnaire `self.settings` vide pour stocker la configuration de l'application.
    *   Crée une instance unique de `KeyManager` (`self.key_manager`), qui gérera l'ensemble du trousseau de clés d'API.
    *   Initialise `self.registry` (mapping d'alias de modèles vers des modèles réels) et `self.agent_mapping` (mapping de rôles d'agents vers des alias de modèles) à des dictionnaires vides.
    *   Appelle `self.refresh_config()` pour charger la configuration initiale.

---

#### `refresh_config(self)`

```python
    @trace_action(source="factory")
    def refresh_config(self):
```

*   **Arguments**:
    *   `self`: L'instance de la classe.
*   **Retours**: `None`
*   **Logique interne**:
    *   Met à jour `self.settings` en récupérant la configuration globale depuis `APP_SETTINGS`.
    *   Récupère les configurations `ai_engine` et `swarm_settings` des paramètres de l'application.
    *   Charge le `cloud_models_registry` (registre d'alias de modèles) dans `self.registry`.
    *   Charge le `role_mapping` (mapping d'agents vers des alias) dans `self.agent_mapping`.
    *   Définit des valeurs par défaut pour les alias de modèles courants (ex: "fast", "smart", "coder") si elles ne sont pas déjà présentes dans le registre, assurant ainsi une configuration de base.
    *   Journalise l'état de chargement de la configuration.

---

#### `_resolve_real_model(self, request_type)`

```python
    def _resolve_real_model(self, request_type):
```

*   **Arguments**:
    *   `request_type` (`str`): Le type de requête ou le nom de l'agent (ex: "coder", "fast").
*   **Retours**: `tuple[str, str]`
    *   Un tuple contenant l'alias de profil résolu et le nom du modèle réel.
*   **Logique interne**:
    *   Convertit `request_type` en minuscules pour une comparaison insensible à la casse.
    *   Utilise `self.agent_mapping` pour traduire le `request_type` en un `profile_alias` (ex: "coder" -> "gemini-pro").
    *   Utilise `self.registry` pour traduire le `profile_alias` en `real_model` (ex: "gemini-pro" -> "gemini-1.5-pro-latest").
    *   Retourne les deux valeurs.

---

#### `_generate_model_cascade(self, primary_model, available_models)`

```python
    def _generate_model_cascade(self, primary_model, available_models):
```

*   **Arguments**:
    *   `primary_model` (`str`): Le nom du modèle principal pour lequel générer une cascade.
    *   `available_models` (`list[str]`): Une liste de tous les noms de modèles disponibles.
*   **Retours**: `list[str]`
    *   Une liste de modèles de secours compatibles, limitée à un maximum de 2.
*   **Logique interne**:
    *   Crée une liste vide `cascade`.
    *   Si le `primary_model` contient "pro", tente d'ajouter la version "flash" correspondante à la cascade comme premier fallback.
    *   Identifie le nom de base du fournisseur du `primary_model` (ex: "gemini").
    *   Ajoute d'autres modèles disponibles qui partagent le même nom de base et qui ne sont ni le modèle principal ni déjà dans la cascade.
    *   Retourne les deux premiers modèles de la cascade générée.

---

#### `create_session(self, model_type="core", enable_tools=True, cache_name=None, system_instruction=None, agent_name=None)`

```python
    @trace_action(source="factory")
    def create_session(self, model_type="core", enable_tools=True, cache_name=None, system_instruction=None, agent_name=None):
```

*   **Arguments**:
    *   `model_type` (`str`, optional): Le type de modèle ou le profil d'agent demandé (ex: "fast", "smart", "coder"). Par défaut à `"core"`.
    *   `enable_tools` (`bool`, optional): Indique si les outils doivent être activés pour la session. Applicable principalement aux modèles Gemini. Par défaut à `True`.
    *   `cache_name` (`str`, optional): Nom du cache à utiliser pour la session. Applicable principalement aux modèles Gemini. Par défaut à `None`.
    *   `system_instruction` (`str`, optional): Une instruction système spécifique à passer au modèle. Si `None`, la fabrique essaiera de la récupérer des `APP_SETTINGS` en fonction du `model_type`.
    *   `agent_name` (`str`, optional): Le nom spécifique de l'agent qui utilise cette session. Utilisé pour l'identité de la session dans les logs. Si `None`, `model_type` sera capitalisé et utilisé.
*   **Retours**: `GeminiSession | GroqSession | DeepSeekSession | GeminiCliSession | UniversalResponseWrapper`
    *   Une instance de session IA configurée et prête à l'emploi.
*   **Logique interne**:
    1.  **Résolution du modèle**: Appelle `_resolve_real_model` pour obtenir l'alias du profil et le nom du modèle réel.
    2.  **Détection du fournisseur**: Détermine le fournisseur (DeepSeek, Groq, OpenAI, Gemini) en analysant le nom du `real_model`.
    3.  **Instruction système**: Si `system_instruction` n'est pas fourni, le récupère des `system_prompts` configurés dans `APP_SETTINGS` en fonction du `model_type`.
    4.  **Identité de l'agent**: Définit `agent_identity` à partir de `agent_name` ou en capitalisant `model_type`.
    5.  **Instanciation par fournisseur**:
        *   **DeepSeek**: Instancie `DeepSeekSession`, gérant un routage spécial via `base_url` si le modèle contient `"(Special)"`.
        *   **Groq**: Instancie `GroqSession`.
        *   **OpenAI**: Retourne un `UniversalResponseWrapper` indiquant que le fournisseur n'est pas implémenté.
        *   **Gemini (par défaut)**:
            *   **Routage CLI**: Vérifie si le `cli_bridge` est activé dans `APP_SETTINGS` et si le `real_model` est configuré pour être routé via le CLI. Si c'est le cas, tente d'instancier `GeminiCliSession`. En cas d'échec de cette instanciation (ex: CLI non disponible), un fallback est effectué vers l'API standard.
            *   **API Standard**: Génère une chaîne de modèles de secours avec `_generate_model_cascade`. Instancie `GeminiSession`, en lui passant le `key_manager` unique, le modèle réel, les instructions système, les options d'outils, le nom du cache et la chaîne de fallback.
    6.  **Gestion des erreurs**: Capture les exceptions lors de l'instanciation, journalise une erreur critique et re-lève l'exception.

---

#### `audit_all_providers(self)`

```python
    @trace_action(source="factory")
    def audit_all_providers(self):
```

*   **Arguments**:
    *   `self`: L'instance de la classe.
*   **Retours**: `dict`
    *   Un dictionnaire où les clés sont les noms des fournisseurs et les valeurs sont des listes de dictionnaires, chacun représentant le statut d'une clé d'API pour ce fournisseur.
*   **Logique interne**:
    *   Initialise un dictionnaire vide `report`.
    *   Itère sur toutes les clés d'API stockées dans `self.key_manager`.
    *   Pour chaque clé, extrait le fournisseur et ses statistiques.
    *   Regroupe les statistiques par fournisseur dans le dictionnaire `report`.
    *   Retourne le rapport consolidé.

---

#### `get_key_status(self, provider, key)`

```python
    @trace_action(source="factory")
    def get_key_status(self, provider, key):
```

*   **Arguments**:
    *   `provider` (`str`): Le nom du fournisseur (ex: "google_gemini", "deepseek").
    *   `key` (`str`): L'identifiant unique de la clé (généralement son préfixe ou son hash).
*   **Retours**: `dict | str`
    *   Un dictionnaire contenant le statut détaillé de la clé si elle est trouvée et correspond au fournisseur, sinon la chaîne `"KEY_NOT_FOUND"`.
*   **Logique interne**:
    *   Recherche la `key` directement dans les clés gérées par `self.key_manager`.
    *   Si la clé est trouvée, vérifie si son fournisseur correspond au `provider` spécifié (ou si `provider` est "all").
    *   Si la correspondance est établie, retourne les statistiques de la clé sous forme de dictionnaire.
    *   Sinon, retourne `"KEY_NOT_FOUND"`.

---

### Variable globale `SessionFactory`

```python
SessionFactory = SmartSessionFactory()
```

**Description**: Une instance unique (singleton) de `SmartSessionFactory` est créée et rendue disponible globalement sous le nom `SessionFactory`. Cela permet à d'autres modules d'importer et d'utiliser directement la fabrique sans avoir à l'instancier eux-mêmes.

## 3. Exemple d'usage

```python
from ai_core.factory import FactorySession

# Exemple 1 : Créer une session pour un agent "fast" avec une instruction système par défaut
fast_session = FactorySession.create_session(model_type="fast", agent_name="AssistantRapide")
print(f"Session rapide créée pour {fast_session.model_name}")
# Utilisez fast_session pour interagir avec le modèle
# response = fast_session.send_message("Quelle est la capitale de la France ?")
# print(response.text)

# Exemple 2 : Créer une session pour un "coder" avec une instruction système personnalisée
coder_instruction = "Tu es un assistant de programmation expert. Réponds uniquement avec du code et des commentaires."
coder_session = FactorySession.create_session(
    model_type="coder",
    system_instruction=coder_instruction,
    enable_tools=False, # Les outils ne sont peut-être pas pertinents pour ce rôle
    agent_name="DevBot"
)
print(f"Session codeur créée pour {coder_session.model_name}")
# response = coder_session.send_message("Écris une fonction Python pour calculer le factoriel.")
# print(response.text)

# Exemple 3 : Créer une session DeepSeek
deepseek_session = FactorySession.create_session(model_type="deepseek-chat") # Supposons que 'deepseek-chat' soit dans le registry
print(f"Session DeepSeek créée pour {deepseek_session.model_name}")

# Exemple 4 : Auditer toutes les clés d'API gérées
report_keys = FactorySession.audit_all_providers()
print("\nRapport d'audit des clés d'API:")
for provider, keys in report_keys.items():
    print(f"  Provider: {provider}")
    for key_info in keys:
        print(f"    - ID: {key_info['id']}, Modèle: {key_info['model_name']}, Statut: {key_info['status']}")

# Exemple 5 : Récupérer le statut d'une clé spécifique
# (Nécessite de connaître une clé existante, ici un exemple générique)
gemini_key_status = FactorySession.get_key_status("google_gemini", "my_gemini_api_key_id")
print(f"\nStatut de la clé Gemini: {gemini_key_status}")
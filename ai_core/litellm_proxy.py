"""
LiteLLM Proxy - Proxy universel pour toutes les APIs LLM.
Phase 1.1 : Création LiteLLMProxy avec préservation Context Caching DeepSeek.
"""

import time
import json
import logging
import os
from typing import Optional, Dict, List, Iterator, Any
from enum import Enum

try:
    import litellm
    # LiteLLM utilise completion() avec stream=True pour le streaming
    # Il n'y a pas de fonction stream_completion() séparée
    from litellm import completion
    LITELLM_AVAILABLE = True
except ImportError as e:
    LITELLM_AVAILABLE = False
    litellm = None
    completion = None

# Import pour l'authentification Google OAuth (Login with Google)
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    GOOGLE_OAUTH_AVAILABLE = True
except ImportError:
    GOOGLE_OAUTH_AVAILABLE = False
    Credentials = None
    Request = None

from features.UnifiedLogger import UnifiedLogger
from features.Decorators import trace_action
from config.settings import APP_SETTINGS

log = logging.getLogger("ai_core.litellm_proxy")


class ModelProvider(Enum):
    """Enum des providers supportés."""
    DEEPSEEK = "deepseek"
    GEMINI = "google"
    GROQ = "groq"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LiteLLMProxy:
    """
    Proxy LiteLLM qui préserve le Context Caching DeepSeek.
    
    Fonctionnalités :
    - Transmet messages dans l'ordre exact (pas de réorganisation)
    - Configure cache par modèle (DeepSeek: context caching, Gemini: cached content)
    - Support streaming
    - Support tool calling
    - Métriques cache hit/miss
    """
    
    def __init__(self):
        """Initialise le proxy LiteLLM."""
        if not LITELLM_AVAILABLE:
            raise ImportError(
                "LiteLLM n'est pas installé. Installez-le avec: pip install litellm"
            )
        
        # Configuration LiteLLM pour préserver l'ordre des messages
        # IMPORTANT : Ne pas réorganiser les messages pour préserver le cache
        litellm.drop_params = True  # Ignore les paramètres non supportés
        litellm.suppress_debug_info = True  # Réduit les logs verbeux
        
        UnifiedLogger.write("AI_CORE", "INIT", "LiteLLMProxy initialisé")
    
    @staticmethod
    def _detect_provider(model_name: str) -> ModelProvider:
        """
        Détecte le provider à partir du nom du modèle.
        
        Args:
            model_name: Nom du modèle (ex: "deepseek-chat", "gemini-2.5-flash")
        
        Returns:
            ModelProvider correspondant
        """
        model_lower = model_name.lower()
        
        if "deepseek" in model_lower:
            return ModelProvider.DEEPSEEK
        elif "gemini" in model_lower or "google" in model_lower:
            return ModelProvider.GEMINI
        elif "groq" in model_lower or "llama" in model_lower or "mixtral" in model_lower:
            return ModelProvider.GROQ
        elif "gpt" in model_lower or "openai" in model_lower:
            return ModelProvider.OPENAI
        elif "claude" in model_lower or "anthropic" in model_lower:
            return ModelProvider.ANTHROPIC
        else:
            # Fallback : essayer de détecter depuis le format
            if model_lower.startswith("deepseek"):
                return ModelProvider.DEEPSEEK
            elif model_lower.startswith("gemini"):
                return ModelProvider.GEMINI
            else:
                # Par défaut, essayer Gemini
                return ModelProvider.GEMINI
    
    @staticmethod
    def _normalize_model_name(model_name: str, provider: ModelProvider) -> str:
        """
        Normalise le nom du modèle pour LiteLLM.
        
        Args:
            model_name: Nom du modèle original
            provider: Provider détecté
        
        Returns:
            Nom du modèle normalisé pour LiteLLM
        """
        model_lower = model_name.lower()
        
        if provider == ModelProvider.DEEPSEEK:
            # DeepSeek : garder le nom tel quel ou normaliser
            if "reasoner" in model_lower:
                return "deepseek-reasoner"
            elif "speciale" in model_lower:
                # Endpoint spécial : utiliser le nom original
                return model_name  # Garder le nom original pour routing
            else:
                return "deepseek-chat"
        
        elif provider == ModelProvider.GEMINI:
            # Gemini : normaliser vers format LiteLLM
            if "2.5" in model_lower:
                if "pro" in model_lower:
                    return "gemini-2.5-pro"
                elif "flash" in model_lower:
                    if "lite" in model_lower:
                        return "gemini-2.5-flash-lite"
                    else:
                        return "gemini-2.5-flash"
            # Fallback
            return model_name
        
        elif provider == ModelProvider.GROQ:
            # Groq : normaliser
            if "llama" in model_lower:
                if "70b" in model_lower:
                    return "llama3-70b-8192"
                elif "8b" in model_lower:
                    return "llama3-8b-8192"
            elif "mixtral" in model_lower:
                return "mixtral-8x7b-32768"
            return model_name
        
        else:
            # Autres providers : garder tel quel
            return model_name
    
    def _try_google_oauth_auth(self) -> bool:
        """
        Essaie d'utiliser l'authentification Google OAuth (Login with Google).
        Permet d'utiliser les tokens gratuits Google AI Pro sans API key.
        Compatible avec gemini-cli.
        
        Returns:
            True si OAuth est disponible, False sinon
        """
        if not GOOGLE_OAUTH_AVAILABLE:
            return False
        
        try:
            import json
            
            # Vérifier si les tokens OAuth sont stockés (comme gemini-cli)
            # os est déjà importé au début du fichier (ligne 9)
            token_path = os.path.join(os.path.expanduser("~"), ".config", "google", "gemini_oauth_token.json")
            
            if not os.path.exists(token_path):
                return False
            
            # Charger et valider les credentials OAuth avec le validateur
            from ai_core.oauth_validator import load_and_validate_oauth_credentials
            
            creds, error_msg = load_and_validate_oauth_credentials(token_path)
            if creds is None:
                UnifiedLogger.write(
                    "AI_CORE",
                    "DEBUG",
                    f"⚠️ Echec chargement credentials OAuth: {error_msg}"
                )
                return False
            
            if creds.valid:
                # CRITIQUE: NE JAMAIS définir GOOGLE_APPLICATION_CREDENTIALS ici !
                # Cela déclencherait la détection Vertex AI dans LiteLLM
                # On utilisera uniquement l'access token comme API key dans completion()
                UnifiedLogger.write(
                    "AI_CORE",
                    "AUTH",
                    "✅ Authentification Google OAuth (Login with Google) disponible - Utilisation des tokens gratuits"
                )
                return True
        except Exception as e:
            UnifiedLogger.write(
                "AI_CORE",
                "DEBUG",
                f"⚠️ Echec vérification OAuth: {e}, utilisation API key"
            )
        
        return False
    
    @trace_action(source="litellm_proxy")
    def completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        api_key: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> Any:
        """
        Appel completion LiteLLM avec préservation de l'ordre des messages.
        Supporte l'authentification Google OAuth (Login with Google) pour profiter des tokens gratuits.
        
        Args:
            model: Nom du modèle
            messages: Liste de messages (ordre préservé)
            api_key: Clé API (optionnel si OAuth disponible pour Gemini)
            stream: Mode streaming
            temperature: Température
            max_tokens: Nombre max de tokens
            tools: Outils (tool calling)
            **kwargs: Paramètres additionnels
        
        Returns:
            Réponse LiteLLM (objet ou générateur si stream)
        """
        provider = self._detect_provider(model)
        normalized_model = self._normalize_model_name(model, provider)
        
        # Ajuster la température pour les modèles Gemini-3
        # LiteLLM émet un warning si température < 1.0 pour Gemini-3
        adjusted_temperature = temperature
        if provider == ModelProvider.GEMINI and "gemini-3" in model.lower():
            # Forcer température = 1.0 pour Gemini-3 comme recommandé par LiteLLM
            if temperature < 1.0:
                UnifiedLogger.write(
                    "AI_CORE",
                    "WARNING",
                    f"⚠️ Ajustement température Gemini-3: {temperature} -> 1.0 (recommandé par LiteLLM pour éviter boucles infinies)"
                )
                adjusted_temperature = 1.0
        
        # Configuration spécifique par provider
        model_config = {
            "model": normalized_model,
            "messages": messages,  # Ordre préservé
            "stream": stream,
            "temperature": adjusted_temperature,
        }
        
        # Gestion de l'authentification : OAuth (Login with Google) pour Gemini si disponible, sinon API key
        use_oauth = False
        if provider == ModelProvider.GEMINI:
            # CAS 3 (Strict) : Si Bridge activé ET Modèle dans la liste -> OAuth/CodeAssist
            # On vérifie les paramètres CLI Bridge
            cli_cfg = APP_SETTINGS.get("cli_bridge", {})
            cli_enabled = cli_cfg.get("enabled", False)
            cli_models = [m.lower().strip() for m in cli_cfg.get("models", [])]
            
            # Modèle est-il dans la liste ?
            is_bridged = cli_enabled and (model.lower().strip() in cli_models or normalized_model.lower().strip() in cli_models)
            
            if is_bridged:
                # Essayer d'utiliser l'auth Google OAuth (Login with Google)
                if self._try_google_oauth_auth():
                    use_oauth = True
                    UnifiedLogger.write("AI_CORE", "CLI_BRIDGE", f"🌉 CAS 3: CodeAssist activé pour {normalized_model}")
            
            if use_oauth:
                # IMPORTANT: Utiliser le custom provider LiteLLM pour CodeAssist
                # Cela permet à LiteLLM d'orchestrer (monitoring, fallback, routing)
                # tout en utilisant CodeAssist (OAuth, tokens gratuits, format CodeAssist)
                
                from ai_core.litellm_codeassist_provider import codeassist_completion
                
                UnifiedLogger.write(
                    "AI_CORE",
                    "AUTH",
                    f"🔐 Utilisation Custom Provider CodeAssist (OAuth) pour {normalized_model} - Orchestration LiteLLM + CodeAssist"
                )
                
                # Appeler le custom provider directement
                # Le format de retour est compatible LiteLLM (choices, usage, etc.)
                # Ne pas passer project_id pour utiliser le quota personnel Google AI Pro
                # (comme gemini-cli le fait)
                
                start_t = time.time()
                
                try:
                    # Extraire session_id de kwargs pour éviter le conflit "multiple values for keyword argument"
                    # lors du déballage de **kwargs
                    assist_session_id = kwargs.pop("session_id", None)
                    
                    # Appeler codeassist_completion avec les paramètres LiteLLM
                    # project_id=None pour utiliser le quota personnel
                    response = codeassist_completion(
                        model=normalized_model,
                        messages=messages,
                        stream=stream,
                        temperature=adjusted_temperature,
                        max_tokens=max_tokens,
                        tools=tools,
                        project_id=None,  # None = utilise quota personnel Google AI Pro
                        session_id=assist_session_id,
                        **kwargs
                    )
                    
                    if not stream:
                        duration = time.time() - start_t
                        UnifiedLogger.write(
                            "AI_CORE",
                            "SUCCESS",
                            f"LiteLLM CodeAssist completion terminé ({duration:.2f}s)"
                        )
                    
                    return response
                except Exception as e:
                    UnifiedLogger.write("AI_CORE", "ERROR", f"LiteLLM CodeAssist Exception: {e}")
                    raise e
            elif api_key:
                # Fallback sur API key si OAuth non disponible
                # IMPORTANT: Préfixer avec "gemini/" pour forcer Google AI Studio
                # Sans ce préfixe, LiteLLM détecte "gemini" et route vers Vertex AI
                # qui nécessite des credentials GCP (Application Default Credentials)
                if not normalized_model.startswith("gemini/"):
                    litellm_model = f"gemini/{normalized_model}"
                else:
                    litellm_model = normalized_model
                
                model_config["model"] = litellm_model
                model_config["api_key"] = api_key
                UnifiedLogger.write(
                    "AI_CORE",
                    "AUTH",
                    f"🔑 Utilisation API key pour {litellm_model} (Google AI Studio)"
                )
            else:
                # Pas d'API key et pas d'OAuth - erreur
                raise ValueError(
                    f"Aucune méthode d'authentification disponible pour {model}. "
                    "Configurez Login with Google (OAuth) ou fournissez une API key."
                )
        else:
            # Autres providers : utiliser API key normalement
            if api_key:
                model_config["api_key"] = api_key
            else:
                raise ValueError(f"API key requise pour {model}")
        
        if max_tokens:
            model_config["max_tokens"] = max_tokens
        
        if tools:
            model_config["tools"] = tools
        
        # Configuration cache par provider
        if provider == ModelProvider.DEEPSEEK:
            # DeepSeek : Context Caching implicite (préfixe stable)
            # Pas de configuration spéciale, l'ordre des messages est déjà préservé
            # Le cache fonctionne automatiquement si le préfixe est stable
            pass
        
        elif provider == ModelProvider.GEMINI:
            # Gemini : CachedContent (si disponible)
            # Note : Le cache Gemini est géré par CacheManager, pas ici
            # Avec OAuth, on utilise l'API Gemini standard qui supporte aussi le cache
            pass
        
        # Ajouter paramètres additionnels
        model_config.update(kwargs)
        
        UnifiedLogger.write(
            "AI_CORE",
            "START",
            f"LiteLLM ({normalized_model}) completion...",
            {"provider": provider.value, "stream": stream}
        )
        
        try:
            from litellm import completion
            
            start_t = time.time()
            
            # CRITIQUE: Désactiver les variables d'environnement Google Cloud AVANT l'appel LiteLLM
            # (si OAuth est utilisé) pour éviter la détection automatique de Vertex AI
            restore_env_vars = model_config.pop('_restore_env_vars', None)
            
            # Si OAuth est utilisé, s'assurer que toutes les variables sont désactivées
            # et que les paramètres Vertex AI sont explicitement désactivés
            if restore_env_vars is not None:
                # Vérifier que toutes les variables sont bien désactivées
                # os est déjà importé au début du fichier (ligne 9)
                for env_var in ['GOOGLE_APPLICATION_CREDENTIALS', 'GCLOUD_PROJECT', 
                               'GOOGLE_CLOUD_PROJECT', 'GCP_PROJECT', 
                               'CLOUDSDK_CORE_PROJECT', 'GOOGLE_CLOUD_QUOTA_PROJECT']:
                    if env_var in os.environ:
                        # Si une variable est encore présente, la désactiver
                        if env_var not in restore_env_vars:
                            restore_env_vars[env_var] = os.environ.pop(env_var)
                
                # Forcer explicitement Gemini API (pas Vertex AI)
                model_config["vertex_project"] = None
                model_config["vertex_location"] = None
                # S'assurer que le modèle commence par "gemini/" et non "vertex/"
                if model_config.get("model", "").startswith("vertex/"):
                    model_config["model"] = model_config["model"].replace("vertex/", "gemini/")
            
            try:
                if stream:
                    # Mode streaming : utiliser completion avec stream=True
                    model_config['stream'] = True
                    response = completion(**model_config)
                    return response
                else:
                    # Mode standard
                    model_config['stream'] = False
                    response = completion(**model_config)
                    
                    duration = time.time() - start_t
                    UnifiedLogger.write(
                        "AI_CORE",
                        "SUCCESS",
                        f"LiteLLM completion terminé ({duration:.2f}s)"
                    )
                    
                    return response
            finally:
                # Restaurer toutes les variables d'environnement Google Cloud si on les avait désactivées
                # Note: os est déjà importé au début du fichier
                if restore_env_vars is not None:
                    for env_var, value in restore_env_vars.items():
                        if value is not None:
                            os.environ[env_var] = value
        
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "ERROR", f"LiteLLM Exception: {e}")
            raise e
    
    @trace_action(source="litellm_proxy")
    def get_available_models(self, provider: Optional[ModelProvider] = None) -> List[str]:
        """
        Liste les modèles disponibles.
        
        Args:
            provider: Provider spécifique (optionnel)
        
        Returns:
            Liste des noms de modèles disponibles
        """
        try:
            if provider:
                # Filtrer par provider
                models = litellm.model_list
                provider_models = [
                    m for m in models
                    if self._detect_provider(m) == provider
                ]
                return provider_models
            else:
                # Tous les modèles
                return litellm.model_list
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARNING", f"Echec récupération modèles: {e}")
            return []
    
    @staticmethod
    def extract_usage_metadata(response: Any) -> Dict[str, Any]:
        """
        Extrait les métriques d'usage depuis la réponse LiteLLM.
        
        Args:
            response: Réponse LiteLLM
        
        Returns:
            Dict avec métriques (prompt_tokens, completion_tokens, cache_hit, etc.)
        """
        usage = {}
        
        try:
            # LiteLLM standardise les métriques dans response.usage
            if hasattr(response, 'usage'):
                usage_data = response.usage
                usage['prompt_tokens'] = getattr(usage_data, 'prompt_tokens', 0)
                usage['completion_tokens'] = getattr(usage_data, 'completion_tokens', 0)
                usage['total_tokens'] = getattr(usage_data, 'total_tokens', 0)
            
            # Métriques cache (DeepSeek)
            if hasattr(response, 'response_metadata'):
                metadata = response.response_metadata
                usage['prompt_cache_hit_tokens'] = getattr(
                    metadata, 'prompt_cache_hit_tokens', 0
                )
                usage['prompt_cache_miss_tokens'] = getattr(
                    metadata, 'prompt_cache_miss_tokens', 0
                )
        
        except Exception as e:
            UnifiedLogger.write("AI_CORE", "WARNING", f"Echec extraction métriques: {e}")
        
        return usage


# Instance globale (singleton)
_global_proxy: Optional[LiteLLMProxy] = None


def get_litellm_proxy() -> LiteLLMProxy:
    """
    Récupère l'instance globale du proxy LiteLLM (singleton).
    
    Returns:
        Instance LiteLLMProxy
    """
    global _global_proxy
    
    if _global_proxy is None:
        if not LITELLM_AVAILABLE:
            raise ImportError(
                "LiteLLM n'est pas installé. Installez-le avec: pip install litellm"
            )
        _global_proxy = LiteLLMProxy()
    
    return _global_proxy


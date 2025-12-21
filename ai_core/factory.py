import google.generativeai as genai
from config.settings import APP_SETTINGS
from config.logs import get_logger
from ai_core.keys import KeyManager

# Import des classes de session
# [CORRECTION] Fusion des imports pour éviter doublons et erreurs
from ai_core.sessions import GeminiSession, GroqSession, DeepSeekSession, GeminiCliSession, UniversalResponseWrapper
from features.Decorators import trace_action
from features.UnifiedLogger import UnifiedLogger

# Phase 1.4 : Import LiteLLMSession
try:
    from ai_core.litellm_session import LiteLLMSession
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    LiteLLMSession = None

log = get_logger("ai_core.factory")

class SmartSessionFactory:
    """
    Fabrique centrale pour les sessions IA (V3.2 - Clean Init).
    Délègue l'entière responsabilité de l'initialisation à la Session elle-même.
    Mise à jour pour utiliser le KeyManager centralisé (Global Keyring).
    """
    def __init__(self):
        self.settings = {}
        # Instance unique du KeyManager qui gère tout le trousseau (Keyring)
        self.key_manager = KeyManager()
        self.registry = {}
        self.agent_mapping = {}
        self.refresh_config()

    @trace_action(source="factory")
    def refresh_config(self):
        self.settings = APP_SETTINGS
        
        # Note : Le KeyManager s'auto-initialise et migre les clés lors de son instanciation.
        # Il n'est plus nécessaire de parser manuellement les clés api_keys ici.
        # Les clés sont gérées de manière opaque par le KeyManager via le Keyring système.

        # --- CHARGEMENT CONFIG ---
        ai_engine = self.settings.get("ai_engine", {})
        swarm_conf = self.settings.get("swarm_settings", {})
        
        # 1. Registre (Alias -> Modèle Réel)
        self.registry = ai_engine.get("cloud_models_registry", {})
        
        # 2. Mapping (Agent -> Alias)
        self.agent_mapping = swarm_conf.get("role_mapping", {})
        
        # Defaults de sécurité
        defaults = {
            "fast": "gemini-2.5-flash",
            "smart": "gemini-2.5-pro",
            "coder": "gemini-2.5-pro",
            "architect": "gemini-2.5-pro",
            "writer": "gemini-2.5-flash",
            "reviewer": "gemini-2.5-flash",
            "router": "gemini-2.5-flash-lite",
            "compressor": "gemini-2.5-flash-lite"
        }
        for k, v in defaults.items():
            if k not in self.registry: self.registry[k] = v

        log.info(f"Factory Config Loaded. Registry: {len(self.registry)}, Mapping: {len(self.agent_mapping)}")

    def _resolve_real_model(self, request_type):
        """Résolution : Agent -> Profil -> Modèle Réel."""
        req = request_type.lower()
        profile_alias = self.agent_mapping.get(req, req)
        real_model = self.registry.get(profile_alias, profile_alias)
        return profile_alias, real_model

    def _generate_model_cascade(self, primary_model, available_models):
        """Génère une liste de modèles de secours compatibles."""
        cascade = []
        if not primary_model: return cascade
        
        # Stratégie simple : si Pro échoue, tenter Flash
        if "pro" in primary_model:
            fallback = primary_model.replace("pro", "flash")
            cascade.append(fallback)
        
        # Ajouter d'autres modèles disponibles de la même famille
        base_name = primary_model.split("-")[0] # ex: gemini
        for m in available_models:
            if m != primary_model and base_name in m and m not in cascade:
                cascade.append(m)
                
        return cascade[:2] # On garde max 2 secours

    @trace_action(source="factory")
    def create_litellm_session(
        self,
        model_type="core",
        enable_tools=True,
        cache_name=None,
        system_instruction=None,
        agent_name=None
    ):
        """
        Phase 1.4 : Crée une session LiteLLM.
        
        Args:
            model_type: Type de modèle (ex: "fast", "smart", "coder")
            enable_tools: Activer tool calling
            cache_name: Nom du cache (optionnel)
            system_instruction: Instructions système
            agent_name: Nom de l'agent
        
        Returns:
            LiteLLMSession ou exception si échec
        """
        if not LITELLM_AVAILABLE:
            raise ImportError(
                "LiteLLM non disponible. Installez-le avec: pip install litellm"
            )
        
        profile_alias, real_model = self._resolve_real_model(model_type)
        
        if not real_model or " " in real_model:
            real_model = "gemini-2.5-flash"
        
        if system_instruction is None:
            system_instruction = self.settings.get("system_prompts", {}).get(model_type, "Tu es une IA utile.")
        
        if agent_name:
            agent_identity = agent_name
        else:
            agent_identity = model_type.capitalize() if model_type else "Core"
        
        # Détection base_url pour DeepSeek spécial
        base_url = None
        if "(Special)" in real_model or "speciale" in real_model.lower():
            base_url = "https://api.deepseek.com/v3.2_speciale_expires_on_20251215"
            UnifiedLogger.write("FACTORY", "ROUTING", f"🚀 Route Spéciale V3.2 activée pour {real_model}")
        
        UnifiedLogger.write(
            "FACTORY",
            "LITELLM",
            f"Création LiteLLMSession ({model_type} -> {profile_alias} -> {real_model})"
        )
        
        return LiteLLMSession(
            key_manager=self.key_manager,
            model_name=real_model,
            system_instruction=system_instruction,
            base_url=base_url,
            agent_name=agent_identity
        )

    @trace_action(source="factory")
    # [MODIF] Ajout du paramètre optionnel agent_name
    def create_session(self, model_type="core", enable_tools=True, cache_name=None, system_instruction=None, agent_name=None):
        """
        Crée une session configurée avec le gestionnaire de clés central.
        Phase 1.4 : Support LiteLLM avec fallback legacy.
        """
        # Phase 1.4 : Vérifier flag USE_LITELLM
        use_litellm = self.settings.get("migration_flags", {}).get("use_litellm", False)
        
        if use_litellm and LITELLM_AVAILABLE:
            try:
                # Tentative création LiteLLMSession
                return self.create_litellm_session(
                    model_type=model_type,
                    enable_tools=enable_tools,
                    cache_name=cache_name,
                    system_instruction=system_instruction,
                    agent_name=agent_name
                )
            except Exception as e:
                UnifiedLogger.write(
                    "FACTORY",
                    "WARNING",
                    f"Echec création LiteLLMSession, fallback legacy: {e}"
                )
                # Continue avec code legacy
        
        # Code legacy (inchangé)
        profile_alias, real_model = self._resolve_real_model(model_type)
        
        if not real_model or " " in real_model: 
            real_model = "gemini-2.5-flash"

        # --- Détection Provider ---
        provider = "google_gemini"
        
        if "deepseek" in real_model.lower():
            provider = "deepseek"
        elif any(x in real_model for x in ["llama", "mixtral", "groq"]):
            provider = "groq"
        elif "gpt" in real_model:
            provider = "openai"
        else:
            provider = "gemini" # Fallback explicite

        UnifiedLogger.write("FACTORY", "INIT", f"Création session ({model_type} -> {profile_alias} -> {real_model})")

        if system_instruction is None:
            system_instruction = self.settings.get("system_prompts", {}).get(model_type, "Tu es une IA utile.")

        # --- CORRECTION MAJEURE ICI ---
        # Si un nom est fourni (par Swarm), on l'utilise. Sinon on fallback sur le type.
        if agent_name:
            agent_identity = agent_name
        else:
            agent_identity = model_type.capitalize() if model_type else "Core"

        # --- Instanciation ---
        # On passe maintenant self.key_manager (l'instance unique) à toutes les sessions.
        # Chaque session utilisera key_manager.get_key(model_name) pour trouver la bonne clé.
        
        if provider == "deepseek":
            # [LOGIQUE SPECIALE V3.2]
            target_base_url = None 
            final_model_name = real_model

            if "(Special)" in real_model:
                # 1. On retire le suffixe pour que l'API ne rejette pas le nom
                final_model_name = real_model.replace(" (Special)", "").strip()
                # 2. On définit l'URL temporaire spécifique
                target_base_url = "https://api.deepseek.com/v3.2_speciale_expires_on_20251215"
                UnifiedLogger.write("FACTORY", "ROUTING", f"🚀 Route Spéciale V3.2 activée pour {final_model_name}")

            return DeepSeekSession(
                self.key_manager,
                model_name=final_model_name,
                system_instruction=system_instruction,
                base_url=target_base_url,
                agent_name=agent_identity  # <-- Tunneling
            )

        if provider == "groq":
            return GroqSession(
                self.key_manager, 
                model_name=real_model, 
                system_instruction=system_instruction,
                agent_name=agent_identity  # <-- Tunneling
            )
        elif provider == "openai":
            return UniversalResponseWrapper("OpenAI non implémenté.")
        else:
            # Gemini
            # Phase 1.4 : Le routage CLI est maintenant géré par LiteLLMSession
            # Si LiteLLM est activé, LiteLLMSession détectera automatiquement le CLI
            # Sinon, on utilise GeminiSession standard
            
            # Instanciation standard via API
            available = list(self.registry.values())
            fallback_chain = self._generate_model_cascade(real_model, available)

            try:
                return GeminiSession(
                    self.key_manager, 
                    model_name=real_model, 
                    system_instruction=system_instruction, 
                    enable_tools=enable_tools, 
                    cache_name=cache_name,
                    fallback_models=fallback_chain,
                    agent_name=agent_identity  # <-- Tunneling
                )

            except Exception as e:
                UnifiedLogger.write("FACTORY", "CRITICAL", f"Echec instanciation modèle {real_model}: {e}")
                raise e

    @trace_action(source="factory")
    def audit_all_providers(self):
        """
        Génère un rapport de toutes les clés gérées par le KeyManager unique,
        regroupées par provider.
        """
        report = {}
        # On itère directement sur les clés stockées dans le manager unique
        for key_str, stats in self.key_manager.keys.items():
            prov = stats.provider
            if prov not in report:
                report[prov] = []
            report[prov].append(stats.to_dict())
        return report

    @trace_action(source="factory")
    def get_key_status(self, provider, key):
        """Récupère le statut d'une clé spécifique via le manager unique."""
        # Note : Le paramètre 'provider' est moins pertinent ici car le manager unique gère tout,
        # mais on peut vérifier si la clé appartient bien au provider demandé si nécessaire.
        if key in self.key_manager.keys:
            stats = self.key_manager.keys[key]
            if stats.provider == provider.lower() or provider == "all":
                return stats.to_dict()
        return "KEY_NOT_FOUND"

# Singleton
SessionFactory = SmartSessionFactory()
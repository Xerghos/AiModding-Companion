import logging
import json
import re
import queue
from features.Decorators import trace_action
from ai_core.factory import SessionFactory
from config.tools_schema import TOOLS_SCHEMA
from config.settings import APP_SETTINGS

# --- Import Dynamique des Personas ---
try:
    from agents.agent_personas import SWARM_AGENTS
except ImportError:
    try:
        from agent_personas import SWARM_AGENTS
    except ImportError:
        print("ERREUR CRITIQUE: agent_personas.py introuvable.")
        SWARM_AGENTS = {}

# --- Configuration Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger("swarm_manager")

class SwarmAgent:
    """
    Agent autonome spécialisé (Swarm V2).
    - Possède sa propre session (Tiering).
    - Possède son propre contexte d'outils (Whitelisting).
    - Possède une mémoire de mission (Context Injection).
    - Capable de boucle autonome (Retry Loop).
    - Supporte le mode Raisonnement (Reasoning Mode).
    """
    def __init__(self, agent_type, parent_session=None, initial_context=None, reasoning_mode=False):
        """
        :param agent_type: Clé dans SWARM_AGENTS (ex: 'CODER', 'ARCHITECT').
        :param parent_session: (Obsolète) Ancienne session du worker, ignorée pour le Tiering.
        :param initial_context: (Str/Dict) Historique ou résumé à injecter au démarrage.
        :param reasoning_mode: (Bool) Si True, upgrade le modèle vers 'reasoning' (sauf si 'fast').
        """
        self.agent_type = agent_type.upper()
        self.initial_context = initial_context
        
        # 1. Chargement du Profil
        if self.agent_type in SWARM_AGENTS:
            self.persona = SWARM_AGENTS[self.agent_type]
        else:
            log.warning(f"Type d'agent '{self.agent_type}' inconnu. Fallback sur 'ROUTER'.")
            self.agent_type = "ROUTER"
            self.persona = SWARM_AGENTS.get("ROUTER", {"prompt": "Tu es un assistant.", "allowed_tools": [], "model_tier": "fast"})

        # 2. Configuration du Tiering (Choix du Modèle)
        self.tier = self.persona.get("model_tier", "fast")

        # [LOGIQUE RAISONNEMENT]
        # Si activé via l'UI et que l'agent n'est pas un agent rapide (ex: Router, Writer),
        # on force l'utilisation d'un modèle de pensée (Thinking Model).
        if reasoning_mode and self.tier != 'fast':
            log.info(f"🧠 Mode Raisonnement activé pour {self.agent_type} (Upgrade {self.tier} -> reasoning)")
            self.tier = 'reasoning'
        
        # 3. Construction du Prompt Système COMPLET (Identité + Whitelist + Contexte)
        self.system_instruction = self._build_system_instruction()
        
        # 4. Création de la Session DÉDIÉE
        # On prépare le nom d'affichage (ex: "CODER" -> "Coder")
        display_name = self.agent_type.capitalize()
        
        log.info(f"Swarm: Init {self.agent_type} (Tier: {self.tier}) | Context: {'Oui' if initial_context else 'Non'}")
        
        # --- CORRECTION ICI ---
        self.session = SessionFactory.create_session(
            model_type=self.tier, 
            enable_tools=True, 
            system_instruction=self.system_instruction,
            agent_name=display_name # <--- ON PASSE L'IDENTITÉ EXPLiCITE
        )

    def _get_tool_definitions(self):
        """
        Récupère les schémas JSON des outils autorisés pour cet agent.
        Gère les formats plats (liste d'outils) et imbriqués (function_declarations).
        """
        allowed = self.persona.get("allowed_tools", [])
        if not allowed:
            return []
            
        definitions = []
        all_funcs = []
        
        # Robustesse : Détection du format de TOOLS_SCHEMA
        for item in TOOLS_SCHEMA:
            if isinstance(item, dict) and "function_declarations" in item:
                # Format Google GenAI : [{"function_declarations": [...]}]
                all_funcs.extend(item["function_declarations"])
            else:
                # Format Plat : [{name: ...}, {name: ...}]
                all_funcs.append(item)
                
        # Filtrage
        for func in all_funcs:
            name = func.get('name')
            if name and name in allowed:
                definitions.append(func)
                
        return definitions

    @trace_action(source="swarm_manager")
    def _build_system_instruction(self):
        """Construit le System Prompt hybride (Identité + Manuel Outils + Contexte)."""
        base_prompt = self.persona.get("prompt", "")
        
        # A. Injection des Outils (Whitelisting)
        tool_defs = self._get_tool_definitions()
        tools_manual = ""
        
        if tool_defs:
            tools_manual += "\n\n--- 🛠️ MANUEL DES OUTILS AUTORISÉS ---\n"
            tools_manual += "Tu as accès STRICTEMENT aux outils suivants. N'en invente pas d'autres.\n"
            for t in tool_defs:
                description = t.get('description', 'Pas de description.')
                tools_manual += f"- {t['name']}: {description}\n"
            tools_manual += "\nPOUR UTILISER UN OUTIL : Utilise le format JSON natif ou !native_tool.\n"
        
        # B. Injection du Contexte (Context Sharing)
        context_block = ""
        if getattr(self, 'initial_context', None):
            context_block += "\n\n--- 📋 CONTEXTE DE MISSION (MÉMOIRE PARTAGÉE) ---\n"
            context_block += "Voici les informations, résumés ou historiques transmis par l'agent précédent ou l'utilisateur.\n"
            context_block += "Utilise ces informations pour comprendre ta tâche sans poser de questions inutiles.\n"
            context_block += f"{str(self.initial_context)}\n"
            context_block += "--- FIN CONTEXTE ---\n"
        
        return base_prompt + tools_manual + context_block

    @trace_action(source="swarm_manager")
    def execute_task(self, task_prompt, result_queue=None, task_queue=None):
        """
        Exécute la tâche avec une boucle d'autonomie (Retry Loop).
        Gère les appels d'outils internes.
        """
        # Lazy Import pour éviter les cycles
        from features.ai_helper import analyze_request_and_dispatch
        
        # 1. Config de la boucle
        max_loops = APP_SETTINGS.get("swarm_settings", {}).get("max_auto_loop", 5)
        current_input = (
            f"--- TÂCHE PRIORITAIRE AGENT {self.agent_type} ---\n"
            f"{task_prompt}\n"
            f"\nRAPPEL : Analyse étape par étape dans des balises <thought> avant d'agir."
        )
        
        loop_count = 0
        final_response_text = ""
        
        # Queues factices si non fournies (pour éviter les crashs des outils qui logguent)
        if not result_queue: result_queue = queue.Queue()
        if not task_queue: task_queue = queue.Queue()

        log.info(f"🔄 Swarm Loop Start (Max: {max_loops})")

        while loop_count < max_loops:
            try:
                # 2. Appel IA
                response = self.session.send_message(current_input, stream=False)
                
                # Extraction texte
                ai_text = response.text if hasattr(response, 'text') else str(response)
                final_response_text = ai_text # On garde la dernière réponse comme vérité
                
                # 3. Détection Outil (!native_tool)
                if "!native_tool" in ai_text:
                    log.info(f"⚙️ Swarm Tool Call détecté (Loop {loop_count+1}/{max_loops})")
                    
                    # Exécution via le Dispatcher Central
                    tool_output = analyze_request_and_dispatch(
                        ai_text, 
                        self.session, 
                        result_queue, # Pour les logs UI
                        task_queue,   # Pour les sous-tâches
                        action_log_path="action_log.json"
                    )
                    
                    # 4. Feedback Loop (On renvoie le résultat à l'IA)
                    current_input = (
                        f"--- RÉSULTAT OUTIL (SYSTÈME) ---\n"
                        f"{str(tool_output)}\n"
                        f"--------------------------------\n"
                        f"Analyse ce résultat. Si c'est terminé, conclus. Sinon, continue."
                    )
                    loop_count += 1
                    
                else:
                    # Pas d'outil = Réponse finale (ou question)
                    log.info("✅ Swarm Loop End (Réponse textuelle)")
                    break
                    
            except Exception as e:
                log.error(f"Erreur Swarm Loop: {e}")
                current_input = f"ERREUR TECHNIQUE : {e}. Essaie une autre approche."
                loop_count += 1

        if loop_count >= max_loops:
            final_response_text += "\n\n[SYSTÈME] ⚠️ Limite d'autonomie atteinte. Je m'arrête là."

        # On retourne un objet compatible avec l'interface attendue par Worker
        # (Un objet qui a un attribut .text)
        return type('obj', (object,), {'text': final_response_text})

@trace_action(source="swarm_manager")
def create_agent(agent_type, worker_session=None, initial_context=None, reasoning_mode=False):
    """Factory wrapper avec support du Reasoning Mode."""
    return SwarmAgent(agent_type, parent_session=worker_session, initial_context=initial_context, reasoning_mode=reasoning_mode)
import logging
from ai_core import SessionFactory, call_ai_robust
from features.Decorators import trace_action

log = logging.getLogger("worker.handlers.swarm")

# Cache pour les sessions "Agents" (Persistant au niveau du module)
_agent_sessions = {}

@trace_action(source="swarm")
def get_agent_session(role):
    """
    Récupère ou crée une session pour un rôle spécifique (Lazy Loading).
    """
    if role not in _agent_sessions:
        # Correspondance avec le model_type du système (cf. config ai_engine)
        # Ex: "ARCHITECT" -> "architect" -> Gemini Pro / GPT-4
        m_key = role.lower()
        
        # [LOG_CLEANED] log.info(f"Création de session Swarm pour le rôle : {role}")
        
        # On calcule le nom d'affichage propre (ex: "ARCHITECT" -> "Architect")
        display_name = role.capitalize()
        
        # On crée une session avec une instruction système forte ET l'identité explicite
        _agent_sessions[role] = SessionFactory.create_session(
            model_type=m_key,
            system_instruction=f"Tu es un expert {role}. Agis strictement selon ce rôle.",
            agent_name=display_name # <--- CORRECTIF : Transmission de l'identité
        )
    return _agent_sessions[role]

@trace_action(source="swarm")
def handle_agent_task(payload):
    """
    Exécute une tâche via un agent spécialisé (Swarm).
    Payload attendu : { 'agent_role': str, 'prompt': str }
    """
    agent_role = payload.get("agent_role", "ASSISTANT").upper()
    prompt = payload.get("prompt")
    
    if not prompt:
        return "Erreur : Prompt manquant pour l'agent."

    # Récupération de la session (avec mémoire conservée)
    session = get_agent_session(agent_role)
    
    # Appel IA
    return call_ai_robust(session, prompt)
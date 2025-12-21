import logging
from ai_core import call_ai_robust
from features.ai_helper import analyze_request_and_dispatch
from features.context import handle_chat_rag_hybrid
from features.Decorators import trace_action

log = logging.getLogger("worker.handlers.chat")

@trace_action(source="chat")
def handle_chat(payload, get_main_session_func, settings):
    """
    Gère le chat standard avec support RAG optionnel.
    """
    user_input = payload.get("message")
    use_rag = payload.get("use_rag", False)
    # [OPTIMISATION] Bypass RAG pour les messages courts/phatiques
    # Évite de charger 2k tokens de contexte pour un simple "Bonjour"
    if not user_input: return None
    if len(user_input) < 20 and any(x in user_input.lower() for x in ['bonjour', 'hello', 'salut', 'merci', 'ca va', 'rebonjour', 'test']):
        use_rag = False
        log.info("⚡ RAG désactivé pour message phatique.")

    session = get_main_session_func()
    
    # Vérification RAG
    if use_rag and settings:
        db_path = settings.get('system_settings', {}).get('rag_database_path', 'db/knowledge_base_hybrid_V2')
        # On tente le RAG hybride
        try:
            return handle_chat_rag_hybrid(user_input, session, db_path)
        except Exception as e:
            log.error(f"Echec RAG, fallback standard: {e}")
            
    return call_ai_robust(session, user_input)

@trace_action(source="chat")
def handle_command(payload, get_main_session_func, response_queue):
    """
    Gère les commandes spéciales (!help, !refactor, etc.).
    """
    command = payload.get("command")
    session = get_main_session_func()
    try:
        return analyze_request_and_dispatch(command, session, result_queue=response_queue)
    except Exception as e:
        log.error(f"Erreur commande: {e}")
        return f"Erreur commande: {e}"
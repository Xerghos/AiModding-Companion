import logging
from ai_core import SessionFactory
from features.Decorators import trace_action

# Imports Fonctionnalités (Modules Features)
try:
    import features.CodeQuality as CodeQuality
    import features.Refactoring as Refactoring
    import features.Documentation as Documentation
except ImportError as e:
    logging.error(f"Erreur d'import des Features dans code_handler: {e}")

log = logging.getLogger("worker.handlers.code")

@trace_action(source="code")
def handle_analyze_file(payload):
    """
    Lance un audit de qualité/sécurité sur un fichier.
    Utilise une session IA de type 'reasoning' (ex: Gemini Pro / GPT-4).
    """
    file_path = payload.get("file_path")
    if not file_path: 
        return "Erreur : Chemin de fichier manquant pour l'analyse."
    
    # [LOG_CLEANED] log.info(f"Audit demandé pour : {file_path}")
    analysis_session = SessionFactory.create_session(model_type="reasoning")
    return CodeQuality.audit_code(file_path, analysis_session)

@trace_action(source="code")
def handle_refactor(payload):
    """
    Applique un refactoring sur un fichier selon des instructions.
    Utilise une session IA de type 'architect' ou 'refactor'.
    """
    file_path = payload.get("file_path")
    instructions = payload.get("instructions", "Améliorer le code selon les standards.")
    
    if not file_path:
        return "Erreur : Fichier cible manquant pour le refactoring."

    log.info(f"Refactoring demandé pour : {file_path}")
    # On utilise un modèle capable de raisonnement complexe pour le code
    refactor_session = SessionFactory.create_session(model_type="architect")
    return Refactoring.apply_refactor(file_path, instructions, refactor_session)

@trace_action(source="code")
def handle_gen_doc(payload):
    """
    Génère la documentation pour un fichier.
    Utilise une session IA de type 'writer' (rapide).
    """
    file_path = payload.get("file_path")
    if not file_path:
        return "Erreur : Fichier cible manquant pour la documentation."

    log.info(f"Documentation demandée pour : {file_path}")
    doc_session = SessionFactory.create_session(model_type="writer")
    return Documentation.generate_doc(file_path, doc_session)
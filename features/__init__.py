# Façade pour le package Features
# Redirige les appels RAG vers le sous-package context

try:
    from .context import (
        handle_load_context,
        handle_maj_contexte,
        handle_sync_kb_to_drive,
        handle_delete_drive_kb,
        handle_chat_rag_hybrid
    )
except ImportError:
    # Fallback si le sous-package a un problème, pour ne pas crasher tout l'import
    pass

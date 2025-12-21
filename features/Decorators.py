import functools
import time
import uuid
import traceback
import inspect
from features.UnifiedLogger import UnifiedLogger

# CORRECTION : Suppression de l'import circulaire "from features.Decorators..."

def generate_trace_id():
    """Génère un identifiant court pour le traçage (ex: 'a1b2c3')."""
    return str(uuid.uuid4())[:6]

def trace_action(source="SYSTEM", action_name=None, level="INFO", safe_mode=False):
    """
    Décorateur Ultime pour l'observabilité et la robustesse.
    
    Usage:
        @trace_action(source="CodeQuality", action_name="Audit")
        def ma_fonction(arg1): ...

    :param source: Nom du module ou composant (ex: 'RAG', 'WORKER').
    :param action_name: Nom de l'action (par défaut: nom de la fonction).
    :param level: Niveau de log (INFO, DEBUG).
    :param safe_mode: Si True, capture l'exception et retourne None au lieu de crasher.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 1. Initialisation Contexte
            trace_id = generate_trace_id()
            op_name = action_name or func.__name__
            start_time = time.time()
            
            # Préparation des arguments pour le log (tronqués si trop longs)
            try:
                # On essaie de lier les arguments aux noms des paramètres pour la clarté
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                # Conversion propre en dict stringifié
                args_map = {k: str(v)[:200] + "..." if len(str(v)) > 200 else v 
                            for k, v in bound_args.arguments.items()}
                args_str = str(args_map)
            except:
                # Fallback si l'inspection échoue
                args_str = f"Args: {len(args)}, Kwargs: {len(kwargs)}"

            # 2. Log Entrée
            UnifiedLogger.write(
                source, 
                "START", 
                f"[{trace_id}] Début {op_name}", 
                {"params": args_str}
            )

            result = None
            try:
                # 3. Exécution
                result = func(*args, **kwargs)
                
                # 4. Log Succès
                duration = time.time() - start_time
                UnifiedLogger.write(
                    source, 
                    "SUCCESS", 
                    f"[{trace_id}] Fin {op_name} ({duration:.3f}s)",
                    # On loggue un résumé du résultat s'il n'est pas trop gros
                    {"result_summary": str(result)[:500] if result else "None"}
                )
                return result

            except Exception as e:
                # 5. Gestion Erreur
                duration = time.time() - start_time
                error_ctx = {
                    "trace_id": trace_id,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "duration": f"{duration:.3f}s"
                }
                
                UnifiedLogger.write(source, "ERROR", f"[{trace_id}] Échec {op_name}: {e}", error_ctx)
                
                if safe_mode:
                    # En safe_mode, on étouffe l'erreur et on rend None (utile pour tâches de fond)
                    return f"Erreur traitée ({trace_id}): {e}"
                else:
                    # Sinon on laisse remonter (pour le Worker qui a son try/except global)
                    raise e

        return wrapper
    return decorator
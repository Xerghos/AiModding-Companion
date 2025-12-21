import logging
import sys
# On utilise un import local (lazy) à l'intérieur du Handler pour éviter
# les cycles d'importation, car UnifiedLogger est un module Feature.

class UnifiedBridgeHandler(logging.Handler):
    """
    Capture les logs standards (log.info) et les envoie 
    vers le moteur de rendu UnifiedLogger (HUD).
    """
    def emit(self, record):
        try:
            # Import Lazy (Indispensable ici)
            from features.UnifiedLogger import UnifiedLogger
            
            msg = self.format(record)
            
            # Mapping des niveaux Python -> Nos types HUD
            level_map = {
                "DEBUG": "INFO",    # On affiche les debugs standards comme des infos
                "INFO": "INFO", 
                "WARNING": "WARNING",
                "ERROR": "ERROR",
                "CRITICAL": "CRITICAL"
            }
            
            # Détection intelligente du type basée sur le message (si possible)
            msg_type = level_map.get(record.levelname, "INFO")
            
            # Si le log vient d'une librairie externe (ex: google, urllib3), on le marque
            source = record.name
            if "google" in source: source = "GoogleAPI"
            if "urllib3" in source: source = "HttpReq"
            if "werkzeug" in source: source = "Flask"

            # Envoi au HUD
            UnifiedLogger.write(
                source=source,
                msg_type=msg_type,
                message=msg,
                data=None # Les logs standards n'ont pas de data structurée
            )
        except Exception:
            self.handleError(record)

def get_logger(name):
    """
    Retourne un logger configuré pour utiliser UNIQUEMENT notre pont HUD.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO) # On ignore les DEBUGs trop verbeux des libs
    
    # On supprime les anciens handlers (console noire moche)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    # On ajoute NOTRE handler (HUD couleur)
    # On vérifie qu'on ne l'a pas déjà ajouté (Singleton pattern via nom)
    has_bridge = any(isinstance(h, UnifiedBridgeHandler) for h in logger.handlers)
    if not has_bridge:
        logger.addHandler(UnifiedBridgeHandler())
    
    logger.propagate = False # On empêche le log de remonter à la racine (double affichage)
    
    return logger

def setup_logging():
    """Compatibility shim."""
    pass

# Configuration du Root Logger aussi, pour attraper les logs sauvages
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if root_logger.hasHandlers():
    root_logger.handlers.clear()
root_logger.addHandler(UnifiedBridgeHandler())
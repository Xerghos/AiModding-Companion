# `config\logs.py`

## Description

Ce module fournit un système de journalisation personnalisé qui redirige les messages de log Python standards vers un moteur de rendu appelé "UnifiedLogger" (souvent désigné comme HUD). Il inclut un gestionnaire de log personnalisé (`UnifiedBridgeHandler`) et une fonction utilitaire (`get_logger`) pour obtenir des loggers préconfigurés pour ce système.

## Dépendances

*   `logging` (module standard Python)
*   `sys` (module standard Python)
*   `features.UnifiedLogger` (importation locale et différée)

## Classes & Fonctions

### `UnifiedBridgeHandler(logging.Handler)`

Un gestionnaire de journalisation qui capture les messages de log Python et les achemine vers le moteur UnifiedLogger.

#### `emit(self, record)`

*   **Description:** Cette méthode est appelée par le système de journalisation lorsqu'un message doit être émis. Elle formate le message et le transmet au `UnifiedLogger`.
*   **Arguments:**
    *   `record` (logging.LogRecord): L'objet log record contenant toutes les informations sur l'événement à journaliser.
*   **Logique interne:**
    1.  Tente d'importer `UnifiedLogger` (importation différée pour éviter les cycles d'importation).
    2.  Formate le message de log en utilisant la méthode `format` héritée.
    3.  Mappe les niveaux de log Python (DEBUG, INFO, WARNING, ERROR, CRITICAL) vers les types correspondants du HUD (INFO, WARNING, ERROR, CRITICAL). Les logs DEBUG de Python sont mappés sur INFO pour le HUD.
    4.  Détermine la source du log. Si la source contient des chaînes spécifiques comme "google", "urllib3" ou "werkzeug", elle est renommée en "GoogleAPI", "HttpReq" ou "Flask" respectivement. Sinon, le nom d'origine du logger est utilisé.
    5.  Appelle `UnifiedLogger.write()` avec la source, le type de message, le message formaté, et `data=None` (car les logs standards n'ont pas de structure de données).
    6.  En cas d'exception lors du traitement, appelle `self.handleError(record)` pour gérer l'erreur du handler.

### `get_logger(name)`

*   **Description:** Crée ou récupère un logger Python et le configure pour utiliser uniquement le `UnifiedBridgeHandler`.
*   **Arguments:**
    *   `name` (str): Le nom du logger à créer ou récupérer (généralement `__name__`).
*   **Retourne:**
    *   `logging.Logger`: Un objet logger configuré.
*   **Logique interne:**
    1.  Récupère un logger avec le nom spécifié en utilisant `logging.getLogger(name)`.
    2.  Définit le niveau du logger à `logging.INFO` pour ignorer les messages de niveau DEBUG trop verbeux provenant potentiellement de bibliothèques externes.
    3.  Supprime tous les gestionnaires existants du logger pour éviter les sorties multiples ou indésirables (comme la sortie console par défaut).
    4.  Vérifie si un `UnifiedBridgeHandler` est déjà présent dans les gestionnaires du logger.
    5.  Si `UnifiedBridgeHandler` n'est pas présent, en crée une nouvelle instance et l'ajoute aux gestionnaires du logger.
    6.  Définit `logger.propagate = False` pour empêcher les messages de log d'être transmis aux loggers parents, évitant ainsi une duplication des logs.
    7.  Retourne le logger configuré.

### `setup_logging()`

*   **Description:** Une fonction de compatibilité dont l'implémentation est vide. Elle ne fait rien.

## Configuration du Root Logger

Le code configure également le `root_logger` pour qu'il utilise le `UnifiedBridgeHandler`. Cela garantit que tous les messages de log qui ne sont pas explicitement gérés par d'autres loggers (logs "sauvages") sont également envoyés au HUD.

*   Le niveau du `root_logger` est défini à `logging.INFO`.
*   Tous les gestionnaires existants du `root_logger` sont supprimés.
*   Un `UnifiedBridgeHandler` est ajouté au `root_logger`.

## Exemple d'usage

```python
# Dans un autre fichier, par exemple main.py

# Importer la fonction pour obtenir un logger configuré
from config.logs import get_logger

# Obtenir un logger pour le module courant
logger = get_logger(__name__)

def my_function():
    logger.info("Ceci est un message d'information.")
    logger.warning("Attention, quelque chose s'est passé.")
    try:
        result = 1 / 0
    except ZeroDivisionError:
        logger.error("Une erreur s'est produite : division par zéro.", exc_info=True)

# Appel de la fonction pour générer des logs
my_function()

# Exemple de log provenant d'une bibliothèque externe (si utilisée)
# import requests
# try:
#     response = requests.get("http://example.com")
# except requests.exceptions.RequestException as e:
#     # Le logger interne de 'requests' pourrait générer des logs qui seront interceptés
#     # et potentiellement reformatés par UnifiedBridgeHandler si le niveau est INFO ou supérieur.
#     pass

# La sortie de ces logs sera gérée par le système UnifiedLogger (HUD).
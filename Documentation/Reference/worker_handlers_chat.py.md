# Documentation Technique: `worker\handlers\chat.py`

## Description Concise

Ce module contient les gestionnaires pour les requêtes de chat et de commandes spéciales dans l'application. Il gère le flux de traitement des messages utilisateurs, incluant le support optionnel pour le Retrieval Augmented Generation (RAG) et l'analyse des commandes spéciales.

## Dépendances

*   `logging`: Pour la journalisation des événements et des erreurs.
*   `ai_core.call_ai_robust`: Fonction pour interagir avec un modèle d'IA de manière robuste.
*   `features.ai_helper.analyze_request_and_dispatch`: Fonction pour analyser et dispatcher les commandes spéciales.
*   `features.context.handle_chat_rag_hybrid`: Fonction pour gérer le chat avec le contexte RAG hybride.
*   `features.Decorators.trace_action`: Décorateur pour tracer les actions.

---

## Classes & Fonctions

### `handle_chat(payload, get_main_session_func, settings)`

Gère le chat standard avec support RAG optionnel.

#### Arguments

*   `payload` (dict): Dictionnaire contenant les données de la requête utilisateur. Doit inclure une clé `"message"` (string) pour le message de l'utilisateur et optionnellement une clé `"use_rag"` (bool, défaut `False`).
*   `get_main_session_func` (function): Fonction qui retourne une instance de session principale.
*   `settings` (dict): Dictionnaire contenant les paramètres de configuration de l'application, potentiellement utilisé pour le chemin de la base de données RAG.

#### Retours

*   `str` ou `None`: Le résultat de la réponse de l'IA, ou `None` si le message est vide.

#### Logique interne

1.  Extrait le message utilisateur (`"message"`) et l'indicateur d'utilisation de RAG (`"use_rag"`) du `payload`.
2.  **Optimisation RAG**: Si le message est vide ou très court (moins de 20 caractères) et qu'il contient des mots phatiques courants (ex: "bonjour", "merci"), le RAG est désactivé (`use_rag` est mis à `False`) et un log est généré. Ceci évite de charger un contexte RAG inutilement pour des messages courts.
3.  Récupère la session principale en appelant `get_main_session_func()`.
4.  **Vérification RAG**: Si `use_rag` est `True` et que `settings` est fourni :
    *   Récupère le chemin de la base de données RAG depuis `settings` (avec un chemin par défaut : `'db/knowledge_base_hybrid_V2'`).
    *   Tente d'appeler `handle_chat_rag_hybrid()` avec le message de l'utilisateur, la session et le chemin de la base de données.
    *   Si une exception survient pendant l'appel RAG, un message d'erreur est logué et le système revient à un traitement standard.
5.  Si le RAG n'est pas utilisé ou a échoué, appelle `call_ai_robust()` avec la session et le message utilisateur pour un traitement IA standard.

### `handle_command(payload, get_main_session_func, response_queue)`

Gère les commandes spéciales spéciales (ex: `!help`, `!refactor`).

#### Arguments

*   `payload` (dict): Dictionnaire contenant les données de la requête. Doit inclure une clé `"command"` (string) représentant la commande à exécuter.
*   `get_main_session_func` (function): Fonction qui retourne une instance de session principale.
*   `response_queue` (Queue): La file d'attente où les résultats doivent être placés.

#### Retours

*   `str`: Le résultat de l'exécution de la commande ou un message d'erreur.

#### Logique interne

1.  Extrait la commande (`"command"`) du `payload`.
2.  Récupère la session principale en appelant `get_main_session_func()`.
3.  Tente d'appeler `analyze_request_and_dispatch()` avec la commande, la session et la `response_queue`.
4.  Si une exception survient pendant l'exécution de la commande, un message d'erreur est logué et une chaîne d'erreur est retournée à l'appelant.

---

## Exemple d'usage

### Chat standard

```python
# Hypothetical setup
from worker.handlers import chat
from my_session_manager import get_session
from config_loader import load_settings

payload_chat = {
    "message": "Bonjour, comment vas-tu aujourd'hui ?"
}
settings = load_settings() # Assume this loads configuration

response = chat.handle_chat(payload_chat, get_session, settings)
print(response)
```

### Chat avec RAG

```python
# Hypothetical setup
from worker.handlers import chat
from my_session_manager import get_session
from config_loader import load_settings

payload_rag_chat = {
    "message": "Peux-tu m'expliquer le fonctionnement du RAG dans le contexte de notre projet ?",
    "use_rag": True
}
settings = load_settings() # Assume this loads configuration

response = chat.handle_chat(payload_rag_chat, get_session, settings)
print(response)
```

### Commande spéciale

```python
# Hypothetical setup
from worker.handlers import chat
from my_session_manager import get_session
from multiprocessing import Queue

payload_command = {
    "command": "!help"
}
command_results_queue = Queue()
settings = load_settings() # Settings might not be directly needed here but often passed around

response = chat.handle_command(payload_command, get_session, command_results_queue)
print(response)

# If the command was designed to put results in the queue
# if not command_results_queue.empty():
#     queue_result = command_results_queue.get()
#     print(f"Command result from queue: {queue_result}")
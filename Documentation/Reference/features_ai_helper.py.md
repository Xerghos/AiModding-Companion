# Documentation Technique : `features/ai_helper.py`

## 1. Description Générale

Ce fichier, `features/ai_helper.py`, sert de passerelle principale pour l'exécution des fonctionnalités (outils) de l'application. Il orchestre l'appel aux différents modules de *features*, gère l'introspection des outils disponibles, implémente des mécanismes de sécurité pour contrôler l'accès aux fichiers et aux actions, et permet le parsing robuste des commandes reçues de l'IA, y compris des formats JSON potentiellement malformés ou tronqués. Il intègre également un mécanisme de boucle de qualité via le module `QualityEngine`.

### Dépendances

*   **Modules Internes:**
    *   `ai_core.sessions.call_ai_robust` (pour les appels IA indirects)
    *   `ai_core.factory.SessionFactory` (pour la création de sessions IA)
    *   `config.settings.APP_SETTINGS` (pour la configuration de sécurité et des agents)
    *   `config.tools_schema.TOOLS_SCHEMA` (pour la description des outils disponibles)
    *   `features.WebSurfer`
    *   `features.QualityEngine`
    *   `features.FileSystem`
    *   `features.Documentation`
    *   `features.CodeQuality`
    *   `features.Refactoring`
    *   `features.ProjectManager`
    *   `features.SearchEngine`
    *   `features.GitActions`
    *   `features.BackupManager`
    *   `features.ContextLoader`
    *   `features.SemanticMemory`
    *   `features.Shared`
    *   `features.context.database` (optionnel, pour la base vectorielle RAG)
*   **Librairies Standard:**
    *   `logging`
    *   `re` (Expressions régulières)
    *   `json`
    *   `ast` (Abstract Syntax Trees)
    *   `traceback`
    *   `os`
    *   `pathlib.Path`

## 2. Classes & Fonctions

### `call_ai_robust(session, prompt, mode="fast", disposable=False, force_text=False, cache_name=None, stream=False, **kwargs)`

*   **Description:** Wrapper pour appeler la fonction `call_ai_robust` du module `ai_core`, évitant ainsi les imports circulaires directs.
*   **Arguments:**
    *   `session`: Objet session de `ai_core`.
    *   `prompt` (str): Le prompt à envoyer à l'IA.
    *   `mode` (str, optionnel): Mode d'appel IA (défaut: "fast").
    *   `disposable` (bool, optionnel): Indique si la session est jetable (défaut: False).
    *   `force_text` (bool, optionnel): Force le retour en texte brut (défaut: False).
    *   `cache_name` (str, optionnel): Nom du cache à utiliser (défaut: None).
    *   `stream` (bool, optionnel): Indique si la réponse doit être streamée (défaut: False).
    *   `**kwargs`: Arguments supplémentaires à passer à `call_ai_robust`.
*   **Retour:** Le résultat de l'appel à `ai_core.sessions.call_ai_robust`.
*   **Logique Interne:** Importe dynamiquement `ai_core.sessions.call_ai_robust` et appelle cette fonction avec les arguments fournis.

### `_get_session_factory()`

*   **Description:** Retourne l'instance de `SessionFactory` de `ai_core`.
*   **Arguments:** Aucun.
*   **Retour:** L'objet `SessionFactory`.
*   **Logique Interne:** Importe dynamiquement `ai_core.factory.SessionFactory` et le retourne.

### `execute_lister_outils(session, action_log_path, result_queue, **kwargs)`

*   **Description:** Génère une liste formatée des outils disponibles, l'affiche à l'utilisateur via `result_queue`, et renvoie une confirmation courte à l'IA. Optimise l'usage des tokens en n'envoyant pas la liste complète à l'IA.
*   **Arguments:**
    *   `session`: Objet session IA.
    *   `action_log_path` (str): Chemin vers le fichier de log des actions.
    *   `result_queue` (Queue): File d'attente pour envoyer les résultats à l'interface utilisateur.
    *   `**kwargs`: Arguments supplémentaires (ignorés).
*   **Retour:** Une chaîne de caractères confirmant l'affichage de la liste ou décrivant une erreur.
*   **Logique Interne:**
    1.  Itère sur `TOOLS_SCHEMA` pour organiser les outils par catégories prédéfinies (Fichiers, Git, Mémoire, Code, Web, Backup, Documentation, Divers).
    2.  Construit une chaîne de caractères formatée (Markdown) pour l'affichage.
    3.  Envoie le message formaté à `result_queue` avec le type "chat\_response" et le rôle "system".
    4.  Retourne une chaîne courte pour l'historique de l'IA.
    5.  Capture et retourne les erreurs potentielles.

### `_get_tool_registry()`

*   **Description:** Construit et retourne un dictionnaire mappant les noms des outils aux fonctions correspondantes. Utilise l'importation dynamique pour éviter les cycles d'importation entre les modules de *features*.
*   **Arguments:** Aucun.
*   **Retour:** Un dictionnaire où les clés sont les noms des outils (str) et les valeurs sont les fonctions associées (callable). Les outils qui n'ont pas pu être chargés sont omis.
*   **Logique Interne:**
    1.  Tente d'importer tous les modules de *features* nécessaires.
    2.  Crée un dictionnaire `registry`.
    3.  Pour chaque outil potentiel, utilise `getattr` pour récupérer la fonction correspondante du module importé. Si la fonction n'existe pas, `None` est assigné.
    4.  Filtre le dictionnaire pour ne conserver que les entrées dont la valeur (la fonction) n'est pas `None`.
    5.  Gère les `ImportError` lors de l'importation des modules de *features*.

### `_clean_pollution(text)`

*   **Description:** Nettoie une chaîne de caractères en supprimant des artefacts spécifiques liés aux conversations IA et aux caractères invisibles ou non standards.
*   **Arguments:**
    *   `text` (str): Le texte à nettoyer.
*   **Retour:** Le texte nettoyé (str).
*   **Logique Interne:**
    *   Remplace des marqueurs spécifiques (`[⚠️ Contenu bloqué]`).
    *   Supprime les délimiteurs de blocs de code (` ``` `) au début et à la fin.
    *   Remplace des espaces insécables (`\xa0`) et des guillemets typographiques par leurs équivalents standards.
    *   Remplace des apostrophes typographiques.

### `_try_parse_payload(payload)`

*   **Description:** Tente de parser une chaîne de caractères comme un JSON strict ou comme une structure de données Python valide (dict, list, etc.) via `ast.literal_eval`.
*   **Arguments:**
    *   `payload` (str): La chaîne à parser.
*   **Retour:** L'objet parsé (dict, list, etc.) si le parsing réussit, sinon `None`.
*   **Logique Interne:**
    1.  Nettoie les guillemets échappés (`\"`).
    2.  Tente `json.loads`. Si échec, tente `ast.literal_eval` après avoir remplacé `true`/`false`/`null` par `True`/`False`/`None`.

### `_repair_and_parse(text)`

*   **Description:** Tente de réparer une chaîne ressemblant à un JSON potentiellement tronqué en ajoutant des accolades fermantes manquantes, puis tente de la parser.
*   **Arguments:**
    *   `text` (str): La chaîne potentiellement tronquée.
*   **Retour:** L'objet parsé en cas de succès après réparation, sinon `None`.
*   **Logique Interne:**
    1.  Compte les accolades ouvrantes et fermantes.
    2.  Si le nombre d'accolades ouvrantes est supérieur aux fermantes, ajoute le nombre d'accolades fermantes manquantes à la fin de la chaîne.
    3.  Appelle `_try_parse_payload` sur la chaîne réparée.
    4.  Log une alerte lorsqu'une tentative de réparation est effectuée.

### `_smart_extract_and_parse(raw_text)`

*   **Description:** Stratégie de parsing avancée pour extraire une structure de données (généralement une commande pour un outil) à partir d'un texte brut. Tente plusieurs méthodes : parsing direct, utilisation de `json.JSONDecoder`, et réparation/parsing.
*   **Arguments:**
    *   `raw_text` (str): Le texte brut contenant potentiellement la commande.
*   **Retour:** L'objet parsé (dict, list, etc.).
*   **Lève:** `ValueError` si aucune accolade ouvrante n'est trouvée ou si le parsing échoue après toutes les tentatives.
*   **Logique Interne:**
    1.  Nettoie le texte d'entrée avec `_clean_pollution`.
    2.  Trouve la première accolade ouvrante (`{`). Si absente, lève une `ValueError`.
    3.  Extrait le sous-string candidat commençant à la première accolade.
    4.  Tente de parser avec `_try_parse_payload`.
    5.  Si échec, tente le parsing avec `json.JSONDecoder`.
    6.  Si échec, tente de réparer et parser avec `_repair_and_parse`.
    7.  Si toutes les tentatives échouent, lève une `ValueError` indiquant l'échec du parsing.

### `_security_check(tool_name, args)`

*   **Description:** Vérifie si l'exécution d'un outil avec les arguments donnés respecte les règles de sécurité définies dans `APP_SETTINGS`. Vérifie le confinement dans le répertoire du projet, la protection de certains dossiers et fichiers critiques.
*   **Arguments:**
    *   `tool_name` (str): Le nom de l'outil appelé.
    *   `args` (dict): Les arguments passés à l'outil.
*   **Retour:** `None` si l'action est autorisée, ou une chaîne d'erreur décrivant la violation de sécurité si elle est détectée.
*   **Logique Interne:**
    1.  Récupère la configuration de sécurité (`security`). Si la vérification est désactivée, retourne `None`.
    2.  Identifie les chemins cibles dans les arguments en se basant sur une liste de clés courantes (`keys_with_paths`).
    3.  Pour chaque chemin cible :
        *   Résout le chemin absolu et vérifie s'il est dans le répertoire du projet (si `block_outside_project` est activé).
        *   Vérifie si le chemin cible se trouve dans un dossier protégé (si `protected_directories` est configuré).
        *   Si l'outil est destructeur (`ecrire_fichier`, `supprimer_fichier`, etc.) et que le chemin cible correspond à un fichier protégé (`protected_files`), bloque l'action.
    4.  Retourne un message d'erreur spécifique en cas de violation.

### `execute_native_tool(name, args, session, action_log_path, result_queue, task_queue)`

*   **Description:** Fonction principale pour exécuter un outil "natif" (défini dans `_get_tool_registry`). Elle gère la résolution de l'outil, le passage des arguments, l'appel au middleware de sécurité et la gestion des erreurs d'exécution.
*   **Arguments:**
    *   `name` (str): Le nom de l'outil à exécuter.
    *   `args` (dict): Les arguments à passer à la fonction de l'outil.
    *   `session`: Objet session IA.
    *   `action_log_path` (str): Chemin du fichier de log des actions.
    *   `result_queue` (Queue): File d'attente pour les résultats destinés à l'interface.
    *   `task_queue` (Queue): File d'attente pour les tâches à exécuter (par les workers).
*   **Retour:** Le résultat de l'exécution de l'outil, ou une chaîne d'erreur en cas d'échec.
*   **Logique Interne:**
    1.  Récupère le registre des outils via `_get_tool_registry`.
    2.  Vérifie si l'outil existe dans le registre. Sinon, retourne une erreur.
    3.  Appelle `_security_check` pour valider l'action. Si une erreur de sécurité est retournée, log l'action bloquée et retourne l'erreur.
    4.  Récupère la fonction de l'outil depuis le registre.
    5.  Prépare les arguments système (`sys_kwargs`) à passer à toutes les fonctions d'outil.
    6.  Exécute la fonction de l'outil en passant à la fois les arguments spécifiques (`args`) et les arguments système (`sys_kwargs`).
    7.  Capture et retourne les erreurs potentielles (`TypeError` pour les arguments, `Exception` générales). Log les erreurs critiques avec traceback.

### `analyze_request_and_dispatch(command_text, session, response_queue, task_queue=None, action_log_path="action_log.json")`

*   **Description:** Le dispatcher principal qui analyse la commande brute reçue et la dirige vers le traitement approprié : introspection des outils, boucle de qualité, exécution d'outil natif via `!native_tool`, ou routage vers l'IA pour les commandes legacy ou inconnues.
*   **Arguments:**
    *   `command_text` (str): La commande brute reçue de l'utilisateur ou de l'IA.
    *   `session`: Objet session IA.
    *   `response_queue` (Queue): File d'attente pour les réponses à l'interface utilisateur.
    *   `task_queue` (Queue, optionnel): File d'attente pour les tâches.
    *   `action_log_path` (str, optionnel): Chemin du fichier de log des actions (défaut: "action\_log.json").
*   **Retour:** Le résultat du traitement de la commande (chaîne de caractères).
*   **Logique Interne:**
    1.  Nettoie la commande d'entrée.
    2.  Gère les commandes spéciales :
        *   `!list_tools`, `liste tes commandes`, `help`, `outils`: Appelle `execute_lister_outils`.
        *   `!quality "instruction"`: Lance la boucle de qualité via `QualityEngine.QualityLoop` avec des paramètres configurables (`max_iterations` depuis `APP_SETTINGS`).
        *   `!native_tool {...}`: Extrait la commande et les arguments en utilisant `_smart_extract_and_parse`, puis appelle `execute_native_tool`. Gère les erreurs de parsing et d'exécution.
    3.  Gère les commandes legacy commençant par `!` :
        *   `!list_models`: Affiche la liste des modèles disponibles via `SessionFactory`.
        *   Autres commandes `!`: Crée une session "router" et demande à l'IA de corriger/interpréter la commande via `call_ai_robust`.
    4.  Si aucune des conditions précédentes n'est remplie, retourne un message indiquant que la commande est ignorée.

### `generate_search_query(user_prompt)`

*   **Description:** Génère des mots-clés de recherche optimaux à partir d'une requête utilisateur en utilisant un appel IA (via une session "router").
*   **Arguments:**
    *   `user_prompt` (str): La requête initiale de l'utilisateur.
*   **Retour:** Une chaîne de caractères contenant les mots-clés optimisés pour la recherche.
*   **Logique Interne:**
    1.  Crée une session IA de type "router".
    2.  Appelle `call_ai_robust` avec un prompt demandant à l'IA de générer des mots-clés de recherche à partir du `user_prompt`.
    3.  Nettoie et retourne le résultat.

## 3. Exemple d'usage

Cet exemple illustre comment un système externe pourrait utiliser `ai_helper` pour exécuter une commande :

```python
# Supposons que ces objets soient disponibles et correctement initialisés
from queue import Queue
from ai_core.sessions import Session  # Simplifié pour l'exemple

session_ia = Session("user_session") # Une session IA existante
response_q = Queue()
task_q = Queue()

# Commande brute reçue, par exemple d'une interface utilisateur
command_from_ui = '!native_tool {"name": "lire_fichier", "args": {"chemin": "mon_projet/README.md"}}'

# Le dispatcher central analyse et exécute
result = analyze_request_and_dispatch(
    command_text=command_from_ui,
    session=session_ia,
    response_queue=response_q,
    task_queue=task_q,
    action_log_path="log/actions.log"
)

# Affichage du résultat (qui pourrait être du texte lu, une confirmation, ou une erreur)
print(result)

# Si l'outil avait écrit dans la response_q (ex: lister_outils)
# if not response_q.empty():
#     ui_message = response_q.get()
#     print(f"Message pour l'UI: {ui_message}")

# Pour lancer la boucle qualité
command_quality = '!quality "Vérifier la qualité du code dans src/utils.py et proposer des améliorations."'
result_quality = analyze_request_and_dispatch(command_from_ui, session_ia, response_q, task_q)
print(result_quality)
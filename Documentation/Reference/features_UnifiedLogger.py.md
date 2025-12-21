# Documentation Technique - `features\UnifiedLogger.py`

## 1. En-tête

*   **Titre**: `UnifiedLogger.py`
*   **Description concise**: Ce module implémente un système de journalisation centralisé et hybride. Il assure la persistance des logs dans des fichiers sur disque et un affichage enrichi et esthétique dans le terminal. Il intègre la gestion de la rétention des fichiers de logs et des fonctionnalités avancées pour la visualisation des métriques, notamment pour les interactions avec des modèles d'IA.
*   **Dépendances**:
    *   `os`: Pour les opérations sur le système de fichiers (création de répertoire, chemins).
    *   `json`: Pour la sérialisation des données complexes en JSON lors de l'écriture des logs.
    *   `datetime`: Pour la génération d'horodatages.
    *   `threading`: Pour garantir la sécurité des accès concurrents au fichier de log via un `Lock`.
    *   `glob`: Pour la recherche de fichiers de log existants dans le cadre de la gestion de la rétention.
    *   `sys`: Non directement utilisé dans le code fourni, mais souvent implicite pour les fonctionnalités d'entrée/sortie.
    *   `ctypes`: Pour activer le support des séquences ANSI dans les terminaux Windows, permettant l'affichage des couleurs.
    *   **Dépendances externes (optionnelles)**: `config.settings` (pour la configuration de la rétention des logs et le filtrage des canaux de journalisation).

## 2. Classes & Fonctions

### Variables Globales de Configuration

*   `LOG_DIR` (str): Chemin du répertoire où les fichiers de log seront stockés ("logs").
*   `current_ts` (str): Horodatage actuel formaté (`%d-%b_%Hh%M`) utilisé pour nommer le fichier de log global.
*   `LOG_FILE` (str): Chemin complet du fichier de log actuel (`global_debug_{current_ts}.log`).
*   `LOCK` (threading.Lock): Verrou utilisé pour sécuriser l'accès au fichier de log en cas d'écritures concurrentes depuis plusieurs threads.

### Fonctions

#### `_clean_old_logs()`

*   **Signature**: `def _clean_old_logs():`
*   **Arguments**: Aucun.
*   **Retours**: Aucun.
*   **Logique interne**:
    *   Cette fonction est responsable de la suppression des anciens fichiers de log afin de maintenir une quantité gérable de fichiers.
    *   Elle tente d'importer `APP_SETTINGS` depuis `config.settings`. Si l'import échoue ou la clé `log_retention_count` n'est pas définie, la limite par défaut est de 10 fichiers.
    *   Elle recherche tous les fichiers de log correspondant au pattern `global_debug_*.log` dans le `LOG_DIR`.
    *   Si le nombre de fichiers trouvés est supérieur ou égal à la limite définie (`max_files`), elle trie les fichiers par date de dernière modification (les plus anciens en premier).
    *   Elle calcule le nombre de fichiers à supprimer pour revenir à la limite de `max_files - 1` (car le fichier de log actuel occupe une place).
    *   Les `nb_to_delete` fichiers les plus anciens sont supprimés.
    *   Des gestionnaires d'exceptions sont en place pour intercepter les erreurs lors de la suppression des fichiers et lors de l'importation des paramètres.
    *   Cette fonction est exécutée une fois au chargement du module.

#### `enable_windows_ansi()`

*   **Signature**: `def enable_windows_ansi():`
*   **Arguments**: Aucun.
*   **Retours**: Aucun.
*   **Logique interne**:
    *   Détecte si le système d'exploitation est Windows (`os.name == 'nt'`).
    *   Utilise la bibliothèque `ctypes` pour interagir directement avec l'API du noyau Windows (`kernel32`).
    *   Récupère le handle de sortie standard de la console.
    *   Lit le mode de la console et ajoute le flag `0x0004` (ENABLE_VIRTUAL_TERMINAL_PROCESSING) pour activer le support des séquences d'échappement ANSI.
    *   Met à jour le mode de la console.
    *   Cela permet aux caractères de couleur ANSI (`\033[...]`) d'être interprétés correctement par le terminal Windows, rendant l'affichage coloré.
    *   Les exceptions sont silencieusement ignorées en cas d'échec de l'activation.

### Classes

#### `class Colors`

*   **Signature**: `class Colors:`
*   **Description**: Cette classe utilitaire définit des constantes pour les codes d'échappement ANSI, permettant d'appliquer des couleurs et des styles au texte affiché dans un terminal compatible ANSI.
*   **Attributs**:
    *   `RESET`: Réinitialise tous les attributs de formatage à leurs valeurs par défaut.
    *   `BOLD`: Active le style gras.
    *   `DIM`: Active le style estompé/diminué.
    *   `GRAY`: Texte gris.
    *   `RED`: Texte rouge.
    *   `GREEN`: Texte vert.
    *   `YELLOW`: Texte jaune.
    *   `BLUE`: Texte bleu.
    *   `MAGENTA`: Texte magenta.
    *   `CYAN`: Texte cyan.
    *   `WHITE`: Texte blanc.
    *   `BG_RED`: Fond rouge.

#### `class UnifiedLogger`

*   **Signature**: `class UnifiedLogger:`
*   **Description**: Un logger statique centralisé qui gère à la fois l'écriture de logs détaillés dans un fichier et l'affichage d'un output beautifié et informatif dans le terminal. Il est conçu pour être la source unique de journalisation dans l'application, offrant une uniformité dans la sortie.

##### `@staticmethod UnifiedLogger.write()`

*   **Signature**: `def write(source, msg_type, message, data=None):`
*   **Arguments**:
    *   `source` (str): La source du message de log (ex: nom de module, nom de classe ou fonction). Utilisé pour identifier l'origine du log.
    *   `msg_type` (str): Le type de message (ex: "INFO", "ERROR", "WARNING", "METRICS", "SUCCESS", etc.).
    *   `message` (str): Le contenu principal du message de log.
    *   `data` (any, optionnel): Des données supplémentaires à associer au log. Si ce n'est pas une chaîne, elles seront sérialisées en JSON. Par défaut à `None`.
*   **Retours**: Aucun.
*   **Logique interne**:
    *   Génère deux horodatages : un précis pour le fichier (avec millisecondes) et un plus court pour l'affichage terminal.
    *   **Écriture dans le fichier de log**:
        *   Construit une entrée de log détaillée incluant l'horodatage, le nom du thread, la source, le type de message et le message principal.
        *   Si des `data` sont fournies, elles sont ajoutées à l'entrée. Si ce ne sont pas des chaînes, elles sont sérialisées en JSON avec `indent=2` pour la lisibilité.
        *   Un `threading.Lock` (`LOCK`) est utilisé pour garantir que l'écriture dans le fichier est atomique et thread-safe, évitant la corruption du fichier en cas d'accès concurrents.
        *   L'entrée est ajoutée au `LOG_FILE` en mode ajout (`"a"`) avec encodage UTF-8.
        *   Les erreurs d'écriture de fichier sont silencieusement ignorées.
    *   **Affichage dans le terminal**:
        *   Délègue la tâche d'affichage formaté à la méthode interne `_print_beautified`.

##### `@staticmethod UnifiedLogger._print_beautified()`

*   **Signature**: `def _print_beautified(timestamp, source, msg_type, message, data):`
*   **Arguments**:
    *   `timestamp` (str): L'horodatage formaté (HH:MM:SS) à afficher.
    *   `source` (str): La source du message de log.
    *   `msg_type` (str): Le type de message.
    *   `message` (str): Le contenu principal du message de log.
    *   `data` (any): Les données supplémentaires associées au log.
*   **Retours**: Aucun.
*   **Logique interne**:
    *   **Filtrage**:
        *   Les messages de type "ERROR", "CRITICAL", "BAN", "WARNING", "FAIL", "METRICS" sont toujours imprimés.
        *   Pour les autres types, un filtrage optionnel est appliqué en tentant d'importer `LOGGING_CHANNELS` et `LOG_SOURCE_MAP` depuis `config.settings`. Si la source ou le canal associé n'est pas activé dans les paramètres, le message n'est pas affiché.
    *   **Styles et Icônes**:
        *   Un dictionnaire `type_styles` mappe chaque `msg_type` à une couleur ANSI et un caractère icône (emoji) pour une identification visuelle rapide.
    *   **Prétraitement du Message**:
        *   Si le `message` contient des crochets `[]`, le contenu entre crochets est estompé (`Colors.DIM`) pour distinguer les préfixes ou identifiants.
    *   **Traitement Spécial pour les Métriques (`msg_type == "METRICS"`)**:
        *   Si le message est de type "METRICS" et que `data` est un dictionnaire, il effectue un formatage spécifique pour les métriques d'IA:
            *   Extrait `provider`, `model`, `agent` des `data`.
            *   Définit des icônes spécifiques pour les fournisseurs (Gemini, Groq, OpenAI, DeepSeek).
            *   **Cas des métriques de cache**: Si `billed` ou `cache_hit` sont présents dans `data`, il affiche un résumé détaillé incluant les "Miss" (tokens facturés), "Hit" (tokens servis par cache), les "Payés" (tokens effectivement facturés) et le pourcentage d'économies.
            *   **Cas des métriques standard**: Sinon, il affiche une ligne plus compacte avec le fournisseur, l'agent (en majuscules pour distinction) et le modèle.
    *   **Affichage de la Ligne Principale**:
        *   Construit la première ligne du log avec l'horodatage estompé, la source tronquée, le type de message coloré avec son icône, et le message principal.
        *   Utilise un bloc `try-except` pour gérer `UnicodeEncodeError`, ce qui peut arriver avec certains terminaux ne supportant pas tous les caractères UTF-8.
    *   **Affichage de l'Arborescence (Lignes Additionnelles)**:
        *   Si des `data` sont présentes, des informations supplémentaires sont affichées sur une ou plusieurs lignes indentées (`└──`) :
            *   **Métriques détaillées**: Pour `msg_type == "METRICS"`, affiche les tokens d'entrée (`in`), de sortie (`out`) et le temps d'exécution (`time`).
            *   **Erreurs/Alertes**: Pour `msg_type` étant "ERROR", "WARNING", ou "CRITICAL", affiche les 200 premiers caractères de l'erreur contenue dans `data`.
            *   **Résumé de résultat**: Si `data` contient une clé `result_summary`, affiche les 100 premiers caractères du résumé.

## 3. Exemple d'usage

```python
from features.UnifiedLogger import UnifiedLogger

# Exemple 1: Message d'information simple
UnifiedLogger.write(
    source="main.py", 
    msg_type="INFO", 
    message="Démarrage de l'application..."
)

# Exemple 2: Message d'erreur avec des données
try:
    1 / 0
except Exception as e:
    UnifiedLogger.write(
        source="data_processor", 
        msg_type="ERROR", 
        message="Erreur lors du calcul", 
        data={"error": str(e), "context": "division par zéro"}
    )

# Exemple 3: Métriques pour une interaction IA (avec cache)
UnifiedLogger.write(
    source="llm_agent.chat",
    msg_type="METRICS",
    message="Requête LLM traitée",
    data={
        "provider": "gemini",
        "model": "gemini-2.5-flash-lite",
        "agent": "compressor",
        "in": 150,
        "out": 30,
        "time": "0.12s",
        "cache_hit": 100,
        "billed": 50
    }
)

# Exemple 4: Métriques pour une interaction IA (sans cache explicite)
UnifiedLogger.write(
    source="image_gen.pipeline",
    msg_type="METRICS",
    message="Génération d'image",
    data={
        "provider": "openai",
        "model": "dall-e-3",
        "in": 50,
        "out": 1,
        "time": "5.3s"
    }
)

# Exemple 5: Message de succès avec un résumé
UnifiedLogger.write(
    source="db.connector",
    msg_type="SUCCESS",
    message="Données sauvegardées",
    data={"result_summary": "12 entrées mises à jour dans la table 'users'.", "rows_affected": 12}
)

# Exemple 6: Message d'avertissement
UnifiedLogger.write(
    source="config.loader",
    msg_type="WARNING",
    message="Paramètre 'api_key' non trouvé, utilisation de la valeur par défaut.",
    data={"key": "api_key", "default_value": "ABC-123"}
)
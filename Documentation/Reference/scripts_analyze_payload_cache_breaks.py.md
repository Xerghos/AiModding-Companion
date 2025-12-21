# Documentation Technique : `analyze_payload_cache_breaks.py`

## 1. En-tête

### Titre
Analyse des Cassures de Cache entre Payloads

### Description concise
Ce script Python analyse deux fichiers de payload (généralement au format JSON) pour détecter les différences qui pourraient invalider le cache implicite de modèles de langage comme Gemini ou DeepSeek. Il se concentre sur les éléments critiques des messages système (`system`) et de l'historique conversationnel (`user`, `assistant`), générant des rapports détaillés en Markdown dans le répertoire `logs/`.

### Dépendances
*   **Modules standards Python:**
    *   `json`: Pour la manipulation des fichiers JSON.
    *   `os`: Pour les opérations sur le système de fichiers (vérification d'existence).
    *   `sys`: Pour la manipulation du chemin système et l'arrêt du script.
    *   `pathlib.Path`: Pour la manipulation des chemins de fichiers de manière orientée objet.
    *   `typing`: `Dict`, `List`, `Tuple`, `Any`, `Optional` pour les annotations de type.
    *   `datetime`: Pour gérer les timestamps lors de la génération des rapports.
    *   `difflib`: Pour générer des comparaisons textuelles (diff) entre contenus.
    *   `argparse`: Pour l'analyse des arguments de la ligne de commande.
*   **Dépendances internes au projet:**
    *   `config.paths.get_path`: Utilitaire pour obtenir des chemins de fichiers ou répertoires configurés dans le projet.

## 2. Classes & Fonctions

### Classe `PayloadCacheAnalyzer`
Analyseur de cassures de cache entre payloads.

#### `__init__(self, payload1_path: str, payload2_path: str)`
*   **Signature**: `__init__(self, payload1_path: str, payload2_path: str)`
*   **Arguments**:
    *   `payload1_path` (`str`): Chemin vers le premier fichier JSON de payload.
    *   `payload2_path` (`str`): Chemin vers le deuxième fichier JSON de payload.
*   **Retours**: `None`
*   **Logique interne**: Initialise l'instance de l'analyseur avec les chemins des deux payloads. Configure des attributs internes pour stocker les payloads chargés et les différences détectées.

#### `load_payloads(self) -> Tuple[bool, Optional[str]]`
*   **Signature**: `load_payloads(self) -> Tuple[bool, Optional[str]]`
*   **Arguments**: `self`
*   **Retours**: `Tuple[bool, Optional[str]]`
    *   `bool`: `True` si les payloads ont été chargés avec succès, `False` sinon.
    *   `Optional[str]`: Message d'erreur si le chargement échoue, `None` sinon.
*   **Logique interne**: Tente de charger les contenus JSON des fichiers spécifiés lors de l'initialisation dans `self.payload1` et `self.payload2`. Gère les exceptions potentielles lors de la lecture ou du parsing JSON.

#### `extract_payload_data(self, payload_obj: Dict) -> Dict`
*   **Signature**: `extract_payload_data(self, payload_obj: Dict) -> Dict`
*   **Arguments**:
    *   `payload_obj` (`Dict`): L'objet payload brut, potentiellement avec des métadonnées.
*   **Retours**: `Dict`
    *   Le dictionnaire contenant uniquement les données du payload réel (le contenu de la clé `'payload'` si elle existe), sinon l'objet entier.
*   **Logique interne**: Cette fonction est essentielle car elle filtre les métadonnées (comme les timestamps de génération) qui ne font pas partie du payload réellement envoyé à l'API du modèle et donc ne devraient pas casser le cache. Le cache Gemini/DeepSeek se base uniquement sur le contenu des messages.

#### `categorize_messages(self, messages: List[Dict]) -> Dict[str, List[Dict]]`
*   **Signature**: `categorize_messages(self, messages: List[Dict]) -> Dict[str, List[Dict]]`
*   **Arguments**:
    *   `messages` (`List[Dict]`): Une liste de dictionnaires représentant les messages du payload.
*   **Retours**: `Dict[str, List[Dict]]`
    *   Un dictionnaire où les clés sont les rôles (`'system'`, `'user'`, `'assistant'`) et les valeurs sont des listes des messages correspondants.
*   **Logique interne**: Parcourt la liste des messages et les classe dans des listes séparées en fonction de leur rôle (`'role'`).

#### `normalize_content(self, content: str) -> str`
*   **Signature**: `normalize_content(self, content: str) -> str`
*   **Arguments**:
    *   `content` (`str`): La chaîne de caractères à normaliser.
*   **Retours**: `str`
    *   Le contenu normalisé.
*   **Logique interne**: Effectue une normalisation simple du contenu textuel pour la comparaison. Cela inclut la suppression des espaces blancs en fin de ligne (`rstrip()`) et des lignes vides terminales. L'objectif est de réduire les "faux positifs" dus à des différences de formatage insignifiantes.

#### `compare_system_messages(self, sys1: List[Dict], sys2: List[Dict]) -> List[Dict]`
*   **Signature**: `compare_system_messages(self, sys1: List[Dict], sys2: List[Dict]) -> List[Dict]`
*   **Arguments**:
    *   `sys1` (`List[Dict]`): Liste des messages système du premier payload.
    *   `sys2` (`List[Dict]`): Liste des messages système du deuxième payload.
*   **Retours**: `List[Dict]`
    *   Une liste de dictionnaires, chacun décrivant une différence détectée dans les messages système.
*   **Logique interne**: Compare les messages système, qui sont considérés comme CRITIQUES pour la stabilité du cache. Elle vérifie d'abord si le nombre de messages système est identique. Ensuite, elle compare le contenu normalisé de chaque message système correspondant. En cas de différence de contenu, elle tente de catégoriser le type de modification (RAG, Repo Map, LTM, etc.) via `_analyze_system_content_diff`.

#### `_analyze_system_content_diff(self, content1: str, content2: str) -> str`
*   **Signature**: `_analyze_system_content_diff(self, content1: str, content2: str) -> str`
*   **Arguments**:
    *   `content1` (`str`): Contenu du message système du premier payload.
    *   `content2` (`str`): Contenu du message système du deuxième payload.
*   **Retours**: `str`
    *   Une chaîne de caractères décrivant le type de différence détectée (ex: `'RAG_DOCS_DYNAMIC'`, `'REPO_MAP_CHANGED'`).
*   **Logique interne**: C'est une méthode auxiliaire qui examine les chaînes de contenu pour identifier des motifs spécifiques indiquant la nature d'une cassure de cache (par exemple, la présence de blocs "DOCS TECHNIQUE (RAG Hybride)", "REPO MAP", "MÉMOIRE LONG TERME", etc.).

#### `compare_histories(self, hist1: List[Dict], hist2: List[Dict]) -> List[Dict]`
*   **Signature**: `compare_histories(self, hist1: List[Dict], hist2: List[Dict]) -> List[Dict]`
*   **Arguments**:
    *   `hist1` (`List[Dict]`): Liste des messages d'historique (utilisateur et assistant) du premier payload.
    *   `hist2` (`List[Dict]`): Liste des messages d'historique (utilisateur et assistant) du deuxième payload.
*   **Retours**: `List[Dict]`
    *   Une liste de dictionnaires décrivant les différences détectées dans l'historique conversationnel.
*   **Logique interne**: Compare la longueur de l'historique et les 3 derniers messages (les plus récents) en termes de rôle et de contenu. Les différences dans l'historique sont généralement moins critiques pour une cassure de cache système que les messages système, mais sont informatives.

#### `generate_diff_text(self, content1: str, content2: str, context_lines: int = 3) -> str`
*   **Signature**: `generate_diff_text(self, content1: str, content2: str, context_lines: int = 3) -> str`
*   **Arguments**:
    *   `content1` (`str`): Le premier contenu à comparer.
    *   `content2` (`str`): Le second contenu à comparer.
    *   `context_lines` (`int`, optionnel): Le nombre de lignes de contexte à inclure dans le diff. (Par défaut: 3)
*   **Retours**: `str`
    *   Une chaîne de caractères représentant le "diff unifié" entre les deux contenus.
*   **Logique interne**: Utilise le module `difflib` pour générer un diff textuel standard (format "unified diff") entre deux blocs de texte, facilitant la visualisation des modifications. (Note: Cette fonction est définie mais n'est pas utilisée directement dans la génération de rapport actuelle, elle pourrait être intégrée pour des détails plus granulaires.)

#### `analyze(self) -> Dict[str, Any]`
*   **Signature**: `analyze(self) -> Dict[str, Any]`
*   **Arguments**: `self`
*   **Retours**: `Dict[str, Any]`
    *   Un dictionnaire contenant les résultats complets de l'analyse, incluant des métadonnées, des statistiques, et les détails des cassures de cache.
*   **Logique interne**: C'est la méthode principale qui orchestre l'ensemble du processus d'analyse. Elle charge les payloads, extrait les données pertinentes, catégorise les messages, puis appelle `compare_system_messages` et `compare_histories`. Elle consolide toutes les informations et les statistiques dans un dictionnaire de résultat structuré.

#### `generate_report(self, analysis: Dict[str, Any], output_path: Optional[str] = None) -> str`
*   **Signature**: `generate_report(self, analysis: Dict[str, Any], output_path: Optional[str] = None) -> str`
*   **Arguments**:
    *   `analysis` (`Dict[str, Any]`): Le dictionnaire de résultats généré par la méthode `analyze()`.
    *   `output_path` (`Optional[str]`, optionnel): Le chemin du fichier où le rapport sera sauvegardé. Si `None`, un chemin par défaut est généré dans `logs/`.
*   **Retours**: `str`
    *   Le chemin complet du fichier de rapport généré.
*   **Logique interne**: Formate les résultats de l'analyse dans un fichier Markdown détaillé. Le rapport inclut les métadonnées des payloads, des statistiques comparatives, l'impact global sur le cache, des sections spécifiques pour les cassures système et d'historique, et des recommandations basées sur les types de différences détectées.

### Fonction `find_latest_payloads(logs_dir: str, pattern: str = "payload_*.json", limit: int = 2) -> List[str]`
*   **Signature**: `find_latest_payloads(logs_dir: str, pattern: str = "payload_*.json", limit: int = 2) -> List[str]`
*   **Arguments**:
    *   `logs_dir` (`str`): Le chemin du répertoire où chercher les payloads.
    *   `pattern` (`str`, optionnel): Le motif de nom de fichier à rechercher (par défaut: `"payload_*.json"`).
    *   `limit` (`int`, optionnel): Le nombre maximal de fichiers les plus récents à retourner (par défaut: 2).
*   **Retours**: `List[str]`
    *   Une liste des chemins des fichiers payload les plus récents trouvés.
*   **Logique interne**: Recherche les fichiers correspondant au motif dans le répertoire spécifié, les trie par date de dernière modification (du plus récent au plus ancien), et retourne les `limit` premiers.

### Fonction `main()`
*   **Signature**: `main()`
*   **Arguments**: `None`
*   **Retours**: `None`
*   **Logique interne**:
    *   Point d'entrée principal du script.
    *   Configure un `ArgumentParser` pour gérer les arguments de la ligne de commande.
    *   Supporte deux modes d'exécution :
        1.  **Manuel**: L'utilisateur spécifie explicitement les chemins de `payload1` et `payload2`.
        2.  **Automatique (`--auto`)**: Le script recherche et compare les deux fichiers `payload_*.json` les plus récents dans le répertoire `logs/`.
    *   Vérifie l'existence des fichiers payload.
    *   Crée une instance de `PayloadCacheAnalyzer`.
    *   Appelle la méthode `analyze()` pour effectuer l'analyse.
    *   Gère les erreurs potentielles lors de l'analyse.
    *   Appelle la méthode `generate_report()` pour créer un rapport Markdown.
    *   Affiche un résumé de l'analyse et le chemin du rapport généré dans la console.

## 3. Exemple d'usage

Pour utiliser ce script, vous pouvez fournir les chemins de deux fichiers payload manuellement ou le laisser détecter les deux derniers automatiquement.

1.  **Analyse de deux payloads spécifiques:**
    ```bash
    python scripts/analyze_payload_cache_breaks.py path/to/payload_A.json path/to/payload_B.json
    ```
    Ou avec un chemin de sortie personnalisé pour le rapport :
    ```bash
    python scripts/analyze_payload_cache_breaks.py path/to/payload_A.json path/to/payload_B.json --output reports/my_custom_analysis.md
    ```

2.  **Analyse des deux payloads les plus récents dans le répertoire `logs/` (mode automatique):**
    Assurez-vous que des fichiers `payload_*.json` existent dans le répertoire `logs/` de votre projet.
    ```bash
    python scripts/analyze_payload_cache_breaks.py --auto
    ```

Le script affichera un résumé des résultats dans la console et générera un fichier Markdown détaillé (par défaut dans `logs/payload_cache_analysis_YYYY-MM-DD_HHMMSS.md`) avec toutes les informations sur les cassures de cache détectées.
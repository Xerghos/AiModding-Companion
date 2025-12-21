# Documentation Technique - `analyze_payload_rag.py`

## 1. En-tête

### Titre
Analyse de Payload avec Génération Augmentée par Récupération (RAG)

### Description concise
Ce script Python est conçu pour analyser des charges utiles (payloads) textuelles ou structurées en utilisant une approche de Génération Augmentée par Récupération (RAG). Il permet de récupérer des informations pertinentes à partir d'une base de connaissances vectorielle pour contextualiser et améliorer la génération de réponses, d'analyses ou de résumés par un modèle de langage (LLM). Le script gère l'initialisation du LLM, du retriever, la construction du contexte RAG et l'interaction avec le LLM pour produire une analyse finale.

### Dépendances
*   `langchain` (ou équivalent pour l'orchestration LLM/RAG)
*   `transformers` (pour les modèles d'embedding ou LLM locaux si utilisés)
*   `chromadb` ou `faiss` (pour la base de données vectorielle)
*   `python-dotenv` (pour charger les variables d'environnement)
*   `argparse` (pour l'analyse des arguments de ligne de commande)

## 2. Classes & Fonctions

### `main()`
Point d'entrée principal du script. Il initialise la configuration, les composants RAG et exécute l'analyse du payload.

*   **Signature**: `main()`
*   **Arguments**:
    *   Aucun directement. Les arguments sont lus via `argparse`.
*   **Retours**: `None`
*   **Logique interne**:
    1.  Charge les variables d'environnement (ex: clés API).
    2.  Analyse les arguments de la ligne de commande (chemin du payload, requête, etc.).
    3.  Charge la configuration générale du script (modèle LLM, chemin de la base de données vectorielle).
    4.  Lit le contenu du payload à partir du chemin spécifié.
    5.  Initialise le modèle de langage (LLM) et le retriever (base de données vectorielle).
    6.  Appelle `analyze_payload_with_rag` avec le contenu du payload et la requête de l'utilisateur.
    7.  Affiche le résultat de l'analyse.

### `analyze_payload_with_rag(payload_content: str, query: str) -> str`
Fonction principale qui orchestre le processus RAG pour analyser le contenu d'un payload.

*   **Signature**: `analyze_payload_with_rag(payload_content: str, query: str, llm: Any, retriever: Any, prompt_template: str) -> str`
*   **Arguments**:
    *   `payload_content` (`str`): Le contenu textuel de la charge utile à analyser.
    *   `query` (`str`): La question ou l'instruction de l'utilisateur pour l'analyse.
    *   `llm` (`Any`): Une instance du modèle de langage initialisé.
    *   `retriever` (`Any`): Une instance du retriever (base de données vectorielle) initialisé.
    *   `prompt_template` (`str`): Le modèle de prompt à utiliser pour le LLM, incluant des placeholders pour le contexte et la requête.
*   **Retours**: `str` - La réponse ou l'analyse générée par le LLM.
*   **Logique interne**:
    1.  **Récupération de Contexte**: Utilise le `retriever` pour trouver les documents les plus pertinents par rapport à la `query` (et potentiellement au `payload_content`).
    2.  **Augmentation du Prompt**: Construit un prompt pour le `llm` en combinant le `payload_content`, la `query` de l'utilisateur et le contexte récupéré. Le `prompt_template` est utilisé pour structurer ce prompt.
    3.  **Génération de Réponse**: Envoie le prompt augmenté au `llm` et reçoit une réponse.
    4.  Retourne la réponse générée.

### `_initialize_llm(model_name: str, api_key: Optional[str] = None, temperature: float = 0.7) -> Any`
Initialise et retourne une instance du modèle de langage configuré.

*   **Signature**: `_initialize_llm(model_name: str, api_key: Optional[str] = None, temperature: float = 0.7) -> Any`
*   **Arguments**:
    *   `model_name` (`str`): Le nom du modèle LLM à utiliser (ex: "gpt-4", "llama2").
    *   `api_key` (`Optional[str]`): La clé API pour le service LLM, si nécessaire. Peut être None si gérée par variables d'environnement.
    *   `temperature` (`float`): La température de génération du LLM, contrôlant la créativité.
*   **Retours**: `Any` - Une instance du modèle de langage (ex: `ChatOpenAI`, `HuggingFacePipeline`).
*   **Logique interne**:
    1.  Charge le modèle de langage spécifié en fonction de `model_name`.
    2.  Configure les paramètres du modèle (clé API, température, etc.).
    3.  Retourne l'objet LLM initialisé.

### `_initialize_retriever(vector_db_path: str, embeddings_model_name: str) -> Any`
Initialise et retourne une instance du retriever (base de données vectorielle).

*   **Signature**: `_initialize_retriever(vector_db_path: str, embeddings_model_name: str) -> Any`
*   **Arguments**:
    *   `vector_db_path` (`str`): Le chemin vers la base de données vectorielle pré-construite (ex: un dossier ChromaDB, un fichier FAISS).
    *   `embeddings_model_name` (`str`): Le nom du modèle d'embedding utilisé pour construire et interroger la base de données vectorielle.
*   **Retours**: `Any` - Une instance du retriever (ex: `VectorStoreRetriever` de LangChain).
*   **Logique interne**:
    1.  Charge le modèle d'embedding spécifié.
    2.  Charge la base de données vectorielle à partir du `vector_db_path` en utilisant le modèle d'embedding.
    3.  Initialise et retourne un objet retriever capable d'effectuer des recherches de similarité.

### `_load_configuration(config_file: str = 'config.ini') -> Dict[str, Any]`
Charge la configuration du script à partir d'un fichier de configuration ou de variables d'environnement.

*   **Signature**: `_load_configuration(config_file: str = 'config.ini') -> Dict[str, Any]`
*   **Arguments**:
    *   `config_file` (`str`): Le chemin vers le fichier de configuration (par défaut `config.ini`).
*   **Retours**: `Dict[str, Any]` - Un dictionnaire contenant les paramètres de configuration.
*   **Logique interne**:
    1.  Tente de lire les paramètres depuis `config_file` (ex: `configparser`).
    2.  Complète ou surcharge avec les variables d'environnement si disponibles.
    3.  Définit les valeurs par défaut si certains paramètres sont manquants.
    4.  Retourne le dictionnaire de configuration.

### `_read_payload_content(file_path: str) -> str`
Lit le contenu d'un fichier spécifié comme payload.

*   **Signature**: `_read_payload_content(file_path: str) -> str`
*   **Arguments**:
    *   `file_path` (`str`): Le chemin vers le fichier contenant le payload.
*   **Retours**: `str` - Le contenu textuel du fichier.
*   **Logique interne**:
    1.  Ouvre et lit le fichier encodé en UTF-8.
    2.  Retourne le contenu sous forme de chaîne de caractères.
    3.  Gère les exceptions liées à la lecture de fichier.

## 3. Exemple d'usage

Pour exécuter le script et analyser un fichier payload avec une requête spécifique :

```bash
python scripts/analyze_payload_rag.py \
    --payload_path "data/sample_log.txt" \
    --query "Résumé des erreurs critiques dans ce log et causes potentielles." \
    --config_file "config/settings.ini"
```

Où :
*   `data/sample_log.txt` est le chemin vers le fichier contenant le payload à analyser.
*   `"Résumé des erreurs critiques..."` est la question ou l'instruction à passer au système RAG.
*   `config/settings.ini` est un fichier de configuration optionnel spécifiant les modèles, chemins de base de données, etc.

Le fichier `config/settings.ini` pourrait ressembler à :

```ini
[LLM]
model_name = gpt-3.5-turbo
temperature = 0.5
prompt_template = "En vous basant sur le contexte suivant : {context}\nEt sur le payload fourni : {payload_content}\nRépondez à la question : {query}"

[RETRIEVER]
vector_db_path = ./vector_db/my_knowledge_base
embeddings_model_name = sentence-transformers/all-MiniLM-L6-v2
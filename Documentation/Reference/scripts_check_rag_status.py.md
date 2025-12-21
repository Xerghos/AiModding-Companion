# `scripts/check_rag_status.py` - Script de Vérification du Statut RAG

## 1. En-tête

### Titre
`scripts/check_rag_status.py` - Script de Vérification du Statut des Composants RAG

### Description concise
Ce script Python est conçu pour évaluer l'état de fonctionnement des composants critiques d'un système de Génération Augmentée par Récupération (RAG). Il vérifie la disponibilité de la base de données vectorielle, l'accessibilité de l'API du modèle de langage (LLM) et l'intégrité de l'index de récupération. En cas de défaillance, il signale les problèmes pour faciliter le diagnostic et la maintenance du système RAG.

### Dépendances
*   **Python 3.x**
*   **Modules standards :**
    *   `os` : Pour l'accès aux variables d'environnement.
    *   `sys` : Pour la gestion du code de sortie du script.
    *   `logging` : Pour la journalisation des opérations et des erreurs.
*   **Modules tiers :**
    *   `requests` : Pour effectuer des requêtes HTTP aux API externes (base de données vectorielle, LLM).
    *   `python-dotenv` (optionnel) : Peut être utilisé pour charger les variables d'environnement depuis un fichier `.env` local si le script est conçu pour le faire.

## 2. Classes & Fonctions

Ce script ne contient pas de classes définies, mais il s'appuie sur plusieurs fonctions pour organiser les vérifications.

---

### `main()`

Cette fonction est le point d'entrée principal du script. Elle orchestre l'ensemble des vérifications du statut RAG.

*   **Signature :** `def main():`
*   **Arguments :** Aucun.
*   **Retours :**
    *   `None`. La fonction gère directement le code de sortie du script via `sys.exit()`. Le script se termine avec un code `0` si toutes les vérifications sont réussies, et un code `1` ou plus en cas d'échec d'une ou plusieurs vérifications.
*   **Logique interne :**
    1.  Configure le système de journalisation (`logging`).
    2.  Charge les variables d'environnement nécessaires via `_load_environment_variables()`.
    3.  Appelle successivement les fonctions de vérification individuelles (`_check_vector_db_health`, `_check_llm_api_health`, `_check_rag_index_integrity`).
    4.  Consolide les résultats de toutes les vérifications.
    5.  Affiche un rapport final indiquant le statut global du système RAG.
    6.  Définit le code de sortie du script (`sys.exit(0)` pour succès, `sys.exit(1)` pour échec).

---

### `_load_environment_variables()`

Charge les variables d'environnement requises pour la configuration des services RAG.

*   **Signature :** `def _load_environment_variables() -> dict:`
*   **Arguments :** Aucun.
*   **Retours :**
    *   `dict` : Un dictionnaire contenant les paires clé-valeur des variables d'environnement chargées. Exemple :
        ```python
        {
            "VECTOR_DB_ENDPOINT": "http://localhost:8000",
            "VECTOR_DB_API_KEY": "your_vector_db_api_key",
            "VECTOR_DB_COLLECTION_NAME": "my_rag_collection",
            "VECTOR_DB_MIN_VECTORS": 100,
            "LLM_API_ENDPOINT": "https://api.openai.com/v1/chat/completions",
            "LLM_API_KEY": "your_llm_api_key"
        }
        ```
    *   **Lève :** `ValueError` si une variable d'environnement critique est manquante.
*   **Logique interne :**
    1.  Tente de charger les variables d'environnement spécifiques (par exemple, `VECTOR_DB_ENDPOINT`, `LLM_API_KEY`) à l'aide de `os.getenv()`.
    2.  Vérifie que toutes les variables critiques sont présentes et non vides.
    3.  Convertit les valeurs numériques (comme `VECTOR_DB_MIN_VECTORS`) en types appropriés.
    4.  Logge les variables chargées (sans révéler les clés API sensibles).

---

### `_check_vector_db_health(endpoint: str, api_key: str) -> bool`

Vérifie l'accessibilité et le bon fonctionnement de la base de données vectorielle.

*   **Signature :** `def _check_vector_db_health(endpoint: str, api_key: str) -> bool:`
*   **Arguments :**
    *   `endpoint` (`str`) : L'URL de base ou l'endpoint de "santé" (par exemple, `/health` ou `/ping`) de l'API de la base de données vectorielle.
    *   `api_key` (`str`) : La clé API ou le jeton d'authentification pour accéder à la base de données vectorielle.
*   **Retours :**
    *   `bool` : `True` si la base de données vectorielle répond correctement et est considérée comme saine ; `False` sinon.
*   **Logique interne :**
    1.  Formule une requête HTTP (généralement GET) vers l'endpoint de santé de la base de données vectorielle.
    2.  Ajoute les en-têtes d'authentification nécessaires (par exemple, `Authorization: Bearer <api_key>`).
    3.  Gère les exceptions liées au réseau (connexion refusée, timeout).
    4.  Vérifie le code de statut de la réponse HTTP (un code `200 OK` indique généralement le succès).
    5.  Optionnellement, peut analyser le corps de la réponse pour des informations de statut plus détaillées.

---

### `_check_llm_api_health(endpoint: str, api_key: str) -> bool`

Vérifie l'accessibilité et la réactivité de l'API du modèle de langage (LLM).

*   **Signature :** `def _check_llm_api_health(endpoint: str, api_key: str) -> bool:`
*   **Arguments :**
    *   `endpoint` (`str`) : L'URL de l'API du modèle de langage (par exemple, un endpoint de complétion de chat).
    *   `api_key` (`str`) : La clé API ou le jeton d'authentification pour accéder au LLM.
*   **Retours :**
    *   `bool` : `True` si l'API du LLM est accessible et répond à une requête de test ; `False` sinon.
*   **Logique interne :**
    1.  Formule une requête HTTP (généralement POST) vers l'endpoint du LLM avec une charge utile de test minimale (par exemple, une requête simple de complétion de chat).
    2.  Ajoute les en-têtes d'authentification requis.
    3.  Gère les exceptions réseau et les timeouts.
    4.  Vérifie le code de statut de la réponse HTTP (un code `200 OK` indique le succès).
    5.  Optionnellement, peut vérifier la structure de la réponse pour s'assurer que le LLM a renvoyé un format attendu.

---

### `_check_rag_index_integrity(vector_db_endpoint: str, collection_name: str, min_vectors: int, api_key: str) -> bool`

Vérifie l'intégrité de l'index de récupération dans la base de données vectorielle, en s'assurant qu'il est peuplé avec un nombre suffisant de vecteurs.

*   **Signature :** `def _check_rag_index_integrity(vector_db_endpoint: str, collection_name: str, min_vectors: int, api_key: str) -> bool:`
*   **Arguments :**
    *   `vector_db_endpoint` (`str`) : L'URL de base de l'API de la base de données vectorielle.
    *   `collection_name` (`str`) : Le nom de la collection, de l'index ou de l'espace de noms à vérifier dans la base de données vectorielle.
    *   `min_vectors` (`int`) : Le nombre minimum de vecteurs que la collection doit contenir pour être considérée comme saine.
    *   `api_key` (`str`) : La clé API pour l'authentification auprès de la base de données vectorielle.
*   **Retours :**
    *   `bool` : `True` si la collection existe et contient au moins `min_vectors` ; `False` sinon.
*   **Logique interne :**
    1.  Construit une requête HTTP (généralement GET ou POST) pour interroger les métriques ou le compte de documents/vecteurs d'une collection spécifique dans la base de données vectorielle.
    2.  Ajoute les en-têtes d'authentification.
    3.  Gère les erreurs de communication et les timeouts.
    4.  Analyse la réponse pour extraire le nombre actuel de vecteurs dans la collection.
    5.  Compare ce nombre avec `min_vectors`. Logge un avertissement ou une erreur si le nombre est inférieur.

## 3. Exemple d'usage

Pour utiliser le script `check_rag_status.py`, vous devez d'abord définir les variables d'environnement requises.

1.  **Installation des dépendances (si ce n'est pas déjà fait) :**
    ```bash
    pip install requests python-dotenv
    ```

2.  **Configuration des variables d'environnement :**
    Créez un fichier `.env` à la racine de votre projet (ou dans un répertoire accessible par le script) et définissez-y les variables. Vous pouvez aussi les exporter directement dans votre shell.

    Exemple de fichier `.env` :
    ```dotenv
    VECTOR_DB_ENDPOINT=http://localhost:8686/api
    VECTOR_DB_API_KEY=your_vector_db_secret_key
    VECTOR_DB_COLLECTION_NAME=my_documents
    VECTOR_DB_MIN_VECTORS=500

    LLM_API_ENDPOINT=https://api.openai.com/v1/chat/completions
    LLM_API_KEY=sk-your_openai_api_key
    ```
    *Assurez-vous de remplacer les valeurs par vos informations réelles.*

3.  **Exécution du script :**
    Naviguez jusqu'au répertoire contenant le script `scripts/check_rag_status.py` et exécutez-le. Si `python-dotenv` est utilisé dans le script, il chargera automatiquement les variables du fichier `.env`.

    ```bash
    python scripts/check_rag_status.py
    ```

4.  **Exemple de sortie (succès) :**
    ```
    INFO:root:Chargement des variables d'environnement...
    INFO:root:Configuration chargée.
    INFO:root:Vérification de la santé de la base de données vectorielle (http://localhost:8686/api)...
    INFO:root:Base de données vectorielle OK. (Temps de réponse: 50ms)
    INFO:root:Vérification de la santé de l'API LLM (https://api.openai.com/v1/chat/completions)...
    INFO:root:API LLM OK. (Temps de réponse: 250ms)
    INFO:root:Vérification de l'intégrité de l'index RAG 'my_documents'...
    INFO:root:Collection 'my_documents' trouvée avec 523 vecteurs. (Minimum requis: 500)
    INFO:root:Intégrité de l'index RAG OK.
    INFO:root:-----------------------------------------------------
    INFO:root:STATUT GLOBAL DU SYSTÈME RAG : SAIN
    INFO:root:Toutes les vérifications sont passées avec succès.
    INFO:root:-----------------------------------------------------
    ```

5.  **Exemple de sortie (échec) :**
    ```
    INFO:root:Chargement des variables d'environnement...
    INFO:root:Configuration chargée.
    INFO:root:Vérification de la santé de la base de données vectorielle (http://localhost:8686/api)...
    ERROR:root:Erreur lors de la connexion à la base de données vectorielle: Échec de la connexion à l'hôte 'localhost'.
    ERROR:root:Base de données vectorielle HORS LIGNE.
    INFO:root:Vérification de la santé de l'API LLM (https://api.openai.com/v1/chat/completions)...
    INFO:root:API LLM OK. (Temps de réponse: 260ms)
    INFO:root:Vérification de l'intégrité de l'index RAG 'my_documents'...
    INFO:root:Collection 'my_documents' trouvée avec 450 vecteurs. (Minimum requis: 500)
    WARNING:root:Nombre de vecteurs inférieur au seuil minimum.
    ERROR:root:Intégrité de l'index RAG ÉCHOUÉE.
    INFO:root:-----------------------------------------------------
    ERROR:root:STATUT GLOBAL DU SYSTÈME RAG : DÉGRADÉ
    ERROR:root:Certaines vérifications ont échoué. Veuillez consulter les logs ci-dessus.
    INFO:root:-----------------------------------------------------
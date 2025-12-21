# Documentation Technique : `features/github.py`

## Description concise

Ce module fournit des fonctionnalités pour interagir avec l'API GitHub, permettant notamment de récupérer le contenu de dépôts distants pour analyse, ainsi que de pousser des fichiers et de créer des branches et des Pull Requests. Il intègre une gestion robuste des requêtes réseau avec des stratégies de retry et gère l'authentification via un token GitHub.

## Dépendances

*   `requests`: Pour effectuer des requêtes HTTP.
*   `logging`: Pour l'enregistrement des événements.
*   `base64`: Pour l'encodage/décodage de contenu.
*   `re`: Pour l'utilisation d'expressions régulières.
*   `time`: Pour les pauses dans l'exécution.
*   `os`: Pour les opérations sur le système de fichiers (utilisé indirectement par `os.path.basename`).
*   `json`: Pour la manipulation de données JSON.
*   `requests.adapters.HTTPAdapter`: Pour personnaliser les adapters de session `requests`.
*   `urllib3.util.retry.Retry`: Pour implémenter une stratégie de retry.
*   `config`: Module local pour charger les configurations (`get_logger`, `load_app_settings`, `SUPPORTED_FILE_EXTENSIONS`).
*   `features.Decorators.trace_action`: Décorateur pour tracer les actions (probablement pour le logging ou le monitoring).

---

## Classes & Fonctions

### Constantes Globales

*   `GITHUB_API_BASE`: URL de base de l'API GitHub (`https://api.github.com`).
*   `MAX_FILE_SIZE_GITHUB`: Taille maximale de fichier autorisée pour le téléchargement (1 Mo).
*   `IGNORED_EXTENSIONS_GITHUB`: Tuple d'extensions de fichiers à ignorer lors de la récupération du contenu.
*   `IGNORED_FILES_GITHUB`: Tuple de noms de fichiers spécifiques à ignorer.
*   `IGNORED_DIRS_GITHUB`: Tuple de noms de répertoires à ignorer.

### Fonction : `_create_session()`

*   **Signature :** `_create_session()`
*   **Arguments :** Aucun.
*   **Retour :** `requests.Session` - Une instance de session `requests` configurée avec une stratégie de retry.
*   **Logique interne :**
    1.  Crée une nouvelle instance de `requests.Session`.
    2.  Définit une stratégie de `Retry` :
        *   Nombre total de tentatives : 3.
        *   Facteur de délai (`backoff_factor`) : 1 seconde (les délais seront 1s, 2s, 4s...).
        *   Codes d'état HTTP pour lesquels retenter : 429 (Rate Limit), 500, 502, 503, 504 (erreurs serveur).
        *   Méthodes HTTP autorisées pour le retry : HEAD, GET, PUT, POST, DELETE.
    3.  Crée un `HTTPAdapter` avec la stratégie de retry définie.
    4.  Monte cet adapter sur la session pour les URLs HTTPS.
    5.  Retourne la session configurée.
*   **Note :** Cette fonction est décorée avec `@trace_action(source="github")`.

### Variable Globale : `SESSION`

*   Une instance de session `requests` créée par `_create_session()`, utilisée pour toutes les interactions avec l'API GitHub.

### Fonction : `_get_auth_headers()`

*   **Signature :** `_get_auth_headers()`
*   **Arguments :** Aucun.
*   **Retour :** `dict` - Un dictionnaire contenant les headers d'authentification et d'acceptation pour l'API GitHub.
*   **Logique interne :**
    1.  Charge les paramètres de l'application en utilisant `load_app_settings()`.
    2.  Tente de récupérer le `github_token` soit directement dans les paramètres principaux, soit dans `general_settings`.
    3.  Initialise un dictionnaire `headers` avec les valeurs par défaut pour `Accept` et `X-GitHub-Api-Version`.
    4.  Si un `token` est trouvé et n'est pas vide :
        *   Ajoute l'en-tête `Authorization` avec le token au format `Bearer <token>`.
    5.  Sinon, enregistre un avertissement indiquant que le mode lecture seule est actif en raison de l'absence de token.
    6.  Retourne le dictionnaire `headers`.
*   **Note :** Cette fonction est décorée avec `@trace_action(source="github")`.

### Fonction : `_parse_github_url(url)`

*   **Signature :** `_parse_github_url(url: str)`
*   **Arguments :**
    *   `url` (`str`): L'URL du dépôt GitHub.
*   **Retour :** `str | None` - Le slug du dépôt (format "user/repo") s'il est trouvé, sinon `None`.
*   **Logique interne :**
    1.  Utilise une expression régulière pour rechercher le motif `github.com/` suivi d'un groupe capturant `([^/]+/[^/]+)`.
    2.  Si une correspondance est trouvée :
        *   Extrait le groupe capturant (qui est le slug "user/repo").
        *   Supprime l'extension `.git` si elle est présente à la fin du slug.
        *   Retourne le slug nettoyé.
    3.  Sinon, retourne `None`.
*   **Note :** Cette fonction est décorée avec `@trace_action(source="github")`.

### Fonction : `_is_relevant_file(file_path)`

*   **Signature :** `_is_relevant_file(file_path: str)`
*   **Arguments :**
    *   `file_path` (`str`): Le chemin complet du fichier dans le dépôt.
*   **Retour :** `bool` - `True` si le fichier est pertinent pour l'analyse, `False` sinon.
*   **Logique interne :**
    1.  Extrait le nom de base du fichier.
    2.  Vérifie si le chemin du fichier commence par l'un des répertoires ignorés (`IGNORED_DIRS_GITHUB`). Si oui, retourne `False`.
    3.  Vérifie si le nom du fichier est dans la liste des fichiers ignorés (`IGNORED_FILES_GITHUB`). Si oui, retourne `False`.
    4.  Vérifie si l'extension du fichier (en minuscules) est dans la liste des extensions ignorées (`IGNORED_EXTENSIONS_GITHUB`). Si oui, retourne `False`.
    5.  Si `SUPPORTED_FILE_EXTENSIONS` est défini (pas `None` ou vide) :
        *   Vérifie si le chemin du fichier (en minuscules) se termine par l'une des extensions supportées. Retourne le résultat de cette vérification.
    6.  Si `SUPPORTED_FILE_EXTENSIONS` n'est pas défini, le fichier est considéré comme pertinent (sauf s'il a été filtré par les étapes précédentes).
*   **Note :** Cette fonction est décorée avec `@trace_action(source="github")`.

### Fonction : `_fetch_tree_internal(repo_slug, branch, result_queue)`

*   **Signature :** `_fetch_tree_internal(repo_slug: str, branch: str, result_queue: queue.Queue | None)`
*   **Arguments :**
    *   `repo_slug` (`str`): Le slug du dépôt (user/repo).
    *   `branch` (`str`): Le nom de la branche à inspecter.
    *   `result_queue` (`queue.Queue | None`): Une file d'attente optionnelle pour envoyer des messages d'état ou d'erreur.
*   **Retour :** `list | None` - Une liste des éléments de l'arborescence (dictionnaires) si succès, sinon `None`.
*   **Logique interne :**
    1.  Construit l'URL de l'API GitHub pour obtenir l'arbre du dépôt avec `recursive=1`.
    2.  Utilise `SESSION.get` pour effectuer la requête, en passant les headers obtenus par `_get_auth_headers()` et un timeout de 15 secondes.
    3.  Lance une exception `HTTPError` pour les codes d'erreur HTTP.
    4.  Si la réponse est OK (200), retourne la liste des éléments de l'arbre (`tree`).
    5.  Gère les exceptions :
        *   `requests.HTTPError` : Enregistre un avertissement si le code est 404 (branche introuvable), sinon enregistre une erreur. Si `result_queue` est fourni, ajoute un message d'erreur.
        *   Autres `Exception` : Enregistre une erreur de connexion.
    6.  Retourne `None` en cas d'erreur.
*   **Note :** Cette fonction est décorée avec `@trace_action(source="github")`.

### Fonction : `_fetch_file_content_internal(url)`

*   **Signature :** `_fetch_file_content_internal(url: str)`
*   **Arguments :**
    *   `url` (`str`): L'URL de l'API GitHub pour obtenir le contenu d'un blob (fichier).
*   **Retour :** `str | None` - Le contenu décodé du fichier s'il est trouvé et lisible, sinon `None`.
*   **Logique interne :**
    1.  Utilise `SESSION.get` pour effectuer la requête vers l'URL du blob avec les headers d'authentification et un timeout de 10 secondes.
    2.  Lance une exception `HTTPError` pour les codes d'erreur HTTP.
    3.  Si la réponse est OK (200) :
        *   Récupère les données JSON.
        *   Si l'encodage est `base64` et qu'il y a du contenu :
            *   Décode le contenu Base64 en UTF-8.
            *   Retourne le contenu décodé.
    4.  Si une exception se produit (erreur HTTP, JSON invalide, contenu manquant, etc.), enregistre un avertissement et retourne `None`.
*   **Note :** Cette fonction est décorée avec `@trace_action(source="github")`.

### Fonction : `get_repo_contents_for_analysis(repo_url, result_queue)`

*   **Signature :** `get_repo_contents_for_analysis(repo_url: str, result_queue: queue.Queue | None)`
*   **Arguments :**
    *   `repo_url` (`str`): L'URL du dépôt GitHub.
    *   `result_queue` (`queue.Queue | None`): Une file d'attente optionnelle pour les mises à jour UI.
*   **Retour :** `tuple[dict | None, str | None]` - Un tuple contenant :
    *   Un dictionnaire `content_map` (chemin du fichier -> contenu) si succès, sinon `None`.
    *   Un message d'erreur (`str`) si échec, sinon `None`.
*   **Logique interne :**
    1.  Extrait le `repo_slug` de l'URL en utilisant `_parse_github_url`. Si invalide, retourne `None, "URL GitHub invalide."`.
    2.  Si `result_queue` est fourni, envoie un message de connexion.
    3.  Appelle `_fetch_tree_internal` pour la branche `main`. Si cela échoue, tente avec la branche `master`.
    4.  Si l'arborescence ne peut être récupérée, retourne `None` avec un message d'erreur approprié.
    5.  Filtre les éléments de l'arbre pour ne garder que les blobs (`type == "blob"`) dont la taille est inférieure à `MAX_FILE_SIZE_GITHUB` et qui sont jugés pertinents par `_is_relevant_file`.
    6.  Si aucun fichier pertinent n'est trouvé, retourne `None` avec un message.
    7.  Si `result_queue` est fourni, envoie un message indiquant le nombre de fichiers à télécharger.
    8.  Initialise un dictionnaire `content_map` vide.
    9.  Itère sur la liste des fichiers à télécharger :
        *   Si `result_queue` est fourni et que l'index est un multiple de 5, envoie une mise à jour du statut avec le chemin du fichier actuel.
        *   Appelle `_fetch_file_content_internal` pour obtenir le contenu du fichier.
        *   Si le contenu est obtenu, l'ajoute à `content_map` avec son chemin comme clé.
        *   Introduit une petite pause (`time.sleep(0.02)`) pour être "gentil" avec l'API.
    10. Retourne `content_map` et `None` (pas d'erreur).
*   **Note :** Cette fonction est décorée avec `@trace_action(source="github")`.

### Fonction : `get_file_sha(repo_slug, file_path, branch)`

*   **Signature :** `get_file_sha(repo_slug: str, file_path: str, branch: str = "main")`
*   **Arguments :**
    *   `repo_slug` (`str`): Le slug du dépôt (user/repo).
    *   `file_path` (`str`): Le chemin du fichier dans le dépôt.
    *   `branch` (`str`, optionnel, défaut `"main"`): Le nom de la branche.
*   **Retour :** `str | None` - Le SHA du fichier s'il existe, sinon `None`.
*   **Logique interne :**
    1.  Construit l'URL de l'API GitHub pour accéder aux informations du contenu d'un fichier sur une branche spécifique.
    2.  Effectue une requête GET en utilisant `SESSION`, les headers d'authentification et un timeout de 5 secondes.
    3.  Si la réponse a un statut 200 (OK), retourne la valeur du champ `sha` du JSON de réponse.
    4.  Sinon (fichier non trouvé, erreur, etc.), retourne `None`.
    5.  Gère les exceptions en retournant `None`.
*   **Note :** Cette fonction est décorée avec `@trace_action(source="github")`.

### Fonction : `create_branch(repo_slug, new_branch, base_branch)`

*   **Signature :** `create_branch(repo_slug: str, new_branch: str, base_branch: str = "main")`
*   **Arguments :**
    *   `repo_slug` (`str`): Le slug du dépôt (user/repo).
    *   `new_branch` (`str`): Le nom de la nouvelle branche à créer.
    *   `base_branch` (`str`, optionnel, défaut `"main"`): Le nom de la branche de base à partir de laquelle créer la nouvelle branche.
*   **Retour :** `tuple[bool, str]` - Un tuple indiquant le succès (`True` ou `False`) et un message descriptif.
*   **Logique interne :**
    1.  **Étape 1:** Récupère le SHA du dernier commit de la `base_branch` via l'API `GET /repos/{owner}/{repo}/git/ref/heads/{branch}`.
        *   Si une erreur se produit lors de cette étape, retourne `False` avec un message d'erreur.
    2.  **Étape 2:** Construit le payload pour créer une nouvelle référence (branche) en utilisant le SHA obtenu et le nom de la `new_branch` préfixé par `refs/heads/`.
    3.  Effectue une requête POST vers `/repos/{owner}/{repo}/git/refs` avec le payload et les headers d'authentification.
    4.  Gère les codes de réponse :
        *   201 (Créé) ou 200 (OK) : Succès, retourne `True` et un message de succès.
        *   422 (Unprocessable Entity) : Indique souvent que la branche existe déjà. Retourne `True` et un message approprié.
        *   Autre code d'erreur : Échec, retourne `False` et le texte de la réponse.
    5.  Gère les exceptions réseau en retournant `False` et le message d'erreur.
*   **Note :** Cette fonction est décorée avec `@trace_action(source="github")`.

### Fonction : `push_file_to_repo(repo_slug, file_path, content, commit_message, branch)`

*   **Signature :** `push_file_to_repo(repo_slug: str, file_path: str, content: str, commit_message: str, branch: str = "main")`
*   **Arguments :**
    *   `repo_slug` (`str`): Le slug du dépôt (user/repo).
    *   `file_path` (`str`): Le chemin du fichier dans le dépôt.
    *   `content` (`str`): Le contenu du fichier à pousser.
    *   `commit_message` (`str`): Le message du commit.
    *   `branch` (`str`, optionnel, défaut `"main"`): Le nom de la branche cible.
*   **Retour :** `tuple[bool, str]` - Un tuple indiquant le succès (`True` ou `False`) et un message descriptif (URL du fichier mis à jour ou message d'erreur).
*   **Logique interne :**
    1.  Construit l'URL de l'API GitHub pour le contenu du fichier.
    2.  Récupère les headers d'authentification.
    3.  Appelle `get_file_sha` pour vérifier si le fichier existe déjà sur la branche spécifiée. Stocke le SHA s'il est trouvé.
    4.  Encode le `content` en Base64 UTF-8.
    5.  Prépare le `payload` pour la requête PUT/POST : `message`, `content` (encodé), `branch`.
    6.  Si un `sha` a été trouvé (le fichier existe), ajoute `sha` au payload pour indiquer une mise à jour. Log une information indiquant la mise à jour.
    7.  Sinon (le fichier n'existe pas), log une information indiquant la création.
    8.  Effectue une requête `PUT` vers l'URL du contenu du fichier avec le payload et les headers.
    9.  Gère les codes de réponse :
        *   200 (OK) ou 201 (Created) : Succès. Retourne `True` et l'URL du fichier mis à jour ou créé.
        *   Autre code d'erreur : Échec. Retourne `False` et le texte de la réponse d'erreur.
    10. Gère les exceptions réseau en retournant `False` et le message d'erreur.
*   **Note :** Cette fonction est décorée avec `@trace_action(source="github")`.

### Fonction : `create_pull_request(repo_slug, title, body, head_branch, base_branch)`

*   **Signature :** `create_pull_request(repo_slug: str, title: str, body: str, head_branch: str, base_branch: str = "main")`
*   **Arguments :**
    *   `repo_slug` (`str`): Le slug du dépôt (user/repo).
    *   `title` (`str`): Le titre de la Pull Request.
    *   `body` (`str`): Le corps/description de la Pull Request.
    *   `head_branch` (`str`): Le nom de la branche qui contient les changements (branche "head").
    *   `base_branch` (`str`, optionnel, défaut `"main"`): Le nom de la branche cible des changements (branche "base").
*   **Retour :** `tuple[bool, str]` - Un tuple indiquant le succès (`True` ou `False`) et un message descriptif (URL de la PR créée ou message d'erreur).
*   **Logique interne :**
    1.  Construit l'URL de l'API GitHub pour créer une Pull Request.
    2.  Prépare le `payload` avec `title`, `body`, `head` (la branche source) et `base` (la branche cible).
    3.  Effectue une requête `POST` vers l'URL des Pull Requests avec le payload et les headers d'authentification.
    4.  Gère les codes de réponse :
        *   201 (Created) : Succès. Retourne `True` et l'URL de la PR créée.
        *   422 (Unprocessable Entity) : Peut indiquer que la PR existe déjà, qu'il n'y a pas de différences entre les branches, ou une autre erreur de validation. Retourne `False` et un message d'erreur.
        *   Autre code d'erreur : Échec. Retourne `False` et le texte de la réponse d'erreur.
    5.  Gère les exceptions réseau en retournant `False` et le message d'erreur.
*   **Note :** Cette fonction est décorée avec `@trace_action(source="github")`.

---

## Exemple d'usage

```python
# Exemple hypothétique d'utilisation pour récupérer et analyser un dépôt

from features import github # Assumant que ce fichier est dans le package 'features'
from queue import Queue

# 1. Récupérer le contenu d'un dépôt GitHub pour analyse
repo_url = "https://github.com/octocat/Spoon-Knife"
result_q = Queue() # Pour les mises à jour UI (optionnel)

print(f"Récupération du contenu de {repo_url}...")
content_map, error = github.get_repo_contents_for_analysis(repo_url, result_q)

if error:
    print(f"Erreur lors de la récupération du dépôt : {error}")
else:
    print(f"Contenu récupéré pour {len(content_map)} fichiers.")
    # Supposons qu'on veuille analyser le fichier README.md
    readme_content = content_map.get("README.md")
    if readme_content:
        print("\n--- Contenu de README.md ---")
        print(readme_content[:500] + "...") # Afficher les 500 premiers caractères
    else:
        print("README.md non trouvé ou ignoré.")

    # 2. Exemple de push d'un fichier (nécessite un token configuré et des droits d'écriture)
    # NOTE: Ceci est un exemple et doit être utilisé avec prudence.
    #       Il est recommandé de travailler sur une branche de développement.
    # target_repo_slug = "votre_utilisateur/votre_repo_forké" # Adaptez ceci
    # file_to_push_path = "mon_nouveau_fichier.txt"
    # file_content = "Ceci est le contenu de mon fichier.\n"
    # commit_msg = "Ajout de mon_nouveau_fichier.txt via l'API"
    # target_branch = "feature/mon-ajout"

    # print(f"\nTentative de création de la branche {target_branch}...")
    # created, msg = github.create_branch(target_repo_slug, target_branch)
    # print(f"Résultat création branche: {created} - {msg}")

    # if created or "existe déjà" in msg: # Continuer si créée ou si elle existe déjà
    #     print(f"Tentative de push du fichier {file_to_push_path} sur la branche {target_branch}...")
    #     success, msg = github.push_file_to_repo(
    #         target_repo_slug,
    #         file_to_push_path,
    #         file_content,
    #         commit_msg,
    #         branch=target_branch
    #     )
    #     print(f"Résultat push fichier: {success} - {msg}")

    #     if success:
    #         print(f"Tentative de création de Pull Request vers 'main'...")
    #         pr_title = "Ajout d'un fichier de test"
    #         pr_body = "Ceci est une PR générée automatiquement pour tester le push."
    #         pr_success, pr_msg = github.create_pull_request(
    #             target_repo_slug,
    #             pr_title,
    #             pr_body,
    #             head_branch=target_branch,
    #             base_branch="main" # Ou la branche principale de votre repo
    #         )
    #         print(f"Résultat création PR: {pr_success} - {pr_msg}")

# Afficher les messages de la queue (pour simulation UI)
# while not result_q.empty():
#     print(f"Queue message: {result_q.get()}")
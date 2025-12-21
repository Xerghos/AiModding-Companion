import requests
import logging
import base64
import re
import time
import os
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import get_logger, load_app_settings, SUPPORTED_FILE_EXTENSIONS
from features.Decorators import trace_action

log = get_logger(__name__)

# --- Constantes GitHub ---
GITHUB_API_BASE = "https://api.github.com"
MAX_FILE_SIZE_GITHUB = 1024 * 1024  # 1 Mo

# --- Listes d'exclusion (Lecture) ---
IGNORED_EXTENSIONS_GITHUB = (
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.bmp',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.gz', '.tar', '.rar', '.7z',
    '.bin', '.exe', '.dll', '.so', '.lib',
    '.mp3', '.mp4', '.wav', '.avi', '.mkv',
    '.woff', '.woff2', '.eot', '.ttf', '.otf',
    '.jar', '.war', '.class'
)
IGNORED_FILES_GITHUB = (
    'package-lock.json', 'yarn.lock', 'composer.lock', 'Gemfile.lock'
)
IGNORED_DIRS_GITHUB = (
    '.git', '.github', 'node_modules', '__pycache__', 
    'venv', '.venv', 'dist', 'build', 'target', 'docs', 'assets'
)

# --- [NOUVEAU Phase 8.1] Session Robuste avec Retry ---
@trace_action(source="github")
def _create_session():
    """Crée une session requests avec stratégie de retry automatique."""
    session = requests.Session()
    # Retry sur : 429 (Rate Limit), 500/502/503/504 (Erreurs Serveur)
    retries = Retry(
        total=3,
        backoff_factor=1, # Attente : 1s, 2s, 4s...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "PUT", "POST", "DELETE"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    return session

SESSION = _create_session()

@trace_action(source="github")
def _get_auth_headers():
    """
    Génère les headers avec le token GitHub s'il est présent dans les settings.
    Permet de passer de 60 req/h à 5000 req/h et d'écrire sur les repos.
    """
    settings = load_app_settings()
    # On cherche 'github_token' à la racine ou dans 'general_settings' par sécurité
    token = settings.get("github_token") or settings.get("general_settings", {}).get("github_token")
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    if token and token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
        # log.debug("Authentification GitHub active.") 
    else:
        log.warning("Aucun token GitHub trouvé. Mode lecture seule (Rate Limit restreint).")
        
    return headers

# --- Fonctions Utilitaires ---

@trace_action(source="github")
def _parse_github_url(url):
    """Extrait 'user/repo' d'une URL."""
    match = re.search(r"github\.com/([^/]+/[^/]+)", url)
    if match:
        slug = match.group(1)
        return slug[:-4] if slug.endswith(".git") else slug
    return None

@trace_action(source="github")
def _is_relevant_file(file_path):
    """Filtre les fichiers binaires ou ignorés."""
    name = os.path.basename(file_path)
    if any(file_path.startswith(f"{d}/") for d in IGNORED_DIRS_GITHUB): return False
    if name in IGNORED_FILES_GITHUB: return False
    if file_path.lower().endswith(IGNORED_EXTENSIONS_GITHUB): return False
    if SUPPORTED_FILE_EXTENSIONS:
        return file_path.lower().endswith(SUPPORTED_FILE_EXTENSIONS)
    return True

# --- Fonctions de LECTURE (GET) ---

@trace_action(source="github")
def _fetch_tree_internal(repo_slug, branch, result_queue):
    url = f"{GITHUB_API_BASE}/repos/{repo_slug}/git/trees/{branch}?recursive=1"
    try:
        # Utilisation de SESSION et _get_auth_headers
        resp = SESSION.get(url, headers=_get_auth_headers(), timeout=15)
        resp.raise_for_status()
        return resp.json().get("tree", [])
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            log.warning(f"Branche '{branch}' introuvable sur {repo_slug}.")
        else:
            log.error(f"Erreur API Tree ({repo_slug}): {e}")
            if result_queue: result_queue.put({"type": "error", "text": f"Erreur GitHub: {e}"})
        return None
    except Exception as e:
        log.error(f"Erreur connexion GitHub: {e}")
        return None

@trace_action(source="github")
def _fetch_file_content_internal(url):
    try:
        # L'URL fournie par l'API Tree est une URL blob API, pas raw.
        resp = SESSION.get(url, headers=_get_auth_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("encoding") == "base64" and data.get("content"):
            return base64.b64decode(data["content"]).decode('utf-8')
        return None
    except Exception as e:
        log.warning(f"Impossible de lire le blob {url}: {e}")
        return None

@trace_action(source="github")
def get_repo_contents_for_analysis(repo_url, result_queue):
    """
    Récupère l'intégralité d'un dépôt (filtré) pour analyse.
    """
    repo_slug = _parse_github_url(repo_url)
    if not repo_slug: return None, "URL GitHub invalide."

    if result_queue:
        result_queue.put({"type": "ui_update", "widget": "message", "text": f"--- Connexion GitHub ({repo_slug})... ---"})

    tree = _fetch_tree_internal(repo_slug, "main", result_queue)
    if not tree: tree = _fetch_tree_internal(repo_slug, "master", result_queue)
    
    if not tree: return None, "Impossible d'accéder à l'arborescence (Dépôt privé sans token ? Branche inconnue ?)."

    files_to_dl = [item for item in tree if item["type"] == "blob" and item["size"] < MAX_FILE_SIZE_GITHUB and _is_relevant_file(item["path"])]
    
    if not files_to_dl: return None, "Aucun fichier pertinent trouvé."
    
    if result_queue:
        result_queue.put({"type": "ui_update", "widget": "message", "text": f"--- Téléchargement de {len(files_to_dl)} fichiers... ---"})

    content_map = {}
    for i, item in enumerate(files_to_dl):
        if i % 5 == 0 and result_queue:
             result_queue.put({"type": "ui_update", "widget": "status", "text": f"DL GitHub: {item['path']}"})
        
        c = _fetch_file_content_internal(item["url"])
        if c: content_map[item["path"]] = c
        time.sleep(0.02) # Gentillesse

    return content_map, None

# --- [NOUVEAU Phase 8.2] Fonctions d'ÉCRITURE (PUT/POST) ---

@trace_action(source="github")
def get_file_sha(repo_slug, file_path, branch="main"):
    """Récupère le SHA d'un fichier s'il existe (nécessaire pour l'update)."""
    url = f"{GITHUB_API_BASE}/repos/{repo_slug}/contents/{file_path}?ref={branch}"
    try:
        resp = SESSION.get(url, headers=_get_auth_headers(), timeout=5)
        if resp.status_code == 200:
            return resp.json().get("sha")
        return None # Fichier n'existe pas
    except Exception:
        return None

@trace_action(source="github")
def create_branch(repo_slug, new_branch, base_branch="main"):
    """Crée une nouvelle branche à partir de base_branch."""
    # 1. Récupérer le SHA du dernier commit de base_branch
    url_ref = f"{GITHUB_API_BASE}/repos/{repo_slug}/git/ref/heads/{base_branch}"
    try:
        resp = SESSION.get(url_ref, headers=_get_auth_headers())
        resp.raise_for_status()
        sha_base = resp.json()["object"]["sha"]
    except Exception as e:
        return False, f"Impossible de trouver la branche base '{base_branch}': {e}"

    # 2. Créer la ref pour la nouvelle branche
    url_create = f"{GITHUB_API_BASE}/repos/{repo_slug}/git/refs"
    payload = {
        "ref": f"refs/heads/{new_branch}",
        "sha": sha_base
    }
    
    try:
        resp = SESSION.post(url_create, headers=_get_auth_headers(), json=payload)
        if resp.status_code in [201, 200]:
            return True, f"Branche '{new_branch}' créée."
        elif resp.status_code == 422:
            return True, f"La branche '{new_branch}' existe déjà."
        else:
            return False, f"Erreur création branche: {resp.text}"
    except Exception as e:
        return False, f"Exception création branche: {e}"

@trace_action(source="github")
def push_file_to_repo(repo_slug, file_path, content, commit_message, branch="main"):
    """
    Push un fichier vers le dépôt (Création ou Update).
    Gère l'encodage Base64 et le SHA.
    """
    url = f"{GITHUB_API_BASE}/repos/{repo_slug}/contents/{file_path}"
    headers = _get_auth_headers()
    
    # 1. Vérifier si le fichier existe pour obtenir le SHA (Update vs Create)
    sha = get_file_sha(repo_slug, file_path, branch)
    
    # 2. Préparer le contenu
    content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": commit_message,
        "content": content_b64,
        "branch": branch
    }
    if sha:
        payload["sha"] = sha
        log.info(f"Mise à jour du fichier existant {file_path} (SHA: {sha})")
    else:
        log.info(f"Création du nouveau fichier {file_path}")
        pass # SECU: Pour ne pas casser l'indentation si le log est supprimé

    # 3. Envoyer la requête
    try:
        resp = SESSION.put(url, headers=headers, json=payload)
        if resp.status_code in [200, 201]:
            return True, f"Fichier pushé avec succès : {resp.json().get('content', {}).get('html_url')}"
        else:
            return False, f"Échec du push ({resp.status_code}): {resp.text}"
    except Exception as e:
        return False, f"Erreur réseau lors du push: {e}"

@trace_action(source="github")
def create_pull_request(repo_slug, title, body, head_branch, base_branch="main"):
    """Crée une Pull Request."""
    url = f"{GITHUB_API_BASE}/repos/{repo_slug}/pulls"
    payload = {
        "title": title,
        "body": body,
        "head": head_branch,
        "base": base_branch
    }
    
    try:
        resp = SESSION.post(url, headers=_get_auth_headers(), json=payload)
        if resp.status_code == 201:
            return True, f"PR Créée : {resp.json().get('html_url')}"
        elif resp.status_code == 422:
            return False, f"Erreur PR (Existe déjà ? Pas de diff ?): {resp.text}"
        else:
            return False, f"Erreur création PR ({resp.status_code}): {resp.text}"
    except Exception as e:
        return False, f"Exception création PR: {e}"
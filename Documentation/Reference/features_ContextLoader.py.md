# Documentation Technique : `ContextLoader.py`

## 1. En-tête

### Titre
ContextLoader

### Description Concise
Ce module est responsable du chargement et de la fourniture de contextes architecturaux spécifiques à partir de fichiers de mapping. Il permet de charger le contenu de fichiers définis comme "primaires" pour un domaine architectural donné, ainsi que de lister les fichiers "liés". Il est conçu pour aider une IA à comprendre l'architecture d'un système en lui fournissant des extraits de code pertinents.

### Dépendances
- `json`: Pour la lecture des fichiers de mapping au format JSON.
- `os`: Pour la vérification de l'existence des fichiers.
- `logging`: Pour la gestion des logs d'erreurs et d'informations.
- `config.get_path`: Fonction pour obtenir le chemin absolu d'un fichier de configuration.
- `config.get_logger`: Fonction pour obtenir un logger unifié.
- `features.Decorators.trace_action`: Décorateur pour tracer les actions exécutées.

## 2. Classes & Fonctions

### Fonction : `_load_architecture_map()`
- **Signature :** `_load_architecture_map() -> dict`
- **Arguments :** Aucune.
- **Retour :**
    - `dict`: Un dictionnaire contenant les données du fichier `architecture_map.json`. Si le fichier est introuvable ou s'il y a une erreur de lecture, un dictionnaire vide `{}` est retourné. Si le fichier utilise le nouveau format ("domains"), seule la partie `domains` est retournée.
- **Logique interne :**
    1. Définit le chemin du fichier de mapping (`ARCHITECTURE_MAP_FILE`).
    2. Obtient le chemin absolu du fichier de mapping via `get_path()`.
    3. Vérifie si le fichier existe. Si non, enregistre une erreur et retourne `{}`.
    4. Ouvre le fichier en mode lecture avec l'encodage UTF-8.
    5. Charge le contenu JSON du fichier.
    6. Gère une correction pour le nouveau format du fichier de mapping (introduit dans V18) : si la clé "domains" existe, retourne la valeur associée (qui est un dictionnaire des domaines). Sinon, retourne l'intégralité des données chargées (ancien format).
    7. En cas d'exception lors de la lecture ou du parsing JSON, enregistre une erreur et retourne `{}`.
- **Décorateurs :** `@trace_action(source="ContextLoader")`

### Fonction : `charger_contexte_domaine(domaine, session=None, action_log_path=None, result_queue=None, **kwargs)`
- **Signature :** `charger_contexte_domaine(domaine: str, session: Any = None, action_log_path: str = None, result_queue: Any = None, **kwargs: Any) -> str`
- **Arguments :**
    - `domaine` (`str`): Le nom du domaine architectural dont on souhaite charger le contexte.
    - `session` (`Any`, optionnel): Non utilisé dans la logique actuelle de cette fonction.
    - `action_log_path` (`str`, optionnel): Non utilisé dans la logique actuelle de cette fonction.
    - `result_queue` (`Any`, optionnel): Une file d'attente (queue) pour envoyer des mises à jour de l'interface utilisateur.
    - `**kwargs`: Arguments supplémentaires non utilisés actuellement.
- **Retour :**
    - `str`: Une chaîne de caractères formatée représentant le contexte architectural du domaine demandé. Cette chaîne inclut la description du domaine, le contenu des fichiers primaires (tronqué si très volumineux), et la liste des fichiers liés.
    - `str`: Si le domaine spécifié n'est pas trouvé dans la carte architecturale, une chaîne d'erreur indiquant le domaine inconnu et la liste des domaines disponibles est retournée.
- **Logique interne :**
    1. Charge la carte architecturale en appelant `_load_architecture_map()`.
    2. Vérifie si le `domaine` demandé existe comme clé dans `arch_map`. Si non, construit et retourne une chaîne d'erreur avec les domaines disponibles.
    3. Récupère les informations du domaine : `description`, `primary_files`, `related_files` à partir de `arch_map[domaine]`. Utilise des valeurs par défaut si certaines clés sont manquantes.
    4. Initialise une chaîne `context_report` avec un en-tête pour le domaine.
    5. Ajoute la description du domaine au rapport.
    6. Itère sur la liste `primary_files` :
        a. Construit le chemin absolu de chaque fichier.
        b. Vérifie l'existence du fichier.
        c. Si le fichier existe, l'ouvre, lit son contenu.
        d. Applique une troncature si le contenu dépasse 50 000 caractères.
        e. Ajoute le chemin du fichier et son contenu (ou un message d'erreur/troncature) au rapport.
        f. Compte le nombre de fichiers primaires chargés avec succès.
        g. En cas d'erreur de lecture, ajoute un message d'erreur au rapport.
        h. Si le fichier n'existe pas, ajoute un message "Introuvable" au rapport.
    7. Itère sur la liste `related_files` et ajoute chaque chemin de fichier lié au rapport sous forme de liste.
    8. Ajoute une section de fin au rapport, incluant le nombre total de fichiers primaires chargés.
    9. Si `result_queue` est fourni, envoie un message de mise à jour de l'interface utilisateur indiquant que le contexte a été chargé.
    10. Retourne la chaîne `context_report` complète.
- **Décorateurs :** `@trace_action(source="ContextLoader")`

## 3. Exemple d'usage

Cet exemple montre comment appeler la fonction `charger_contexte_domaine` pour un domaine spécifique et afficher le résultat.

```python
# Simulation des dépendances si elles ne sont pas disponibles dans l'environnement d'exécution
# Dans un vrai projet, ces imports seraient corrects.
class MockLogger:
    def error(self, msg):
        print(f"ERROR: {msg}")

def get_logger(name):
    return MockLogger()

def get_path(rel_path):
    # Retourne un chemin fictif pour l'exemple
    return f"/fake/path/to/{rel_path}"

def trace_action(source):
    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"--- Action tracée: {source} -> {func.__name__} ---")
            result = func(*args, **kwargs)
            print(f"--- Fin action tracée: {source} -> {func.__name__} ---")
            return result
        return wrapper
    return decorator

# Assurez-vous que ces imports sont corrects dans votre projet
import json
import os
import logging
from config import get_path, get_logger # Simulé ici
from features.Decorators import trace_action # Simulé ici

# Simuler le contenu du fichier architecture_map.json pour l'exemple
ARCHITECTURE_MAP_FILE = "config/architecture_map.json"
mock_arch_map_content = {
    "logging": {
        "description": "Gestion des logs de l'application.",
        "primary_files": ["src/logging_utils.py", "config/log_config.yaml"],
        "related_files": ["src/main.py", "tests/test_logging.py"]
    },
    "database": {
        "description": "Module d'interaction avec la base de données.",
        "primary_files": ["src/db_manager.py"],
        "related_files": ["src/models.py"]
    }
}

# Remplacer les fonctions réelles par leurs simulations pour l'exemple
# Dans votre projet, ces lignes ne sont pas nécessaires car les imports seraient valides.
log = get_logger("Features.ContextLoader")
_original_get_path = get_path
_original_open = open
_original_os_path_exists = os.path.exists

def mock_get_path(rel_path):
    if rel_path == ARCHITECTURE_MAP_FILE:
        return "fake_architecture_map.json"
    return _original_get_path(rel_path)

def mock_open(filename, mode='r', encoding='utf-8'):
    if filename == "fake_architecture_map.json" and mode == 'r':
        class MockFile:
            def __init__(self, content):
                self.content = content
                self.closed = False
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.closed = True
            def read(self):
                return json.dumps(mock_arch_map_content)
            def __iter__(self):
                 return iter(self.content.splitlines())
        return MockFile(json.dumps(mock_arch_map_content))
    elif filename.endswith(".py"): # Simuler la lecture d'un fichier primaire
         class MockFile:
            def __init__(self, content):
                self.content = content
                self.closed = False
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.closed = True
            def read(self):
                return f"# Contenu simulé du fichier {os.path.basename(filename)}\n{self.content}"
            def __iter__(self):
                 return iter(self.content.splitlines())
         return MockFile(f"def dummy_function(): pass # Fichier: {os.path.basename(filename)}")
    return _original_open(filename, mode, encoding)

def mock_os_path_exists(path):
    if path == "fake_architecture_map.json":
        return True
    if path.endswith(".py") or path.endswith(".yaml"):
        return True
    return _original_os_path_exists(path)

# Appliquer les mocks
os.path.exists = mock_os_path_exists
get_path = mock_get_path
open = mock_open


# --- Le code réel de ContextLoader (pour exécution avec les mocks) ---
@trace_action(source="ContextLoader")
def _load_architecture_map():
    """Charge le fichier de mapping architectural."""
    map_path = get_path(ARCHITECTURE_MAP_FILE)
    if not os.path.exists(map_path):
        log.error(f"Fichier de mapping introuvable : {map_path}")
        return {}
    
    try:
        with open(map_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "domains" in data:
                return data["domains"] 
            return data 
    except Exception as e:
        log.error(f"Erreur lecture mapping architecture : {e}")
        return {}

@trace_action(source="ContextLoader")
def charger_contexte_domaine(domaine, session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    [RENOMMÉ] Charge le contenu des fichiers liés à un domaine architectural spécifique.
    Permet à l'IA de récupérer un contexte ciblé et pertinent.
    """
    arch_map = _load_architecture_map()
    
    if domaine not in arch_map:
        domaines_dispo = ", ".join(arch_map.keys())
        return f"❌ Domaine '{domaine}' inconnu. Domaines disponibles : {domaines_dispo}"
    
    info_domaine = arch_map[domaine]
    description = info_domaine.get("description", "Pas de description.")
    primary_files = info_domaine.get("primary_files", [])
    related_files = info_domaine.get("related_files", [])
    
    context_report = f"=== CONTEXTE ARCHITECTURAL : {domaine.upper()} ===\n"
    context_report += f"Description : {description}\n\n"
    
    context_report += "--- FICHIERS PRIMAIRES (Cœur du domaine) ---\n"
    count_primary = 0
    for rel_path in primary_files:
        abs_path = get_path(rel_path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if len(content) > 50000:
                        content = content[:50000] + "\n... [TRONQUÉ > 50k chars] ..."
                    context_report += f"\n>>> FICHIER : {rel_path}\n{content}\n"
                    count_primary += 1
            except Exception as e:
                context_report += f"\n>>> FICHIER : {rel_path} (Erreur lecture: {e})\n"
        else:
             context_report += f"\n>>> FICHIER : {rel_path} (Introuvable)\n"

    context_report += "\n--- FICHIERS LIÉS (Dépendances / Utilisateurs) ---\n"
    for rel_path in related_files:
        context_report += f"- {rel_path}\n"
        
    context_report += f"\n=== FIN DU CONTEXTE ({count_primary} fichiers chargés) ==="
    
    if result_queue:
        result_queue.put({"type": "ui_update", "widget": "message", "text": f"📚 Contexte chargé : {domaine} ({count_primary} fichiers)"})
    
    return context_report

# --- Fin du code réel de ContextLoader ---

# Exécution de l'exemple
print("--- Début de l'exemple d'usage ---")
contexte_logging = charger_contexte_domaine("logging")
print(contexte_logging)

print("\n" + "="*40 + "\n")

contexte_db = charger_contexte_domaine("database")
print(contexte_db)

print("\n" + "="*40 + "\n")

contexte_inconnu = charger_contexte_domaine("security")
print(contexte_inconnu)

# Réinitialiser les mocks si nécessaire pour d'autres tests
os.path.exists = _original_os_path_exists
get_path = _original_get_path
open = _original_open

print("--- Fin de l'exemple d'usage ---")
# Documentation Technique - `config/utils.py`

## 1. En-tête

*   **Titre**: `config/utils.py` - Utilitaires de Gestion de Fichiers JSON
*   **Description concise**: Ce module fournit des fonctions utilitaires pour la lecture et l'écriture robuste de fichiers JSON, ainsi que des abstractions pour gérer spécifiquement les fichiers d'historique et de liens de contexte de l'application. Il gère les erreurs potentielles lors des opérations de fichier et de sérialisation/désérialisation.
*   **Dépendances**:
    *   `json`: Pour la sérialisation et désérialisation JSON.
    *   `os`: Pour les opérations sur le système de fichiers (vérification d'existence de fichier).
    *   `./paths`: Module interne fournissant la fonction `get_path` pour résoudre les chemins de fichiers par défaut.
    *   `./constants`: Module interne fournissant les constantes `HISTORY_FILE` et `CONTEXT_FILE`.

## 2. Classes & Fonctions

### `charger_json_robuste(file_path)`

Charge le contenu d'un fichier JSON de manière robuste, gérant les cas où le fichier n'existe pas ou contient des données invalides.

*   **Signature**:
    ```python
    def charger_json_robuste(file_path: str) -> list | dict
    ```
*   **Arguments**:
    *   `file_path` (`str`): Le chemin complet vers le fichier JSON à charger.
*   **Retours**:
    *   (`list` ou `dict`): Le contenu du fichier JSON si le fichier existe et peut être parsé correctement.
    *   (`list`): Une liste vide (`[]`) si le fichier n'existe pas, s'il y a une erreur de lecture ou de parsing JSON.
*   **Logique interne**:
    1.  Vérifie si le fichier spécifié par `file_path` existe.
    2.  Si le fichier existe, tente de l'ouvrir en mode lecture (`'r'`) avec l'encodage `utf-8`.
    3.  Tente de charger le contenu JSON en utilisant `json.load()`.
    4.  En cas d'erreur (par exemple, fichier corrompu, permissions insuffisantes), capture l'exception, imprime un message d'erreur sur la console et retourne une liste vide.
    5.  Si le fichier n'existe pas, retourne immédiatement une liste vide.

### `sauvegarder_json(file_path, data)`

Sauvegarde des données Python dans un fichier JSON, gérant les objets non sérialisables par défaut via un sérialiseur personnalisé.

*   **Signature**:
    ```python
    def sauvegarder_json(file_path: str, data: any) -> bool
    ```
*   **Arguments**:
    *   `file_path` (`str`): Le chemin complet vers le fichier JSON où sauvegarder les données. Le fichier sera créé ou écrasé.
    *   `data` (`any`): Les données Python (dictionnaires, listes, objets personnalisés) à sérialiser et sauvegarder.
*   **Retours**:
    *   (`bool`): `True` si la sauvegarde a été effectuée avec succès, `False` en cas d'erreur.
*   **Logique interne**:
    1.  Définit une fonction `default_serializer` interne pour gérer les objets non sérialisables par défaut par `json.dump`. Cette fonction essaie de convertir l'objet en dictionnaire via `to_dict()`, `to_json()`, ou son `__dict__`, ou le convertit en chaîne de caractères.
    2.  Tente d'ouvrir le fichier en mode écriture (`'w'`) avec l'encodage `utf-8`.
    3.  Utilise `json.dump()` pour écrire les données dans le fichier, avec une indentation de 2 espaces, `ensure_ascii=False` (pour permettre les caractères non-ASCII), et le `default_serializer` défini.
    4.  En cas d'erreur de sérialisation ou d'écriture, capture l'exception, imprime un message d'erreur sur la console et retourne `False`.
    5.  Si l'opération réussit, retourne `True`.

### `charger_historique_robuste_worker(file_path=None)`

Charge l'historique de l'application à partir d'un fichier JSON, en s'assurant que les données retournées sont une liste de dictionnaires.

*   **Signature**:
    ```python
    def charger_historique_robuste_worker(file_path: Optional[str] = None) -> list[dict]
    ```
*   **Arguments**:
    *   `file_path` (`Optional[str]`, optionnel): Chemin spécifique du fichier d'historique. Si `None`, le chemin par défaut est déterminé via `get_path(HISTORY_FILE)`.
*   **Retours**:
    *   (`list[dict]`): Une liste de dictionnaires représentant les entrées de l'historique. Retourne une liste vide si le fichier est manquant, invalide, ou ne contient pas une liste de dictionnaires.
*   **Logique interne**:
    1.  Détermine le chemin du fichier à utiliser : `file_path` si fourni, sinon `get_path(HISTORY_FILE)`.
    2.  Appelle `charger_json_robuste` avec le chemin déterminé.
    3.  Si les données chargées sont une liste, filtre cette liste pour ne retenir que les éléments qui sont des dictionnaires.
    4.  Si les données chargées ne sont pas une liste, retourne une liste vide.

### `sauvegarder_historique_worker(data, file_path=None)`

Sauvegarde les données de l'historique de l'application dans un fichier JSON.

*   **Signature**:
    ```python
    def sauvegarder_historique_worker(data: list, file_path: Optional[str] = None) -> None
    ```
*   **Arguments**:
    *   `data` (`list`): La liste des entrées d'historique à sauvegarder.
    *   `file_path` (`Optional[str]`, optionnel): Chemin spécifique du fichier d'historique. Si `None`, le chemin par défaut est déterminé via `get_path(HISTORY_FILE)`.
*   **Retours**:
    *   (`None`): Cette fonction ne retourne aucune valeur directement, mais la fonction sous-jacente `sauvegarder_json` retourne un booléen.
*   **Logique interne**:
    1.  Détermine le chemin du fichier à utiliser : `file_path` si fourni, sinon `get_path(HISTORY_FILE)`.
    2.  Appelle `sauvegarder_json` avec le chemin déterminé et les données fournies.

### `charger_liens_contexte_worker(file_path=None)`

Charge les liens de contexte de l'application à partir d'un fichier JSON.

*   **Signature**:
    ```python
    def charger_liens_contexte_worker(file_path: Optional[str] = None) -> list
    ```
*   **Arguments**:
    *   `file_path` (`Optional[str]`, optionnel): Chemin spécifique du fichier de contexte. Si `None`, le chemin par défaut est déterminé via `get_path(CONTEXT_FILE)`.
*   **Retours**:
    *   (`list`): Une liste représentant les liens de contexte. Retourne une liste vide si le fichier est manquant, invalide, ou ne contient pas une liste.
*   **Logique interne**:
    1.  Détermine le chemin du fichier à utiliser : `file_path` si fourni, sinon `get_path(CONTEXT_FILE)`.
    2.  Appelle `charger_json_robuste` avec le chemin déterminé.
    3.  Vérifie si les données chargées sont une instance de `list`. Si oui, retourne ces données ; sinon, retourne une liste vide.

### `sauvegarder_liens_contexte_worker(data, file_path=None)`

Sauvegarde les liens de contexte de l'application dans un fichier JSON.

*   **Signature**:
    ```python
    def sauvegarder_liens_contexte_worker(data: list, file_path: Optional[str] = None) -> bool
    ```
*   **Arguments**:
    *   `data` (`list`): La liste des liens de contexte à sauvegarder.
    *   `file_path` (`Optional[str]`, optionnel): Chemin spécifique du fichier de contexte. Si `None`, le chemin par défaut est déterminé via `get_path(CONTEXT_FILE)`.
*   **Retours**:
    *   (`bool`): `True` si la sauvegarde a été effectuée avec succès, `False` en cas d'erreur.
*   **Logique interne**:
    1.  Détermine le chemin du fichier à utiliser : `file_path` si fourni, sinon `get_path(CONTEXT_FILE)`.
    2.  Appelle `sauvegarder_json` avec le chemin déterminé et les données fournies, et retourne son résultat booléen.

## 3. Exemple d'usage

Pour cet exemple, nous allons simuler les modules `paths` et `constants`.

```python
# --- Simulation des dépendances pour l'exemple ---
# (Ces classes/fonctions existeraient réellement dans .paths et .constants)

class MockPaths:
    def get_path(self, filename: str) -> str:
        # Dans un vrai cas, ceci résoudrait un chemin d'accès réel, par ex. "./data/history.json"
        return f"./temp_data/{filename}"

class MockConstants:
    HISTORY_FILE = "history.json"
    CONTEXT_FILE = "context.json"

# Remplacer les importations réelles par nos mocks pour l'exemple
# from .paths import get_path
# from .constants import HISTORY_FILE, CONTEXT_FILE
get_path = MockPaths().get_path
HISTORY_FILE = MockConstants.HISTORY_FILE
CONTEXT_FILE = MockConstants.CONTEXT_FILE

# Créer un dossier temporaire pour les fichiers de test
import os
if not os.path.exists("./temp_data"):
    os.makedirs("./temp_data")

# --- Utilisation des fonctions réelles du module config/utils.py ---

# Exemple 1: Sauvegarde et chargement JSON générique
print("--- Exemple 1: JSON générique ---")
test_data = {"name": "Test", "value": 123, "items": [{"id": 1, "status": "ok"}, {"id": 2, "status": "pending"}]}
test_file = "./temp_data/my_config.json"

print(f"Sauvegarde de données dans {test_file}...")
success = sauvegarder_json(test_file, test_data)
if success:
    print("Sauvegarde réussie.")
    print(f"Chargement de données depuis {test_file}...")
    loaded_data = charger_json_robuste(test_file)
    print(f"Données chargées: {loaded_data}")
else:
    print("Échec de la sauvegarde.")

# Tester un chargement de fichier inexistant
print(f"\nTentative de chargement d'un fichier inexistant: ./temp_data/non_existent.json")
no_data = charger_json_robuste("./temp_data/non_existent.json")
print(f"Résultat: {no_data} (attendu: [])")

# Tester un chargement de fichier JSON malformé (créons-en un)
print(f"\nTentative de chargement d'un fichier JSON malformé.")
malformed_file = "./temp_data/malformed.json"
with open(malformed_file, 'w', encoding='utf-8') as f:
    f.write("{'key': 'value',}") # JSON invalide
loaded_malformed = charger_json_robuste(malformed_file)
print(f"Résultat: {loaded_malformed} (attendu: [])")


# Exemple 2: Gestion de l'historique
print("\n--- Exemple 2: Gestion de l'historique ---")
history_data = [
    {"timestamp": "2023-10-27T10:00:00Z", "event": "App started"},
    {"timestamp": "2023-10-27T10:05:00Z", "event": "User login"}
]
history_path = get_path(HISTORY_FILE) # Utilise le chemin par défaut simulé

print(f"Sauvegarde de l'historique dans {history_path}...")
sauvegarder_historique_worker(history_data)
print("Sauvegarde de l'historique terminée.")

print(f"Chargement de l'historique depuis {history_path}...")
loaded_history = charger_historique_robuste_worker()
print(f"Historique chargé: {loaded_history}")

# Ajout d'une nouvelle entrée
history_data.append({"timestamp": "2023-10-27T10:10:00Z", "event": "New action"})
print(f"\nSauvegarde de l'historique mis à jour dans {history_path}...")
sauvegarder_historique_worker(history_data)
print("Historique mis à jour sauvegardé.")

loaded_history_updated = charger_historique_robuste_worker()
print(f"Historique rechargé: {loaded_history_updated}")


# Exemple 3: Gestion des liens de contexte
print("\n--- Exemple 3: Gestion des liens de contexte ---")
context_links = [
    {"type": "doc", "url": "https://example.com/doc1"},
    {"type": "video", "url": "https://example.com/video_intro"}
]
context_path = get_path(CONTEXT_FILE) # Utilise le chemin par défaut simulé

print(f"Sauvegarde des liens de contexte dans {context_path}...")
success_context = sauvegarder_liens_contexte_worker(context_links)
if success_context:
    print("Sauvegarde des liens de contexte réussie.")
    print(f"Chargement des liens de contexte depuis {context_path}...")
    loaded_context = charger_liens_contexte_worker()
    print(f"Liens de contexte chargés: {loaded_context}")
else:
    print("Échec de la sauvegarde des liens de contexte.")

# Nettoyage des fichiers temporaires
print("\nNettoyage des fichiers temporaires...")
os.remove(test_file)
os.remove(malformed_file)
os.remove(history_path)
os.remove(context_path)
os.rmdir("./temp_data")
print("Nettoyage terminé.")
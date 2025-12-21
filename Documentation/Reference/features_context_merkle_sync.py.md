# Documentation Technique du Module `merkle_sync.py`

## 1. En-tête

### Titre
Module de Synchronisation Incrémentale via Arbre de Merkle

### Description concise
Ce module implémente une logique de synchronisation incrémentale basée sur la structure d'un arbre de Merkle. Il permet de détecter efficacement les modifications (ajouts, suppressions, changements de contenu) dans un ensemble de fichiers et de répertoires sans nécessiter une ré-indexation complète à chaque vérification, optimisant ainsi les performances pour la détection des changements.

### Dépendances
*   `os`: Interactions avec le système de fichiers (listage de répertoires, vérification de types de chemin).
*   `hashlib`: Génération de hachages (SHA-256) pour les fichiers et les nœuds de Merkle.
*   `logging`: Enregistrement des informations, avertissements et erreurs.
*   `typing`: Pour les annotations de type (`Dict`, `List`, `Optional`, `Tuple`).
*   `config.get_logger`: Utilitaire de configuration pour l'obtention d'un logger spécifique.
*   `features.Decorators.trace_action`: Décorateur pour le traçage des actions (logging d'entrée/sortie de fonctions).
*   `json` (utilisé en interne par `save_state` et `load_state`): Sérialisation/désérialisation des états de l'arbre.

---

## 2. Classes & Fonctions

### Classe `MerkleNode`
Représente un nœud dans l'arbre de Merkle. Chaque nœud peut être soit un fichier, soit un répertoire, et contient son propre hachage basé sur son contenu (pour les fichiers) ou sur les hachages de ses enfants (pour les répertoires).

#### `__init__(self, path: str, is_file: bool = True, hash_value: Optional[str] = None)`
*   **Description**: Initialise un nouveau nœud de Merkle.
*   **Arguments**:
    *   `path` (`str`): Le chemin absolu du fichier ou du répertoire représenté par ce nœud.
    *   `is_file` (`bool`, optionnel, défaut `True`): Indique si le nœud représente un fichier (`True`) ou un répertoire (`False`).
    *   `hash_value` (`Optional[str]`, optionnel, défaut `None`): Le hachage pré-calculé du nœud. Sera calculé si non fourni, surtout pour les répertoires.
*   **Retours**: `None`
*   **Logique interne**:
    *   Stocke le chemin, le type (fichier/répertoire) et le hachage.
    *   Initialise une liste vide pour les enfants (`self.children`), pertinente uniquement pour les nœuds de répertoire.

#### `add_child(self, child: 'MerkleNode')`
*   **Description**: Ajoute un nœud enfant à ce nœud (applicable uniquement aux nœuds de répertoire).
*   **Arguments**:
    *   `child` (`MerkleNode`): Le nœud enfant à ajouter.
*   **Retours**: `None`
*   **Logique interne**:
    *   Ajoute simplement le nœud `child` à la liste `self.children`.

#### `compute_hash(self) -> str`
*   **Description**: Calcule le hachage SHA-256 du nœud.
*   **Arguments**: `None`
*   **Retours**: `str`: Le hachage calculé du nœud.
*   **Logique interne**:
    *   Si le nœud est un fichier:
        *   Si `self.hash` est déjà défini, le retourne.
        *   Sinon, appelle la méthode statique `_hash_file` pour calculer le hachage du fichier et le stocke dans `self.hash` avant de le retourner.
    *   Si le nœud est un répertoire:
        *   Si le répertoire est vide (pas d'enfants), son hachage est celui d'une chaîne vide.
        *   Sinon, il récupère les hachages de tous ses enfants (en appelant `compute_hash` sur chacun d'eux récursivement).
        *   Ces hachages enfants sont triés lexicographiquement, concaténés, encodés en UTF-8, puis hachés avec SHA-256.
        *   Le résultat est stocké dans `self.hash` et retourné.

#### `_hash_file(file_path: str) -> str` (Méthode statique)
*   **Description**: Calcule le hachage SHA-256 du contenu d'un fichier donné.
*   **Arguments**:
    *   `file_path` (`str`): Le chemin absolu du fichier à hacher.
*   **Retours**: `str`: Le hachage SHA-256 du fichier, ou le hachage d'une chaîne vide en cas d'erreur de lecture.
*   **Logique interne**:
    *   Ouvre le fichier en mode binaire (`'rb'`).
    *   Lit l'intégralité de son contenu.
    *   Calcule le hachage SHA-256 du contenu.
    *   Gère les exceptions lors de la lecture du fichier, loguant un avertissement et retournant un hachage vide.

---

### Classe `MerkleTreeSync`
Gère la construction et la comparaison d'arbres de Merkle pour la synchronisation incrémentale.

#### `__init__(self, root_path: str)`
*   **Description**: Initialise le gestionnaire d'arbre de Merkle avec un chemin racine.
*   **Arguments**:
    *   `root_path` (`str`): Le chemin du répertoire racine à partir duquel l'arbre sera construit.
*   **Retours**: `None`
*   **Logique interne**:
    *   Normalise le `root_path` en chemin absolu.
    *   Initialise `self.root_node` à `None` (l'arbre n'est pas encore construit).
    *   Crée `self.node_map`, un dictionnaire qui stocke une référence de chaque nœud par son chemin, permettant un accès rapide.

#### `@trace_action(source="merkle_sync")`
#### `build_tree(self, exclude_dirs: Optional[List[str]] = None) -> MerkleNode`
*   **Description**: Construit l'arbre de Merkle complet pour le système de fichiers à partir du chemin racine.
*   **Arguments**:
    *   `exclude_dirs` (`Optional[List[str]]`, optionnel, défaut `None`): Une liste de noms de répertoires à exclure de l'arbre (ex: `['.git', '__pycache__']`). Une liste par défaut est utilisée si `None`.
*   **Retours**: `MerkleNode`: Le nœud racine de l'arbre de Merkle construit.
*   **Logique interne**:
    *   Définit une liste `exclude_dirs` par défaut si non fournie.
    *   Appelle la méthode récursive `_build_node` pour construire l'arbre à partir du `root_path`.
    *   Calcule le hachage final du nœud racine (ce qui déclenche le calcul des hachages de tous les enfants).
    *   Logue un message d'information sur la construction de l'arbre.

#### `_build_node(self, path: str, exclude_dirs: List[str]) -> MerkleNode`
*   **Description**: Méthode interne récursive pour construire un nœud et ses enfants.
*   **Arguments**:
    *   `path` (`str`): Le chemin du fichier ou répertoire pour lequel construire le nœud.
    *   `exclude_dirs` (`List[str]`): La liste des noms de répertoires à exclure.
*   **Retours**: `MerkleNode`: Le nœud Merkle construit pour le chemin donné.
*   **Logique interne**:
    *   Gère le cas où le chemin n'existe pas en retournant un nœud de répertoire vide.
    *   Si `path` est un fichier:
        *   Crée un `MerkleNode` pour le fichier et l'ajoute à `self.node_map`.
    *   Si `path` est un répertoire:
        *   Crée un `MerkleNode` pour le répertoire et l'ajoute à `self.node_map`.
        *   Liste les entrées du répertoire (fichiers/sous-répertoires).
        *   Pour chaque entrée non exclue, appelle récursivement `_build_node` pour créer un nœud enfant et l'ajoute au nœud courant.
        *   Gère les `PermissionError` et autres exceptions lors du listage des répertoires.

#### `@trace_action(source="merkle_sync")`
#### `compare_trees(self, other_tree: 'MerkleTreeSync') -> List[str]`
*   **Description**: Compare l'arbre actuel avec un autre arbre de Merkle (généralement l'état précédent) pour trouver les fichiers modifiés.
*   **Arguments**:
    *   `other_tree` (`MerkleTreeSync`): L'instance `MerkleTreeSync` représentant l'état précédent de l'arbre.
*   **Retours**: `List[str]`: Une liste des chemins absolus des fichiers qui ont été modifiés (ajoutés, supprimés ou dont le contenu a changé).
*   **Logique interne**:
    *   Retourne une liste vide si l'un des arbres n'est pas construit.
    *   Initialise une liste vide `modified_files`.
    *   Appelle la méthode récursive `_compare_nodes` pour démarrer la comparaison à partir des nœuds racines.

#### `_compare_nodes(self, node1: MerkleNode, node2: MerkleNode, modified_files: List[str])`
*   **Description**: Méthode interne récursive pour comparer deux nœuds et détecter les modifications.
*   **Arguments**:
    *   `node1` (`MerkleNode`): Le nœud de l'arbre actuel.
    *   `node2` (`MerkleNode`): Le nœud correspondant de l'arbre précédent.
    *   `modified_files` (`List[str]`): La liste qui accumule les chemins des fichiers modifiés.
*   **Retours**: `None`
*   **Logique interne**:
    *   Si les hachages de `node1` et `node2` sont identiques, la branche n'a pas changé; la fonction se termine.
    *   Si les nœuds sont des fichiers et que leurs hachages diffèrent, le chemin de `node1` est ajouté à `modified_files`.
    *   Si les nœuds sont des répertoires et que leurs hachages diffèrent:
        *   Il crée des mappings des enfants par nom pour un accès facile.
        *   Compare les enfants communs récursivement.
        *   Identifie les nouveaux fichiers/répertoires (présents dans `node1` mais pas `node2`) et les ajoute à `modified_files` (ou leurs contenus s'il s'agit d'un nouveau répertoire).
        *   Identifie les fichiers/répertoires supprimés (présents dans `node2` mais pas `node1`). Les fichiers supprimés ne sont pas ajoutés à `modified_files` par défaut, mais cette logique pourrait être modifiée si nécessaire pour inclure les suppressions.

#### `_collect_files(self, node: MerkleNode, files: List[str])`
*   **Description**: Méthode interne récursive pour collecter tous les chemins de fichiers sous un nœud donné.
*   **Arguments**:
    *   `node` (`MerkleNode`): Le nœud à partir duquel collecter les fichiers.
    *   `files` (`List[str]`): La liste qui accumule les chemins de fichiers.
*   **Retours**: `None`
*   **Logique interne**:
    *   Si le `node` est un fichier, son chemin est ajouté à la liste `files`.
    *   Si le `node` est un répertoire, la fonction s'appelle récursivement pour chacun de ses enfants.

#### `@trace_action(source="merkle_sync")`
#### `get_file_hash(self, file_path: str) -> Optional[str]`
*   **Description**: Récupère le hachage d'un fichier spécifique s'il existe dans l'arbre.
*   **Arguments**:
    *   `file_path` (`str`): Le chemin absolu du fichier dont le hachage est demandé.
*   **Retours**: `Optional[str]`: Le hachage du fichier, ou `None` si le fichier n'est pas trouvé ou n'est pas un fichier.
*   **Logique interne**:
    *   Recherche le `MerkleNode` correspondant à `file_path` dans `self.node_map`.
    *   Si le nœud existe et représente un fichier, il retourne son hachage (qui sera calculé si nécessaire).

#### `save_state(self, state_file: str)`
*   **Description**: Sauvegarde l'état actuel de l'arbre (principalement les hachages des fichiers et le hachage racine) dans un fichier JSON.
*   **Arguments**:
    *   `state_file` (`str`): Le chemin du fichier où sauvegarder l'état.
*   **Retours**: `None`
*   **Logique interne**:
    *   Construit un dictionnaire contenant le hachage racine et un mapping des chemins de fichiers vers leurs hachages.
    *   Sérialise ce dictionnaire en JSON et l'écrit dans le `state_file`.
    *   Logue un message d'information ou d'erreur sur l'opération.

#### `load_state(state_file: str) -> Dict[str, str]` (Méthode statique)
*   **Description**: Charge un état précédent (un mapping de chemins de fichiers vers leurs hachages) depuis un fichier JSON.
*   **Arguments**:
    *   `state_file` (`str`): Le chemin du fichier à charger.
*   **Retours**: `Dict[str, str]`: Un dictionnaire où les clés sont les chemins de fichiers et les valeurs sont leurs hachages. Retourne un dictionnaire vide si le fichier n'existe pas ou en cas d'erreur.
*   **Logique interne**:
    *   Vérifie l'existence du `state_file`.
    *   Désérialise le contenu JSON du fichier.
    *   Retourne la partie `file_hashes` du dictionnaire chargé.
    *   Gère les exceptions lors de la lecture/désérialisation, loguant une erreur.

---

## 3. Exemple d'usage

Voici un exemple illustrant comment utiliser la classe `MerkleTreeSync` pour suivre les modifications dans un répertoire.

```python
import os
import time
import shutil

# Assurez-vous que les modules 'config' et 'features.Decorators' sont disponibles
# ou adaptez les imports si vous exécutez cet exemple hors du contexte du projet.
# Pour cet exemple simple, nous pouvons mocker get_logger et trace_action
class MockLogger:
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass
    def debug(self, msg): pass

def mock_get_logger(name):
    return MockLogger()

def mock_trace_action(source):
    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Remplacez les imports réels par nos mocks pour l'exemple
# from config import get_logger
# from features.Decorators import trace_action
get_logger = mock_get_logger
trace_action = mock_trace_action

# Re-importer les classes après avoir mocké les dépendances si nécessaire
# (dans un environnement réel, ces mocks ne seraient pas nécessaires)
import hashlib
from typing import Dict, List, Optional
class MerkleNode: # Redéfini pour l'exemple, normalement importé directement
    def __init__(self, path: str, is_file: bool = True, hash_value: Optional[str] = None):
        self.path = path
        self.is_file = is_file
        self.hash = hash_value
        self.children: List['MerkleNode'] = []
    
    def add_child(self, child: 'MerkleNode'):
        self.children.append(child)
    
    def compute_hash(self) -> str:
        if self.is_file:
            if not self.hash:
                self.hash = self._hash_file(self.path)
            return self.hash
        else:
            if not self.children:
                return hashlib.sha256(b"").hexdigest()
            
            child_hashes = sorted([child.compute_hash() for child in self.children])
            combined = "".join(child_hashes).encode('utf-8')
            self.hash = hashlib.sha256(combined).hexdigest()
            return self.hash
    
    @staticmethod
    def _hash_file(file_path: str) -> str:
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            return hashlib.sha256(content).hexdigest()
        except Exception:
            return hashlib.sha256(b"").hexdigest()

# Simulate the log object from the module
log = mock_get_logger("merkle_sync_example")

class MerkleTreeSync: # Redéfini pour l'exemple, normalement importé directement
    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(root_path)
        self.root_node: Optional[MerkleNode] = None
        self.node_map: Dict[str, MerkleNode] = {}  # path -> node
    
    @trace_action(source="merkle_sync")
    def build_tree(self, exclude_dirs: Optional[List[str]] = None) -> MerkleNode:
        if exclude_dirs is None:
            exclude_dirs = ['.git', '__pycache__', 'venv', 'env', 'node_modules', 
                          'db', 'logs', 'dist', 'build', 'audio_cache', '.idea', '.vscode']
        
        self.root_node = self._build_node(self.root_path, exclude_dirs)
        self.root_node.compute_hash()
        
        log.info(f"✅ Arbre Merkle construit: {len(self.node_map)} nœuds, hash racine: {self.root_node.hash[:16]}...")
        return self.root_node
    
    def _build_node(self, path: str, exclude_dirs: List[str]) -> MerkleNode:
        if not os.path.exists(path):
            return MerkleNode(path, is_file=False, hash_value=hashlib.sha256(b"").hexdigest())
        
        if os.path.isfile(path):
            node = MerkleNode(path, is_file=True)
            self.node_map[path] = node
            return node
        else:
            node = MerkleNode(path, is_file=False)
            self.node_map[path] = node
            
            try:
                entries = sorted(os.listdir(path))
                for entry in entries:
                    if entry in exclude_dirs:
                        continue
                    
                    entry_path = os.path.join(path, entry)
                    child_node = self._build_node(entry_path, exclude_dirs)
                    node.add_child(child_node)
            except PermissionError:
                log.warning(f"Permission refusée pour {path}")
            except Exception as e:
                log.warning(f"Erreur parcours {path}: {e}")
            
            return node
    
    @trace_action(source="merkle_sync")
    def compare_trees(self, other_tree: 'MerkleTreeSync') -> List[str]:
        if not self.root_node or not other_tree.root_node:
            return []
        
        modified_files = []
        self._compare_nodes(self.root_node, other_tree.root_node, modified_files)
        
        return modified_files
    
    def _compare_nodes(self, node1: MerkleNode, node2: MerkleNode, modified_files: List[str]):
        if node1.hash == node2.hash:
            return
        
        if node1.is_file and node2.is_file:
            modified_files.append(node1.path)
            return
        
        if not node1.is_file and not node2.is_file:
            children1_map = {os.path.basename(c.path): c for c in node1.children}
            children2_map = {os.path.basename(c.path): c for c in node2.children}
            
            common_names = set(children1_map.keys()) & set(children2_map.keys())
            for name in common_names:
                self._compare_nodes(children1_map[name], children2_map[name], modified_files)
            
            new_files = set(children1_map.keys()) - set(children2_map.keys())
            # deleted_files = set(children2_map.keys()) - set(children1_map.keys()) # Not used here, but could be for deleted files
            
            for name in new_files:
                child = children1_map[name]
                if child.is_file:
                    modified_files.append(child.path)
                else:
                    self._collect_files(child, modified_files)
    
    def _collect_files(self, node: MerkleNode, files: List[str]):
        if node.is_file:
            files.append(node.path)
        else:
            for child in node.children:
                self._collect_files(child, files)
    
    @trace_action(source="merkle_sync")
    def get_file_hash(self, file_path: str) -> Optional[str]:
        node = self.node_map.get(file_path)
        if node and node.is_file:
            return node.compute_hash()
        return None
    
    def save_state(self, state_file: str):
        import json
        state = {
            'root_hash': self.root_node.hash if self.root_node else None,
            'file_hashes': {
                path: node.hash
                for path, node in self.node_map.items()
                if node.is_file
            }
        }
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            log.info(f"État Merkle sauvegardé: {len(state['file_hashes'])} fichiers")
        except Exception as e:
            log.error(f"Erreur sauvegarde état: {e}")
    
    @staticmethod
    def load_state(state_file: str) -> Dict[str, str]:
        import json
        if not os.path.exists(state_file):
            return {}
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            return state.get('file_hashes', {})
        except Exception as e:
            log.error(f"Erreur chargement état: {e}")
            return {}

# --- Démarrage de l'exemple ---

# 1. Préparation d'un répertoire de test
test_dir = "merkle_test_project"
state_file = os.path.join(test_dir, ".merkle_state.json")

if os.path.exists(test_dir):
    shutil.rmtree(test_dir)
os.makedirs(os.path.join(test_dir, "src"))
os.makedirs(os.path.join(test_dir, "docs"))
os.makedirs(os.path.join(test_dir, "data"))

# Création de fichiers initiaux
with open(os.path.join(test_dir, "src", "app.py"), "w") as f:
    f.write("print('Hello Merkle!')")
with open(os.path.join(test_dir, "docs", "README.md"), "w") as f:
    f.write("# Mon Projet")
with open(os.path.join(test_dir, "data", "config.json"), "w") as f:
    f.write('{"version": "1.0"}')
with open(os.path.join(test_dir, "ignore_me.log"), "w") as f: # Fichier à ignorer
    f.write("Log content")

print(f"Répertoire de test '{test_dir}' créé avec des fichiers initiaux.")

# 2. Construction de l'arbre initial
print("\n--- Étape 1: Construction de l'arbre initial ---")
initial_merkle_tree = MerkleTreeSync(test_dir)
initial_merkle_tree.build_tree(exclude_dirs=['ignore_me.log', '__pycache__'])

# Afficher le hash racine initial
print(f"Hash racine initial: {initial_merkle_tree.root_node.hash}")

# 3. Sauvegarde de l'état initial
initial_merkle_tree.save_state(state_file)
print(f"État initial sauvegardé dans {state_file}")

# 4. Simulation de modifications
print("\n--- Étape 2: Simulation de modifications ---")
# Modification d'un fichier existant
with open(os.path.join(test_dir, "src", "app.py"), "w") as f:
    f.write("print('Hello Merkle, updated!')")
print("Fichier src/app.py modifié.")

# Ajout d'un nouveau fichier
with open(os.path.join(test_dir, "src", "utils.py"), "w") as f:
    f.write("def helper(): pass")
print("Nouveau fichier src/utils.py ajouté.")

# Ajout d'un nouveau répertoire et de son contenu
os.makedirs(os.path.join(test_dir, "tests"))
with open(os.path.join(test_dir, "tests", "test_app.py"), "w") as f:
    f.write("import unittest")
print("Nouveau répertoire 'tests' avec test_app.py ajouté.")

# Suppression d'un fichier (simulé, le fichier est physiquement supprimé)
os.remove(os.path.join(test_dir, "docs", "README.md"))
print("Fichier docs/README.md supprimé.")

# 5. Construction de l'arbre mis à jour et comparaison
print("\n--- Étape 3: Construction de l'arbre mis à jour et comparaison ---")
updated_merkle_tree = MerkleTreeSync(test_dir)
updated_merkle_tree.build_tree(exclude_dirs=['ignore_me.log', '__pycache__'])

print(f"Hash racine mis à jour: {updated_merkle_tree.root_node.hash}")

modified_files = updated_merkle_tree.compare_trees(initial_merkle_tree)

print("\nFichiers modifiés détectés:")
if modified_files:
    for f in modified_files:
        print(f"- {os.path.basename(f)}")
else:
    print("Aucun fichier modifié détecté (ceci ne devrait pas arriver ici).")

# 6. Vérification du chargement de l'état
print("\n--- Étape 4: Chargement de l'état précédent ---")
loaded_state_hashes = MerkleTreeSync.load_state(state_file)
print(f"Nombre de hachages de fichiers chargés depuis l'état précédent: {len(loaded_state_hashes)}")

# Nettoyage
print(f"\nNettoyage du répertoire de test '{test_dir}'...")
shutil.rmtree(test_dir)
print("Nettoyage terminé.")
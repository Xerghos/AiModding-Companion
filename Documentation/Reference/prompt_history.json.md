# `prompt_history.json` - Historique des Requêtes Utilisateur

## Description concise
Ce fichier JSON stocke une séquence chronologique des requêtes (prompts) soumises par l'utilisateur à l'application ou au système. Il sert de journal des interactions passées, permettant de conserver une trace des commandes ou des questions posées par l'utilisateur.

## Dépendances
*   **Format**: JSON (JavaScript Object Notation).
*   **Librairies/Modules (conceptuels)**: Nécessite un parser/sérialiseur JSON dans le langage de programmation utilisé (ex: `json` en Python, `JSON.parse`/`JSON.stringify` en JavaScript).

---

## Structure du fichier
Le fichier `prompt_history.json` est une liste (tableau) JSON où chaque élément est une chaîne de caractères (string) représentant un prompt utilisateur unique.

*   **Type de données racine**: Tableau JSON (`Array`).
*   **Éléments du tableau**: Chaque élément est de type `string`.
*   **Ordre**: Les prompts sont stockés dans l'ordre chronologique de leur soumission, du plus ancien au plus récent.

### Exemple de structure
```json
[
  "premier prompt de l'utilisateur",
  "deuxième prompt de l'utilisateur",
  "etc."
]
```

---

## Opérations conceptuelles
Bien qu'il s'agisse d'un fichier de données sans fonctions exécutables en lui-même, les opérations typiques effectuées par une application sur ce fichier sont les suivantes :

### 1. `charger_historique()`
*   **Signature (conceptuelle)**: `charger_historique() -> list[str]`
*   **Arguments**: Aucun.
*   **Retourne**: Une liste de chaînes de caractères (`list[str]`), où chaque chaîne est un prompt de l'historique. En cas d'erreur de lecture ou si le fichier est vide/inexistant, une liste vide ou une exception peut être retournée/levée.
*   **Logique interne**:
    1.  Ouvre le fichier `prompt_history.json` en mode lecture.
    2.  Parse le contenu JSON pour le convertir en une structure de données native (généralement une liste/tableau).
    3.  Retourne cette structure de données.

### 2. `ajouter_prompt(nouveau_prompt: str)`
*   **Signature (conceptuelle)**: `ajouter_prompt(nouveau_prompt: str) -> None`
*   **Arguments**:
    *   `nouveau_prompt` (str): La chaîne de caractères du prompt à ajouter à l'historique.
*   **Retourne**: `None`.
*   **Logique interne**:
    1.  Charge l'historique existant en appelant `charger_historique()`.
    2.  Ajoute `nouveau_prompt` à la fin de la liste des prompts.
    3.  Ouvre le fichier `prompt_history.json` en mode écriture (ce qui écrase le contenu précédent).
    4.  Sérialise la liste mise à jour en format JSON et l'écrit dans le fichier.
    5.  Assure un encodage correct (ex: UTF-8) et un formatage lisible (ex: `indent=2`).

### 3. `obtenir_derniers_prompts(nombre: int)`
*   **Signature (conceptuelle)**: `obtenir_derniers_prompts(nombre: int) -> list[str]`
*   **Arguments**:
    *   `nombre` (int): Le nombre de prompts les plus récents à récupérer.
*   **Retourne**: Une liste de chaînes de caractères (`list[str]`) contenant les `nombre` derniers prompts. Si le nombre total de prompts est inférieur à `nombre`, tous les prompts disponibles sont retournés.
*   **Logique interne**:
    1.  Charge l'historique complet en appelant `charger_historique()`.
    2.  Extrait les `nombre` derniers éléments de la liste.
    3.  Retourne cette sous-liste.

---

## Exemple d'usage (Python conceptuel)
```python
import json
import os

FICHIER_HISTORIQUE = 'prompt_history.json'

def charger_historique():
    """Charge l'historique des prompts depuis le fichier JSON."""
    if not os.path.exists(FICHIER_HISTORIQUE):
        return []
    with open(FICHIER_HISTORIQUE, 'r', encoding='utf-8') as f:
        return json.load(f)

def ajouter_prompt(prompt):
    """Ajoute un nouveau prompt à l'historique et le sauvegarde."""
    historique = charger_historique()
    historique.append(prompt)
    with open(FICHIER_HISTORIQUE, 'w', encoding='utf-8') as f:
        json.dump(historique, f, indent=2, ensure_ascii=False)
    print(f"Prompt ajouté : \"{prompt}\"")

def obtenir_derniers_prompts(nombre):
    """Retourne les N derniers prompts de l'historique."""
    historique = charger_historique()
    return historique[-nombre:] if len(historique) >= nombre else historique[:]

# --- Simulation d'utilisation ---

# Initialisation/Création du fichier si inexistant
# (Contenu initial fourni dans la source, pour l'exemple on charge ou initie)
try:
    current_history = charger_historique()
    print(f"Historique actuel (total {len(current_history)} prompts) :")
    for i, p in enumerate(current_history[-3:]): # Afficher les 3 derniers pour l'exemple
        print(f"  {i+1}. {p}")
except json.JSONDecodeError:
    print("Le fichier prompt_history.json est corrompu ou vide. Initialisation d'un nouvel historique.")
    current_history = []
    with open(FICHIER_HISTORIQUE, 'w', encoding='utf-8') as f:
        json.dump(current_history, f, indent=2, ensure_ascii=False)


# Exemple d'ajout d'un nouveau prompt
ajouter_prompt("quel est l'état actuel du projet ?")

# Exemple de récupération des 2 derniers prompts
derniers_prompts = obtenir_derniers_prompts(2)
print(f"\nLes 2 derniers prompts :")
for i, prompt in enumerate(derniers_prompts):
    print(f"  {i+1}. {prompt}")

# Supposons le fichier a été initialisé avec le contenu fourni:
# current_history = [
#   "je voulais une documentation atomique...",
#   "stop",
#   # ... et les autres prompts du code source ...
# ]
# print(f"\nExemple de dernier prompt du fichier source: \"{current_history[-1]}\"")
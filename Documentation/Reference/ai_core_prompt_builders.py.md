# `ai_core/prompt_builders.py` - Gestion et Construction de Prompts

Ce module fournit des utilitaires pour la construction et la sanitation de prompts destinés aux modèles de langage, notamment pour l'intégration avec le CLI de Gemini. Il gère la troncature de contenu, l'adaptation des prompts au contexte CLI, et la construction de prompts structurés incluant des composants RAG (Retrieval Augmented Generation), l'historique de conversation et le contexte projet.

**Dépendances:**
*   `re`
*   `dataclasses`
*   `typing`

---

## Classes & Fonctions

### `PromptBuildMeta`

```python
@dataclass
class PromptBuildMeta:
    total_chars: int
    truncated: Dict[str, bool]
    sizes: Dict[str, int]
```

Une dataclass simple utilisée pour encapsuler les métadonnées de la construction d'un prompt, notamment sa taille totale et le statut de troncature de ses différentes sections.

**Arguments:**
*   `total_chars` (`int`): Le nombre total de caractères dans le prompt final après toutes les troncatures.
*   `truncated` (`Dict[str, bool]`): Un dictionnaire où les clés sont les noms des sections du prompt (e.g., "repo_map", "rag", "history", "total") et les valeurs sont des booléens indiquant si la section correspondante a été tronquée.
*   `sizes` (`Dict[str, int]`): Un dictionnaire où les clés sont les noms des sections et les valeurs sont la taille en caractères de chaque section après leur troncature individuelle.

**Retours:**
*   N/A (Ceci est une dataclass, pas une fonction.)

---

### `_truncate`

```python
def _truncate(text: str, max_chars: int) -> Tuple[str, bool]:
```

Tronque une chaîne de caractères à une longueur maximale spécifiée. Si la chaîne est tronquée, un marqueur de troncature est ajouté à la fin, après avoir conservé la partie initiale du texte.

**Arguments:**
*   `text` (`str`): La chaîne de caractères à potentiellement tronquer.
*   `max_chars` (`int`): Le nombre maximal de caractères que la chaîne résultante doit contenir.

**Retours:**
*   `Tuple[str, bool]`: Un tuple contenant la chaîne tronquée (ou originale si pas de troncature) et un booléen `True` si la chaîne a été tronquée, `False` sinon.

**Logique interne:**
1.  Gère les cas de texte vide ou de `max_chars` non positif en retournant une chaîne vide.
2.  Si la longueur du `text` est inférieure ou égale à `max_chars`, le texte est retourné tel quel sans troncature.
3.  Sinon, un marqueur de troncature est construit (`\n\n...[TRONQUÉ: X caractères]...`). La longueur à conserver du texte original est calculée pour s'assurer que le marqueur complet puisse être inclus.
4.  Le texte est tronqué et le marqueur est ajouté.

---

### `sanitize_system_instruction_for_cli`

```python
def sanitize_system_instruction_for_cli(system_instruction: Optional[str]) -> str:
```

Nettoie une instruction système (system prompt) pour qu'elle soit adaptée à une utilisation avec le CLI de Gemini, en supprimant les éléments spécifiques au "tool-calling" ou à l'exécution de commandes qui ne seraient pas gérés par le CLI stateless.

**Arguments:**
*   `system_instruction` (`Optional[str]`): L'instruction système originale, potentiellement générée par un Swarm/Agent.

**Retours:**
*   `str`: L'instruction système nettoyée.

**Logique interne:**
1.  Retourne une chaîne vide si l'`system_instruction` est `None` ou vide.
2.  Utilise des expressions régulières pour:
    *   Supprimer les blocs de texte qui ressemblent à un manuel d'outils (ex: `--- 🛠️ MANUEL DES OUTILS AUTORISÉS --- ...`).
    *   Supprimer les lignes qui incitent explicitement à appeler des outils ou à utiliser des formats de tool-calling (ex: `!native_tool`, `POUR UTILISER UN OUTIL`).
3.  Normalise les sauts de ligne multiples, en les réduisant à deux maximum (`\n\n`).
4.  Supprime les espaces blancs en début et fin de chaîne.

---

### `build_cli_system_md`

```python
def build_cli_system_md(system_instruction: Optional[str], *, language: str = "fr", extra: str = "") -> str:
```

Construit le contenu du fichier `.gemini/system.md`, qui est utilisé par le CLI de Gemini via la variable d'environnement `GEMINI_SYSTEM_MD`. Ce contenu vise à remplacer le comportement par défaut du CLI par un mode chat plus cohérent avec l'application AiModding-Companion.

**Arguments (Keyword-Only):**
*   `system_instruction` (`Optional[str]`): L'instruction système de base, qui sera nettoyée avant d'être incluse.
*   `language` (`str`, optionnel, défaut: `"fr"`): La langue dans laquelle le modèle doit répondre et dans laquelle les "guardrails" seront formulés.
*   `extra` (`str`, optionnel, défaut: `""`): Un bloc de texte additionnel à inclure à la fin du prompt système.

**Retours:**
*   `str`: Le contenu complet du prompt système formaté.

**Logique interne:**
1.  Appelle `sanitize_system_instruction_for_cli` pour nettoyer l'`system_instruction` de base.
2.  Construit un ensemble de "guardrails" (règles de comportement) pour le modèle, l'instruisant d'agir comme un assistant conversationnel, de répondre dans la langue spécifiée et de ne pas tenter d'appeler des outils ou des commandes.
3.  Formate le bloc `extra` s'il est fourni, en l'encadrant de séparateurs `---`.
4.  Assemble l'instruction de base nettoyée, les "guardrails" et le bloc `extra` avec des séparateurs appropriés.

---

### `_format_history`

```python
def _format_history(history: List[Dict[str, Any]], max_turns: int) -> str:
```

Formate une liste de messages d'historique de conversation en une seule chaîne de caractères, en ne conservant qu'un nombre limité de tours de conversation récents.

**Arguments:**
*   `history` (`List[Dict[str, Any]]`): Une liste de dictionnaires, où chaque dictionnaire représente un message de l'historique et contient les clés `role` (e.g., "user", "assistant") et `content`.
*   `max_turns` (`int`): Le nombre maximal de tours de conversation (une paire user/assistant compte pour un tour) à inclure dans l'historique formaté.

**Retours:**
*   `str`: L'historique formaté sous forme de chaîne de caractères, chaque message étant préfixé par son rôle.

**Logique interne:**
1.  Retourne une chaîne vide si l'`history` est vide.
2.  Sélectionne les `max_turns * 2` derniers messages pour s'assurer que des paires complètes user/assistant sont incluses.
3.  Pour chaque message sélectionné, le formate avec le préfixe "Assistant: " ou "User: " et son contenu.
4.  Joint toutes les lignes formatées avec des sauts de ligne.

---

### `_detect_query_type`

```python
def _detect_query_type(query: str) -> str:
```

Détecte le type de requête de l'utilisateur (par exemple, "code", "concept", "debug", "refactor", "general") en se basant sur la présence de mots-clés spécifiques dans la requête. Cela permet une allocation adaptative des composants de contexte dans le prompt final.

**Arguments:**
*   `query` (`str`): La requête textuelle de l'utilisateur.

**Retours:**
*   `str`: Le type de requête détecté ("code", "concept", "debug", "refactor", "general").

**Logique interne:**
1.  Convertit la requête en minuscules pour une correspondance insensible à la casse.
2.  Définit des listes de mots-clés pour chaque type de requête (`code`, `concept`, `debug`, `refactor`).
3.  Calcule un score pour chaque type en comptant les occurrences de ses mots-clés dans la requête.
4.  Le type avec le score le plus élevé est retenu.
5.  Si aucun type n'a de score supérieur à zéro, ou en cas d'égalité, des heuristiques par défaut sont appliquées (ex: requête courte -> "general", présence de "?" -> "concept").

---

### `build_cli_prompt`

```python
def build_cli_prompt(
    *,
    message: str,
    rag_context: Optional[str],
    history: List[Dict[str, Any]],
    cache_components: Optional[Dict[str, str]] = None,
    max_history_turns: int = 3,
    limits: Optional[Dict[str, int]] = None,
    defer_message: bool = False,
) -> Tuple[str, PromptBuildMeta]:
```

Construit un prompt structuré complet pour une utilisation avec le CLI de Gemini (en mode "stateless" texte). Le prompt inclut des sections pour le contexte projet (repo map, architecture, arborescence, LTM), le contexte RAG, l'historique de conversation et le message utilisateur actuel. Il intègre une allocation adaptative des tailles de contexte basée sur le type de requête.

**Arguments (Keyword-Only):**
*   `message` (`str`): Le message (requête) actuel de l'utilisateur.
*   `rag_context` (`Optional[str]`): Le contenu textuel du contexte RAG (Retrieval Augmented Generation), si disponible.
*   `history` (`List[Dict[str, Any]]`): Une liste de dictionnaires représentant l'historique de la conversation.
*   `cache_components` (`Optional[Dict[str, str]]`, optionnel, défaut: `None`): Un dictionnaire contenant divers composants de contexte mis en cache, tels que "repo_map", "arch" (architecture), "tree" (arborescence), et "ltm" (mémoire à long terme).
*   `max_history_turns` (`int`, optionnel, défaut: `3`): Le nombre maximal de tours de conversation (paires user/assistant) à inclure dans l'historique.
*   `limits` (`Optional[Dict[str, int]]`, optionnel, défaut: `None`): Un dictionnaire spécifiant les limites de caractères pour le prompt total et chaque section individuelle (ex: `"total"`, `"arch"`, `"tree"`, `"rag"`). Si non fourni, des valeurs par défaut sont utilisées.
*   `defer_message` (`bool`, optionnel, défaut: `False`): Si `True`, le message utilisateur n'est pas inclus dans la section "MESSAGE ACTUEL" du prompt, car il est géré séparément par l'interface du CLI.

**Retours:**
*   `Tuple[str, PromptBuildMeta]`: Un tuple contenant la chaîne de caractères du prompt final structuré et un objet `PromptBuildMeta` avec les métadonnées de construction.

**Logique interne:**
1.  **Détection du type de requête**: Utilise `_detect_query_type` pour analyser le `message` utilisateur et déterminer s'il s'agit d'une requête "code", "concept", "debug", "refactor" ou "general".
2.  **Initialisation et allocation des limites**: Définit des limites de caractères par défaut pour chaque section du prompt (`total`, `arch`, `tree`, `ltm`, `rag`, `history`, `message`).
3.  **Allocation adaptative**: Ajuste ces limites en fonction du type de requête détecté, par exemple, en augmentant la limite pour "repo_map" et "tree" pour une requête de "code", ou "ltm" pour une requête de "concept".
4.  **Extraction des composants**: Récupère les différents composants de contexte (`repo_map`, `arch`, `tree`, `ltm`) du dictionnaire `cache_components`. `repo_map` est priorisé sur `arch` si les deux sont présents.
5.  **Troncature par bloc**: Applique la fonction `_truncate` à chaque section de contexte (repo map/arch, tree, ltm, rag, message) en respectant leurs limites de caractères adaptatives. L'historique est d'abord formaté via `_format_history` puis tronqué.
6.  **Assemblage du prompt**: Construit le prompt final en joignant les différentes sections tronquées, chacune précédée d'un en-tête descriptif (ex: `=== CONTEXTE PROJET ===`).
7.  **Troncature globale**: Si la longueur totale du prompt assemblé dépasse la limite `total_max`, une troncature finale est appliquée à l'ensemble du prompt.
8.  **Métadonnées**: Crée et retourne un objet `PromptBuildMeta` qui résume les informations de troncature et les tailles finales de chaque section.

---

## Exemple d'usage

```python
import json
from typing import Dict, Any
from ai_core.prompt_builders import build_cli_system_md, build_cli_prompt

# --- Exemple d'utilisation de build_cli_system_md ---
system_instruction_raw = """
Tu es un assistant IA spécialisé dans la programmation.
--- 🛠️ MANUEL DES OUTILS AUTORISÉS ---
Tu as accès à ces outils:
- native_tool("read_file", path: str) -> str: Lit le contenu d'un fichier.
- native_tool("write_file", path: str, content: str) -> None: Écrit dans un fichier.
POUR UTILISER UN OUTIL, réponds avec un objet JSON natif.
---
Ton objectif est d'aider les développeurs.
"""

# Nettoyage et construction du system.md pour le CLI
cli_system_md = build_cli_system_md(system_instruction_raw, language="en", extra="Be precise and concise.")
print("--- Contenu généré pour .gemini/system.md ---")
print(cli_system_md)
print("\n" + "="*50 + "\n")


# --- Exemple d'utilisation de build_cli_prompt ---
# Données de démonstration
message_utilisateur = "Comment implémenter une API RESTful simple en Python avec FastAPI ?"
rag_context_data = "FastAPI est un framework web moderne et rapide (basé sur Starlette et Pydantic) pour construire des API avec Python 3.7+..."
history_data = [
    {"role": "user", "content": "Salut, peux-tu m'aider avec Python ?"},
    {"role": "assistant", "content": "Bien sûr, je suis là pour ça. Que veux-tu savoir ?"},
    {"role": "user", "content": "Quelle est la différence entre une liste et un tuple ?"},
    {"role": "assistant", "content": "Une liste est mutable, un tuple est immutable."},
]
cache_components_data: Dict[str, str] = {
    "repo_map": "project_root/\n  src/\n    main.py\n  tests/\n    test_main.py\n  README.md",
    "tree": "src/main.py: contient le point d'entrée de l'application.\ntests/test_main.py: tests unitaires pour main.py.",
    "ltm": "L'utilisateur a récemment travaillé sur des projets FastAPI et Flask."
}
limits_data = {
    "total": 500, # Limite totale très basse pour démonstration de troncature
    "arch": 100,
    "tree": 100,
    "ltm": 100,
    "rag": 100,
    "history": 100,
    "message": 100,
}

# Construction du prompt complet
prompt, meta = build_cli_prompt(
    message=message_utilisateur,
    rag_context=rag_context_data,
    history=history_data,
    cache_components=cache_components_data,
    max_history_turns=2,
    limits=limits_data
)

print("--- Prompt généré pour gemini prompt ---")
print(prompt)
print("\n" + "="*50 + "\n")

print("--- Métadonnées du prompt ---")
print(f"Total chars: {meta.total_chars}")
print(f"Tronqué: {json.dumps(meta.truncated, indent=2)}")
print(f"Tailles des sections: {json.dumps(meta.sizes, indent=2)}")

# Exemple avec defer_message=True
prompt_deferred, meta_deferred = build_cli_prompt(
    message=message_utilisateur,
    rag_context=rag_context_data,
    history=history_data,
    cache_components=cache_components_data,
    max_history_turns=1,
    limits=limits_data,
    defer_message=True
)
print("\n--- Prompt généré (message différé) ---")
print(prompt_deferred)
print(f"\nMessage tronqué dans les métadonnées: {meta_deferred.truncated.get('message')}")
print(f"Taille du message dans les métadonnées: {meta_deferred.sizes.get('message')}")
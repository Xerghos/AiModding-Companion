# Documentation Technique du Module `features\context\context_manager.py`

## 1. En-tête

### Titre
Gestionnaire de Contexte Avancé avec PriomptiPy

### Description Concise
Ce module fournit une solution sophistiquée pour la gestion du contexte des Large Language Models (LLM). Il utilise la bibliothèque `PriomptiPy` pour allouer dynamiquement un budget de tokens en fonction de la priorité des différents éléments du contexte (instructions système, fichier actif, historique de chat, contexte RAG, erreurs de compilation). En cas d'indisponibilité de `PriomptiPy` ou d'erreur lors de son utilisation, le module bascule sur une méthode de construction de contexte simple et séquentielle. Un pattern singleton est implémenté pour l'accès au gestionnaire.

### Dépendances

*   **Standard Library**: `logging`, `typing` (pour `Dict`, `List`, `Optional`)
*   **Projet Interne**:
    *   `config.get_logger`: Pour la configuration centralisée du logger.
    *   `features.Decorators.trace_action`: Pour le traçage des actions (décorateur).
*   **Externe (Optionnel)**:
    *   `priomptipy`: `Scope`, `SystemMessage`, `UserMessage`, `Isolate`, `render`. Cette dépendance est gérée de manière facultative ; le module fonctionne en mode dégradé si `priomptipy` n'est pas installé.

## 2. Classes & Fonctions

### Classe : `ContextManager`

```python
class ContextManager:
    """
    Gestionnaire de contexte intelligent utilisant PriomptiPy.
    
    Utilise PriomptiPy pour prioriser les éléments du prompt.
    """
    # ...
```

**Description:**
Cette classe gère la construction du contexte pour un LLM, en s'appuyant sur PriomptiPy pour optimiser l'utilisation des tokens en fonction de la priorité. Elle encapsule la logique de priorisation et fournit un mécanisme de fallback.

#### Méthode : `__init__`

```python
    def __init__(self, max_tokens: int = 32000):
        """
        Initialise le gestionnaire de contexte.

        Args:
            max_tokens: Budget maximum de tokens disponible pour le contexte total.
        """
        # ...
```

**Description:**
Initialise une nouvelle instance du `ContextManager`. Vérifie la disponibilité de `PriomptiPy` et configure le mode de fonctionnement (priorisé ou basique).

**Arguments:**
*   `max_tokens` (`int`, optionnel, défaut: `32000`): Le nombre maximum de tokens que le contexte généré ne doit pas dépasser.

**Logique Interne:**
1.  Stocke `max_tokens`.
2.  Définit l'attribut `self.enabled` à `True` si `PriomptiPy` a été importé avec succès, sinon à `False`.
3.  Si `PriomptiPy` n'est pas disponible, un avertissement est logué.

#### Méthode : `build_context`

```python
    @trace_action(source="context_manager")
    def build_context(self, 
                     system_instruction: str,
                     active_file: Optional[str] = None,
                     rag_context: Optional[str] = None,
                     chat_history: Optional[List] = None,
                     errors: Optional[List[str]] = None) -> str:
        """
        Construit le contexte optimisé avec priorités en utilisant PriomptiPy ou un fallback simple.

        Les priorités des composants sont définies comme suit :
        - Haute: Instruction système, contenu du fichier actif.
        - Moyenne: Historique de chat récent, erreurs de compilation.
        - Basse: Snippets RAG (Retrieval Augmented Generation).

        Args:
            system_instruction: L'instruction système principale pour le LLM.
            active_file: Le contenu du fichier actuellement en cours d'édition ou pertinent.
            rag_context: Des informations contextuelles obtenues via une recherche RAG.
            chat_history: L'historique de la conversation, une liste de dictionnaires (ex: `[{'role': 'user', 'content': '...'}]`).
            errors: Une liste de messages d'erreur de compilation ou d'exécution.

        Returns:
            Une chaîne de caractères représentant le contexte formaté et optimisé.
        """
        # ...
```

**Description:**
C'est la méthode principale pour assembler le contexte. Elle tente d'utiliser `PriomptiPy` pour une allocation intelligente des tokens en fonction des priorités définies. En cas d'échec de `PriomptiPy` (non disponible ou erreur lors du rendu), elle utilise une méthode de construction de contexte simple.

**Arguments:**
*   `system_instruction` (`str`): Instruction principale pour le système.
*   `active_file` (`Optional[str]`, optionnel): Contenu du fichier actuellement actif.
*   `rag_context` (`Optional[str]`, optionnel): Contexte fourni par une opération RAG.
*   `chat_history` (`Optional[List]`, optionnel): Historique de la conversation. Chaque élément est un dictionnaire avec `role` et `content`.
*   `errors` (`Optional[List[str]]`, optionnel): Liste de chaînes de caractères représentant des messages d'erreur.

**Retours:**
*   `str`: Le contexte complet, formaté pour être envoyé à un LLM.

**Logique Interne:**
1.  **Vérification `PriomptiPy`**: Si `self.enabled` est `False`, la méthode `_build_context_simple` est appelée directement.
2.  **Construction `PriomptiPy` (bloc `try`):**
    *   Crée une liste `components` qui sera remplie d'objets `priomptipy` (`Scope`, `Isolate`, `SystemMessage`, `UserMessage`).
    *   **Instruction Système**: Ajoutée avec `absolute_priority=100` (la plus haute).
    *   **Fichier Actif**: Ajouté si présent, avec `absolute_priority=90`.
    *   **Erreurs**: Ajoutées si présentes, avec `absolute_priority=50`. Les erreurs sont formatées en une seule chaîne.
    *   **Historique de Chat**: Si présent, les 4 dernières entrées sont extraites, formatées et encapsulées dans un `Isolate` avec `max_tokens=2000` et `absolute_priority=40`.
    *   **Contexte RAG**: Si présent, encapsulé dans un `Isolate` avec `max_tokens=5000` et `absolute_priority=20`.
    *   La fonction `priomptipy.render()` est appelée avec la liste des composants et le `self.max_tokens` global pour générer le contexte final.
3.  **Gestion des Erreurs (bloc `except`):**
    *   Si une `Exception` se produit lors de la construction ou du rendu `PriomptiPy`, l'erreur est loguée et `_build_context_simple` est appelée comme fallback.

#### Méthode (Privée) : `_build_context_simple`

```python
    def _build_context_simple(self,
                              system_instruction: str,
                              active_file: Optional[str] = None,
                              rag_context: Optional[str] = None,
                              chat_history: Optional[List] = None,
                              errors: Optional[List[str]] = None) -> str:
        """
        Fallback: construction simple du contexte sans PriomptiPy.

        Cette méthode concatène les différents éléments du contexte dans un ordre prédéfini,
        avec des coupes basiques si nécessaire.
        """
        # ...
```

**Description:**
Cette méthode est utilisée comme mécanisme de fallback lorsque `PriomptiPy` n'est pas disponible ou qu'une erreur se produit lors de son utilisation. Elle construit le contexte en concaténant les différentes parties de manière séquentielle, avec une troncature rudimentaire pour éviter de dépasser des limites raisonnables.

**Arguments:**
*   `system_instruction` (`str`): Instruction principale pour le système.
*   `active_file` (`Optional[str]`, optionnel): Contenu du fichier actuellement actif (tronqué à 3000 caractères).
*   `rag_context` (`Optional[str]`, optionnel): Contexte fourni par une opération RAG (tronqué à 5000 caractères).
*   `chat_history` (`Optional[List]`, optionnel): Historique de la conversation (les 4 dernières entrées, contenu tronqué à 500 caractères).
*   `errors` (`Optional[List[str]]`, optionnel): Liste de chaînes de caractères représentant des messages d'erreur.

**Retours:**
*   `str`: Le contexte complet, formaté de manière simple.

**Logique Interne:**
1.  Initialise une liste `parts`.
2.  Ajoute l'instruction système.
3.  Si présents, ajoute successivement le fichier actif (tronqué), les erreurs, l'historique de chat (les 4 dernières entrées, messages tronqués) et le contexte RAG (tronqué).
4.  Joint toutes les parties avec des sauts de ligne pour former la chaîne de contexte finale.

### Fonction : `get_context_manager`

```python
def get_context_manager(max_tokens: int = 32000) -> ContextManager:
    """
    Retourne l'instance singleton du gestionnaire de contexte.

    Args:
        max_tokens: Le budget maximum de tokens pour le gestionnaire de contexte
                    lors de sa première initialisation.

    Returns:
        L'instance unique de ContextManager.
    """
    # ...
```

**Description:**
Cette fonction implémente le pattern Singleton pour le `ContextManager`. Elle garantit qu'une seule instance de `ContextManager` est créée et réutilisée à travers l'application, évitant ainsi des initialisations multiples et gérant l'état global du budget de tokens.

**Arguments:**
*   `max_tokens` (`int`, optionnel, défaut: `32000`): Le budget maximum de tokens utilisé pour initialiser l'instance de `ContextManager` si elle n'existe pas encore. Cet argument est ignoré si une instance existe déjà.

**Retours:**
*   `ContextManager`: L'instance unique du gestionnaire de contexte.

**Logique Interne:**
1.  Vérifie si l'instance globale `_context_manager_instance` est `None`.
2.  Si c'est le cas, une nouvelle instance de `ContextManager` est créée avec le `max_tokens` fourni et stockée dans `_context_manager_instance`.
3.  L'instance (nouvellement créée ou existante) est retournée.

## 3. Exemple d'usage

```python
from features.context.context_manager import get_context_manager

# Obtenir l'instance singleton du gestionnaire de contexte
# Le max_tokens sera utilisé lors de la première initialisation.
context_manager = get_context_manager(max_tokens=8000)

# Préparer les données pour le contexte
system_instruction = "Tu es un assistant de code. Aide-moi à déboguer et à écrire du code Python."
active_file_content = """
def my_function(a, b):
    # This function adds two numbers
    return a  +  b + c # Error here: c is not defined
"""
rag_info = "Informations trouvées sur la fonction `my_function` : prend deux arguments et les additionne."
chat_history_data = [
    {"role": "user", "content": "J'ai un problème avec ma fonction `my_function`."},
    {"role": "assistant", "content": "Pouvez-vous me montrer le code ?"},
    {"role": "user", "content": "Oui, voici le code ci-dessus."},
    {"role": "assistant", "content": "Je vois. Y a-t-il des messages d'erreur ?"},
]
compilation_errors = ["NameError: name 'c' is not defined on line 4"]

# Construire le contexte
full_context = context_manager.build_context(
    system_instruction=system_instruction,
    active_file=active_file_content,
    rag_context=rag_info,
    chat_history=chat_history_data,
    errors=compilation_errors
)

print(full_context)

# Si PriomptiPy est disponible, la sortie sera priorisée et tronquée intelligemment.
# Si non, ou en cas d'erreur, elle sera une simple concaténation:

# Exemple de sortie (PriomptiPy activé, priorisation et troncature appliquées):
# --- INSTRUCTION SYSTÈME ---
# Tu es un assistant de code. Aide-moi à déboguer et à écrire du code Python.
#
# --- FICHIER ACTIF ---
# def my_function(a, b):
#     # This function adds two numbers
#     return a  +  b + c # Error here: c is not defined
#
# --- ERREURS ---
# - NameError: name 'c' is not defined on line 4
#
# --- HISTORIQUE RÉCENT ---
# [user]: J'ai un problème avec ma fonction `my_function`.
# [assistant]: Pouvez-vous me montrer le code ?
# [user]: Oui, voici le code ci-dessus.
# [assistant]: Je vois. Y a-t-il des messages d'erreur ?
#
# --- CONTEXTE RAG ---
# Informations trouvées sur la fonction `my_function` : prend deux arguments et les additionne.
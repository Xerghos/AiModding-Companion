# Package `features`

Ce package sert de façade pour le module RAG (Retrieval-Augmented Generation), redirigeant les appels vers le sous-package `context`.

## Dépendances

Aucune dépendance externe déclarée dans ce fichier `__init__.py`. Les dépendances sont gérées au niveau des sous-packages importés.

## Classes & Fonctions

Ce fichier `__init__.py` ne définit pas de classes ou de fonctions directement. Son rôle est d'exporter les fonctions clés du sous-package `context` pour faciliter leur importation au niveau supérieur du package `features`.

Les fonctions suivantes sont importées et rendues disponibles sous le namespace `features` si l'importation du sous-package `context` réussit :

### `handle_load_context`

*   **Signature :** `handle_load_context()`
*   **Arguments :** Aucun.
*   **Retours :** Dépend de l'implémentation dans `features.context`.
*   **Logique interne :** Répercute l'appel vers la fonction `handle_load_context` du sous-package `context`.

### `handle_maj_contexte`

*   **Signature :** `handle_maj_contexte()`
*   **Arguments :** Aucun.
*   **Retours :** Dépend de l'implémentation dans `features.context`.
*   **Logique interne :** Répercute l'appel vers la fonction `handle_maj_contexte` du sous-package `context`.

### `handle_sync_kb_to_drive`

*   **Signature :** `handle_sync_kb_to_drive()`
*   **Arguments :** Aucun.
*   **Retours :** Dépend de l'implémentation dans `features.context`.
*   **Logique interne :** Répercute l'appel vers la fonction `handle_sync_kb_to_drive` du sous-package `context`.

### `handle_delete_drive_kb`

*   **Signature :** `handle_delete_drive_kb()`
*   **Arguments :** Aucun.
*   **Retours :** Dépend de l'implémentation dans `features.context`.
*   **Logique interne :** Répercute l'appel vers la fonction `handle_delete_drive_kb` du sous-package `context`.

### `handle_chat_rag_hybrid`

*   **Signature :** `handle_chat_rag_hybrid()`
*   **Arguments :** Aucun.
*   **Retours :** Dépend de l'implémentation dans `features.context`.
*   **Logique interne :** Répercute l'appel vers la fonction `handle_chat_rag_hybrid` du sous-package `context`.

## Gestion des erreurs d'importation

Le bloc `try...except ImportError` garantit que si le sous-package `context` n'est pas accessible, l'importation du package `features` ne provoquera pas d'erreur fatale. Dans ce scénario de repli (`fallback`), les fonctions mentionnées ci-dessus ne seront pas disponibles sous le namespace `features`.

## Exemple d'usage

```python
# Supposons que le package 'features' et son sous-package 'context' sont correctement installés.

from features import (
    handle_load_context,
    handle_maj_contexte,
    handle_sync_kb_to_drive,
    handle_delete_drive_kb,
    handle_chat_rag_hybrid
)

# Appel des fonctions disponibles via la façade
try:
    handle_load_context()
    print("Contexte chargé avec succès.")

    handle_maj_contexte()
    print("Mise à jour du contexte effectuée.")

    handle_sync_kb_to_drive()
    print("Synchronisation KB vers Drive réussie.")

    # Exemple d'utilisation hypothétique pour la suppression
    # handle_delete_drive_kb("id_du_kb_a_supprimer")

    # Exemple d'utilisation hypothétique pour le chat hybride
    # reponse = handle_chat_rag_hybrid("Quelle est la capitale de la France ?")
    # print(f"Réponse du RAG hybride : {reponse}")

except ImportError:
    print("Erreur: Le sous-package 'context' n'a pas pu être importé.")
except Exception as e:
    print(f"Une erreur est survenue lors de l'appel d'une fonction features : {e}")
# `features\context\__init__.py`

Ce fichier sert d'interface principale pour le module `context`, exposant les fonctions nécessaires à la gestion du contexte RAG (Retrieval-Augmented Generation) et de la synchronisation avec le stockage cloud.

**Dépendances:**
*   `.rag`

---

## Classes & Fonctions

### `handle_load_context`

*   **Signature:** `handle_load_context()`
*   **Arguments:** Aucun.
*   **Retours:** Les données chargées pour le contexte.
*   **Logique interne:** Cette fonction est importée du module `.rag` et est responsable du chargement des données contextuelles. Les détails de son implémentation se trouvent dans `features.context.rag`.

### `handle_maj_contexte`

*   **Signature:** `handle_maj_contexte()`
*   **Arguments:** Aucun.
*   **Retours:** Statut ou informations relatives à la mise à jour du contexte.
*   **Logique interne:** Importée de `.rag`, cette fonction gère la mise à jour du contexte. Les détails sont dans `features.context.rag`.

### `handle_sync_kb_to_drive`

*   **Signature:** `handle_sync_kb_to_drive()`
*   **Arguments:** Aucun.
*   **Retours:** Statut ou informations relatives à la synchronisation de la base de connaissances avec le stockage cloud.
*   **Logique interne:** Importée de `.rag`, cette fonction orchestre la synchronisation de la base de connaissances avec le stockage cloud. Voir `features.context.rag` pour les détails.

### `handle_delete_drive_kb`

*   **Signature:** `handle_delete_drive_kb()`
*   **Arguments:** Aucun.
*   **Retours:** Statut ou informations relatives à la suppression d'une base de connaissances du stockage cloud.
*   **Logique interne:** Importée de `.rag`, cette fonction gère la suppression d'une base de connaissances du stockage cloud. Les détails sont disponibles dans `features.context.rag`.

### `handle_chat_rag_hybrid`

*   **Signature:** `handle_chat_rag_hybrid()`
*   **Arguments:** Aucun.
*   **Retours:** Résultat de la fonction de chat RAG hybride.
*   **Logique interne:** Importée de `.rag`, cette fonction est utilisée pour exécuter une logique de chat hybride RAG. L'implémentation détaillée se trouve dans `features.context.rag`.

---

## Exemple d'usage

Bien que ce fichier soit principalement une façade, voici comment les fonctions importées pourraient être utilisées dans un autre module :

```python
# Dans un autre fichier Python, par exemple features/chatbot.py

from features.context import (
    handle_load_context,
    handle_maj_contexte,
    handle_sync_kb_to_drive,
    handle_delete_drive_kb,
    handle_chat_rag_hybrid
)

def main_chatbot_workflow():
    # Charger le contexte initial
    context_data = handle_load_context()
    print("Contexte chargé:", context_data)

    # Mettre à jour le contexte si nécessaire
    update_status = handle_maj_contexte()
    print("Statut de mise à jour du contexte:", update_status)

    # Synchroniser la base de connaissances avec le stockage cloud
    sync_status = handle_sync_kb_to_drive()
    print("Statut de synchronisation KB vers Drive:", sync_status)

    # Supprimer une base de connaissances du stockage cloud (exemple)
    # delete_status = handle_delete_drive_kb("nom_de_la_kb_a_supprimer")
    # print("Statut de suppression KB depuis Drive:", delete_status)

    # Exécuter une session de chat RAG hybride
    chat_response = handle_chat_rag_hybrid("Quelle est la capitale de la France ?")
    print("Réponse du chat RAG hybride:", chat_response)

if __name__ == "__main__":
    main_chatbot_workflow()
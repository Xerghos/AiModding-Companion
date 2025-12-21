# Documentation Technique - `analyze_payload_issues.py`

## En-tête

*   **Titre**: `analyze_payload_issues.py` - Script d'analyse des problèmes de digestibilité des charges utiles (payloads)
*   **Description concise**: Ce script Python est conçu pour analyser des fichiers JSON de payloads et d'historiques de chat afin d'identifier divers problèmes qui pourraient affecter la "digestibilité" du contenu par un modèle de langage (LLM). Il détecte les échappements doubles, les caractères Unicode échappés, les messages vides, et mesure la taille de différentes sections.
*   **Dépendances**:
    *   `json`: Pour la manipulation des données JSON.
    *   `re`: Pour les opérations d'expressions régulières (recherche d'échappements Unicode).
    *   `os`: Pour les interactions avec le système d'exploitation (vérification de l'existence des fichiers).
    *   `pathlib`: (Importé mais non utilisé directement dans le code fourni).
    *   `sys`: Pour l'accès aux paramètres système (gestion de l'encodage de la sortie standard).
    *   `io`: Pour la gestion des flux d'E/S (encodage de la sortie standard).

## Fonctions

### `analyze_payload_file(filepath)`

*   **Signature**: `analyze_payload_file(filepath: str) -> dict | None`
*   **Arguments**:
    *   `filepath` (str): Le chemin complet vers le fichier JSON de payload à analyser.
*   **Retours**:
    *   `dict`: Un dictionnaire contenant les statistiques et les problèmes détectés dans le fichier payload. Le dictionnaire inclut les clés suivantes :
        *   `double_escaped_quotes` (int): Nombre de guillemets doubles échappés ( `\"` ).
        *   `double_escaped_newlines` (int): Nombre de sauts de ligne échappés ( `\n` ).
        *   `unicode_escapes` (int): Nombre total de séquences d'échappement Unicode ( `\uXXXX` ).
        *   `empty_messages` (int): Nombre de messages dont le contenu est vide ou ne contient que des espaces.
        *   `duplicate_content` (int): (Actuellement non implémenté dans la logique fournie, toujours 0).
        *   `total_size` (int): Taille totale en caractères de tous les contenus de messages combinés.
        *   `arch_json_size` (int): Taille en caractères du message identifié comme "CARTOGRAPHIE TECHNIQUE".
        *   `rag_context_size` (int): Taille en caractères du message identifié comme "RAG CONTEXT".
    *   `None`: Si le fichier spécifié par `filepath` est introuvable.
*   **Logique interne**:
    1.  Vérifie l'existence du fichier. Si le fichier n'existe pas, affiche un message d'erreur et retourne `None`.
    2.  Ouvre et charge le fichier JSON.
    3.  Initialise un dictionnaire `issues` avec des compteurs à zéro.
    4.  Si le JSON contient une clé `'messages'`, itère sur chaque message dans la liste.
    5.  Pour chaque message :
        *   Récupère le contenu du message.
        *   Ajoute la longueur du contenu à `total_size`.
        *   Incrémente `empty_messages` si le contenu est vide ou ne contient que des espaces.
        *   Compte les occurrences de `\"` pour `double_escaped_quotes`.
        *   Compte les occurrences de `\n` pour `double_escaped_newlines`.
        *   Utilise une expression régulière (`r'\\u[0-9a-fA-F]{4}'`) pour trouver et compter les séquences d'échappement Unicode.
        *   Si le contenu contient la chaîne `'CARTOGRAPHIE TECHNIQUE'`, enregistre sa taille dans `arch_json_size` et compte spécifiquement les `\"` dans cette partie du contenu.
        *   Si le contenu contient la chaîne `'RAG CONTEXT'`, enregistre sa taille dans `rag_context_size`.
    6.  Retourne le dictionnaire `issues` rempli.

### `analyze_history_file(filepath)`

*   **Signature**: `analyze_history_file(filepath: str) -> dict | None`
*   **Arguments**:
    *   `filepath` (str): Le chemin complet vers le fichier JSON d'historique de chat à analyser.
*   **Retours**:
    *   `dict`: Un dictionnaire contenant les statistiques et les problèmes détectés dans le fichier d'historique. Le dictionnaire inclut les clés suivantes :
        *   `unicode_escapes` (int): Nombre total de séquences d'échappement Unicode ( `\uXXXX` ).
        *   `empty_messages` (int): Nombre de messages dont le contenu est vide ou ne contient que des espaces.
        *   `duplicate_content` (int): (Actuellement non implémenté dans la logique fournie, toujours 0).
        *   `total_size` (int): Taille totale en caractères de tous les contenus de messages combinés.
        *   `messages_with_escapes` (int): Nombre de messages contenant au moins une séquence d'échappement Unicode.
    *   `None`: Si le fichier spécifié par `filepath` est introuvable.
*   **Logique interne**:
    1.  Vérifie l'existence du fichier. Si le fichier n'existe pas, affiche un message d'erreur et retourne `None`.
    2.  Ouvre et charge le fichier JSON.
    3.  Initialise un dictionnaire `issues` avec des compteurs à zéro.
    4.  Itère sur chaque message dans la liste (le fichier d'historique est supposé être une liste de messages).
    5.  Pour chaque message :
        *   Récupère le contenu du message.
        *   Ajoute la longueur du contenu à `total_size`.
        *   Incrémente `empty_messages` si le contenu est vide ou ne contient que des espaces.
        *   Utilise une expression régulière (`r'\\u[0-9a-fA-F]{4}'`) pour trouver les séquences d'échappement Unicode.
        *   Si des échappements Unicode sont trouvés, incrémente `messages_with_escapes` et ajoute le nombre d'échappements à `unicode_escapes`.
    6.  Retourne le dictionnaire `issues` rempli.

## Exemple d'usage

Pour utiliser ce script, exécutez-le directement depuis la ligne de commande. Il tentera d'analyser deux fichiers spécifiques : `debug_deepseek_payload.json` et `full_chat_history.json`, qui doivent être présents dans le même répertoire que le script.

```bash
python scripts/analyze_payload_issues.py
```

**Exemple de sortie attendue (le contenu exact dépendra des fichiers JSON analysés):**

```
================================================================================
ANALYSE DES PROBLEMES DE DIGESTIBILITE DES PAYLOADS
================================================================================

[ANALYSE] debug_deepseek_payload.json
--------------------------------------------------------------------------------
Taille totale : 123,456 caractères
Guillemets échappés (") : 1,234
Sauts de ligne échappés (\n) : 567
Échappements Unicode (\uXXXX) : 89
Messages vides : 2
Taille JSON architecture : 45,678 caractères
Taille RAG context : 34,567 caractères

[ANALYSE] full_chat_history.json
--------------------------------------------------------------------------------
Taille totale : 98,765 caractères
Échappements Unicode (\uXXXX) : 123
Messages avec échappements : 5
Messages vides : 1

================================================================================
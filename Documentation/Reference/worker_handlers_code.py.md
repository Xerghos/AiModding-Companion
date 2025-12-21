# Documentation Technique : worker/handlers/code.py

## Description Concise

Ce module contient les gestionnaires de requêtes pour les opérations liées au code. Il permet d'analyser la qualité et la sécurité d'un fichier, d'appliquer des refactorisations selon des instructions spécifiques, et de générer automatiquement la documentation d'un fichier. Chaque fonction de gestion utilise une session IA configurée avec un type de modèle approprié (reasoning, architect, writer) via `SessionFactory`. Les fonctions sont décorées avec `trace_action` pour le suivi des actions.

## Dépendances

*   `logging`: Module standard Python pour la journalisation.
*   `ai_core.SessionFactory`: Classe pour créer des sessions d'IA.
*   `features.Decorators.trace_action`: Décorateur pour tracer les actions.
*   `features.CodeQuality`: Module pour l'analyse de qualité du code.
*   `features.Refactoring`: Module pour le refactoring du code.
*   `features.Documentation`: Module pour la génération de documentation.

## Classes & Fonctions

### `handle_analyze_file(payload)`

*   **Signature :** `def handle_analyze_file(payload)`
*   **Arguments :**
    *   `payload` (dict) : Dictionnaire contenant les données de la requête. Doit inclure la clé `"file_path"` (str) spécifiant le chemin du fichier à analyser.
*   **Retours :**
    *   `str` : Un message d'erreur si le `"file_path"` est manquant.
    *   Le résultat de la fonction `CodeQuality.audit_code` si l'analyse réussit.
*   **Logique interne :**
    1.  Récupère le chemin du fichier (`file_path`) à partir du `payload`.
    2.  Vérifie si `file_path` est présent. Si absent, retourne un message d'erreur.
    3.  Crée une session IA de type `"reasoning"` en utilisant `SessionFactory.create_session()`.
    4.  Appelle la fonction `CodeQuality.audit_code` avec le chemin du fichier et la session IA créée.
    5.  Retourne le résultat de `CodeQuality.audit_code`.
*   **Décorateurs :** `@trace_action(source="code")`

### `handle_refactor(payload)`

*   **Signature :** `def handle_refactor(payload)`
*   **Arguments :**
    *   `payload` (dict) : Dictionnaire contenant les données de la requête. Doit inclure la clé `"file_path"` (str) spécifiant le chemin du fichier à refactoriser. Peut inclure la clé optionnelle `"instructions"` (str) pour spécifier les consignes de refactoring (par défaut : "Améliorer le code selon les standards.").
*   **Retours :**
    *   `str` : Un message d'erreur si le `"file_path"` est manquant.
    *   Le résultat de la fonction `Refactoring.apply_refactor` si le refactoring réussit.
*   **Logique interne :**
    1.  Récupère le chemin du fichier (`file_path`) et les instructions (`instructions`) à partir du `payload`. Les instructions ont une valeur par défaut.
    2.  Vérifie si `file_path` est présent. Si absent, retourne un message d'erreur.
    3.  Journalise l'information de demande de refactoring.
    4.  Crée une session IA de type `"architect"` en utilisant `SessionFactory.create_session()`.
    5.  Appelle la fonction `Refactoring.apply_refactor` avec le chemin du fichier, les instructions et la session IA créée.
    6.  Retourne le résultat de `Refactoring.apply_refactor`.
*   **Décorateurs :** `@trace_action(source="code")`

### `handle_gen_doc(payload)`

*   **Signature :** `def handle_gen_doc(payload)`
*   **Arguments :**
    *   `payload` (dict) : Dictionnaire contenant les données de la requête. Doit inclure la clé `"file_path"` (str) spécifiant le chemin du fichier pour lequel générer la documentation.
*   **Retours :**
    *   `str` : Un message d'erreur si le `"file_path"` est manquant.
    *   Le résultat de la fonction `Documentation.generate_doc` si la génération de documentation réussit.
*   **Logique interne :**
    1.  Récupère le chemin du fichier (`file_path`) à partir du `payload`.
    2.  Vérifie si `file_path` est présent. Si absent, retourne un message d'erreur.
    3.  Journalise l'information de demande de génération de documentation.
    4.  Crée une session IA de type `"writer"` en utilisant `SessionFactory.create_session()`.
    5.  Appelle la fonction `Documentation.generate_doc` avec le chemin du fichier et la session IA créée.
    6.  Retourne le résultat de `Documentation.generate_doc`.
*   **Décorateurs :** `@trace_action(source="code")`

## Exemple d'usage

Bien que ce module contienne des gestionnaires de requêtes qui sont généralement appelés par un système de messagerie ou un framework web, voici un exemple illustratif de comment ces fonctions pourraient être appelées avec des données simulées :

```python
# Simulation d'un payload pour l'analyse de fichier
payload_analyze = {
    "file_path": "/chemin/vers/votre/fichier.py"
}
result_analyze = handle_analyze_file(payload_analyze)
print(f"Résultat de l'analyse : {result_analyze}")

# Simulation d'un payload pour le refactoring
payload_refactor = {
    "file_path": "/chemin/vers/votre/fichier_a_refactoriser.py",
    "instructions": "Optimiser les boucles et améliorer la lisibilité."
}
result_refactor = handle_refactor(payload_refactor)
print(f"Résultat du refactoring : {result_refactor}")

# Simulation d'un payload pour la génération de documentation
payload_doc = {
    "file_path": "/chemin/vers/votre/module_source.py"
}
result_doc = handle_gen_doc(payload_doc)
print(f"Résultat de la génération de documentation : {result_doc}")

# Simulation d'un payload invalide
payload_invalid = {}
result_invalid = handle_analyze_file(payload_invalid)
print(f"Résultat avec payload invalide : {result_invalid}")
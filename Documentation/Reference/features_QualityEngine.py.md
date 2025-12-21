# Moteur de Qualité (QualityEngine.py)

## Description concise

Ce module implémente un moteur de validation itérative multi-agents (V2) appelé `QualityLoop`. Il orchestre un dialogue entre un Agent 'Générateur' et un Agent 'Critique' pour améliorer et valider la qualité d'un contenu généré en fonction d'une tâche donnée. La boucle s'arrête soit lorsque le score atteint un seuil minimum (`min_score`), soit lorsque le nombre maximum d'itérations (`max_iterations`) est atteint.

## Dépendances

*   `logging`: Pour la journalisation des événements.
*   `re`: Pour l'analyse des chaînes de caractères (extraction de scores).
*   `time`: Potentiellement pour des délais, bien qu'actuellement non utilisé explicitement dans le code fourni.
*   `config.logs.get_logger`: Pour obtenir une instance de logger configurée.
*   `ai_core.sessions.call_ai_robust`: Fonction pour interagir de manière robuste avec une IA (non utilisée directement dans `QualityLoop` mais potentiellement en amont ou en aval).
*   `features.Decorators.trace_action`: Décorateur pour tracer l'exécution des actions.
*   `agents.swarm_manager.create_agent`: Fonction pour créer des agents (importation dynamique pour éviter les cycles).

---

## Classes

### `QualityLoop`

Moteur de validation itérative multi-agents (V2). Orchestre un dialogue entre un Agent 'Générateur' et un Agent 'Critique'.

#### `__init__(self, session, max_iterations=3, min_score=85)`

Initialise le moteur de qualité.

*   **Arguments:**
    *   `session`: Session 'Worker' parente. Nécessaire pour la création des agents.
    *   `max_iterations` (int, optional): Nombre maximum d'itérations pour la boucle de qualité. Par défaut à 3.
    *   `min_score` (int, optional): Score minimum requis (sur 100) pour considérer le contenu comme validé. Par défaut à 85.

*   **Logique interne:**
    Stocke la session parente, le nombre maximum d'itérations et le score minimum requis comme attributs de l'instance.

#### `_parse_score(self, review_text)`

Extrait le score numérique (0-100) à partir du texte de la critique.

*   **Arguments:**
    *   `review_text` (str): Le texte de la critique contenant potentiellement le score.

*   **Retours:**
    *   `int`: Le score extrait (entre 0 et 100). Retourne 0 si aucun score valide n'est trouvé ou en cas d'erreur d'extraction.

*   **Logique interne:**
    Utilise une liste d'expressions régulières (`patterns`) pour rechercher des formats courants de score (ex: "Score: XX/100", "Note: XX", "XX/100"). Si un motif correspond, tente de convertir la valeur capturée en entier. Le score est ensuite borné entre 0 et 100. Si aucun motif ne correspond ou si la conversion échoue, retourne 0.

#### `run_cycle(self, task_prompt, generator_role="CODER", validator_role="REVIEWER")`

Lance la boucle de qualité itérative.

*   **Arguments:**
    *   `task_prompt` (str): Le prompt initial décrivant la tâche à accomplir.
    *   `generator_role` (str, optional): Le rôle de l'agent responsable de la génération et de la correction du contenu. Par défaut à "CODER".
    *   `validator_role` (str, optional): Le rôle de l'agent responsable de l'évaluation et de la critique du contenu. Par défaut à "REVIEWER".

*   **Retours:**
    *   `str`: Un message indiquant le résultat final. Si la qualité est validée, il inclut le score et le contenu final. Si la limite d'itérations est atteinte, il indique cela avec le dernier score et une partie de la critique. En cas d'indisponibilité du Swarm Manager, retourne un message d'erreur.

*   **Logique interne:**
    1.  **Vérification des dépendances:** S'assure que `create_agent` est disponible. Sinon, retourne un message d'erreur.
    2.  **Génération Initiale:** Crée un agent avec le `generator_role` et l'utilise pour exécuter la `task_prompt`. Le contenu résultant est stocké.
    3.  **Boucle d'Amélioration:** Itère jusqu'à `max_iterations`.
        a.  **Critique:** Crée un agent avec le `validator_role`. Construit un prompt pour l'évaluation incluant la tâche originale, le contenu actuel (tronqué à 20000 caractères pour éviter les limites de token), et des instructions claires sur le format de sortie attendu (doit commencer par "Score: XX/100"). Le résultat de la critique est récupéré.
        b.  **Extraction du Score:** Utilise `_parse_score` pour obtenir le score de la critique.
        c.  **Décision:**
            *   Si `score >= self.min_score`, la qualité est validée. La fonction retourne un message de succès avec le score et le contenu.
            *   Si c'est la dernière itération (`i == self.max_iterations - 1`), la limite est atteinte. La fonction retourne un message d'avertissement avec le score final, le contenu et les premières 500 caractères de la dernière critique.
        d.  **Correction:** Si la qualité n'est pas validée et que ce n'est pas la dernière itération, un prompt de correction est construit. Il inclut le score obtenu, les critiques du reviewer, et la tâche de réécrire le contenu pour corriger les points soulevés. L'agent générateur exécute ce prompt, et le `current_content` est mis à jour avec le résultat.
    4.  **Retour Final:** Si la boucle se termine sans validation (ce qui ne devrait arriver que si `max_iterations` est 0 ou 1 et que le score initial est insuffisant), le dernier `current_content` est retourné.

---

## Fonctions

### `execute_quality_cycle(prompt, session, gen_role="CODER", val_role="REVIEWER")`

Fonction d'aide pour lancer un cycle de qualité de manière simplifiée.

*   **Arguments:**
    *   `prompt` (str): Le prompt initial pour la tâche.
    *   `session`: La session 'Worker' parente.
    *   `gen_role` (str, optional): Le rôle de l'agent générateur. Par défaut à "CODER".
    *   `val_role` (str, optional): Le rôle de l'agent validateur. Par défaut à "REVIEWER".

*   **Retours:**
    *   Le résultat de `QualityLoop.run_cycle`.

*   **Logique interne:**
    Crée une instance de `QualityLoop` avec la session fournie, puis appelle sa méthode `run_cycle` avec les arguments donnés.

---

## Exemple d'usage

```python
# Assurez-vous que les dépendances sont correctement importées et configurées
# from my_app.sessions import get_current_session # Exemple
# from features.QualityEngine import execute_quality_cycle

# session = get_current_session() # Obtenir la session actuelle
# task_description = "Écris une fonction Python simple pour additionner deux nombres."

# # Lancer le cycle de qualité avec les rôles par défaut
# result = execute_quality_cycle(task_description, session)
# print(result)

# # Lancer le cycle de qualité avec des rôles personnalisés et plus d'itérations
# result_custom = execute_quality_cycle(
#     task_description,
#     session,
#     gen_role="PYTHON_DEVELOPER",
#     val_role="CODE_AUDITOR"
# )
# print(result_custom)

# # Pour utiliser directement la classe QualityLoop :
# quality_engine = QualityLoop(session, max_iterations=5, min_score=90)
# result_direct = quality_engine.run_cycle(task_description)
# print(result_direct)
```
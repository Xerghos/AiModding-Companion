# Documentation Technique : `tests\test_security.py`

## Description concise

Ce fichier contient des tests unitaires pour vérifier la robustesse des mécanismes de sécurité implémentés dans l'application, notamment le middleware de sécurité qui intercepte les appels aux outils natifs. Les tests visent à s'assurer que :
1. Les accès légitimes aux fichiers sont autorisés.
2. Les tentatives de sortie du répertoire du projet (confinement) sont bloquées.
3. Les fichiers critiques (comme la configuration) sont protégés contre les modifications non autorisées.

## Dépendances

*   `sys`
*   `os`
*   `config.settings.load_app_settings`
*   `features.ai_helper.execute_native_tool`

---

## Classes & Fonctions

### Fonction : `test_security_middleware()`

*   **Signature :** `def test_security_middleware():`
*   **Arguments :** Aucune.
*   **Retours :** Aucune. La fonction imprime les résultats des tests directement dans la console.
*   **Logique interne :**
    1.  Imprime un message indiquant le début des tests de sécurité.
    2.  Appelle `load_app_settings()` pour s'assurer que les paramètres de sécurité sont correctement chargés.
    3.  Initialise un dictionnaire `mock_args` avec des valeurs `None` pour les objets `session`, `action_log_path`, `result_queue`, et `task_queue`. Ces objets ne sont pas nécessaires car le middleware de sécurité doit intercepter les appels avant leur utilisation.
    4.  **Test 1 : Accès Légitime**
        *   Imprime un message décrivant le test.
        *   Appelle `execute_native_tool` pour lire le fichier `README.md` (un fichier légitime).
        *   Vérifie si la réponse ne contient pas les marqueurs d'erreur de sécurité ("⛔ SÉCURITÉ", "❌").
        *   Imprime un message de succès ou d'échec basé sur le résultat.
    5.  **Test 2 : Confinement (Jailbreak)**
        *   Imprime un message décrivant le test.
        *   Appelle `execute_native_tool` pour lire un fichier situé en dehors du répertoire du projet (`../outside.txt`).
        *   Vérifie si la réponse contient les marqueurs spécifiques à l'interdiction d'accès hors du projet ("⛔ SÉCURITÉ", "Accès interdit hors du projet").
        *   Imprime un message de succès ou d'échec basé sur le résultat.
    6.  **Test 3 : Protection Fichiers Critiques**
        *   Imprime un message décrivant le test.
        *   Appelle `execute_native_tool` pour tenter d'écrire dans le fichier de configuration `config/settings.py`.
        *   Vérifie si la réponse contient les marqueurs spécifiques à la protection des fichiers critiques ("⛔ SÉCURITÉ", "protégé contre la modification").
        *   Gère également un cas où l'interception pourrait échouer et le test continuerait, signalant une erreur critique.
        *   Imprime un message de succès, d'échec, ou de résultat inattendu basé sur le résultat.

---

## Exemple d'usage

Ce fichier est conçu pour être exécuté en tant que script de test autonome. Il n'a pas d'exemple d'usage direct dans le sens d'une intégration dans une autre partie du code.

Pour exécuter ces tests, vous pouvez naviguer dans le répertoire contenant ce fichier et lancer :

```bash
python tests/test_security.py
```

ou si vous utilisez un outil de test comme `pytest` :

```bash
pytest tests/test_security.py
# Documentation Technique : `tests\test_swarm_setup.py`

## Description concise

Ce fichier contient des tests unitaires pour vérifier la bonne initialisation et configuration des agents de swarm (swarm agents) lors du lancement de l'application. Il s'assure que les agents sont créés avec les instructions système appropriées, notamment en ce qui concerne la présence ou l'absence d'outils autorisés en fonction de leur rôle ("CODER", "ROUTER").

## Dépendances

*   `sys` : Module système pour interagir avec l'interpréteur Python (gestion du `sys.path`, sortie du script).
*   `os` : Module système pour interagir avec le système d'exploitation (gestion des chemins de fichiers).
*   `agents.swarm_manager.create_agent` : Fonction pour créer des instances d'agents de swarm.
*   `config.settings.load_app_settings` : Fonction pour charger les paramètres de l'application, nécessaire pour initialiser certains composants internes (comme `SessionFactory`).

---

## Fonctions

### `test_swarm_initialization()`

#### Signature

```python
def test_swarm_initialization():
```

#### Arguments

Aucun.

#### Retour

Aucun (imprime les résultats des tests dans la console).

#### Logique interne

1.  **Affichage de l'en-tête du test :** Imprime un message indicatif du début des tests du swarm.
2.  **Chargement des paramètres :** Appelle `load_app_settings()` pour s'assurer que la configuration de l'application est chargée. Ceci est crucial pour éviter des erreurs lors de l'initialisation des agents qui pourraient dépendre de ces paramètres (par exemple, la configuration de la base de données ou des services externes).
3.  **Test 1 : Agent "CODER" (Expert avec Outils)**
    *   Affiche une description du test en cours.
    *   Tente de créer une instance d'agent avec le nom "CODER" en utilisant `create_agent("CODER")`.
    *   En cas de succès, imprime un message de succès et affiche le niveau (tier) de l'agent.
    *   **Vérification du prompt système :** Récupère l'instruction système de l'agent (`coder.system_instruction`). Elle vérifie si ce prompt contient à la fois la chaîne "MANUEL DES OUTILS AUTORISÉS" et la chaîne "lire\_fichier". Ces vérifications visent à s'assurer que l'agent "CODER" est correctement configuré pour avoir accès à ses outils.
    *   En cas de succès de la vérification du prompt, imprime un message de succès.
    *   En cas d'échec, imprime un message d'échec et un extrait du prompt pour faciliter le débogage.
    *   En cas d'exception lors de la création de l'agent ou de la vérification, imprime un message d'erreur critique et utilise `traceback.print_exc()` pour afficher la pile d'appels détaillée.
4.  **Test 2 : Agent "ROUTER" (Fast sans Outils)**
    *   Affiche une description du test en cours.
    *   Tente de créer une instance d'agent avec le nom "ROUTER" en utilisant `create_agent("ROUTER")`.
    *   En cas de succès, imprime un message de succès et affiche le niveau (tier) de l'agent.
    *   **Vérification du prompt système :** Récupère l'instruction système de l'agent (`router.system_instruction`). Elle vérifie si ce prompt **ne contient pas** la chaîne "MANUEL DES OUTILS AUTORISÉS". Cela confirme que l'agent "ROUTER" est bien configuré pour ne pas avoir d'outils.
    *   En cas de succès de la vérification, imprime un message de succès.
    *   En cas d'échec (présence inattendue des outils), imprime un message d'avertissement.
    *   En cas d'exception lors de la création de l'agent ou de la vérification, imprime un message d'erreur critique.

---

## Exemple d'usage

Ce fichier est destiné à être exécuté directement dans le cadre de la suite de tests, par exemple via un runner de tests comme `pytest` ou en l'exécutant directement avec `python tests/test_swarm_setup.py`.

Si exécuté directement :

```bash
python tests/test_swarm_setup.py
```

**Sortie attendue (en cas de succès) :**

```
--- 🧪 TEST DIAGNOSTIC SWARM V2 ---

🔹 [1] Test Initialisation 'CODER' (Expert + Outils)
✅ Instance créée avec succès.
ℹ️  Modèle Tier détecté : expert
✅ SUCCÈS : Le Prompt contient bien le manuel des outils.

🔹 [2] Test Initialisation 'ROUTER' (Fast + Sans Outils)
✅ Instance créée avec succès.
ℹ️  Modèle Tier détecté : fast
✅ SUCCÈS : Le Prompt est propre (pas d'outils).
```

**Sortie attendue (en cas d'échec pour le CODER) :**

```
--- 🧪 TEST DIAGNOSTIC SWARM V2 ---

🔹 [1] Test Initialisation 'CODER' (Expert + Outils)
❌ CRASH : Impossible de créer l'agent CODER. Détail : ...
Traceback (most recent call last):
  ...
```

**Sortie attendue (en cas d'échec pour le ROUTER) :**

```
--- 🧪 TEST DIAGNOSTIC SWARM V2 ---

🔹 [1] Test Initialisation 'CODER' (Expert + Outils)
✅ Instance créée avec succès.
ℹ️  Modèle Tier détecté : expert
✅ SUCCÈS : Le Prompt contient bien le manuel des outils.

🔹 [2] Test Initialisation 'ROUTER' (Fast + Sans Outils)
✅ Instance créée avec succès.
ℹ️  Modèle Tier détecté : fast
⚠️ AVERTISSEMENT : Le Router a reçu des outils (Inattendu).
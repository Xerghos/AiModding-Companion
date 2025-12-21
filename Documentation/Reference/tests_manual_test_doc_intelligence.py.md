# Documentation Technique : `tests\manual_test_doc_intelligence.py`

## Description concise

Ce script `manual_test_doc_intelligence.py` sert de test manuel pour évaluer la capacité d'un agent "WRITER" à documenter le code source d'un fichier Python qui a une dépendance externe. Il simule un scénario où le fichier cible importe une fonction depuis un autre fichier (simulant ainsi une dépendance). Le test vise à vérifier si l'agent peut non seulement comprendre le code du fichier cible mais aussi explorer et documenter la logique de sa dépendance, en particulier lorsque celle-ci contient une opération spécifique (ici, un calcul mathématique).

## Dépendances

*   **Python 3.x**
*   **Bibliothèques standard Python :**
    *   `os` : Pour les opérations liées au système d'exploitation (chemins, création de dossiers).
    *   `sys` : Pour interagir avec l'interpréteur Python (ajout de chemins au `sys.path`).
    *   `shutil` : Pour les opérations de haut niveau sur les fichiers et répertoires (suppression, copie).
    *   `time` : Potentiellement utilisé pour des temporisations (bien que non explicitement utilisé dans la version fournie).
*   **Bibliothèques externes / modules du projet :**
    *   `agents.swarm_manager.create_agent` : Fonction pour instancier un agent du swarm.
    *   `config.paths.get_path` : Fonction pour obtenir des chemins de configuration, utilisée ici pour définir le répertoire de sandbox.

---

## Classes & Fonctions

### Fonction `setup_sandbox()`

#### Signature

```python
def setup_sandbox() -> str
```

#### Arguments

*   Aucun.

#### Retours

*   `str`: Le chemin absolu du répertoire de sandbox créé.

#### Logique interne

1.  Définit le chemin du répertoire de sandbox en utilisant `get_path("sandbox_test_doc")`.
2.  Vérifie si le répertoire de sandbox existe déjà. Si c'est le cas, il est supprimé à l'aide de `shutil.rmtree()`.
3.  Crée le répertoire de sandbox s'il n'existe pas ou s'il a été supprimé, en utilisant `os.makedirs()`.
4.  Crée un fichier `secret_utils.py` dans le répertoire de sandbox. Ce fichier contient une fonction `operation_secrete(valeur)` qui multiplie la valeur d'entrée par 999 et ajoute 1.
5.  Crée un fichier `main_app.py` dans le répertoire de sandbox. Ce fichier importe la fonction `operation_secrete` de `secret_utils` et définit une fonction `process_data(data)` qui appelle `operation_secrete` avec la donnée fournie.
6.  Affiche un message de succès indiquant la création du sandbox.
7.  Retourne le chemin du répertoire de sandbox créé.

### Fonction `run_test()`

#### Signature

```python
def run_test() -> None
```

#### Arguments

*   Aucun.

#### Retours

*   `None`.

#### Logique interne

1.  Appelle `setup_sandbox()` pour créer l'environnement de test et obtient le chemin du sandbox.
2.  Définit le chemin complet du fichier cible (`main_app.py`) à l'intérieur du sandbox.
3.  Affiche des messages indiquant le début du test et l'instruction donnée à l'agent.
4.  **Crée un agent de type "WRITER"** en utilisant `create_agent("WRITER", reasoning_mode=False)`. Le `reasoning_mode=False` indique un mode d'exécution plus rapide, mais l'agent est censé utiliser ses outils si nécessaire pour comprendre le code.
5.  Construit un prompt détaillé pour l'agent WRITER, lui demandant de documenter `main_app.py`, d'expliquer précisément la fonction `process_data`, et de rechercher la définition de `operation_secrete` s'il ne la connaît pas.
6.  Exécute la tâche de l'agent en appelant `agent.execute_task(prompt)`. La logique de gestion des outils et de l'exécution est supposée être gérée par le framework `swarm_manager`.
7.  Récupère le texte de la réponse de l'agent. S'il y a un attribut `text`, il l'utilise ; sinon, il convertit la réponse entière en chaîne de caractères.
8.  Affiche la réponse de l'agent de manière formatée.
9.  **Vérifie le succès du test :** Il recherche la présence des mots clés "999", "multiplie", ou "ajoute 1" dans la documentation générée. Si l'un de ces termes est présent, le test est considéré comme un succès, indiquant que l'agent a correctement analysé la dépendance `secret_utils.py`. Sinon, il est considéré comme un échec, suggérant que l'agent n'a pas approfondi l'analyse de la dépendance.
10. Capture et affiche toute exception survenant pendant le processus, indiquant une erreur technique.

---

## Exemple d'usage

Ce script est conçu pour être exécuté directement comme un test unitaire ou manuel.

```bash
python tests/manual_test_doc_intelligence.py
```

**Sortie attendue (similaire à) :**

```
✅ Sandbox créé : C:\chemin\vers\votre\projet\sandbox_test_doc

🤖 Lancement de l'Agent WRITER (Mode Investigation)...
Instruction : Documente 'main_app.py'.

==================================================
📄 RÉSULTAT DE LA DOCUMENTATION :
==================================================
Le fichier `main_app.py` contient la fonction `process_data(data)`.

Cette fonction a pour rôle de traiter les données d'entrée `data` en appliquant une transformation spécifique. Elle utilise pour cela une fonction externe nommée `operation_secrete` importée depuis le module `secret_utils`.

Spécifiquement, la fonction `operation_secrete` prend la valeur fournie (`data`) et effectue le calcul suivant : elle multiplie la valeur par 999, puis ajoute 1 au résultat.

Ainsi, `process_data(data)` retourne le résultat de `(data * 999) + 1`.

==================================================

🎉 SUCCÈS : L'agent a lu 'secret_utils.py' et a trouvé la logique cachée !
```

*(Note : Le chemin du sandbox et la formulation exacte de la documentation peuvent varier légèrement.)*
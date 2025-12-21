# worker.py

Ce module fournit la classe principale `Worker` pour gérer l'exécution de tâches dans des processus séparés.

**Dépendances :**
* Aucune dépendance externe. Utilise des modules standards de Python comme `multiprocessing`.

---

## Classes & Fonctions

### Classe `Worker`

Représente un travailleur capable d'exécuter des tâches dans un processus distinct.

#### Méthode `__init__`

```python
def __init__(self, target, args=(), kwargs=None):
```

*   **Description :** Initialise un objet `Worker`.
*   **Arguments :**
    *   `target` (callable) : La fonction à exécuter par le worker.
    *   `args` (tuple, optionnel) : Les arguments positionnels à passer à la fonction `target`. Par défaut, un tuple vide.
    *   `kwargs` (dict, optionnel) : Les arguments nommés à passer à la fonction `target`. Par défaut, `None` (représente un dictionnaire vide).
*   **Retour :** Aucun.
*   **Logique interne :**
    1. Stocke la fonction `target`, les arguments positionnels `args` et les arguments nommés `kwargs`.
    2. Initialise une variable `_process` à `None`. Cette variable contiendra l'instance `multiprocessing.Process` une fois le worker démarré.

#### Méthode `start`

```python
def start(self):
```

*   **Description :** Démarre le processus worker.
*   **Arguments :** Aucun.
*   **Retour :** Aucun.
*   **Logique interne :**
    1. Vérifie si un processus `_process` existe déjà. Si oui, lève une `RuntimeError`.
    2. Crée une nouvelle instance de `multiprocessing.Process`, en passant la fonction `target` et ses arguments `args` et `kwargs` à l'argument `target` du constructeur `Process`.
    3. Stocke cette nouvelle instance dans `self._process`.
    4. Appelle la méthode `start()` du processus `multiprocessing.Process` pour démarrer l'exécution.

#### Méthode `join`

```python
def join(self, timeout=None):
```

*   **Description :** Attend que le processus worker se termine.
*   **Arguments :**
    *   `timeout` (float, optionnel) : Le nombre de secondes à attendre avant de renvoyer. Si `None` (par défaut), attend indéfiniment.
*   **Retour :** Aucun.
*   **Logique interne :**
    1. Vérifie si un processus `_process` existe. Si non, lève une `RuntimeError`.
    2. Appelle la méthode `join()` du processus `multiprocessing.Process` avec le `timeout` spécifié.

#### Méthode `is_alive`

```python
def is_alive(self):
```

*   **Description :** Vérifie si le processus worker est toujours en cours d'exécution.
*   **Arguments :** Aucun.
*   **Retour :** `bool`. `True` si le processus est actif, `False` sinon.
*   **Logique interne :**
    1. Vérifie si un processus `_process` existe. Si non, retourne `False`.
    2. Appelle la méthode `is_alive()` du processus `multiprocessing.Process` et retourne le résultat.

#### Méthode `terminate`

```python
def terminate(self):
```

*   **Description :** Termine le processus worker de manière forcée.
*   **Arguments :** Aucun.
*   **Retour :** Aucun.
*   **Logique interne :**
    1. Vérifie si un processus `_process` existe. Si non, lève une `RuntimeError`.
    2. Appelle la méthode `terminate()` du processus `multiprocessing.Process` pour le terminer.

#### Propriété `process`

```python
@property
def process(self):
```

*   **Description :** Retourne l'objet `multiprocessing.Process` sous-jacent.
*   **Arguments :** Aucun.
*   **Retour :** `multiprocessing.Process` ou `None` si le worker n'a pas encore été démarré.
*   **Logique interne :** Retourne la valeur de `self._process`.

---

## Exemple d'usage

```python
import time
from worker import Worker

def ma_tache(nom, duree):
    print(f"Worker '{nom}' démarre...")
    time.sleep(duree)
    print(f"Worker '{nom}' a terminé.")

# Créer un worker pour exécuter 'ma_tache' avec des arguments
mon_worker = Worker(target=ma_tache, args=("Tâche1", 3))

# Démarrer le worker
mon_worker.start()

print("Le thread principal continue...")

# Vérifier si le worker est toujours en vie
if mon_worker.is_alive():
    print("Le worker est toujours en cours d'exécution.")

# Attendre que le worker se termine
mon_worker.join()

print("Le worker est terminé.")

# Exemple avec kwargs
autre_worker = Worker(target=ma_tache, kwargs={"nom": "Tâche2", "duree": 2})
autre_worker.start()
autre_worker.join()
print("Les deux workers ont terminé.")
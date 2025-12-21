# Documentation Technique : `features\core_backup.py`

## Description concise

Ce module gère la création, la compression et le nettoyage des sauvegardes du projet. Il permet de créer des archives ZIP du répertoire d'application spécifié, en excluant certains fichiers et dossiers courants pour optimiser la taille et la pertinence de la sauvegarde. Il intègre également une logique pour éviter les sauvegardes trop fréquentes et pour maintenir un nombre limité de sauvegardes récentes.

## Dépendances

*   `os` : Pour les opérations sur le système de fichiers (création de répertoires, listage, suppression).
*   `shutil` : Potentiellement utilisé pour des opérations de copie de fichiers/dossiers (bien que `zipfile` soit utilisé ici pour la compression).
*   `datetime` : Pour la génération d'horodatages dans les noms de fichiers de sauvegarde.
*   `logging` : Pour l'enregistrement des événements et des erreurs liés aux opérations de sauvegarde.
*   `zipfile` : Pour la création d'archives ZIP.
*   `threading` : Pour gérer un verrou (`_backup_lock`) afin d'éviter les exécutions simultanées de sauvegardes.
*   `time` : Utilisé pour mesurer le temps écoulé entre les sauvegardes.

### Imports de Configuration Modulaire :

*   `config.settings` :
    *   `BACKUP_DIR` : Chemin absolu ou relatif où les sauvegardes seront stockées.
    *   `APP_TO_BACKUP` : Chemin absolu ou relatif du répertoire principal de l'application à sauvegarder.
    *   `MAX_BACKUPS_TO_KEEP` : Nombre maximum de sauvegardes à conserver.
    *   `BACKUP_INTERVAL_MINUTES` : Intervalle minimum (en minutes) entre deux sauvegardes automatiques.
*   `config.logs` :
    *   `get_logger` : Fonction pour obtenir une instance du logger configuré.
*   `features.Decorators` :
    *   `trace_action` : Décorateur utilisé pour tracer l'exécution des fonctions de sauvegarde.

---

## Classes & Fonctions

### Fonction : `create_backup(force=False, comment="Auto")`

#### Signature

`def create_backup(force: bool = False, comment: str = "Auto") -> Optional[str]`

#### Arguments

*   `force` (bool, optionnel, défaut `False`):
    *   Si `True`, la sauvegarde sera créée même si l'intervalle de temps minimum n'est pas écoulé. Utile pour déclencher manuellement une sauvegarde sans attendre.
*   `comment` (str, optionnel, défaut `"Auto"`):
    *   Une chaîne de caractères décrivant le motif de la sauvegarde. Utilisé pour les journaux et potentiellement pour des métadonnées futures.

#### Retour

*   `str` : Le chemin complet du fichier de sauvegarde créé si l'opération réussit.
*   `None` : Si la sauvegarde est ignorée en raison de l'intervalle de temps non écoulé ou si une erreur empêche sa création.

#### Logique interne

1.  **Verrouillage :** Utilise un `threading.Lock` (`_backup_lock`) pour garantir qu'une seule instance de `create_backup` s'exécute à la fois.
2.  **Vérification de l'Intervalle :** Si `force` est `False`, le temps actuel est comparé au `_last_backup_time`. Si le `BACKUP_INTERVAL_MINUTES` n'est pas écoulé, la fonction retourne `None` avec un message de log `debug`.
3.  **Préparation du Répertoire de Sauvegarde :** Crée le répertoire `BACKUP_DIR` s'il n'existe pas.
4.  **Construction du Nom de Fichier :** Génère un nom de fichier basé sur un horodatage au format `backup_YYYYMMDD_HHMMSS.zip`. Le chemin complet est construit en joignant `BACKUP_DIR` et le nom du fichier.
5.  **Log de Démarrage :** Enregistre un message `info` indiquant le début de la sauvegarde, incluant le commentaire fourni.
6.  **Configuration des Exclusions :** Définit des ensembles (`EXCLUDED_DIR_NAMES`, `EXCLUDED_EXTENSIONS`) pour exclure des répertoires et des types de fichiers courants qui ne sont généralement pas nécessaires dans une sauvegarde de projet (par exemple, `__pycache__`, `venv`, `.git`, fichiers `.pyc`, `.log`).
7.  **Création de l'Archive ZIP :**
    *   Ouvre le fichier ZIP spécifié en mode écriture (`'w'`) avec compression `ZIP_DEFLATED`.
    *   Utilise `os.walk` pour parcourir le répertoire `APP_TO_BACKUP`.
    *   **Filtrage des Répertoires :**
        *   Exclut les répertoires dont le chemin absolu commence par le chemin absolu de `BACKUP_DIR` pour éviter de sauvegarder les sauvegardes elles-mêmes (protection anti-récursion).
        *   Filtre les sous-répertoires en fonction de `EXCLUDED_DIR_NAMES`, des noms commençant par `.` (sauf `.gitignore`), et du répertoire de sauvegarde lui-même. Les répertoires à conserver sont modifiés *in-place* dans `dirs[:]`.
    *   **Filtrage des Fichiers :**
        *   Exclut les fichiers commençant par `.` (sauf `.gitignore`).
        *   Exclut les fichiers dont l'extension (en minuscule) est dans `EXCLUDED_EXTENSIONS`.
    *   Pour chaque fichier à inclure, calcule son nom d'archive (`arcname`) en utilisant `os.path.relpath` pour conserver la structure des répertoires relative à `APP_TO_BACKUP`.
    *   Écrit le fichier dans l'archive ZIP. Enregistre un message `warning` si un fichier ne peut pas être écrit.
    *   Compte le nombre de fichiers ajoutés (`file_count`).
8.  **Mise à Jour de l'Horodatage :** Met à jour `_last_backup_time` avec le temps actuel après la création réussie du ZIP.
9.  **Nettoyage des Anciens Backups :** Appelle la fonction `_clean_old_backups()` pour supprimer les sauvegardes excédant `MAX_BACKUPS_TO_KEEP`.
10. **Log de Fin :** Enregistre un message `info` confirmant la réussite de la sauvegarde et le nombre de fichiers inclus.
11. **Gestion des Erreurs :** Capture les exceptions générales, enregistre un message `error` critique, et propage l'exception pour informer l'appelant.

### Fonction : `_clean_old_backups()`

#### Signature

`def _clean_old_backups() -> None`

#### Arguments

Aucun.

#### Retour

Aucun (`None`).

#### Logique interne

1.  **Vérification du Répertoire :** Si `BACKUP_DIR` n'existe pas, la fonction retourne immédiatement.
2.  **Collecte des Backups :** Parcourt le `BACKUP_DIR` et collecte les chemins de tous les fichiers qui commencent par `"backup_"` et se terminent par `".zip"`.
3.  **Tri par Date :** Trie la liste des chemins de sauvegarde par date de modification (`os.path.getmtime`), du plus ancien au plus récent.
4.  **Suppression des Anciens :**
    *   Si le nombre de sauvegardes collectées dépasse `MAX_BACKUPS_TO_KEEP`, calcule la liste des fichiers à supprimer (`to_delete`) : il s'agit de tous les fichiers sauf les `MAX_BACKUPS_TO_KEEP` plus récents.
    *   Itère sur `to_delete` et supprime chaque fichier en utilisant `os.remove`. Enregistre un message `warning` en cas d'échec de suppression.
5.  **Gestion des Erreurs :** Capture et enregistre les exceptions générales survenant pendant le processus de nettoyage.

---

## Exemple d'usage

```python
import features.core_backup
import time
import os

# Assurez-vous que les configurations (BACKUP_DIR, APP_TO_BACKUP, etc.)
# sont correctement définies dans config.settings

# Exemple 1: Créer une sauvegarde standard (respectant l'intervalle)
print("Tentative de sauvegarde standard...")
backup_file = features.core_backup.create_backup()
if backup_file:
    print(f"Sauvegarde créée à : {backup_file}")
else:
    print("Sauvegarde ignorée (trop tôt ou en cours).")

# Attendre un peu pour simuler un intervalle
time.sleep(2) 

# Exemple 2: Créer une sauvegarde forcée (ignore l'intervalle)
print("\nTentative de sauvegarde forcée...")
backup_file_forced = features.core_backup.create_backup(force=True, comment="Manuel_Test")
if backup_file_forced:
    print(f"Sauvegarde forcée créée à : {backup_file_forced}")
else:
    print("Échec de la création de la sauvegarde forcée.")

# Exemple 3: Simuler la création de plusieurs backups pour tester le nettoyage
print("\nSimulation de création de backups pour tester le nettoyage...")
# Supposons MAX_BACKUPS_TO_KEEP = 2
# Créer 5 backups forcés rapidement
for i in range(5):
    time.sleep(0.5) # Petit délai pour que les timestamps soient différents
    features.core_backup.create_backup(force=True, comment=f"Nettoyage_Test_{i+1}")
    print(f"Backup forcé {i+1}/5 créé.")

print("\nVérification des backups restants (devrait être les 2 plus récents)...")
backup_dir = os.environ.get("BACKUP_DIR", "backups") # Ajuster si BACKUP_DIR est une variable d'env
if os.path.exists(backup_dir):
    backups_after_clean = [f for f in os.listdir(backup_dir) if f.startswith("backup_") and f.endswith(".zip")]
    print(f"Nombre de backups trouvés après nettoyage : {len(backups_after_clean)}")
    for b in backups_after_clean:
        print(f"- {b}")
else:
    print(f"Le répertoire de sauvegarde {backup_dir} n'existe pas.")
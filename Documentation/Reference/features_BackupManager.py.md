# Gestionnaire de Sauvegarde (BackupManager)

## Description concise

Ce module gère les opérations de sauvegarde et de restauration pour le projet. Il s'interface avec le module de bas niveau `core_backup` pour la création des archives et utilise des fonctions utilitaires pour la gestion des fichiers et des formats. Il est décoré avec `trace_action` pour l'enregistrement des opérations.

## Dépendances

*   **Modules standards Python:**
    *   `os` : Pour les opérations sur le système de fichiers (chemins, création de dossiers, statut de fichiers).
    *   `logging` : Pour l'enregistrement des événements et erreurs.
    *   `glob` : Pour la recherche de fichiers correspondant à un motif.
    *   `zipfile` : Pour la manipulation des archives ZIP.
    *   `shutil` : Pour les opérations de copie de fichiers (potentiellement utilisé implicitement par `zipfile.extractall`).
    *   `time` : Pour la gestion du temps (potentiellement utilisé par le module `core_backup` ou pour des temporisations).
    *   `datetime` : Pour la gestion des dates et heures (création de commentaires, formatage des dates de sauvegarde).

*   **Modules de Configuration:**
    *   `config.paths.get_path` : Pour obtenir le chemin racine du projet.
    *   `config.logs.get_logger` : Pour initialiser le logger spécifique au module.
    *   `config.settings.BACKUP_DIR` : Chemin du répertoire où stocker les sauvegardes.

*   **Modules "Features & Core":**
    *   `features.Shared.log_action` : Pour enregistrer les actions dans un fichier de log spécifique.
    *   `features.Decorators.trace_action` : Décorateur pour tracer l'exécution des fonctions.
    *   `features.core_backup` (ou `core_backup`) : Module de bas niveau implémentant la logique principale de création de sauvegarde. Le chargement est robuste pour gérer différents chemins d'importation.

---

## Classes & Fonctions

### Fonction `_format_size(size_bytes)`

#### Signature

```python
def _format_size(size_bytes)
```

#### Arguments

*   `size_bytes` (int): La taille en octets à formater.

#### Retours

*   `str`: La taille formatée en une chaîne lisible (ex: "1.23 Mo", "56.78 Ko").

#### Logique interne

Cette fonction prend une taille en octets et la convertit en une unité plus lisible (Ko, Mo, Go, To) en la divisant par 1024 jusqu'à ce qu'elle soit inférieure à cette limite.

---

### Fonction `execute_creer_backup(commentaire=None, force=False, session=None, action_log_path=None, result_queue=None, **kwargs)`

#### Signature

```python
@trace_action(source="BackupManager")
def execute_creer_backup(commentaire=None, force=False, session=None, action_log_path=None, result_queue=None, **kwargs)
```

#### Arguments

*   `commentaire` (str, optionnel): Un commentaire pour décrire cette sauvegarde. S'il n'est pas fourni, un commentaire par défaut "Backup Auto HH:MM" sera utilisé. Peut aussi être passé via `kwargs`.
*   `force` (bool, optionnel): Si `True`, force la création de la sauvegarde même si le délai minimum entre les sauvegardes n'est pas écoulé. S'il n'est pas fourni, sa valeur par défaut est `False`. Peut aussi être passé via `kwargs`. Le booléen peut être reçu sous forme de chaîne ('true'/'false').
*   `session` (any, optionnel): Paramètre passé par le décorateur `trace_action`.
*   `action_log_path` (str, optionnel): Chemin vers le fichier où les actions doivent être loguées.
*   `result_queue` (any, optionnel): Une queue pour envoyer des mises à jour à l'interface utilisateur ou à d'autres composants.
*   `**kwargs`: Arguments supplémentaires, utilisés pour `commentaire` et `force` si non passés directement.

#### Retours

*   `str`: Un message indiquant le succès de la création de la sauvegarde (incluant le nom du fichier) ou une erreur. Si le backup est ignoré à cause du délai, un message d'avertissement est retourné.

#### Logique interne

1.  Récupère les arguments `commentaire` et `force`, en utilisant `kwargs` comme fallback.
2.  Vérifie si le module `core_backup` a été chargé avec succès. Sinon, retourne une erreur.
3.  Envoie une mise à jour UI "⏳ Création backup..." via `result_queue` si fournie.
4.  Appelle `core_backup.create_backup` avec le commentaire et le flag `force`.
5.  Gère le cas où `core_backup.create_backup` retourne `None` (sauvegarde ignorée à cause du délai), en informant l'utilisateur et en envoyant une mise à jour UI.
6.  Si la sauvegarde est créée, formate un message de succès avec le nom du fichier.
7.  Log l'action dans le fichier spécifié par `action_log_path` si fourni.
8.  Envoie une mise à jour UI de succès via `result_queue`.
9.  Retourne le message de succès.
10. En cas d'exception lors de la création, loggue l'erreur, envoie une notification d'erreur via `result_queue` et retourne un message d'erreur formaté.

---

### Fonction `execute_lister_backups(session=None, action_log_path=None, result_queue=None, **kwargs)`

#### Signature

```python
@trace_action(source="BackupManager")
def execute_lister_backups(session=None, action_log_path=None, result_queue=None, **kwargs)
```

#### Arguments

*   `session` (any, optionnel): Paramètre passé par le décorateur `trace_action`.
*   `action_log_path` (str, optionnel): Chemin vers le fichier où les actions doivent être loguées.
*   `result_queue` (any, optionnel): Une queue pour envoyer des mises à jour à l'interface utilisateur ou à d'autres composants.
*   `**kwargs`: Arguments supplémentaires (non utilisés dans cette fonction).

#### Retours

*   `str`: Un rapport formaté listant les sauvegardes disponibles (les 10 plus récentes) ou un message indiquant l'absence de sauvegardes ou la création du dossier.

#### Logique interne

1.  Vérifie si le répertoire `BACKUP_DIR` existe. Si non, il le crée.
2.  Utilise `glob.glob` pour trouver tous les fichiers `.zip` dans `BACKUP_DIR`.
3.  Trie les fichiers par date de modification (`st_mtime`) en ordre décroissant.
4.  Initialise une liste `backups_data` pour stocker les détails structurés des backups et une chaîne `ai_report` pour le résumé textuel.
5.  Si aucun fichier zip n'est trouvé, envoie une liste vide via `result_queue` et retourne un message approprié.
6.  Itère sur les fichiers zip trouvés :
    *   Récupère le nom du fichier, la date de modification et la taille.
    *   Formate la taille en utilisant `_format_size`.
    *   Ajoute les détails structurés à `backups_data`.
    *   Construit le rapport `ai_report` avec les 10 sauvegardes les plus récentes.
    *   Loggue les erreurs lors de la lecture des métadonnées d'un fichier spécifique.
7.  Si plus de 10 sauvegardes existent, ajoute une note à `ai_report`.
8.  Envoie les données structurées `backups_data` via `result_queue`.
9.  Retourne le rapport textuel `ai_report`.

---

### Fonction `execute_restaurer_backup(nom_backup, session=None, action_log_path=None, result_queue=None, **kwargs)`

#### Signature

```python
@trace_action(source="BackupManager")
def execute_restaurer_backup(nom_backup, session=None, action_log_path=None, result_queue=None, **kwargs)
```

#### Arguments

*   `nom_backup` (str): Le nom du fichier de sauvegarde à restaurer (par exemple, "backup_2023-10-27_15-30.zip").
*   `session` (any, optionnel): Paramètre passé par le décorateur `trace_action`.
*   `action_log_path` (str, optionnel): Chemin vers le fichier où les actions doivent être loguées.
*   `result_queue` (any, optionnel): Une queue pour envoyer des mises à jour à l'interface utilisateur ou à d'autres composants.
*   `**kwargs`: Arguments supplémentaires (non utilisés dans cette fonction).

#### Retours

*   `str`: Un message indiquant le succès de la restauration, un message d'erreur si le backup n'est pas trouvé ou si une erreur survient, ou un message d'annulation en cas d'échec de la création du backup de sécurité.

#### Logique interne

1.  Vérifie si `nom_backup` est fourni. Sinon, retourne une erreur.
2.  Construit le chemin complet du fichier de sauvegarde en utilisant `BACKUP_DIR`. Tente également de chercher le `nom_backup` directement s'il est déjà un chemin absolu ou relatif valide.
3.  Vérifie si le fichier de sauvegarde existe. Sinon, retourne une erreur.
4.  Envoie une mise à jour UI "⏳ Sécurité : Création point de restauration..." via `result_queue`.
5.  **Crée un backup de sécurité automatique** en appelant `core_backup.create_backup(comment="AUTO-SAFETY: Avant restauration", force=True)`. Ceci est une étape critique pour pouvoir revenir en arrière en cas de problème lors de la restauration principale.
6.  Si la création du backup de sécurité échoue ou si `core_backup` n'est pas disponible, annule l'opération et retourne une erreur critique.
7.  Envoie une mise à jour UI "⏳ Restauration de ..." via `result_queue`.
8.  Ouvre le fichier de sauvegarde spécifié (`zipfile.ZipFile`).
9.  Extrait toutes les archives dans le répertoire courant du projet (`get_path(".")`).
10. Formate un message de succès avec le nom du fichier restauré.
11. Log l'action de restauration dans le fichier spécifié par `action_log_path`.
12. Envoie une mise à jour UI de succès et une demande de rechargement système (`reload_system`) via `result_queue`.
13. Retourne le message de succès.
14. En cas d'exception lors de l'extraction ou de la manipulation du fichier zip, loggue l'erreur et retourne un message d'erreur critique formaté.

---

## Exemple d'usage

```python
# Assurez-vous que les configurations nécessaires sont chargées
# from config.settings import BACKUP_DIR
# from config.paths import get_path
# from config.logs import get_logger

# Importer le gestionnaire
# from features.BackupManager import execute_creer_backup, execute_lister_backups, execute_restaurer_backup

# --- Créer une sauvegarde ---
# message_creation = execute_creer_backup(commentaire="Sauvegarde manuelle avant mise à jour")
# print(message_creation)

# --- Lister les sauvegardes ---
# rapport_backups = execute_lister_backups()
# print(rapport_backups)

# --- Restaurer une sauvegarde spécifique ---
# nom_du_backup_a_restaurer = "backup_2023-10-27_15-30.zip" # Remplacez par un nom de fichier existant
# message_restauration = execute_restaurer_backup(nom_du_backup_a_restaurer)
# print(message_restauration)

# --- Créer une sauvegarde en forçant ---
# message_creation_forcee = execute_creer_backup(force=True, commentaire="Forcer backup même si récent")
# print(message_creation_forcee)
```
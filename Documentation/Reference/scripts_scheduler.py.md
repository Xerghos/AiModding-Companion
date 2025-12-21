# Fichier : `scripts\scheduler.py`

## Description Concise

Ce script implémente un planificateur simple pour exécuter des sauvegardes de manière périodique. Il utilise les configurations définies dans `config.py` pour déterminer l'intervalle entre les sauvegardes et le nombre maximum de sauvegardes à conserver. Le script démarre immédiatement une sauvegarde, puis entre dans une boucle infinie où il attend l'intervalle spécifié avant d'exécuter la sauvegarde suivante. Il gère également les interruptions clavier pour un arrêt propre et les erreurs inattendues avec un mécanisme de reprise.

## Dépendances

*   `time`: Module Python standard pour la gestion du temps.
*   `sys`: Module Python standard pour l'interaction avec l'interpréteur.
*   `logging`: Module Python standard pour la journalisation.
*   `features.core_backup`: Module contenant la fonction `perform_backup_and_rotation` pour effectuer la sauvegarde et la rotation.
*   `config`: Module personnalisé contenant les constantes de configuration `BACKUP_INTERVAL_MINUTES`, `MAX_BACKUPS_TO_KEEP` et la fonction `get_logger`.

## Classes & Fonctions

### Fonction : `run_scheduler()`

*   **Signature :** `def run_scheduler():`
*   **Arguments :** Aucune.
*   **Retours :** Aucune.
*   **Logique Interne :**
    1.  Convertit l'intervalle de sauvegarde des minutes en secondes (`interval_seconds`).
    2.  Logue des messages d'information indiquant que le système de sauvegarde a démarré, l'intervalle de sauvegarde et le nombre maximum de sauvegardes à conserver.
    3.  Exécute la fonction `perform_backup_and_rotation()` une première fois immédiatement au démarrage.
    4.  Entre dans une boucle infinie (`while True`):
        *   Logue un message indiquant le temps avant la prochaine sauvegarde.
        *   Attend pendant `interval_seconds` en utilisant `time.sleep()`.
        *   Appelle `perform_backup_and_rotation()` pour exécuter une sauvegarde.
    5.  Gère les exceptions :
        *   `KeyboardInterrupt`: Capture l'interruption par l'utilisateur (par exemple, Ctrl+C), logue un message d'arrêt et sort de la boucle.
        *   `Exception`: Capture toute autre erreur inattendue survenant dans la boucle principale, logue un message d'erreur, puis attend 5 minutes (300 secondes) avant de continuer dans la boucle, tentant ainsi de reprendre le processus.

## Exemple d'Usage

Le script est conçu pour être exécuté comme un processus autonome. Son exécution est initiée par la section `if __name__ == "__main__":`, qui appelle la fonction `run_scheduler()`.

Pour l'utiliser, assurez-vous que :

1.  Le fichier `config.py` existe dans le répertoire parent et contient les constantes `BACKUP_INTERVAL_MINUTES`, `MAX_BACKUPS_TO_KEEP` et la fonction `get_logger`.
2.  Le répertoire `features` existe et contient `core_backup.py` avec la fonction `perform_backup_and_rotation`.

**Pour lancer le planificateur :**

```bash
python scripts/scheduler.py
```

Une fois lancé, le script affichera des messages de log indiquant son état et exécutera les sauvegardes selon l'intervalle configuré. Pour l'arrêter, utilisez `Ctrl+C` dans le terminal.
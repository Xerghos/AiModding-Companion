# Documentation Technique : `ui\windows\__init__.py`

## Description Concise

Ce fichier agit comme un point d'entrée principal pour le module `ui.windows`. Il expose de manière propre les différentes classes de fenêtres définies dans les sous-modules, permettant ainsi aux autres parties de l'application d'importer ces fenêtres sans avoir à connaître leur organisation interne détaillée.

## Dépendances

Ce fichier ne possède pas de dépendances externes directes au-delà des modules Python standard. Les dépendances sont gérées au niveau des sous-modules importés :

*   `ui.windows.base`
*   `ui.windows.settings`
*   `ui.windows.chat`
*   `ui.windows.tools`
*   `ui.windows.queue`

## Classes & Fonctions Exposées

Ce fichier n'implémente pas de classes ou de fonctions directement. Son rôle est d'importer et d'exposer les classes des sous-modules. Les classes suivantes sont rendues disponibles pour l'importation depuis `ui.windows`:

### 1. Fenêtres de Base

*   **`BaseWindow`** : (Importée de `.base`)
    *   **Description :** Fournit une classe de base pour toutes les fenêtres de l'interface utilisateur. Elle peut contenir des fonctionnalités communes et une structure de base pour les fenêtres.
    *   **Arguments, Retours, Logique interne :** Doivent être consultés dans `ui/windows/base.py`.

### 2. Paramètres & API

*   **`SettingsWindow`** : (Importée de `.settings`)
    *   **Description :** Représente la fenêtre dédiée à la gestion des paramètres de l'application.
    *   **Arguments, Retours, Logique interne :** Doivent être consultés dans `ui/windows/settings.py`.

*   **`ApiKeyManager`** : (Importée de `.settings`)
    *   **Description :** Une classe potentiellement liée aux paramètres, responsable de la gestion des clés d'API.
    *   **Arguments, Retours, Logique interne :** Doivent être consultés dans `ui/windows/settings.py`.

### 3. Chat

*   **`SecondaryChatWindow`** : (Importée de `.chat`)
    *   **Description :** Représente une fenêtre de chat secondaire, distincte potentiellement de la fenêtre de chat principale.
    *   **Arguments, Retours, Logique interne :** Doivent être consultés dans `ui/windows/chat.py`.

### 4. Outils (RAG, Backup)

*   **`DbManagerWindow`** : (Importée de `.tools`)
    *   **Description :** Représente la fenêtre pour la gestion de la base de données, potentiellement liée à des fonctionnalités RAG (Retrieval-Augmented Generation).
    *   **Arguments, Retours, Logique interne :** Doivent être consultés dans `ui/windows/tools.py`.

*   **`BackupManagerWindow`** : (Importée de `.tools`)
    *   **Description :** Représente la fenêtre pour la gestion des sauvegardes.
    *   **Arguments, Retours, Logique interne :** Doivent être consultés dans `ui/windows/tools.py`.

### 5. File d'attente (Module Isolé)

*   **`WaitingListWindow`** : (Importée de `.queue`)
    *   **Description :** Représente la fenêtre dédiée à la gestion d'une file d'attente. Ce module est marqué comme "isolé", suggérant une certaine indépendance fonctionnelle.
    *   **Arguments, Retours, Logique interne :** Doivent être consultés dans `ui/windows/queue.py`.

## Exemple d'usage

Cet exemple montre comment importer et potentiellement instancier une classe de fenêtre depuis le module `ui.windows`.

```python
# Supposons que cette partie du code est dans un autre fichier,
# par exemple dans le module principal de l'application.

from ui.windows import SettingsWindow, SecondaryChatWindow

# Création d'une instance de la fenêtre de paramètres
settings_win = SettingsWindow()
settings_win.show() # Supposons une méthode show() commune

# Création d'une instance de la fenêtre de chat secondaire
chat_win = SecondaryChatWindow()
chat_win.show()

# Vous pouvez également importer d'autres fenêtres de la même manière
from ui.windows import DbManagerWindow
db_manager = DbManagerWindow()
db_manager.show()
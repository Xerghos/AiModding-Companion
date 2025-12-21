# Documentation Technique : Fichier `changelogs.md`

## En-tête

*   **Titre :** Journal des Modifications - Assistant Gemini (Historique Exhaustif)
*   **Description Concise :** Ce document est la source de vérité absolue concernant l'évolution technique du projet **AiModding-Companion**. Il retrace de manière exhaustive toutes les modifications majeures, les correctifs, les améliorations architecturales et les nouvelles fonctionnalités, depuis ses fondations multithreadées jusqu'à son état actuel.
*   **Dépendances (Modules Internes Clés Affectés) :**
    *   `ai_core/factory.py`
    *   `ai_core/sessions.py`
    *   `ai_core/keys.py`
    *   `Features/UnifiedLogger.py`
    *   `worker/core.py`
    *   `Features/CacheManager.py`
    *   `Features/Documentation.py`
    *   `Features/SemanticMemory.py`
    *   `Features/ai_helper.py` (Dispatcher)
    *   `Features/Refactoring.py`
    *   `Features/BackupManager.py`
    *   `Features/FileSystem.py`
    *   `Features/SearchEngine.py`
    *   `Features/GitActions.py`
    *   `Features/CodeQuality.py`
    *   `ui/windows/settings.py`
    *   `ui/widgets.py`
    *   `config.py` / `app_settings.json`
    *   `agent_personas.py`
    *   `swarm_manager` (module de gestion d'agents)
    *   `audio_manager.py`
    *   `github_manager` (module d'intégration GitHub)
    *   `tests/` (suite de tests unitaires)

## Classes & Fonctions

Le fichier `changelogs.md` est un journal des modifications et non une spécification de code. Par conséquent, les signatures de classes et fonctions sont implicites et leurs logiques internes sont décrites par les changements apportés ou les nouveaux comportements.

### Module `ai_core`

*   **`ai_core/factory.py` (SmartSessionFactory)**
    *   **Fonctionnalité : `create_session`**
        *   **Arguments Implicites :** `agent_name: str`, `rag_context`.
        *   **Logique Interne :**
            *   Priorise l'argument `agent_name` pour garantir l'identité de l'agent (rôle métier).
            *   Gère l'instanciation unique du `KeyManager`.
            *   Intègre une chaîne de secours hiérarchique (`Fallback Cascade V2`) pour la sélection de modèle en cas de clés API peu saines.
            *   Corrige le mappage des modèles en lisant depuis `cloud_models_registry`.
*   **`ai_core/sessions.py` (GeminiSession, DeepSeekSession, GroqSession, BaseSession)**
    *   **Attributs :** `system_instruction` (pour DeepSeekSession), identité immuable (`agent_name`).
    *   **Logique Interne :**
            *   Stocke l'identité immuable de l'agent et l'injecte dans chaque appel au `Logger`.
            *   Corrige un `AttributeError` bloquant dans `DeepSeekSession` en assurant la persistance de `system_instruction`.
            *   Supporte l'argument `rag_context` pour l'injection isolée de contexte documentaire.
            *   Implémente l'architecture Payload "Atomique" (V5) pour la segmentation du contexte.
            *   Corrige les dépendances circulaires via `Lazy Import` de `TokenManager`.
            *   Ajoute le calcul des tokens (in/out) pour les sessions de streaming.
*   **`ai_core/keys.py` (KeyManager)**
    *   **Fonctionnalité : Rotation et Sélection de Clés API**
        *   **Logique Interne :**
            *   Implémente une stratégie de "Health Score Routing" (V3) : chaque clé a un score (100%), décrémenté à l'usage ou aux erreurs (429), et incrémenté au repos.
            *   La sélection automatique privilégie la clé la plus saine et la moins utilisée récemment.
            *   Intègre le stockage sécurisé via `keyring` (coffre-fort OS) et la migration automatique des clés depuis `settings.json`.

### Module `worker`

*   **`worker/core.py` (Core Worker Logic)**
    *   **Fonctionnalité : `_handle_chat_stream` (gestionnaire de flux de chat)**
        *   **Logique Interne :**
            *   Réécrit pour parser simultanément le texte brut et les objets `FunctionCall` natifs de Google (support hybride).
            *   Implémente un filtre pour intercepter les hallucinations où l'IA relance une commande identique.
            *   Force la `SessionFactory` à recharger sa configuration lors des modifications UI.
            *   Implémente une "Boucle de Rétroaction Fermée" injectant les résultats d'outils (`{tool_output, system_instruction}`) dans la session de l'IA.
            *   Ajout d'un "Détecteur Polyglotte" pour traduire les hallucinations de type `[TOOL_CALL: ...]`.
            *   Ajout d'un "Traducteur Kwargs -> JSON" pour corriger les commandes Pythoniques en JSON valide.
            *   Intègre un `ThreadPoolExecutor` pour l'exécution asynchrone des tâches lourdes.
            *   Gère le nettoyage rétroactif de la mémoire en tronquant les messages anciens.
            *   Implémente l'arrêt propre (`abort_current_stream`) lors de l'interruption.
            *   Optimisation de la mémoire avec une fenêtre glissante (10 messages) et troncation des blocs de code.
            *   Détecte l'intention NLP pour l'usage des outils.
            *   Déplace le chargement de `database.init_db` en début de thread pour un démarrage sans latence.
            *   Rafraîchit `architecture_map.json` toutes les 15 minutes.

### Module `Features`

*   **`Features/UnifiedLogger.py` (UnifiedLogger)**
    *   **Fonctionnalité : Journalisation**
        *   **Arguments Implicites :** `provider`, `model`, `agent`.
        *   **Logique Interne :**
            *   Reçoit systématiquement le triplet contextuel `{provider, model, agent}`.
            *   Supprime les mentions génériques ("Unknown", "AI").
            *   Affiche simultanément le nom de l'Agent et le modèle technique.
            *   Harmonise le formatage des métriques entre les modes streaming et standard.
            *   Supporte le multithreading (`_log_lock`) et l'UTF-8.
            *   Intègre un `RotatingFileHandler` pour gérer la taille des logs.
*   **`Features/CacheManager.py` (CacheManager)**
    *   **Logique Interne :**
            *   Gère la création "Just-In-Time" des caches pour chaque couple (Clé API + Modèle).
            *   Implémente un "Circuit Breaker" pour détecter les erreurs de quota et désactiver le cache.
            *   Ne fusionne plus les données ; l'assemblage dynamique dans la session est fait par blocs de messages distincts.
*   **`Features/Documentation.py` (Smart Doc)**
    *   **Logique Interne :**
            *   Ajout des filtres `include_patterns` et `ignore_patterns`.
            *   Implémente une liste noire de sécurité forcée (exclut `.env`, secrets, logs).
            *   Rejette les contenus trop courts, les phrases de chat parasites et les balises Markdown englobantes.
            *   Mise à jour immédiate des hashs en mémoire (`Optimistic Locking`).
            *   Déclenche une régénération forcée si le fichier .md de destination est manquant.
            *   Rétablit la génération atomique asynchrone via une file de tâches.
*   **`Features/SemanticMemory.py` (SemanticMemory)**
    *   **Fonctionnalité : `_extract_text`**
        *   **Logique Interne :**
            *   Refonte critique pour décoder les objets Protobuf `MapComposite` de Google Gemini.
            *   Standardise l'enregistrement des `function_response`.
            *   Corrige une régression RAG en remplaçant `add_memory_fragment` par `store_memory` (compatible base vectorielle V2).
*   **`Features/ai_helper.py` (Dispatcher)**
    *   **Logique Interne :**
            *   Sécurisation critique avec un middleware "Sanity Check" : confinement (`Jail`) hors du dossier projet et protection des actifs vitaux.
            *   Amélioration du parser JSON pour réparer les erreurs de syntaxe de l'IA.
            *   Résolution des cycles d'importation via `Lazy Loading` des modules Features.
            *   Ajout de l'introspection native (`lister_outils`).
            *   Renforcement du parser JSON pour gérer les tronquages et les doubles échappements.
            *   Cartographie complète des 15 outils du schéma vers leurs fonctions respectives.
*   **`Features/Refactoring.py` (Refactoring)**
    *   **Logique Interne :**
            *   Vérification syntaxique AST (`ast.parse`) avant toute écriture disque.
            *   Sauvegarde forcée (`force=True`) avant modification.
            *   Extraction chirurgicale du code Python (suppression des balises Markdown).
            *   Ajout du paramètre `auto_apply` pour les modifications directes.
            *   Implémente un nettoyeur Regex (`_extraire_code_python`).
*   **`Features/BackupManager.py` & `core_backup.py` (Système de Sauvegarde)**
    *   **Logique Interne :**
            *   Alignement des signatures de méthode (`comment` vs `reason`).
            *   Gestion du paramètre `force` pour outrepasser les cooldowns.
            *   Protection contre les crashs si le Core renvoie `None`.
            *   Correction critique de la boucle infinie lors de la création de ZIP.
            *   Déclenchement systématique d'une sauvegarde complète avant toute modification de code.
*   **`Features/FileSystem.py` (Système de Fichiers)**
    *   **Logique Interne :**
            *   Ajout de `comparer_fichiers` (diff), `deplacer_fichier`, `copier_fichier`, `obtenir_infos_fichier`.
            *   Réduit la verbosité des retours d'écriture pour l'IA.
*   **`Features/SearchEngine.py` (Moteur de Recherche)**
    *   **Fonctionnalité : `rechercher_texte` / `execute_recherche_texte`**
        *   **Logique Interne :** Refonte (`Grep`) avec filtrage robuste (exclusion `.git`, `node_modules`, binaires). Implémente une protection anti-flood.
*   **`Features/GitActions.py` (Actions Git)**
    *   **Logique Interne :** Passage en mode session `disposable` pour l'analyse de dépôts. Fournit un feedback UI en temps réel.
*   **`Features/CodeQuality.py` (Qualité de Code)**
    *   **Logique Interne :** Ajout de la détection de fichiers vides pour éviter les hallucinations.

### Module `ui`

*   **`ui/windows/settings.py` (Fenêtre de Paramètres)**
    *   **Logique Interne :**
            *   Ajout d'un menu contextuel (+) pour ajouter des exclusions.
            *   Intégration visuelle du "Health Score" des clés API.
            *   Suppression de la boucle de monitoring infinie (optimisation CPU).
            *   Fusion complète de `SettingsWindow` et `DetailedConfigWindow` en une interface unifiée.
            *   Remplacement des champs statiques par un `Treeview` interactif pour les clés API.
            *   Correction d'un patch critique JSON (`app_settings.json`).
            *   Ajout de protections (`dict.get`) pour la compatibilité avec les anciens formats de configuration.
*   **`ui/widgets.py`**
    *   **Logique Interne :** Correction du widget "Raisonnement" pour renvoyer un booléen strict (`True`/`False`).
*   **`ui/windows/tools.py` (Fenêtre d'Outils)**
    *   **Logique Interne :** Découplage total IA/Système : les boutons appellent directement le Worker sans passer par le chat.

### Autres Composants

*   **`config.py` / `app_settings.json`**
    *   **Logique Interne :** Inclut les définitions des clés et modèles Groq. Corrige le formatage JSON corrompu. Migration de toutes les variables d'environnement et constantes vers JSON.
*   **Swarm Manager (Architecture Multi-Agents)**
    *   **Logique Interne :** Refonte complète pour une autonomie supervisée. Implémente le `Whitelisting` (sécurité cognitive), le `Tiering Dynamique` des modèles, le `Context Awareness` (STM, RAG), et une `Boucle d'Autonomie` (`Retry Loop`). Gère un système de messagerie asynchrone et le recrutement dynamique d'agents spécialisés.
*   **`agent_personas.py`**
    *   **Logique Interne :** Définit les rôles et les outils whitelisting pour chaque agent (`CODER`, `ARCHITECT`, `ROUTER`, `GUARDIAN`, `REVIEWER`, `WRITER`).
*   **RAG/Database (Implémentation)**
    *   **Logique Interne :** Correction des imports conditionnels. Fonctions `index_project_files` et `add_file_to_db` (avec idempotence). Algorithme 1+3+4 (Frecency + Graphe + Vecteur). Migration FAISS + SQLite. Chargement différé (`Lazy Loading`) des modèles lourds. Mécanisme de compression ZIP automatique pour la synchronisation GDrive.

## Exemple d'Usage

Le fichier `changelogs.md` est un document de suivi de projet et n'est pas destiné à être exécuté comme du code. Son "usage" pertinent est sa consultation et son interprétation dans le cadre du développement et de la gestion du projet `AiModding-Companion`.

**Exemple d'Interprétation (non-code) :**

*   **Pour un Développeur :** En cas d'erreur `AttributeError` lors de l'initialisation d'un agent `DeepSeek`, la lecture du patch "Identity Tunneling & DeepSeek Stability" (18 Décembre 2025) révèle un correctif spécifique pour `DeepSeekSession` concernant l'attribut `system_instruction`. Cela indique que la cause racine était une non-persistance de cet attribut et que le problème est désormais résolu, ou aide à vérifier que le déploiement inclut bien cette correction.
*   **Pour un Chef de Projet :** Le patch "Swarm V2 & Fortification" (11 Décembre 2025) détaille l'introduction de l'autonomie supervisée des agents, le `Whitelisting` d'outils et une boucle d'autonomie avec retry. Ces informations permettent de comprendre les nouvelles capacités du système, d'évaluer la robustesse et de planifier les prochaines étapes de développement en tirant parti de ces avancées.
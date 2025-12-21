# Journal des Modifications - Assistant Gemini (Historique Exhaustif)
#Ce document est la source de vérité absolue concernant l'évolution technique du projet **AiModding-Companion**, depuis ses fondations multithreadées jusqu'à son état actuel.
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#🔧 Patch "Identity Tunneling & DeepSeek Stability"

## 18 Décembre 2025 Focus : Restauration de la traçabilité des Agents (Data Flow), Stabilité DeepSeek et Observabilité.


## 🏗️ 1. Architecture (Identity Tunneling V3.3)

*Rétablissement complet de la chaîne de transmission de l'identité des agents, résolvant le problème de "Téléphone Arabe" entre les modules.


*Transmission Explicite (SwarmManager) : Le Manager transmet désormais le Rôle métier (ex: "Coder", "Architect") à la Factory lors de la création de session, au lieu de laisser la Factory déduire un nom générique basé sur le modèle technique (ex: "Fast").

*Priorité Factory (ai_core/factory.py) : La méthode create_session accepte et priorise l'argument agent_name, garantissant que l'intention du Swarm prévaut sur les déductions par défaut.

*Persistance Session : Les classes de session (GeminiSession, DeepSeekSession, etc.) stockent cette identité immuable et l'injectent dans chaque appel au Logger. L'agent sait "qui il est" du début à la fin du cycle de vie.

### 🐛 2. Correctifs Critiques (DeepSeek & Streams)

*Crash Initialisation DeepSeek : Correction d'un AttributeError bloquant dans DeepSeekSession. L'attribut system_instruction est désormais correctement persistant dans self avant la construction du premier payload, empêchant les crashs au démarrage des agents "Smart".

*Métriques Orphelines (Stream Wrapper) : Résolution d'un bug dans la gestion des flux (stream_wrapper) où les métriques de fin de génération (Token Usage/Cost) étaient envoyées sans métadonnées d'agent, rendant les logs anonymes ou mal attribués.

### 📊 3. Observabilité & UnifiedLogger

*Attribution Dynamique : Suppression définitive des mentions "Unknown" ou "AI" génériques. Le Logger reçoit systématiquement le triplet contextuel complet {provider, model, agent}.

*Affichage Hybride (Agent + Modèle) : Mise à jour de la logique d'affichage METRICS pour présenter simultanément le nom de l'Agent (ex: "COMPRESSOR") et le modèle technique réel (ex: "gemini-2.5-flash-lite"), levant l'ambiguïté entre la configuration et l'exécution.

*Harmonisation Visuelle : Alignement strict du formatage des métriques (In/Out/Time/Cost) entre les modes Streaming et Standard pour tous les providers (DeepSeek, Gemini, Groq).

------

## -Date : 18 Décembre 2025 Architecture V5 "Atomique", Sécurité Keyring & Stabilisation DeepDoc

## 🏗️ [CORE] Architecture Payload "Atomique" (V5)

*DeepSeek V3/Reasoner : Transition complète vers le Native Tool Calling. Les définitions d'outils ne sont plus injectées en texte brut (économie massive de tokens).

*Segmentation du Contexte : Le CacheManager ne fusionne plus les données. L'assemblage se fait dynamiquement dans la session sous forme de blocs messages distincts :

*System : Instructions Agent.

*System : Cartographie Technique (Architecture).

*System : Arborescence Projet.

*User : Injection RAG isolée (Docs & LTM).

*User : Prompt utilisateur final.

*Isolation RAG : Le contexte documentaire est désormais passé via un argument dédié rag_context et injecté dans un bloc utilisateur séparé pour éviter la pollution du prompt principal.

### 🔐 [SECURITY] Gestion des Clés & Keyring Système

*Coffre-fort OS : Implémentation du stockage sécurisé via keyring. Les clés API sont automatiquement migrées depuis settings.json vers le coffre-fort système (Windows/Mac/Linux) au démarrage, puis effacées physiquement du fichier de configuration.

*Rotation Intelligente : Refonte de KeyManager.

*Introduction d'un système de Santé (Health).

*Punition immédiate des erreurs 429 Quota Exceeded (Santé -> 0, Cooldown 1h).

*Sélection pondérée : Le système choisit toujours la clé la plus saine et la moins utilisée récemment.

### ⚡ [FIX] Streaming & Compatibilité

*DeepSeek Stream : Correction de la reconstruction des tool_calls fragmentés en mode streaming. Les commandes !native_tool sont désormais générées correctement à la volée.

*Universalité : Mise à jour de GeminiSession et GroqSession pour supporter l'argument rag_context (mode fusion fallback) et éviter les crashs TypeError.

*Factory : Nettoyage de SmartSessionFactory pour gérer l'instanciation unique du KeyManager sans arguments.

### 📚 [FEATURE] Durcissement DeepDoc (Documentation)

*Filtre Anti-Déchets : Le worker de documentation rejette désormais :

*Les contenus trop courts (< 50 chars).

*Les phrases de chat parasites ("Voici la documentation...", "Opération terminée").

*Les balises Markdown englobantes (```markdown```). 

*Optimistic Locking : Mise à jour immédiate des hashs en mémoire pour éviter les boucles de régénération.

*Résilience : Régénération forcée si le fichier source n'a pas changé mais que le fichier .md de destination est manquant.

### ⚙️ [UI] Gestion des Exclusions

*Settings : Ajout d'un menu contextuel (+) dans l'onglet "Système" pour ajouter facilement des fichiers ou des dossiers à la liste d'exclusion (ignored_files).

*Intégration : Le module de documentation respecte désormais strictement ces exclusions globales.

*Fichiers impactés :

*ai_core/sessions.py (V5 Logic, Native Tools)

*ai_core/keys.py (Keyring, Rotation Logic)

*ai_core/factory.py (Singleton Refactor)

*features/CacheManager.py (Atomic Components)

*features/Documentation.py (Hardening, Wrapper)

*worker/core.py (RAG Injection)

*ui/windows/settings.py (Exclusion UI)

---
## 🛠️ Patch "Polyglotte & Stabilité"

## 12 Décembre 2025 Focus : Résolution des conflits d'architecture (Texte vs Outils Natifs) et fiabilisation du moteur.
### 🧠 1. Moteur & Worker (Le "Cerveau Polyglotte")

*Correction majeure de la communication entre le Worker et l'API Gemini en mode Swarm.

    **Support Hybride (Fix "Réponse Vide") : Réécriture de _handle_chat_stream dans Worker/core.py. Le Worker est désormais capable de parser simultanément le texte brut et les objets FunctionCall natifs de Google. Cela résout définitivement le bug où l'IA semblait muette alors qu'elle envoyait des commandes.

    **Filtre Anti-Bégaiement : Implémentation d'une sécurité dans la boucle de rétroaction (Worker/core.py). Si l'IA tente de relancer une commande identique à celle qui vient de réussir (hallucination de zèle), l'action est interceptée et seul le commentaire est affiché.

### ⚙️ 2. Configuration & Factory

    *Correction du Mapping des Modèles : Mise à jour de ai_core/factory.py pour lire la configuration depuis cloud_models_registry. Cela corrige le bug qui forçait l'utilisation du modèle gemini-2.5-flash-lite (quota limité) alors que l'utilisateur avait sélectionné gemini-2.5-flash (quota standard), éliminant les erreurs 429.

    *Synchronisation Hot-Reload : Patch de Worker/core.py pour forcer la SessionFactory à recharger sa configuration interne lors d'une modification des paramètres dans l'UI (le changement de modèle est désormais immédiat sans redémarrage).

### 🖥️ 3. Interface Utilisateur

    *Switch Raisonnement (ui/widgets.py) : Correction du widget pour renvoyer un booléen strict (True/False) au lieu de chaînes de caractères. Le Worker détecte maintenant correctement l'activation/désactivation du mode "Thinking".

### 🧹 4. Nettoyage Technique

    *Gestion des Clés API : Correction de l'appel de méthode dans la Factory (get_key au lieu de get_valid_key).

    *Logs : Clarification des logs de streaming pour distinguer les contenus textuels des appels d'outils.

## 🚀 Update "Swarm V2 & Fortification"

##  11 Décembre 2025 Focus : Intelligence Agentique, Sécurité Active & Tests Unitaires.
### 🧠 1. Architecture Swarm V2 (Agents Autonomes)

*Refonte complète du cerveau des agents pour permettre une véritable autonomie supervisée.

    **Whitelisting (Sécurité Cognitive) : Chaque agent (CODER, ARCHITECT, ROUTER) ne voit désormais que les outils strictement nécessaires à son rôle. Fini les hallucinations d'outils.

    **Tiering Dynamique : Attribution intelligente des modèles. Le ROUTER utilise un modèle rapide ("Fast"), l' ARCHITECT un modèle de raisonnement ("Thinking").

    **Context Awareness (Mémoire Partagée) : Les agents naissent désormais avec une "conscience" de la conversation (STM) et de la documentation (RAG) injectée au démarrage.

    **Boucle d'Autonomie (Retry Loop) : Implémentation d'une boucle de rétroaction (Max 5 itérations). Si un agent échoue ou doit enchaîner des actions, il analyse le résultat de l'outil et continue sans intervention humaine.

    **Mode Raisonnement (On/Off) : Ajout du support pour basculer dynamiquement les agents sur des modèles de "Pensée Profonde" via l'UI.

### 🛡️ 2. Sécurité & Dispatcher (Le Gardien)

*Sécurisation critique du moteur d'exécution features/ai_helper.py.

    **Middleware "Sanity Check" : Interception de toutes les commandes avant exécution.

        ***Confinement (Jail) : Blocage strict de toute tentative d'accès hors du dossier projet (../../).

        ***Protection des Actifs : Interdiction d'écriture sur les fichiers vitaux (config/settings.py, .git/, agent_personas.py).

    **Robustesse Parsing : Amélioration du parser JSON pour réparer automatiquement les erreurs de syntaxe générées par l'IA (accolades manquantes, double escape).

    **Lazy Loading : Résolution des cycles d'importation via chargement différé des modules Features.

### 🔧 3. Standardisation des Outils

*Mise à niveau des modules pour respecter la signature standard (session, queue, logs).

    **WebSurfer : Réécriture complète pour supporter l'injection de dépendances et intégration au registre central.

    **SemanticMemory : Correction de la régression RAG (remplacement de l'appel obsolète add_memory_fragment par store_memory compatible base vectorielle V2).

### 🧪 4. Infrastructure de Tests (QA)

*Création d'une suite de tests unitaires complète (tests/) garantissant la non-régression.

    **Couverture : Filesystem (Sandbox), Backup, CodeQuality, SemanticMemory (Mock DB), Swarm Manager, AI Helper.

    **Fiabilité : Tests isolés ne touchant jamais aux vraies données utilisateur.
	
## - 2025-12-09 - Architecture "Closed-Loop" & Standardisation Totale 

### 🚀 Changements Majeurs (Core & Architecture)

#### 1. Système de "Feedback Loop" (Cerveau & Mémoire)
* **Boucle de Rétroaction Fermée (`Worker/core.py`) :** Implémentation d'un mécanisme d'injection des résultats d'outils directement dans la session de l'IA.
    * *Avant :* L'IA exécutait une commande et ne voyait jamais le résultat (Cécité).
    * *Après :* Le Worker injecte un payload JSON `{tool_output, system_instruction}` forçant l'IA à accuser réception.
* **Correction des Hallucinations de Protocole :**
    * Ajout d'un **Détecteur Polyglotte** dans le Worker capable d'intercepter et de traduire les hallucinations de type `[TOOL_CALL: ...]` générées par la mémoire sémantique.
    * Implémentation d'un **Traducteur Kwargs -> JSON** pour corriger les commandes Pythoniques (ex: `func(a='b')`) en JSON valide.
* **Mémoire Sémantique (`Features/SemanticMemory.py`) :**
    * Refonte critique de `_extract_text` pour décoder les objets Protobuf `MapComposite` de Google Gemini (qui étaient auparavant enregistrés comme des pointeurs mémoire vides).
    * Standardisation de l'enregistrement des `function_response`.

#### 2. Gestionnaire de Clés & Sessions (Stabilité)
* **Smart Key Manager V3 (`ai_core/keys.py`) :**
    * Remplacement de la rotation simple par une stratégie de **"Health Score Routing"**.
    * Chaque clé possède une barre de vie (100%). Usage = -1%, Erreur = -50%, Repos = +5%/min.
    * Sélection automatique de la clé la plus "fraîche".
* **Fallback Cascade V2 (`ai_core/factory.py`) :**
    * Intégration d'une chaîne de secours hiérarchique (ex: Gemini 2.5 Pro -> Gemini 1.5 Pro -> Gemma 27b -> Gemini Flash).
    * Bascule automatique de modèle en cas de refus du KeyManager (Santé < 30%).
* **Métriques & Logs (`ai_core/sessions.py`) :**
    * Correction des dépendances circulaires via Lazy Import de `TokenManager`.
    * Ajout du calcul de tokens (`in/out`) pour les sessions **Streaming** (Gemini & Groq), couvrant enfin l'usage du Compresseur et des Agents.
    * Correction du bug de portée variable (`free variable 'e'`) dans la gestion d'erreurs.

### 🛠️ Standardisation des Features (Outils)

Mise à niveau de **tous** les modules pour respecter la signature universelle du Dispatcher.

* **Dispatcher (`Features/ai_helper.py`) :**
    * Ajout de l'introspection native : Commande `lister_outils` câblée officiellement.
    * Renforcement du parser JSON pour gérer les tronuquatures et les doubles échappements (`\\"`).
* **Refactoring (`Features/Refactoring.py`) :**
    * **Sécurité :** Vérification syntaxique AST (`ast.parse`) avant toute écriture disque.
    * **Backup :** Sauvegarde forcée (`force=True`) avant modification.
    * **Nettoyage :** Extraction chirurgicale du code Python (suppression des balises Markdown).
* **Backup System (`Features/BackupManager.py` & `core_backup.py`) :**
    * Alignement des signatures (`comment` vs `reason`).
    * Gestion du paramètre `force` pour outrepasser les cooldowns.
    * Protection contre les crashs si le Core renvoie `None` (Cooldown actif).
* **FileSystem (`Features/FileSystem.py`) :**
    * Ajout de `comparer_fichiers` (Diff), `deplacer_fichier`, `copier_fichier`, `obtenir_infos_fichier`.
* **Search Engine (`Features/SearchEngine.py`) :**
    * Refonte de `rechercher_texte` (Grep) avec filtrage robuste (exclusion `.git`, `node_modules`, binaires).
    * Protection anti-flood (limite de résultats pour le contexte).
* **Git Actions (`Features/GitActions.py`) :**
    * Passage en mode session `disposable` pour l'analyse de dépôts (évite de polluer le contexte).
    * Feedback UI en temps réel (Clonage, Lecture, Analyse).
* **Code Quality (`Features/CodeQuality.py`) :**
    * Ajout de la détection de fichiers vides pour éviter les hallucinations.

### 🎨 Interface Utilisateur (UI)

* **Menu Paramètres (`Ui/Windows/settings.py`) :**
    * Intégration visuelle du "Health Score" des clés (🟢/🟠/🔴) dans le Treeview.
    * Suppression de la boucle de monitoring infinie (optimisation CPU) au profit d'un audit à la demande.
* **Menu Outils (`Ui/Windows/tools.py`) :**
    * Découplage total IA/Système : Les boutons "Reconstruire DB" ou "Backup" appellent directement le Worker (`backup_now`, `reindex_db`) sans passer par le chat.

### 🐛 Correctifs Divers
* **RAG/Database :** Correction des imports conditionnels pour éviter les crashs si `chromadb` est absent.
* **Auto-Maintenance :** Ajout d'un timer dans le Worker pour rafraîchir l'`architecture_map.json` toutes les 15 minutes.
###-----------------------------------------------------------------------------------------------------------------------###

## - 2025-11-30 - Phase 23 : Performance & Fiabilité

### Nouveautés basées sur le Plan Technique
*   23.1. Stratégie de Cache pour les Requêtes LLM : `ai_core.py` implémente un cache sur disque via `diskcache`, réduisant drastiquement les appels API redondants et la latence. L'UI permet de vider le cache.
*   23.2. Log Rotation et Nettoyage Automatique : `Features/UnifiedLogger.py` intègre un `RotatingFileHandler` pour gérer la taille des logs, prévenant la saturation du disque et assurant une observabilité pérenne.

[2025-11-30] - Architecture V42 "Ultimate" (Streaming, Caching & Swarm)

###🏗️ Architecture & Core
* **Streaming End-to-End (V38-V40) : Implémentation complète du streaming de réponse (effet "machine à écrire").
      * Mise à jour de ai_core.py pour retourner des générateurs au lieu de texte bloquant.
      * Création d'un stream_wrapper pour intercepter les appels d'outils (function_call) au milieu du flux texte.
      * Mise à jour de worker.py pour consommer les chunks et les envoyer à l'UI en temps réel.
* **Shadow Caching Multi-Clés (V33-V34) : Système de cache contextuel avancé pour contourner les limites de l'API.
      * Création de Features/CacheManager.py : Gère la création "Just-In-Time" des caches pour chaque couple (Clé API + Modèle).
      * Implémentation du "Circuit Breaker" : Détecte les erreurs de quota (Free Tier) et désactive le cache pour éviter les crashs, basculant en mode standard transparent.
* **Hygiène Mémoire (V26-V35) :
      * Nettoyage Rétroactif : Le Worker tronque désormais les vieux messages systèmes (>1500 chars) et utilisateurs (>2000 chars) dans l'historique pour stabiliser la consommation de tokens autour de 10k-12k.
      * Sessions Jetables (disposable=True) : Généralisation pour les tâches atomiques (DeepDoc, Analyse) afin de ne pas polluer le contexte principal.
* **Swarm & Parallélisme (V30) :
      * Intégration d'un ThreadPoolExecutor dans le Worker.
      * Exécution asynchrone des tâches lourdes (Documentation Atomique, Indexation RAG) sans bloquer le chat.
* **Intégration Groq (V37) :
      * Ajout de la classe GroqSession dans ai_core.py pour supporter les modèles Llama 3 et Mixtral via l'API Groq (Ultra-rapide).
      * Mise à jour de config.py pour inclure les clés et modèles Groq.
###⚡ Fonctionnalités & Outils
    Documentation Intelligente ("Smart Doc") :
        Ajout du filtrage include_patterns et ignore_patterns dans Features/Documentation.py.
        Correction du bug d'exclusion silencieuse : config.py passait les logs en INFO, masquant le rejet des fichiers .py.
        Liste noire de sécurité forcée (exclut .env, secrets, logs) dans le scanner de documentation.
    Recherche Native (Grep) :
        Ajout de execute_recherche_texte dans Features/SearchEngine.py pour scanner le contenu des fichiers sans utiliser de tokens IA.
        Exposition via l'outil rechercher_texte.
    Refactoring "Fast-Track" :
        Ajout du paramètre auto_apply pour permettre des modifications directes sans l'étape de "Plan de Refactoring".
    Dispatcher (ai_helper.py) : Refonte complète (V42) pour router correctement toutes les commandes (RAG, Système, Git, Web) et gérer les nouveaux arguments.
###🖥️ Interface Utilisateur (UI)
    Contrôle d'Interruption :
        Le bouton "Envoyer" devient "Stop" (Rouge) pendant le streaming.
        La saisie reste active pendant la génération.
        Implémentation de l'arrêt propre (abort_current_stream) dans le Worker.
    Diagnostic : Ajout d'un sélecteur de "Niveau de Log" (DEBUG/INFO) dans l'onglet Système.
    Robustesse : Sécurisation de BackupManagerWindow (fix crash TclError) pour éviter les plantages si la fenêtre est fermée pendant une mise à jour.
###🐛 Correctifs (Bug Fixes)
    Fix UnboundLocalError: free variable 'e' : Correction critique dans la gestion des erreurs des générateurs Python.
    Fix AttributeError: resolve : Suppression de l'appel erroné sur le générateur dans le Worker.
    Fix JSON Config : Correction du formatage corrompu dans app_settings.json (suppression de la ligne "json" en trop).
    Fix Import re : Réintégration du module manquant dans worker.py.
    Fix RAG Latency : Déplacement du chargement database.init_db en début de thread Worker pour un démarrage sans latence.
---
## 2025-11-28 - Architecture "Phoenix" (Post-Rollback)

**Refonte majeure suite au rollback de la version instable. Stabilisation complète du flux Gemini 2.5, introduction du Tunneling JSON pour les outils, et activation de l'autonomie ReAct sécurisée.**

### 🚀 Fonctionnalités Principales
* **Cerveau Hybride Gemini 2.5 :** Migration complète vers `gemini-2.5-flash` (Chat) et `gemini-2.5-pro` (Code/Architecte). Résolution des alias (`fast`, `smart`) pour éviter les erreurs 404.
* **Tunnel d'Outils (`!native_tool`) :** Implémentation d'un pont robuste transmettant les objets JSON natifs de Gemini vers le système sans perte de données (arguments complexes, listes).
* **Autonomie ReAct V29 :** Le Worker dispose désormais d'une boucle de réflexion autonome (Action -> Observation (Mémoire) -> Réaction) avec une limite de profondeur configurable.
* **Mémoire RAG Active :** Le système indexe automatiquement chaque fichier modifié (`FileSystem`, `Refactoring`) et injecte un contexte pertinent (Top-3 chunks) avant chaque réponse de l'IA.
* **Sécurité "Force Text" :** Les agents créatifs (`Coder`, `Writer`) sont forcés en mode texte pur pour empêcher les boucles récursives d'appel d'outils (ex: `generer_tests` appelant l'outil `generer_tests`).

### 🛠️ Correctifs Techniques & Système
* **Worker (Cerveau) :**
    * Correction de l'assignation de session (`NoneType` error).
    * Optimisation de la mémoire : Fenêtre glissante (10 msgs) + Troncation des vieux blocs de code (>1000 chars).
    * Détection d'intention NLP : Suppression des regex rigides pour laisser l'IA décider de l'usage des outils.
    * Fix des bindings UI (`get_backup_list`, `restore_backup`).
* **Backup Manager :**
    * **Anti-Récursion :** Correction critique de la boucle infinie lors de la création de ZIP (exclusion stricte du dossier de backup et des venv/db).
    * **Sécurité :** Déclenchement systématique d'une sauvegarde complète du projet avant toute modification de code (`CodeQuality`, `Refactoring`, `Documentation`).
* **Database (RAG) :**
    * Ajout de `index_project_files` pour le scan global (`!indexer_contexte`).
    * Ajout de `add_file_to_db` avec gestion de l'idempotence (suppression anciens chunks avant ajout).
    * Correction de syntaxe (`global` variable scope).
* **AI Core (Noyau) :**
    * Ajout de `_proto_to_dict_recursive` pour corriger le crash de sérialisation `RepeatedCompositeContainer`.
    * Gestion de l'erreur `MALFORMED_FUNCTION_CALL` (Feedback automatique à l'IA pour auto-correction).

### 🔌 Outils & Features
* **Refactoring :** Ajout d'un nettoyeur Regex (`_extraire_code_python`) pour extraire le code même si l'IA est bavarde.
* **FileSystem :** Réduction de la verbosité des retours d'écriture (Succès court pour l'IA, contenu complet pour l'UI).
* **Documentation :** Rétablissement de la génération atomique asynchrone (Task Queue).
* **AI Helper :** Mapping complet des 15 outils du schéma vers leurs fonctions respectives.
---

### (25 Novembre 2025) - Consolidation UX & Robustesse Core

**Objectif :** Unification radicale des interfaces, sécurisation des configurations et correction de la dette technique accumulée sur l'UI.

**Refonte Interface & Configuration**
* **Centre de Contrôle Unifié (SettingsWindow) :** Fusion complète des classes `SettingsWindow` et `DetailedConfigWindow` en une seule interface modulaire à onglets, éliminant la redondance du code UI.
* **Onglet Moteurs & API Dynamique :** Remplacement des champs statiques par un `Treeview` interactif pour la gestion des clés API (`api_keys_list`), permettant l'ajout/suppression à chaud de clés pour n'importe quel provider.
* **Composants UI Riches :** Implémentation de sliders avec labels de valeur dynamiques et de `Tooltip` contextuels sur tous les paramètres critiques (Température, Rétention, etc.).

**Robustesse & Correctifs Techniques**
* **Patch Critique JSON :** Correction de la syntaxe du fichier `app_settings.json` (virgule manquante dans `fallback_order`) qui empêchait le démarrage à froid.
* **Patch UI Widget :** Résolution de l'`AttributeError: 'DoubleVar' object has no attribute 'widget'` en stockant explicitement les références des widgets (`_WIDGET`) dans le dictionnaire de variables.
* **Compatibilité Legacy :** Ajout de protections (`dict.get`) dans `_refresh_api_key_list` pour gérer les anciens formats de configuration sans crasher (`KeyError: provider`).

---

### (21 Novembre 2025) - Observabilité Industrielle & Refactoring

**Objectif :** Transformer le prototype en une application de production observable, mesurable et modulaire.

**Observabilité & Métriques (Le "Système Nerveux")**
* **Unified Logger v2 :** Réécriture complète du système de logs (`Features/UnifiedLogger.py`) pour supporter le multithreading (`_log_lock`), l'UTF-8 et capturer l'ID du thread pour le débogage parallèle.
* **Instrumentation Performance :** Introduction du Context Manager `Timer` pour mesurer la latence exacte des modules critiques (Routage vs Dispatch vs RAG).
* **Métriques Consommation :** Suivi précis des tokens (entrée/sortie) et identification du modèle réel utilisé (ex: `gemini-1.5-pro`) dans `ai_core.py`.

**Refactoring Architecturel (La "Grande Migration")**
* **Explosion de `local_actions.py` :** Découpage du fichier monolithique en modules spécialisés et autonomes dans `Features/` :
    * `ProjectManager.py` : Gestion de la Roadmap, Synthèse et Historique.
    * `Refactoring.py` : Logique de modification de code et plans de refactoring.
    * `CodeQuality.py` : Audit de code, Sécurité et Génération de Tests.
    * `FileSystem.py` : Opérations disque sécurisées (Lecture/Écriture/Listing).
* **Nettoyage des Cycles :** Résolution des dépendances circulaires entre le Worker, le Registre de Commandes et le Swarm Manager.

**Stabilité Core**
* **Patch Worker :** Correction du crash `Tuple Index Error` dans la boucle de traitement des tâches `_handle_command`.
* **Support SOTA :** Mise à jour de `config.py` pour inclure les définitions des modèles Gemini 2.0 Flash et Pro Experimental.

---

### (20 Novembre 2025) - Omniscience & Résilience

**Objectif :** Doter l'IA d'une compréhension contextuelle totale du projet et immuniser le système contre les pannes API.

**Moteur Omniscient (RAG Avancé)**
* **Algorithme 1+3+4 :** Implémentation d'une stratégie de recherche hybride fusionnant :
    1.  **Frecency :** Pondération des fichiers récemment modifiés.
    2.  **Graphe :** Analyse statique des symboles (classes/fonctions).
    3.  **Vecteur :** Recherche sémantique via FAISS.
* **DeepDoc (Map-Reduce) :** Capacité à documenter intégralement un projet via `Features/Documentation.py` en découpant l'analyse en lots (Map) puis en synthétisant une carte d'architecture (Reduce).

**Résilience & UX**
* **Smart Queue :** Système de file d'attente prioritaire qui capture les erreurs `429 Rate Limit`, met les tâches en pause et les relance automatiquement.
* **Journaled State :** Gestion de la roadmap en mode "Append-Only" pour garantir l'historique des modifications sans jamais écraser les données précédentes.
* **Key Binder :** Système de capture de touches physiques pour la configuration personnalisée des raccourcis clavier (`KeyCaptureDialog`).

---

### (19 Novembre 2025) - Swarm Intelligence

**Objectif :** Transition d'un agent unique vers une architecture multi-agents spécialisée.

* **Architecture Swarm :** Création du `swarm_manager` et définition des `agent_personas` (ARCHITECT, GUARDIAN, CODER, REVIEWER, WRITER).
* **Routing Dynamique :** Capacité du Worker à changer l'instruction système de l'IA (`update_system_instruction`) à la volée pour spécialiser la session en cours.
* **Pools Isolés :** Séparation physique des workers en pools distincts (Chat Interactif vs Tâches de Fond) pour garantir la réactivité de l'interface.

---

### (18 Novembre 2025) - Stabilisation RAG

**Objectif :** Résolution définitive des problèmes de dépendances vectorielles.

* **Migration FAISS + SQLite :** Abandon des solutions basées sur Pydantic (LanceDB) au profit d'une architecture hybride robuste : FAISS pour les vecteurs en mémoire et SQLite pour le stockage textuel.
* **Lazy Loading RAG :** Chargement différé des modèles lourds (`sentence-transformers`) via `_ensure_rag_dependencies`, permettant un démarrage instantané de l'application.
* **Synchro GDrive :** Mécanisme de compression ZIP automatique pour synchroniser le trio de fichiers DB (.sqlite, .faiss, .pkl) vers le cloud.

---

### (17 Novembre 2025) - Intégration GitHub

**Objectif :** Connecter l'assistant au monde extérieur.

* **Module `github_manager` :** Client API GitHub capable de scanner l'arborescence récursivement, de filtrer les fichiers binaires/inutiles et de télécharger le code pertinent.
* **Agents Distants :**
    * `!analyser_repo` : Clone virtuel et audit architectural.
    * `!creer_pr` : Création automatisée de Pull Requests.
* **Session Robuste :** Implémentation du `Retry Backoff` dans `requests.Session` pour gérer les instabilités réseau et les rate-limits GitHub.

---

### Versions Historiques (Fondations & Évolutions)

#### (Hot-Swap)
* **Config Dynamique :** Capacité du Worker à recharger `load_app_settings()` à la volée sans redémarrage.

#### (Multi-Key Architecture)
* **Rotation de Clés :** Implémentation de `KeyManager` avec gestion des verrous (`Lock`) et rotation automatique des clés API en cas d'erreur 429.
* **Pools de Clés :** Introduction de la structure `api_keys_list` pour supporter un nombre illimité de clés.

#### (IDE Avancé)
* **Éditeur Riche :** Création du widget `TextEditorWithLineNumbers` supportant la numérotation et le scroll synchronisé.
* **Syntax Highlighting :** Intégration de `pygments` pour la coloration syntaxique temps réel du code dans le chat et les éditeurs.
* **Navigation par Onglets :** Adoption de `CTkTabview` pour gérer Chat Principal, Chat Secondaire et Fichiers.

#### (Intégration Audio)
* **Module Audio :** Création de `audio_manager.py` gérant l'ASR (SpeechRecognition) et le TTS (Gemini).
* **Lazy Loading Audio :** Chargement différé des libs lourdes (`sounddevice`, `numpy`) pour ne pas impacter le temps de démarrage.

#### (Configuration Centralisée)
* **Standardisation JSON :** Migration de toutes les variables d'environnement et constantes hardcodées vers `app_settings.json`.

#### (Refonte UI)
* **CustomTkinter :** Migration complète de `tkinter` standard vers `CustomTkinter` pour un design moderne et le support du mode sombre.

#### (Multithreading)
* **Architecture Worker :** Séparation du thread UI (Main) et du thread logique (Worker) avec communication par `queue.Queue` pour éviter le gel de l'interface.

---

##  Essaim 2.0 & Fondations de Scalabilité

**Objectif :** Maturation de l'architecture multi-agents (Swarm), optimisation des performances pour les tâches de fond, et amélioration de l'ergonomie des outils de développement.

### Optimisation & Scalabilité (Fondations)
* **Indexation RAG Asynchrone :** L'indexation des connaissances (RAG) s'exécute désormais en arrière-plan (`worker.py`), garantissant que l'interface utilisateur (`app.py`) reste fluide et réactive pendant les opérations lourdes.
* **Commandes Vocales :** Activation du module `audio_manager`, posant les bases pour les interactions vocales futures (reconnaissance et synthèse).
* **Journalisation Robuste et Centralisée :** Intégration du `UnifiedLogger` (`Features/UnifiedLogger.py`) pour une capture d'événements structurée et thread-safe à travers toute l'application.

### Intelligence de l'Essaim (Swarm) 2.0
* **Bus de Communication Asynchrone pour les Agents :** Le `swarm_manager` utilise un système de messagerie pour découpler la communication entre agents, permettant des interactions plus complexes et parallèles.
* **Recrutement Dynamique d'Agents Spécialisés :** Mise en place d'une logique de "recrutement" où le `swarm_manager` sélectionne et instancie l'agent le plus adapté à une tâche en se basant sur ses compétences prédéfinies (`agent_personas.py`).
* **Visualiseur d'Activité du Swarm en Temps Réel :** Un nouvel onglet dans l'interface (`ui_windows.py`) permet de visualiser les agents actifs et les messages qu'ils échangent, améliorant l'observabilité.

### Outils & Ergonomie Avancée
* **Menu Contextuel Enrichi :** Le menu clic-droit sur l'explorateur de fichiers a été étendu avec des actions rapides comme "Ajouter au contexte RAG" et "Restaurer version précédente".
* **Contrôles d'Optimisation des Coûts :** L'interface utilisateur propose désormais des réglages pour limiter le nombre de pas de réflexion de l'IA (ReAct) et activer un "Mode Économique" forçant l'usage de modèles moins coûteux.
* **Gestion Dynamique des Modèles d'IA :** Les utilisateurs peuvent désormais ajouter, éditer et supprimer des configurations de modèles d'IA directement depuis l'interface, qui sont persistées dans `app_settings.json`.

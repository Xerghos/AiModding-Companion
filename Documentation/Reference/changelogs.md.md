```json
[
  {
    "path": "changelogs.md",
    "description": "Ce fichier journalise de manière exhaustive toutes les modifications apportées au projet AiModding-Companion, classées par date et par thème. Il sert de référence pour suivre l'évolution technique, les corrections de bugs, les ajouts de fonctionnalités et les refactorisations architecturales.",
    "atomic_technical_documentation": {
      "nature": "Documentation Technique Atomique",
      "file_path": "changelogs.md",
      "content_summary": "Journal des modifications détaillé du projet AiModding-Companion, couvrant les évolutions par date, avec des sections sur les correctifs, les nouvelles fonctionnalités, les refactorisations architecturales, et les améliorations d'interface utilisateur. Documente l'historique des versions depuis les fondations multithreadées jusqu'aux architectures avancées comme Swarm V2 et 'Closed-Loop'.",
      "related_architectural_components": [],
      "usage_context": "Suivi de l'historique des versions, compréhension des évolutions techniques, identification des changements par date ou par fonctionnalité.",
      "change_log": [
        {
          "version_date": "12 Décembre 2025",
          "version_name": "Patch \"Polyglotte & Stabilité\"",
          "focus": "Résolution des conflits d'architecture (Texte vs Outils Natifs) et fiabilisation du moteur.",
          "changes": [
            {
              "component": "Moteur & Worker",
              "details": "Correction majeure de la communication Worker/API Gemini en mode Swarm. Support Hybride (Fix \"Réponse Vide\"): réécriture de _handle_chat_stream pour parser texte brut et objets FunctionCall natifs. Filtre Anti-Bégaiement: interception des commandes identiques relancées.",
              "technical_debt_addressed": "Bugs de réponse vide, hallucinations de commandes."
            },
            {
              "component": "Configuration & Factory",
              "details": "Correction du Mapping des Modèles: mise à jour de ai_core/factory.py pour lire config depuis cloud_models_registry. Synchronisation Hot-Reload: patch de Worker/core.py pour recharger la SessionFactory sans redémarrage.",
              "technical_debt_addressed": "Utilisation forcée du modèle gemini-2.5-flash-lite, changement de modèle non immédiat."
            },
            {
              "component": "Interface Utilisateur",
              "details": "Switch Raisonnement (ui/widgets.py): correction du widget pour renvoyer un booléen strict.",
              "technical_debt_addressed": "Détection incorrecte de l'activation/désactivation du mode 'Thinking'."
            },
            {
              "component": "Nettoyage Technique",
              "details": "Gestion des Clés API: correction de l'appel de méthode dans Factory. Logs: clarification des logs de streaming.",
              "technical_debt_addressed": "Appel de méthode obsolète, logs de streaming ambigus."
            }
          ]
        },
        {
          "version_date": "11 Décembre 2025",
          "version_name": "Update \"Swarm V2 & Fortification\"",
          "focus": "Intelligence Agentique, Sécurité Active & Tests Unitaires.",
          "changes": [
            {
              "component": "Architecture Swarm V2",
              "details": "Refonte complète des agents pour autonomie supervisée. Whitelisting (Sécurité Cognitive), Tiering Dynamique (routage modèles), Context Awareness (mémoire partagée), Boucle d'Autonomie (Retry Loop), Mode Raisonnement (On/Off).",
              "technical_debt_addressed": "Agents avec accès à des outils non pertinents, manque de mémoire contextuelle, nécessité d'intervention humaine pour les enchaînements."
            },
            {
              "component": "Sécurité & Dispatcher",
              "details": "Sécurisation de features/ai_helper.py. Middleware \"Sanity Check\" (Confinement, Protection des Actifs). Robustesse Parsing (réparation auto erreurs JSON). Lazy Loading pour résoudre cycles d'importation.",
              "technical_debt_addressed": "Vulnérabilités d'accès aux fichiers, erreurs de parsing JSON, cycles d'importation."
            },
            {
              "component": "Standardisation des Outils",
              "details": "Mise à niveau des modules (WebSurfer, SemanticMemory) pour signature standard et compatibilité base vectorielle V2.",
              "technical_debt_addressed": "Appels obsolètes, manque d'injection de dépendances."
            },
            {
              "component": "Infrastructure de Tests (QA)",
              "details": "Création d'une suite de tests unitaires complète (tests/) pour garantir la non-régression.",
              "technical_debt_addressed": "Manque de tests unitaires."
            }
          ]
        },
        {
          "version_date": "2025-12-09",
          "version_name": "Architecture \"Closed-Loop\" & Standardisation Totale",
          "focus": "Implémentation du feedback loop, correction des hallucinations, amélioration de la gestion des clés et sessions.",
          "changes": [
            {
              "component": "Système de \"Feedback Loop\"",
              "details": "Boucle de Rétroaction Fermée (`Worker/core.py`): injection des résultats d'outils dans la session IA. Correction des Hallucinations de Protocole: Détecteur Polyglotte, Traducteur Kwargs -> JSON. Mémoire Sémantique (`Features/SemanticMemory.py`): refonte de `_extract_text` pour objets Protobuf, standardisation enregistrement `function_response`.",
              "technical_debt_addressed": "IA aveugle aux résultats des outils, hallucinations de protocole, crash de sérialisation."
            },
            {
              "component": "Gestionnaire de Clés & Sessions",
              "details": "Smart Key Manager V3 (`ai_core/keys.py`): Health Score Routing. Fallback Cascade V2 (`ai_core/factory.py`): chaîne de secours hiérarchique. Métriques & Logs (`ai_core/sessions.py`): calcul de tokens streaming, correction de portée variable.",
              "technical_debt_addressed": "Rotation de clés basique, manque de fallback de modèles, bugs de portée variable et de calcul de tokens."
            },
            {
              "component": "Standardisation des Features (Outils)",
              "details": "Dispatcher (`Features/ai_helper.py`): `lister_outils`, renforcement parser JSON. Refactoring: sécurité AST, backup forcé, nettoyage code. Backup Manager: alignement signatures, gestion `force`, protection crashs. FileSystem: ajout ops disque. Search Engine: filtrage robuste. Git Actions: mode session `disposable`. Code Quality: détection fichiers vides.",
              "technical_debt_addressed": "Signatures non standard, manque d'introspection des outils, bugs de parsing, manque d'opérations disque, recherche peu robuste, manque de sécurité dans Git Actions, détection fichiers vides manquante."
            },
            {
              "component": "Interface Utilisateur (UI)",
              "details": "Menu Paramètres: affichage Health Score clés, audit à la demande. Menu Outils: découplage IA/Système pour appels directs Worker.",
              "technical_debt_addressed": "Monitoring CPU excessif, appels UI passant par le chat non nécessaires."
            },
            {
              "component": "Correctifs Divers",
              "details": "RAG/Database: imports conditionnels. Auto-Maintenance: timer refresh `architecture_map.json`.",
              "technical_debt_addressed": "Crashs si chromadb absent, rafraîchissement manuel de la map d'architecture."
            }
          ]
        },
        {
          "version_date": "2025-11-30",
          "version_name": "Phase 23 : Performance & Fiabilité",
          "focus": "Implémentation du caching LLM et de la rotation des logs.",
          "changes": [
            {
              "component": "Stratégie de Cache pour les Requêtes LLM",
              "details": "`ai_core.py` implémente un cache sur disque via `diskcache`, réduction des appels API redondants.",
              "technical_debt_addressed": "Appels API redondants, latence élevée."
            },
            {
              "component": "Log Rotation et Nettoyage Automatique",
              "details": "`Features/UnifiedLogger.py` intègre un `RotatingFileHandler` pour gérer la taille des logs.",
              "technical_debt_addressed": "Saturation du disque par les logs."
            }
          ]
        },
        {
          "version_date": "[2025-11-30]",
          "version_name": "Architecture V42 \"Ultimate\" (Streaming, Caching & Swarm)",
          "focus": "Streaming complet, caching multi-clés, hygiène mémoire, parallélisme, intégration Groq.",
          "changes": [
            {
              "component": "Streaming End-to-End (V38-V40)",
              "details": "Implémentation complète du streaming de réponse ('machine à écrire'). Mise à jour `ai_core.py`, `stream_wrapper`, `worker.py`.",
              "technical_debt_addressed": "Réponses bloquantes."
            },
            {
              "component": "Shadow Caching Multi-Clés (V33-V34)",
              "details": "Cache contextuel avancé via `Features/CacheManager.py`. Circuit Breaker pour erreurs de quota.",
              "technical_debt_addressed": "Limites API, crashs dus aux quotas."
            },
            {
              "component": "Hygiène Mémoire (V26-V35)",
              "details": "Troncation des vieux messages système/utilisateur dans l'historique. Sessions Jetables (`disposable=True`) pour tâches atomiques.",
              "technical_debt_addressed": "Consommation excessive de tokens, pollution du contexte principal."
            },
            {
              "component": "Swarm & Parallélisme (V30)",
              "details": "ThreadPoolExecutor dans Worker pour exécution asynchrone des tâches lourdes.",
              "technical_debt_addressed": "Blocage du chat par les tâches de fond."
            },
            {
              "component": "Intégration Groq (V37)",
              "details": "Ajout de `GroqSession` dans `ai_core.py` pour modèles Llama 3 et Mixtral. Mise à jour `config.py`.",
              "technical_debt_addressed": "Manque de support pour des fournisseurs d'API alternatifs rapides."
            },
            {
              "component": "Documentation Intelligente (\"Smart Doc\")",
              "details": "Filtrage `include_patterns`, `ignore_patterns`. Correction bug exclusion silencieuse. Liste noire de sécurité.",
              "technical_debt_addressed": "Exclusion de fichiers non désirée, manque de sécurité dans le scanner."
            },
            {
              "component": "Recherche Native (Grep)",
              "details": "Ajout de `execute_recherche_texte` dans `Features/SearchEngine.py` (scan sans tokens IA).",
              "technical_debt_addressed": "Recherche gourmande en tokens."
            },
            {
              "component": "Refactoring \"Fast-Track\"",
              "details": "Paramètre `auto_apply` pour modifications directes.",
              "technical_debt_addressed": "Étape de plan de refactoring parfois superflue."
            },
            {
              "component": "Dispatcher (ai_helper.py)",
              "details": "Refonte complète pour routage correct et gestion nouveaux arguments.",
              "technical_debt_addressed": "Routage des commandes obsolète."
            },
            {
              "component": "Contrôle d'Interruption UI",
              "details": "Bouton 'Envoyer' devient 'Stop' pendant streaming. Arrêt propre (`abort_current_stream`) dans Worker.",
              "technical_debt_addressed": "Impossible d'interrompre la génération en cours."
            },
            {
              "component": "Diagnostic UI",
              "details": "Sélecteur de 'Niveau de Log' (DEBUG/INFO) dans onglet Système.",
              "technical_debt_addressed": "Niveau de log fixe."
            },
            {
              "component": "Robustesse UI",
              "details": "Sécurisation `BackupManagerWindow` (fix crash TclError).",
              "technical_debt_addressed": "Plantage de l'UI lors de la fermeture pendant une mise à jour."
            },
            {
              "component": "Correctifs (Bug Fixes)",
              "details": "Fix UnboundLocalError, AttributeError, JSON Config, Import re, RAG Latency.",
              "technical_debt_addressed": "Erreurs critiques diverses."
            }
          ]
        },
        {
          "version_date": "2025-11-28",
          "version_name": "Architecture \"Phoenix\" (Post-Rollback)",
          "focus": "Stabilisation Gemini 2.5, Tunneling JSON, autonomie ReAct sécurisée.",
          "changes": [
            {
              "component": "Cerveau Hybride Gemini 2.5",
              "details": "Migration vers `gemini-2.5-flash` et `gemini-2.5-pro`. Résolution des alias.",
              "technical_debt_addressed": "Erreurs 404 dues aux alias de modèles."
            },
            {
              "component": "Tunnel d'Outils (\"!native_tool\")",
              "details": "Pont robuste pour transmettre objets JSON natifs de Gemini.",
              "technical_debt_addressed": "Perte de données lors de la transmission des outils."
            },
            {
              "component": "Autonomie ReAct V29",
              "details": "Boucle de réflexion autonome avec limite de profondeur.",
              "technical_debt_addressed": "Manque d'autonomie et de capacité à enchaîner les actions."
            },
            {
              "component": "Mémoire RAG Active",
              "details": "Indexation automatique fichiers modifiés, injection contexte pertinent.",
              "technical_debt_addressed": "Contexte IA non à jour avec les modifications du projet."
            },
            {
              "component": "Sécurité \"Force Text\"",
              "details": "Agents créatifs forcés en mode texte pour éviter boucles récursives d'outils.",
              "technical_debt_addressed": "Boucles récursives d'appels d'outils."
            },
            {
              "component": "Worker (Cerveau)",
              "details": "Correction assignation session, optimisation mémoire, détection intention NLP, fix bindings UI.",
              "technical_debt_addressed": "Crashs, consommation mémoire excessive, regex rigides, bindings UI défectueux."
            },
            {
              "component": "Backup Manager",
              "details": "Anti-Récursion (exclusion dossiers), sauvegarde forcée avant modification code.",
              "technical_debt_addressed": "Boucle infinie lors de la création ZIP, manque de sauvegarde préventive.",
              "technical_debt_addressed": "Boucle infinie lors de la création ZIP, manque de sauvegarde préventive."
            },
            {
              "component": "Database (RAG)",
              "details": "Ajout `index_project_files`, `add_file_to_db` (idempotence), correction syntaxe `global`.",
              "technical_debt_addressed": "Manque d'indexation globale, problèmes d'idempotence, erreurs de scope `global`."
            },
            {
              "component": "AI Core (Noyau)",
              "details": "Ajout `_proto_to_dict_recursive` (correction sérialisation), gestion `MALFORMED_FUNCTION_CALL`.",
              "technical_debt_addressed": "Crash de sérialisation, manque de gestion des erreurs d'appel de fonction."
            },
            {
              "component": "Outils & Features",
              "details": "Refactoring: nettoyeur Regex, retours écriture réduits. FileSystem: retours écriture optimisés. Documentation: génération asynchrone. AI Helper: mapping complet outils.",
              "technical_debt_addressed": "Extraction de code difficile, verbosité des retours, génération synchrone, mapping incomplet."
            }
          ]
        },
        {
          "version_date": "(25 Novembre 2025)",
          "version_name": "Consolidation UX & Robustesse Core",
          "focus": "Unification des interfaces, sécurisation des configurations, correction dette technique UI.",
          "changes": [
            {
              "component": "Centre de Contrôle Unifié (SettingsWindow)",
              "details": "Fusion de `SettingsWindow` et `DetailedConfigWindow` en une interface modulaire à onglets.",
              "technical_debt_addressed": "Redondance du code UI."
            },
            {
              "component": "Onglet Moteurs & API Dynamique",
              "details": "Remplacement champs statiques par `Treeview` interactif pour gestion clés API.",
              "technical_debt_addressed": "Gestion statique des clés API."
            },
            {
              "component": "Composants UI Riches",
              "details": "Sliders avec labels dynamiques, `Tooltip` contextuels.",
              "technical_debt_addressed": "Manque d'interactivité et de contexte sur les paramètres."
            },
            {
              "component": "Patch Critique JSON",
              "details": "Correction syntaxe `app_settings.json` (virgule manquante).",
              "technical_debt_addressed": "Impossibilité de démarrage à froid."
            },
            {
              "component": "Patch UI Widget",
              "details": "Résolution `AttributeError: 'DoubleVar' object has no attribute 'widget'`.",
              "technical_debt_addressed": "Référence widget manquante."
            },
            {
              "component": "Compatibilité Legacy",
              "details": "Protections (`dict.get`) dans `_refresh_api_key_list` pour gérer anciens formats.",
              "technical_debt_addressed": "Crashs avec anciens formats de configuration."
            }
          ]
        },
        {
          "version_date": "(21 Novembre 2025)",
          "version_name": "Observabilité Industrielle & Refactoring",
          "focus": "Application de production observable, mesurable et modulaire.",
          "changes": [
            {
              "component": "Unified Logger v2",
              "details": "Réécriture `Features/UnifiedLogger.py` pour supporter multithreading, UTF-8, capture ID thread.",
              "technical_debt_addressed": "Logs non thread-safe, problèmes d'encodage, difficulté de débogage parallèle."
            },
            {
              "component": "Instrumentation Performance",
              "details": "Introduction Context Manager `Timer` pour mesurer latence modules critiques.",
              "technical_debt_addressed": "Manque de mesure précise de la performance."
            },
            {
              "component": "Métriques Consommation",
              "details": "Suivi tokens (entrée/sortie), identification modèle réel utilisé dans `ai_core.py`.",
              "technical_debt_addressed": "Suivi de consommation de tokens imprécis."
            },
            {
              "component": "Explosion de `local_actions.py`",
              "details": "Découpage en modules spécialisés dans `Features/` (`ProjectManager`, `Refactoring`, `CodeQuality`, `FileSystem`).",
              "technical_debt_addressed": "Fichier monolithique difficile à maintenir."
            },
            {
              "component": "Nettoyage des Cycles",
              "details": "Résolution dépendances circulaires Worker, Registre Commandes, Swarm Manager.",
              "technical_debt_addressed": "Dépendances circulaires."
            },
            {
              "component": "Patch Worker",
              "details": "Correction crash `Tuple Index Error` dans `_handle_command`.",
              "technical_debt_addressed": "Crash lors du traitement des tâches."
            },
            {
              "component": "Support SOTA",
              "details": "Mise à jour `config.py` pour modèles Gemini 2.0 Flash et Pro Experimental.",
              "technical_debt_addressed": "Manque de support pour les derniers modèles Gemini."
            }
          ]
        },
        {
          "version_date": "(20 Novembre 2025)",
          "version_name": "Omniscience & Résilience",
          "focus": "Compréhension contextuelle totale du projet, immunisation contre pannes API.",
          "changes": [
            {
              "component": "Moteur Omniscient (RAG Avancé)",
              "details": "Algorithme 1+3+4: Frecency, Graphe, Vecteur (FAISS). DeepDoc (Map-Reduce) via `Features/Documentation.py`.",
              "technical_debt_addressed": "Compréhension contextuelle limitée, documentation de projet non automatisée."
            },
            {
              "component": "Résilience & UX",
              "details": "Smart Queue (capture erreurs 429, pause/relance). Journaled State (roadmap Append-Only). Key Binder (capture touches physiques).",
              "technical_debt_addressed": "Gestion des rate limits inefficace, perte d'historique, configuration raccourcis fastidieuse."
            }
          ]
        },
        {
          "version_date": "(19 Novembre 2025)",
          "version_name": "Swarm Intelligence",
          "focus": "Transition vers une architecture multi-agents spécialisée.",
          "changes": [
            {
              "component": "Architecture Swarm",
              "details": "Création `swarm_manager`, définition `agent_personas` (ARCHITECT, GUARDIAN, CODER, REVIEWER, WRITER).",
              "technical_debt_addressed": "Architecture mono-agent."
            },
            {
              "component": "Routing Dynamique",
              "details": "Changement `update_system_instruction` à la volée pour spécialisation.",
              "technical_debt_addressed": "Manque de flexibilité dans la spécialisation de l'agent."
            },
            {
              "component": "Pools Isolés",
              "details": "Séparation physique workers (Chat Interactif vs Tâches de Fond).",
              "technical_debt_addressed": "Impact des tâches de fond sur la réactivité de l'interface."
            }
          ]
        },
        {
          "version_date": "(18 Novembre 2025)",
          "version_name": "Stabilisation RAG",
          "focus": "Résolution des problèmes de dépendances vectorielles.",
          "changes": [
            {
              "component": "Migration FAISS + SQLite",
              "details": "Abandon solutions Pydantic (LanceDB) au profit d'une architecture hybride robuste.",
              "technical_debt_addressed": "Instabilité des solutions RAG précédentes."
            },
            {
              "component": "Lazy Loading RAG",
              "details": "Chargement différé libs lourdes (`sentence-transformers`) via `_ensure_rag_dependencies`.",
              "technical_debt_addressed": "Temps de démarrage élevé."
            },
            {
              "component": "Synchro GDrive",
              "details": "Compression ZIP auto pour synchronisation DB (sqlite, faiss, pkl).",
              "technical_debt_addressed": "Synchronisation manuelle des fichiers de base de données."
            }
          ]
        },
        {
          "version_date": "(17 Novembre 2025)",
          "version_name": "Intégration GitHub",
          "focus": "Connexion de l'assistant au monde extérieur.",
          "changes": [
            {
              "component": "Module `github_manager`",
              "details": "Client API GitHub: scan récursif, filtrage, téléchargement code.",
              "technical_debt_addressed": "Manque d'intégration avec GitHub."
            },
            {
              "component": "Agents Distants",
              "details": "`!analyser_repo` (audit architectural), `!creer_pr` (création automatisée).",
              "technical_debt_addressed": "Fonctionnalités GitHub non automatisées."
            },
            {
              "component": "Session Robuste",
              "details": "Retry Backoff dans `requests.Session` pour gérer instabilités réseau et rate-limits.",
              "technical_debt_addressed": "Erreurs réseau et rate-limits non gérés."
            }
          ]
        },
        {
          "version_date": "Versions Historiques (Fondations & Évolutions)",
          "version_name": "Hot-Swap, Multi-Key, IDE Avancé, Audio, Config Centralisée, Refonte UI, Multithreading",
          "focus": "Construire les fondations robustes et modernes de l'application.",
          "changes": [
            {
              "component": "Config Dynamique",
              "details": "Worker recharge `load_app_settings()` à la volée.",
              "technical_debt_addressed": "Nécessité de redémarrage pour les changements de configuration."
            },
            {
              "component": "Rotation de Clés",
              "details": "KeyManager avec gestion verrous et rotation auto en cas d'erreur 429.",
              "technical_debt_addressed": "Gestion basique des clés API."
            },
            {
              "component": "Pools de Clés",
              "details": "Structure `api_keys_list` pour support illimité de clés.",
              "technical_debt_addressed": "Limite du nombre de clés API."
            },
            {
              "component": "Éditeur Riche",
              "details": "Widget `TextEditorWithLineNumbers` (numérotation, scroll synchronisé).",
              "technical_debt_addressed": "Manque de fonctionnalités d'édition de code avancées."
            },
            {
              "component": "Syntax Highlighting",
              "details": "Intégration `pygments` pour coloration temps réel.",
              "technical_debt_addressed": "Pas de coloration syntaxique dans l'interface."
            },
            {
              "component": "Navigation par Onglets",
              "details": "Adoption `CTkTabview` pour Chat Principal, Chat Secondaire, Fichiers.",
              "technical_debt_addressed": "Navigation d'interface basique."
            },
            {
              "component": "Module Audio",
              "details": "Gestion ASR (SpeechRecognition) et TTS (Gemini).",
              "technical_debt_addressed": "Pas d'intégration audio."
            },
            {
              "component": "Lazy Loading Audio",
              "details": "Chargement différé libs audio lourdes.",
              "technical_debt_addressed": "Impact sur le temps de démarrage dû aux libs audio."
            },
            {
              "component": "Standardisation JSON",
              "details": "Migration vars d'env et constantes vers `app_settings.json`.",
              "technical_debt_addressed": "Configuration éparpillée et hardcodée."
            },
            {
              "component": "Refonte UI",
              "details": "Migration `tkinter` vers `CustomTkinter` (design moderne, mode sombre).",
              "technical_debt_addressed": "Interface utilisateur datée."
            },
            {
              "component": "Architecture Worker",
              "details": "Séparation thread UI (Main) et thread logique (Worker) via `queue.Queue`.",
              "technical_debt_addressed": "Blocage de l'interface utilisateur par les traitements lourds."
            }
          ]
        },
        {
          "version_date": "Essaim 2.0 & Fondations de Scalabilité",
          "version_name": "Optimisation, Scalabilité, Swarm 2.0, Outils Avancés",
          "focus": "Maturation architecture multi-agents, optimisation performances fond de tâches, ergonomie outils dev.",
          "changes": [
            {
              "component": "Indexation RAG Asynchrone",
              "details": "Indexation s'exécute en arrière-plan (`worker.py`), interface fluide.",
              "technical_debt_addressed": "Interface gelée pendant l'indexation RAG."
            },
            {
              "component": "Commandes Vocales",
              "details": "Activation `audio_manager` pour interactions vocales futures.",
              "technical_debt_addressed": "Absence d'interaction vocale."
            },
            {
              "component": "Journalisation Robuste et Centralisée",
              "details": "Intégration `UnifiedLogger` (`Features/UnifiedLogger.py`) thread-safe.",
              "technical_debt_addressed": "Journalisation non structurée et potentiellement conflictuelle."
            },
            {
              "component": "Bus de Communication Asynchrone pour les Agents",
              "details": "`swarm_manager` utilise messagerie pour découpler agents.",
              "technical_debt_addressed": "Communication inter-agents simple et synchrone."
            },
            {
              "component": "Recrutement Dynamique d'Agents Spécialisés",
              "details": "Sélection et instanciation de l'agent adapté à la tâche.",
              "technical_debt_addressed": "Manque de flexibilité dans l'attribution des agents."
            },
            {
              "component": "Visualiseur d'Activité du Swarm en Temps Réel",
              "details": "Nouvel onglet UI (`ui_windows.py`) pour visualiser agents actifs et messages.",
              "technical_debt_addressed": "Manque d'observabilité sur le fonctionnement du Swarm."
            },
            {
              "component": "Menu Contextuel Enrichi",
              "details": "Actions rapides sur explorateur fichiers ('Ajouter au contexte RAG', 'Restaurer version').",
              "technical_debt_addressed": "Fonctionnalités limitées dans le menu contextuel."
            },
            {
              "component": "Contrôles d'Optimisation des Coûts",
              "details": "Réglages pour limiter pas de réflexion IA et activer 'Mode Économique'.",
              "technical_debt_addressed": "Contrôle limité sur les coûts d'utilisation de l'IA."
            },
            {
              "component": "Gestion Dynamique des Modèles d'IA",
              "details": "Ajout/édition/suppression configurations modèles IA via interface, persistées dans `app_settings.json`.",
              "technical_debt_addressed": "Configuration des modèles d'IA statique et non modifiable par l'utilisateur."
            }
          ]
        }
      ]
    }
  }
]
```
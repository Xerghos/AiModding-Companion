# Analyse de Performance et Pistes d'Amélioration (Logs 02-Jan 20h12)

Basé sur l'analyse des logs `global_debug_02-Jan_20h12_26.log`, voici les goulots d'étranglement identifiés et les solutions proposées pour accélérer l'application.

## 📊 Métriques Clés (Pour une requête simple "bonjour!")
- **Temps Total Traitement:** ~7.5s
- **Génération Repo Map:** ~1.94s (Bloquant pour le contexte RAG)
- **Récupération RAG:** ~1.97s
- **Génération LLM (Thinking + Réponse):** ~4.5s
- **Tâche de fond "Compressor":** ~7.8s (Concurrent)

## 🚀 Pistes d'Amélioration Prioritaires

### 1. ⚡ Réparation et Mise en Cache Persistante de la Repo Map
**Diagnostic :** Les logs affichent `⚠️ WARNING │ Aucun fichier trouvé pour la Repo Map`. Cela indique que le scan actuel échoue ou filtre tout, rendant la génération inutilement coûteuse (2s) pour un résultat vide.
**Solution :**
- **Correction du scan :** Vérifier pourquoi `RepoMapGenerator` ne trouve rien (problème de chemin racine ou filtres trop stricts).
- **Cache Persistant Intelligent :** Implémenter un cache fichier (JSON/Pickle) stockant la map.
- **Règle d'Invalidation :** Ne régénérer que si :
    1.  Le fichier de cache a > 5 minutes.
    2.  ET le hash global des fichiers sources a changé (utiliser `ContextLoader` ou un tri efficace pour détecter les changements pertinents sans tout rescanner).

### 2. 📉 Déplacer la Compression en Fin de Cycle (Post-Réponse)
**Problème :** Le worker "Compressor" se déclenche dès la réception du prompt utilisateur (`[TASK_RECEIVED] Type: user_prompt` suivi immédiatement de `optimize_history`). Cela crée une contention CPU/Réseau pile au moment où l'utilisateur attend une réponse.
**Solution :**
- **Déplacement du Trigger :** S'assurer que l'appel à `optimize_history` (ou la tâche de fond associée) ne soit lancé qu'**après** la fin complète de la génération de la réponse de l'IA (`stream_end`).
- Cela libère les ressources pour la génération et permet potentiellement d'inclure l'échange qui vient de se terminer dans l'analyse future.

### 3. 🚀 Optimisation RAG (Non-Bloquant)
**Problème:** `_retrieve_rag_context` attend séquentiellement la fin de la génération de la Repo Map.
**Solution:**
- Si une Repo Map "stale" (ancienne de quelques minutes) existe, l'utiliser immédiatement pour le contexte RAG au lieu d'attendre la régénération.
- Lancer la régénération en arrière-plan pur pour la *prochaine* requête.

## 📝 Plan d'Action Technique (TODOs)

### A. Système de Fichiers & RepoMap
- [ ] **Debug Scan :** Créer un script `scripts/debug_repo_map.py` pour lister exactement quels fichiers sont vus par `RepoMapGenerator` et comprendre le warning "Aucun fichier trouvé".
- [ ] **Implémenter Cache Persistant :** Modifier `features/context/repo_map.py` pour sauvegarder/charger `repo_map_cache.json`.
- [ ] **Logique d'Invalidation :** Ajouter une vérification de timestamp (5 min) et implémenter un calcul de hash rapide sur les dossiers clés (ex: `features/`, `ai_core/`) pour éviter la régénération si rien n'a bougé.

### B. Orchestration Worker
- [ ] **Déplacer le Hook de Compression :** Dans `worker/core.py`, localiser l'appel à `optimize_history` (probablement dans `_handle_user_prompt`) et le déplacer dans le bloc `finally` ou après la boucle de streaming de `_handle_chat_stream`.
- [ ] **Vérification Asynchrone :** S'assurer que ce lancement post-réponse ne bloque pas l'interface (le faire dans un thread séparé ou via la queue de tâches avec une priorité basse).

### C. Optimisation RAG
- [ ] **RAG Non-Bloquant :** Modifier `_retrieve_rag_context` pour charger la RepoMap du cache s'il existe, et ne lancer la régénération que si le cache est absent ou invalide, sans bloquer si une version "suffisante" est dispo.
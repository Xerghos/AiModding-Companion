# Stratégies d'Optimisation de la Vitesse CodeAssist (Gemini)

Ce document analyse les goulots d'étranglement actuels de l'implémentation CodeAssist et propose des solutions concrètes pour réduire la latence de 15s+ à une cible de 2-4s (similaire à gemini-cli).

## 📊 Analyse des Performances Actuelles (Log: 02-Jan_07h35_36)

| Étape | Temps (approx) | Cause Principale | Statut |
| :--- | :--- | :--- | :--- |
| **Préparation Contexte** | ~3.0s | Génération Repo Map + Scan fichiers | 🔴 Critique |
| **Appel API 1 (Tool)** | ~3.0s | Latence réseau + Inférence | 🟡 Moyen |
| **Exécution Outil** | ~0.6s | Lecture fichier locale | 🟢 Bon |
| **Appel API 2 (Réponse)** | ~10-16s | "Thinking" long + Upload contexte (11k tokens) | 🔴 Critique |
| **Total** | **~17s** | Cumul des étapes séquentiels | **Trop Lent** |

---

## 🚀 Pistes d'Amélioration Prioritaires

### 1. ⚡ Optimisation du Contexte (RAG & RepoMap) - Gain estimé: 2-3s
Actuellement, `_retrieve_rag_context` prend ~3s avant même d'envoyer la requête.
*   **Problème :** La Repo Map est régénérée à chaque requête (`generate_repo_map`), ce qui scanne le disque.
*   **Solution :**
    *   **Mise en cache agressive :** Ne régénérer la Repo Map que si des fichiers ont changé (hash global du projet) ou toutes les N minutes.
    *   **Parallélisation :** Lancer `retrieve_relevant_context` (RAG) et `generate_repo_map` en parallèle strict (threads séparés) et non séquentiellement.
    *   **Mode "Fast" :** Pour les requêtes simples (chat), désactiver ou réduire la profondeur de la Repo Map.

### 2. on passe.

### 3. 💾 Context Caching 
Le contexte statique pour le caching implicite doit être analysé sous supervision de l'utilisateur
### 4. 🌐 Connexion Persistante (Keep-Alive) - Gain estimé: 0.5-1s
*   **Problème :** `AuthorizedSession` est recréée ou la connexion TCP/TLS est fermée entre les appels.
*   **Solution :**
    *   S'assurer que `requests.Session` (via `AuthorizedSession`) est bien réutilisée entre les appels `streamGenerateContent` pour bénéficier du `Connection: keep-alive` (évite le handshake SSL à chaque fois).

### 5. 🏎️ Streaming Optimisé (Client Side) - Gain estimé: Perception utilisateur
*   **Problème :** Le parsing des chunks SSE et la conversion en objets LiteLLM ajoutent une micro-latence.
*   **Solution :**
    *   Optimiser la boucle de lecture du stream (`iter_lines` vs `iter_content`).
    *   Réduire le logging debug excessif dans la boucle critique de streaming (actuellement très verbeux).

---

## 🛠️ Plan d'Action Technique

### Phase A : Quick Wins (Immédiat)
1.  **Désactiver les logs DEBUG** dans `CodeAssistClient._request_streaming_post` (trop d'I/O disque).
2.  **Mettre en cache la RepoMap** dans `features.context.repo_map`. Ne pas la recalculer si < 60s.
3.  **Réutiliser la session HTTP** : Vérifier que `self._session` dans `CodeAssistClient` reste ouvert et vivant.

### Phase B : ON PASSE.

### Phase C : Architecture
1.  **Pré-chargement (Prefetching) :** Lancer la génération de contexte (RAG/RepoMap) dès que l'utilisateur commence à taper (si possible) ou en arrière-plan périodique.

---

*Fichier généré le 02 Janvier 2026 par l'Agent d'Optimisation.*

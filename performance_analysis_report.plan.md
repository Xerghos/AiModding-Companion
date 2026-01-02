# Plan d'Optimisation des Performances - Exécutable

> **Basé sur l'analyse des logs du 02 Janvier 2026**  
> **Objectif : Réduire la latence de ~7.5s à < 1s pour une requête simple**

## 📊 Métriques Clés Actuelles

- **Temps Total Traitement:** ~7.5s
- **Génération Repo Map:** ~1.94s (Bloquant pour le contexte RAG)
- **Récupération RAG:** ~1.97s
- **Génération LLM (Thinking + Réponse):** ~4.5s
- **Tâche de fond "Compressor":** ~7.8s (Concurrent)

## 🎯 Objectifs

- [ ] Réduire le temps de préparation du contexte (actuellement ~2s bloquant) à < 0.1s via caching
- [ ] Supprimer la contention CPU/Réseau pendant la génération de réponse
- [ ] Rendre la récupération RAG non-bloquante

---

## Étape 1 : Système de Cache Persistant pour RepoMap

**Objectif :** Éliminer la régénération systématique de la Repo Map (2s/requête) en implémentant un cache disque intelligent.

### 1.1 Créer le script de diagnostic

**Fichier à créer :** `scripts/debug_repo_map.py`

**Tâches :**

- [ ] Créer le fichier `scripts/debug_repo_map.py`
- [ ] Ajouter les imports nécessaires :

  ```python
  from features.context.repo_map import RepoMapGenerator, get_repo_map_generator
  from features.context.symbol_graph import get_symbol_graph
  from config.paths import get_path
  from config.settings import APP_SETTINGS
  import os
  ```

- [ ] Implémenter la fonction `analyze_symbol_graph()` :
  - Créer une instance : `symbol_graph = get_symbol_graph(db_path_base)`
  - Appeler `symbol_graph.get_top_files(top_n=20)` pour obtenir la liste des fichiers
  - Logger chaque fichier avec son score PageRank : `print(f"  - {file_path} (PageRank: {score:.4f})")`
  - Vérifier si `top_files` est vide et logger un avertissement
- [ ] Implémenter la fonction `analyze_exclusions()` :
  - Lire `APP_SETTINGS.get("code_analysis", {}).get("ignored_folders", [])`
  - Lire `APP_SETTINGS.get("system_settings", {}).get("ignored_files", [])`
  - Lister tous les fichiers Python dans `features/`, `ai_core/`, `worker/`
  - Pour chaque fichier, vérifier s'il est exclu par les patterns avec `fnmatch.fnmatch()`
  - Logger les fichiers exclus et les motifs d'exclusion
- [ ] Implémenter la fonction `test_signature_extraction()` :
  - Pour chaque fichier dans `top_files`, appeler `repo_map_gen._extract_signatures(abs_path)`
  - Logger le nombre de signatures extraites par fichier
  - Identifier les fichiers qui retournent des listes vides
- [ ] Créer la fonction `main()` :

  ```python
  def main():
      db_path = get_path(APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid"))
      repo_map_gen = get_repo_map_generator(db_path)
      symbol_graph = get_symbol_graph(db_path)
      
      print("=== Analyse SymbolGraph ===")
      analyze_symbol_graph(symbol_graph)
      
      print("\n=== Analyse Exclusions ===")
      analyze_exclusions()
      
      print("\n=== Test Extraction Signatures ===")
      test_signature_extraction(repo_map_gen, symbol_graph)
  ```

- [ ] Ajouter `if __name__ == "__main__": main()`
- [ ] Tester le script : `python scripts/debug_repo_map.py`

### 1.2 Améliorer les utilitaires existants (PRÉREQUIS)

**⚠️ IMPORTANT :** Avant d'implémenter le cache, améliorer les fonctions utilitaires existantes.

#### 1.2.1 Améliorer `config/utils.py::charger_json_robuste()`

**Fichier à modifier :** `config/utils.py`

**Problèmes identifiés :**

- Retourne `[]` (liste vide) par défaut, même pour des fichiers qui devraient retourner un dict
- Utilise `print()` au lieu de logging
- Pas de distinction entre fichier inexistant et erreur de parsing

**Tâches :**

- [ ] Modifier `charger_json_robuste()` pour accepter un paramètre `default_return` :

  ```python
  def charger_json_robuste(file_path, default_return=None):
      """
      Charge un fichier JSON de manière robuste.
      
      Args:
          file_path: Chemin du fichier JSON
          default_return: Valeur à retourner si fichier inexistant ou erreur (None par défaut)
      
      Returns:
          Données JSON chargées ou default_return
      """
      if not os.path.exists(file_path):
          return default_return
      try:
          with open(file_path, 'r', encoding='utf-8') as f:
              data = json.load(f)
          return data
      except Exception as e:
          # Utiliser logging au lieu de print
          import logging
          logging.getLogger("config.utils").warning(f"Erreur chargement JSON {file_path}: {e}")
          return default_return
  ```

- [ ] Mettre à jour les appels existants pour maintenir la compatibilité :
  - `charger_historique_robuste_worker()` : `charger_json_robuste(path, default_return=[])`
  - `charger_liens_contexte_worker()` : `charger_json_robuste(path, default_return=[])`
- [ ] Tester que les fonctions existantes fonctionnent toujours

#### 1.2.2 Exposer `_calculate_file_hash()` publiquement

**Fichier à modifier :** `features/Documentation.py`

**Problème identifié :**

- `_calculate_file_hash()` est privée (commence par `_`) mais utile ailleurs

**Tâches :**

- [ ] Créer une fonction publique `calculate_file_hash()` qui appelle la privée :

  ```python
  def calculate_file_hash(file_path: str) -> Optional[str]:
      """
      Calcule le hash SHA256 d'un fichier (fonction publique).
      
      Args:
          file_path: Chemin du fichier
      
      Returns:
          Hash hexadécimal ou None en cas d'erreur
      """
      return _calculate_file_hash(file_path)
  ```

- [ ] OU renommer `_calculate_file_hash()` en `calculate_file_hash()` (breaking change, vérifier les usages)

### 1.3 Implémenter la persistance du cache (OPTIMISÉ)

**Fichier à modifier :** `features/context/repo_map.py`

**Tâches :**

- [ ] Ajouter les imports nécessaires en haut du fichier :

  ```python
  from config.utils import charger_json_robuste, sauvegarder_json
  from features.Documentation import calculate_file_hash  # OU _calculate_file_hash si non exposée
  from features.context.merkle_sync import MerkleTreeSync
  ```

- [ ] Définir les constantes de cache après les imports :

  ```python
  CACHE_DIR = "cache"  # Dossier relatif au workspace
  REPO_MAP_CACHE_FILE = "repo_map_cache.json"
  REPO_MAP_HASH_FILE = "repo_map_hash.json"
  ```

- [ ] Ajouter la méthode `_get_cache_path()` dans la classe `RepoMapGenerator` :

  ```python
  def _get_cache_path(self, filename: str) -> str:
      """Retourne le chemin absolu du fichier de cache."""
      cache_dir = get_path(CACHE_DIR)
      os.makedirs(cache_dir, exist_ok=True)
      return os.path.join(cache_dir, filename)
  ```

- [ ] Ajouter la méthode `_load_cache()` en utilisant `charger_json_robuste()` amélioré :

  ```python
  def _load_cache(self) -> Optional[Dict[str, Any]]:
      """Charge le cache depuis le disque (utilise utilitaire amélioré)."""
      cache_path = self._get_cache_path(REPO_MAP_CACHE_FILE)
      cache_data = charger_json_robuste(cache_path, default_return=None)
      if cache_data and isinstance(cache_data, dict):
          log.debug(f"✅ Cache Repo Map chargé depuis {cache_path}")
          return cache_data
      return None
  ```

- [ ] Ajouter la méthode `_save_cache()` en utilisant `sauvegarder_json()` :

  ```python
  def _save_cache(self, content: str, top_n: int, db_path_base: str) -> None:
      """Sauvegarde le cache sur le disque (utilise utilitaire existant)."""
      cache_path = self._get_cache_path(REPO_MAP_CACHE_FILE)
      cache_data = {
          "content": content,
          "timestamp": time.time(),
          "top_n": top_n,
          "db_path_base": str(db_path_base) if db_path_base else None
      }
      if sauvegarder_json(cache_path, cache_data):
          log.info(f"✅ Cache Repo Map sauvegardé: {len(content)} caractères")
      else:
          log.warning(f"⚠️ Échec sauvegarde cache Repo Map")
  ```

- [ ] Modifier la méthode `generate_repo_map()` pour utiliser le cache :
  - Avant la génération, appeler `_load_cache()`
  - Si le cache existe et est valide (vérification d'âge dans étape 1.3), retourner `cache["content"]`
  - Sinon, générer normalement et appeler `_save_cache()` après génération
  - Code à ajouter au début de `generate_repo_map()` :

    ```python
    # Vérifier le cache (validation complète dans étape 1.3)
    cache_data = self._load_cache()
    if cache_data:
        cache_age = time.time() - cache_data.get('timestamp', 0)
        if cache_age < 60:  # Temporaire, sera remplacé par _is_cache_valid()
            log.debug(f"✅ Repo Map récupérée depuis le cache ({cache_age:.1f}s)")
            return cache_data.get('content', '')
    ```

  - Code à ajouter à la fin de `generate_repo_map()`, avant `return repo_map_text` :

    ```python
    # Sauvegarder le cache
    self._save_cache(repo_map_text, top_n, self.db_path_base)
    ```

### 1.4 Implémenter la logique d'invalidation (OPTIMISÉ avec MerkleTreeSync)

**Fichier à modifier :** `features/context/repo_map.py`

**⚠️ OPTIMISATION :** Utiliser `MerkleTreeSync` existant au lieu de créer `_compute_directory_hash()`.

**Tâches :**

- [ ] Ajouter la configuration dans `config/settings.py` :
  - Localiser la section `DEFAULT_SETTINGS` dans `config/settings.py`
  - Ajouter après la section `"ai_engine"` :

    ```python
    "repo_map_cache": {
        "ttl_seconds": 300,  # 5 minutes par défaut
        "watch_directories": ["features/", "ai_core/", "worker/"],
        "watch_files": ["config/architecture_map.json"]
    },
    ```

- [ ] **SUPPRIMER** les méthodes `_compute_directory_hash()` et `_compute_file_hash()` (utiliser MerkleTreeSync et calculate_file_hash à la place)
- [ ] Ajouter la méthode `_get_project_hash()` en RÉUTILISANT MerkleTreeSync :

  ```python
  def _get_project_hash(self) -> str:
      """Calcule le hash global du projet via MerkleTreeSync (réutilise code existant)."""
      cache_config = APP_SETTINGS.get("repo_map_cache", {})
      watch_dirs = cache_config.get("watch_directories", ["features/", "ai_core/", "worker/"])
      watch_files = cache_config.get("watch_files", ["config/architecture_map.json"])
      
      hasher = hashlib.sha256()
      
      # Utiliser MerkleTreeSync pour chaque dossier surveillé
      for dir_path in watch_dirs:
          abs_dir = get_path(dir_path) if not os.path.isabs(dir_path) else dir_path
          if os.path.exists(abs_dir):
              try:
                  merkle = MerkleTreeSync(abs_dir)
                  root = merkle.build_tree()
                  if root and root.hash:
                      hasher.update(root.hash.encode())
              except Exception as e:
                  log.warning(f"Erreur construction Merkle pour {dir_path}: {e}")
      
      # Ajouter les fichiers surveillés individuellement (utilise fonction existante)
      for file_path in watch_files:
          abs_file = get_path(file_path) if not os.path.isabs(file_path) else file_path
          file_hash = calculate_file_hash(abs_file)  # OU _calculate_file_hash() si non exposée
          if file_hash:
              hasher.update(file_hash.encode())
      
      return hasher.hexdigest()
  ```

  - **Note :** `MerkleTreeSync.build_tree()` peut être coûteux pour de gros projets. Considérer un cache du hash Merkle si nécessaire.
- [ ] Ajouter la méthode `_save_project_hash()` en utilisant `sauvegarder_json()` :

  ```python
  def _save_project_hash(self, project_hash: str) -> None:
      """Sauvegarde le hash du projet (utilise utilitaire amélioré)."""
      hash_path = self._get_cache_path(REPO_MAP_HASH_FILE)
      sauvegarder_json(hash_path, {"hash": project_hash, "timestamp": time.time()})
  ```

- [ ] Ajouter la méthode `_load_project_hash()` en utilisant `charger_json_robuste()` amélioré :

  ```python
  def _load_project_hash(self) -> Optional[str]:
      """Charge le hash précédent (utilise utilitaire amélioré)."""
      hash_path = self._get_cache_path(REPO_MAP_HASH_FILE)
      data = charger_json_robuste(hash_path, default_return=None)
      return data.get("hash") if isinstance(data, dict) else None
  ```

- [ ] Ajouter la méthode `_is_cache_valid()` dans `RepoMapGenerator` :

  ```python
  def _is_cache_valid(self, cache_data: Dict[str, Any]) -> bool:
      """Vérifie si le cache est valide (âge + hash)."""
      if not cache_data:
          return False
      
      # Vérifier l'âge
      cache_config = APP_SETTINGS.get("repo_map_cache", {})
      ttl_seconds = cache_config.get("ttl_seconds", 300)
      cache_age = time.time() - cache_data.get("timestamp", 0)
      
      if cache_age >= ttl_seconds:
          log.debug(f"Cache expiré: {cache_age:.1f}s >= {ttl_seconds}s")
          return False
      
      # Vérifier le hash
      previous_hash = self._load_project_hash()
      current_hash = self._get_project_hash()
      
      if previous_hash != current_hash:
          log.debug(f"Hash projet changé: {previous_hash[:8]}... -> {current_hash[:8]}...")
          return False
      
      return True
  ```

- [ ] Modifier `generate_repo_map()` pour utiliser `_is_cache_valid()` :
  - Remplacer la vérification temporaire (étape 1.2) par :

    ```python
    cache_data = self._load_cache()
    if cache_data and self._is_cache_valid(cache_data):
        log.debug(f"✅ Repo Map récupérée depuis le cache valide")
        return cache_data.get('content', '')
    ```

- [ ] Modifier `generate_repo_map()` pour sauvegarder le hash après génération :
  - Après `_save_cache()`, ajouter :

    ```python
    # Sauvegarder le hash du projet
    project_hash = self._get_project_hash()
    self._save_project_hash(project_hash)
    ```

- [ ] Ajouter une méthode d'invalidation manuelle `invalidate_cache()` :

  ```python
  def invalidate_cache(self) -> None:
      """Invalide le cache manuellement."""
      cache_path = self._get_cache_path(REPO_MAP_CACHE_FILE)
      hash_path = self._get_cache_path(REPO_MAP_HASH_FILE)
      try:
          if os.path.exists(cache_path):
              os.remove(cache_path)
          if os.path.exists(hash_path):
              os.remove(hash_path)
          log.info("🗑️ Cache Repo Map invalidé manuellement")
      except Exception as e:
          log.warning(f"Erreur invalidation cache: {e}")
  ```

- [ ] Exposer `invalidate_cache()` dans la fonction globale `invalidate_repo_map_cache()` :
  - Modifier la fonction existante pour aussi supprimer les fichiers disque :

    ```python
    def invalidate_repo_map_cache():
        """Invalide le cache Repo Map (mémoire + disque)."""
        global _repo_map_cache
        _repo_map_cache = None
        
        # Invalider aussi le cache disque
        if _repo_map_generator:
            _repo_map_generator.invalidate_cache()
        else:
            # Si le générateur n'existe pas encore, supprimer directement les fichiers
            cache_dir = get_path("cache")
            cache_file = os.path.join(cache_dir, REPO_MAP_CACHE_FILE)
            hash_file = os.path.join(cache_dir, REPO_MAP_HASH_FILE)
            for f in [cache_file, hash_file]:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass
        
        log.debug("🗑️ Cache Repo Map invalidé (mémoire + disque)")
    ```

- [ ] Exposer `invalidate_cache()` dans la fonction globale `get_repo_map_generator()` :
  - Ajouter après `get_repo_map_generator()` :

    ```python
    def invalidate_repo_map_cache():
        """Invalide le cache Repo Map (fonction globale)."""
        global _repo_map_generator
        if _repo_map_generator:
            _repo_map_generator.invalidate_cache()
    ```

### 1.4 Intégration dans l'UI Settings

**Fichier à modifier :** `ui/windows/settings.py`

**Tâches :**

- [ ] Localiser la méthode `_build_general_tab()` ou créer `_build_performance_tab()`
- [ ] Ajouter une section "Cache Repo Map" :

  ```python
  self._add_header(scroll, "🗺️ Cache Repo Map")
  self._add_slider(scroll, "repo_map_cache.ttl_seconds", "TTL Cache (secondes)", 60, 3600, 300)
  self._add_text(scroll, "repo_map_cache.watch_directories", "Dossiers surveillés (un par ligne)", 
                 "\n".join(APP_SETTINGS.get("repo_map_cache", {}).get("watch_directories", [])))
  self._add_text(scroll, "repo_map_cache.watch_files", "Fichiers surveillés (un par ligne)",
                 "\n".join(APP_SETTINGS.get("repo_map_cache", {}).get("watch_files", [])))
  ```

- [ ] Ajouter un bouton "Invalidate Cache" :

  ```python
  invalidate_btn = ctk.CTkButton(scroll, text="🗑️ Invalider le Cache", 
                                  command=lambda: self._invalidate_repo_map_cache())
  invalidate_btn.pack(pady=5)
  ```

- [ ] Ajouter la méthode `_invalidate_repo_map_cache()` :

  ```python
  def _invalidate_repo_map_cache(self):
      """Invalide le cache Repo Map."""
      try:
          from features.context.repo_map import invalidate_repo_map_cache
          invalidate_repo_map_cache()
          # Afficher un message de confirmation
          messagebox.showinfo("Cache invalidé", "Le cache Repo Map a été invalidé avec succès.")
      except Exception as e:
          messagebox.showerror("Erreur", f"Erreur lors de l'invalidation: {e}")
  ```

---

## 📝 Résumé des Améliorations Nécessaires aux Fonctions Existantes

> **⚠️ IMPORTANT :** Ces améliorations doivent être faites AVANT l'étape 1.3 (voir section 1.2)

### `config/utils.py::charger_json_robuste()`

**Problèmes :**

- ❌ Retourne `[]` par défaut (incompatible avec dict)
- ❌ Utilise `print()` au lieu de logging
- ❌ Pas de paramètre pour valeur par défaut personnalisée

**Améliorations nécessaires :**

- ✅ Ajouter paramètre `default_return=None`
- ✅ Remplacer `print()` par logging
- ✅ Retourner `default_return` au lieu de `[]` hardcodé

### `features/Documentation.py::_calculate_file_hash()`

**Problèmes :**

- ❌ Fonction privée (commence par `_`)
- ❌ Pas accessible depuis d'autres modules

**Améliorations nécessaires :**

- ✅ Exposer publiquement (renommer ou créer wrapper)
- ✅ OU documenter comme API publique si intentionnellement privée

### `features/context/merkle_sync.py::MerkleTreeSync`

**Points d'attention :**

- ⚠️ `build_tree()` peut être coûteux pour gros projets
- ✅ Déjà optimisé avec exclusions
- ✅ Hash racine disponible directement

**Utilisation recommandée :**

- ✅ Utiliser tel quel pour détection de changements
- ⚠️ Considérer cache du hash Merkle si performance insuffisante

---

## Étape 2 : Optimisation de l'Orchestration Worker

**Objectif :** Libérer les ressources pendant que l'utilisateur attend la réponse en déplaçant les tâches de fond.

### 2.1 Déplacer le trigger de compression

**Fichier à modifier :** `worker/core.py`

**Tâches :**

- [ ] Localiser l'appel actuel à `optimize_history` :
  - Ouvrir `worker/core.py`
  - Chercher la ligne ~1290 dans la méthode `run()` de la classe `Worker`
  - Code actuel à trouver :

    ```python
    if action == 'chat':
        self.bg_executor.submit(self._handle_chat_stream, payload)
        if GlobalMemoryManager and self.main_session:
            self.bg_executor.submit(GlobalMemoryManager.optimize_history, self.main_session)
    ```

- [ ] **SUPPRIMER** la ligne `self.bg_executor.submit(GlobalMemoryManager.optimize_history, self.main_session)`
- [ ] Localiser la méthode `_handle_chat_stream()` :
  - Chercher la ligne ~872 : `def _handle_chat_stream(self, payload):`
  - Identifier la fin de la méthode (après `self.response_queue.put({'type': 'ui_stream_end'})`)
- [ ] Ajouter l'appel à `optimize_history` à la fin de `_handle_chat_stream()` :
  - Localiser le point juste avant le `return` final ou dans un bloc `finally`
  - Ajouter après `self.response_queue.put({'type': 'ui_stream_end'})` :

    ```python
    # Compression mémoire en arrière-plan (non-bloquant)
    if GlobalMemoryManager and self.main_session:
        def optimize_async():
            try:
                if hasattr(self.main_session, 'chat'):
                    GlobalMemoryManager.optimize_history(self.main_session)
                    log.debug("✅ Optimisation mémoire terminée en arrière-plan")
            except Exception as e:
                log.warning(f"Erreur optimisation mémoire asynchrone: {e}", exc_info=True)
        
        # Lancer dans un thread séparé avec priorité basse
        optimize_thread = threading.Thread(
            target=optimize_async,
            daemon=True,
            name="MemoryOptimizer"
        )
        optimize_thread.start()
    ```

### 2.2 Vérifications et tests

**Tâches :**

- [ ] Vérifier que `threading` est importé en haut de `worker/core.py`
- [ ] Vérifier que `GlobalMemoryManager` est importé en haut de `worker/core.py`
- [ ] Vérifier que `self.main_session` est accessible dans `_handle_chat_stream()`
- [ ] Tester que `ui_stream_end` est envoyé immédiatement
- [ ] Tester que l'UI passe à l'état "Prêt" sans délai
- [ ] Vérifier que la compression se fait bien en arrière-plan (logs)
- [ ] Vérifier qu'une nouvelle requête ne bloque pas si la compression est en cours

---

## Étape 3 : RAG Non-Bloquant

**Objectif :** Lancer la génération LLM plus tôt en utilisant des données contextuelles "suffisantes" plutôt que "parfaites mais lentes".

### 3.1 Modifier la récupération de contexte

**Fichier à modifier :** `worker/core.py` (méthode `_retrieve_rag_context`)

**Tâches :**

- [ ] Localiser la méthode `_retrieve_rag_context()` :
  - Chercher la ligne ~195 : `def _retrieve_rag_context(self, query):`
  - Identifier la section "A. Repo Map" (ligne ~205-215)
- [ ] Modifier la logique Repo Map pour utiliser le cache même périmé :
  - Remplacer le code actuel :

    ```python
    from features.context.repo_map import get_cached_repo_map
    db_path = get_path(APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid"))
    repo_map = get_cached_repo_map(db_path_base=db_path, max_chars=None)
    if repo_map:
        rag_components["repo_map"] = repo_map
    ```

  - Par :

    ```python
    from features.context.repo_map import get_cached_repo_map, get_repo_map_generator
    from features.context.repo_map import _repo_map_cache  # Accès au cache global
    
    db_path = get_path(APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid"))
    
    # Essayer le cache d'abord (même légèrement périmé < 10 min)
    repo_map = get_cached_repo_map(db_path_base=db_path, max_chars=None)
    
    # Si cache absent ou très vieux (> 10 min), lancer régénération en arrière-plan
    cache_age = 0
    if _repo_map_cache:
        cache_age = time.time() - _repo_map_cache.get('timestamp', 0)
    
    if not repo_map or cache_age > 600:  # 10 minutes
        # Utiliser le cache actuel si disponible (même périmé)
        if _repo_map_cache and _repo_map_cache.get('content'):
            rag_components["repo_map"] = _repo_map_cache['content']
            log.info("⚠️ Utilisation cache Repo Map périmé, régénération en cours...")
        
        # Lancer régénération en arrière-plan
        def regenerate_repo_map_async():
            try:
                repo_map_gen = get_repo_map_generator(db_path)
                new_repo_map = repo_map_gen.generate_repo_map()
                # Le cache sera mis à jour automatiquement par generate_repo_map()
                log.info("✅ Repo Map régénérée en arrière-plan")
            except Exception as e:
                log.warning(f"Erreur régénération Repo Map: {e}")
        
        threading.Thread(target=regenerate_repo_map_async, daemon=True, name="RepoMapRegen").start()
    else:
        rag_components["repo_map"] = repo_map
    ```

- [ ] Ajouter l'import `time` en haut de `worker/core.py` si absent
- [ ] Vérifier que `threading` est importé (déjà fait dans étape 2)

### 3.2 Tests et validation

**Tâches :**

- [ ] Mesurer le temps d'exécution de `_retrieve_rag_context()` avec cache valide
- [ ] Vérifier que la régénération asynchrone fonctionne (logs)
- [ ] Vérifier qu'une nouvelle requête utilise le cache mis à jour
- [ ] Tester avec cache absent (première requête)
- [ ] Tester avec cache périmé (> 10 min)
- [ ] Vérifier que la latence totale est < 100ms avec cache

---

## 📋 Résumé des Fichiers à Modifier

### Fichiers à créer

- [ ] `scripts/debug_repo_map.py` - Script de diagnostic

### Fichiers à modifier

- [ ] `config/utils.py` - Améliorer `charger_json_robuste()` (PRÉREQUIS)
- [ ] `features/Documentation.py` - Exposer `calculate_file_hash()` publiquement (PRÉREQUIS)
- [ ] `features/context/repo_map.py` - Cache persistant + invalidation (utilise MerkleTreeSync)
- [ ] `worker/core.py` - Déplacement optimize_history + RAG non-bloquant
- [ ] `config/settings.py` - Configuration cache Repo Map
- [ ] `ui/windows/settings.py` - UI pour configuration cache

### Imports à vérifier/ajouter

- [ ] `config/utils.py` : `import logging` (pour améliorer `charger_json_robuste()`)
- [ ] `features/Documentation.py` : Exposer `calculate_file_hash()` publiquement
- [ ] `features/context/repo_map.py` :
  - `from config.utils import charger_json_robuste, sauvegarder_json`
  - `from features.Documentation import calculate_file_hash` (ou `_calculate_file_hash` si non exposée)
  - `from features.context.merkle_sync import MerkleTreeSync`
  - `import hashlib` (pour combiner les hashs)
- [ ] `worker/core.py` : `threading` (vérifier), `time` (vérifier)

---

## ✅ Métriques de Succès

- [ ] **Temps de préparation contexte :** < 0.1s (actuellement ~2s)
- [ ] **Latence UI "Prêt" :** Immédiate après `ui_stream_end` (actuellement bloquée par `optimize_history`)
- [ ] **Utilisation CPU/Réseau :** Réduite pendant génération réponse
- [ ] **Cache hit rate Repo Map :** > 90% après première génération

---

## 🔍 Notes Techniques

### Structure du cache Repo Map

```json
{
  "content": "string (contenu de la Repo Map)",
  "timestamp": 1234567890.123,
  "top_n": 20,
  "db_path_base": "db/knowledge_base_hybrid"
}
```

### Structure du hash projet

```json
{
  "hash": "sha256_hex_string",
  "timestamp": 1234567890.123
}
```

### Ordre d'implémentation recommandé

1. **Étape 1.2.1-1.2.2 :** Améliorer les utilitaires existants (PRÉREQUIS)
2. **Étape 1.1 :** Script de diagnostic (comprendre le problème)
3. **Étape 1.3 :** Cache persistant basique (utilise utilitaires améliorés)
4. **Étape 1.4 :** Invalidation intelligente (utilise MerkleTreeSync)
5. **Étape 1.5 :** UI Settings
6. **Étape 2 :** Déplacement compression
7. **Étape 3 :** RAG non-bloquant

### Points d'attention

- Le cache doit être thread-safe (accès depuis plusieurs threads)
- La régénération asynchrone ne doit pas créer de race conditions
- L'invalidation doit être atomique (supprimer cache + hash ensemble)
- Les erreurs de cache ne doivent pas bloquer la génération normale

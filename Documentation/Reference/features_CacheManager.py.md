# Documentation Technique - `features\CacheManager.py`

## 1. En-tête

*   **Titre**: Gestionnaire de Cache Multi-Modèle pour Contexte Dynamique
*   **Description concise**: Ce module implémente `MultiModelCacheManager`, une classe conçue pour gérer de manière atomique et contextuelle les caches pour plusieurs modèles d'IA (ex: Google Gemini) et clés API. Il prépare et assemble divers composants contextuels (arborescence du projet, architecture technique, mapping du dépôt, historique de la mémoire à long terme) pour optimiser les appels API, réduire la latence et les coûts via le caching. La version 5 introduit une architecture atomique des composants et une déduplication intelligente pour minimiser la redondance.
*   **Dépendances**:
    *   `logging`: Pour la journalisation des informations et des erreurs.
    *   `datetime`: Pour la gestion de la durée de vie (TTL) du cache.
    *   `os`: Pour les opérations sur le système de fichiers (arborescence).
    *   `json`: Pour la lecture et la manipulation des fichiers JSON (carte d'architecture).
    *   `pathlib.Path`: Pour des manipulations de chemins de fichiers orientées objet.
    *   `google.generativeai` (alias `genai`): SDK principal pour interagir avec les modèles Google GenAI.
    *   `google.generativeai.caching`: Module spécifique pour la gestion du caching de contenu GenAI.
    *   `config.get_path`: Utilitaire pour obtenir des chemins de fichiers configurés.
    *   `features.Decorators.trace_action`: Décorateur pour tracer l'exécution des méthodes clés.
    *   `features.context.repo_map.get_repo_map_generator` (importé dynamiquement): Pour générer la carte du dépôt.
    *   `features.SemanticMemory.GlobalMemoryManager` (importé dynamiquement): Pour récupérer l'historique de la mémoire à long terme.

## 2. Classes & Fonctions

### Classe `MultiModelCacheManager`

Gère les caches contextuels pour plusieurs modèles et plusieurs clés API. Sa structure interne utilise des tuples `(api_key, model_name)` comme clés pour stocker les noms des caches. La version 5 met l'accent sur une architecture atomique des composants contextuels, permettant une flexibilité accrue pour les modèles qui ne supportent pas le "prefix caching" natif.

#### `__init__(self)`

*   **Signature**: `__init__(self)`
*   **Arguments**:
    *   `self`: L'instance de la classe.
*   **Retours**: `None`
*   **Logique interne**:
    *   Initialise `self.cache_map` comme un dictionnaire vide pour stocker les noms de cache associés aux paires `(api_key, model_name)`.
    *   Initialise `self.content_payload` à `None`. Ce champ est utilisé pour stocker le contenu contextuel fusionné (mode rétrocompatible pour les caches Gemini).
    *   Initialise `self.components` comme un dictionnaire vide. Il stocke les blocs de contenu atomiques (ex: 'tree', 'arch', 'ltm', 'repo_map') pour une injection flexible.
    *   Définit `self.ttl_minutes` à 60, représentant la durée de vie par défaut du cache en minutes.
    *   Initialise `self.blacklisted_models` comme un `set` pour lister les noms de modèles pour lesquels le caching a échoué (souvent à cause de limites de quota ou d'erreurs).

#### `prepare_content(self)`

*   **Signature**: `prepare_content(self)`
*   **Arguments**:
    *   `self`: L'instance de la classe.
*   **Retours**: `None`
*   **Logique interne**:
    *   Cette méthode orchestre la génération et la collecte des divers composants du contexte global du projet. Ces composants sont stockés séparément dans `self.components` pour permettre une utilisation atomique ou fusionnée.
    *   **1. ARBORESCENCE PROJET (`tree`)**: Appelle `self._get_complete_tree()` pour générer une arborescence complète du répertoire de travail, ignorant les dossiers non pertinents (`.git`, `__pycache__`, `venv`, etc.). Le résultat est stocké sous la clé `'tree'`.
    *   **2. CARTOGRAPHIE ARCHITECTURALE (`arch`)**: Charge le fichier `config/architecture_map.json`. Si le fichier existe, il est condensé via `self._condense_architecture_map()` pour réduire sa taille et stocké sous la clé `'arch'`. Le JSON condensé est minifié et trié pour assurer une stabilité binaire.
    *   **3. REPO MAP (`repo_map`)**: Importe dynamiquement `get_repo_map_generator` et `APP_SETTINGS` pour obtenir le chemin de la base de données RAG. Génère ensuite une carte de la structure du dépôt via `repo_map_gen.get_repo_map()` et la stocke sous la clé `'repo_map'`.
    *   **4. HISTORIQUE LTM (`ltm`)**: Importe dynamiquement `GlobalMemoryManager` et récupère le bloc d'historique compressé de la mémoire à long terme, stocké sous la clé `'ltm'`.
    *   **5. DÉDUPLICATION INTER-SECTIONS**: Appelle `self._deduplicate_components()` pour supprimer les informations redondantes entre le `'repo_map'` et le `'ltm'`, donnant la priorité au `'repo_map'`.
    *   Finalement, assemble les composants `'tree'`, `'arch'`, et `'ltm'` (s'ils existent) dans `self.content_payload` pour la rétrocompatibilité avec les systèmes de cache qui attendent un unique bloc de texte.

#### `_get_optimized_tree(self, root_path, max_depth=3, ignore_dirs=None)`

*   **Signature**: `_get_optimized_tree(self, root_path, max_depth=3, ignore_dirs=None)`
*   **Arguments**:
    *   `self`: L'instance de la classe.
    *   `root_path` (str): Le chemin du répertoire racine à partir duquel générer l'arborescence.
    *   `max_depth` (int, optionnel): La profondeur maximale d'exploration de l'arborescence. Par défaut à 3.
    *   `ignore_dirs` (set, optionnel): Un ensemble de noms de répertoires à ignorer lors de la traversée.
*   **Retours**: `str` - Une chaîne de caractères représentant une vue arborescente compacte et nettoyée du projet.
*   **Logique interne**:
    *   Parcourt récursivement le système de fichiers à partir de `root_path`.
    *   Filtre les répertoires spécifiés dans `ignore_dirs` et les empêche d'être explorés.
    *   Limite la profondeur d'exploration à `max_depth`.
    *   Affiche les noms des dossiers et des fichiers avec une indentation correspondant à leur niveau de profondeur.
    *   Pour les dossiers contenant un grand nombre de fichiers (plus de 20), affiche un résumé "(... X fichiers ...)" au lieu de lister tous les fichiers pour une meilleure concision.
    *   Ignore les fichiers avec des extensions typiquement non pertinentes (`.pyc`, `.log`, `.sqlite`, etc.).

#### `_get_complete_tree(self, root_path, ignore_dirs=None)`

*   **Signature**: `_get_complete_tree(self, root_path, ignore_dirs=None)`
*   **Arguments**:
    *   `self`: L'instance de la classe.
    *   `root_path` (str): Le chemin du répertoire racine.
    *   `ignore_dirs` (set, optionnel): Un ensemble de noms de répertoires à ignorer.
*   **Retours**: `str` - Une chaîne de caractères représentant une arborescence complète du projet.
*   **Logique interne**:
    *   Similaire à `_get_optimized_tree`, mais génère une arborescence **complète** sans limite de profondeur.
    *   Ignore uniquement les dossiers explicitement listés dans `ignore_dirs` et une liste prédéfinie d'extensions de fichiers système/de cache jugées non pertinentes pour le contexte IA.
    *   Les dossiers et fichiers sont triés alphabétiquement pour garantir une sortie déterministe et cohérente.

#### `_condense_architecture_map(self, arch_data)`

*   **Signature**: `_condense_architecture_map(self, arch_data)`
*   **Arguments**:
    *   `self`: L'instance de la classe.
    *   `arch_data` (dict): Le dictionnaire complet de la carte d'architecture chargée depuis `architecture_map.json`.
*   **Retours**: `dict` - Une version condensée et optimisée de la carte d'architecture.
*   **Logique interne**:
    *   Réduit la taille de la carte d'architecture pour s'adapter aux limites de contexte des modèles et améliorer la pertinence.
    *   Conserve les métadonnées et les domaines.
    *   Pour la section `graph` (représentant les fichiers et leurs relations) :
        *   Limite le nombre de classes, fonctions et globales listées par fichier (ex: 5 classes, 8 fonctions).
        *   Tronque les docstrings à 100 caractères et les nettoie.
        *   Minifie les clés de dictionnaire pour réduire la verbosité (ex: "definitions" devient "def", "classes" devient "c").
        *   Limite le nombre de dépendances et de modules qui utilisent un fichier donné (ex: 5).
        *   N'inclut les métriques (lignes de code, complexité) que si elles sont significatives.
        *   Exclut les fichiers du graphe condensé s'ils ne contiennent que des informations de base et peu d'éléments sémantiques.

#### `_deduplicate_components(self)`

*   **Signature**: `_deduplicate_components(self)`
*   **Arguments**:
    *   `self`: L'instance de la classe.
*   **Retours**: `None`
*   **Logique interne**:
    *   Cette méthode est cruciale pour éviter la redondance d'informations, notamment entre les définitions de code (présentes dans la "Repo Map") et les extraits potentiellement extraits du "LTM" (mémoire à long terme).
    *   Elle extrait les signatures de fonctions (`def function_name(`) et de classes (`class ClassName`) du composant `repo_map`.
    *   Ensuite, elle parcourt les lignes du composant `ltm`. Si une ligne du `ltm` contient l'une des signatures détectées dans le `repo_map` (avec une tolérance pour les préfixes de ligne couramment utilisés), cette ligne est considérée comme un doublon et est supprimée du `ltm`.
    *   Le `repo_map` est traité comme la source faisant autorité pour les définitions de code, d'où la suppression des doublons du `ltm`.
    *   Met à jour `self.components['ltm']` avec le contenu dédupliqué.

#### `get_components(self)`

*   **Signature**: `get_components(self)`
*   **Arguments**:
    *   `self`: L'instance de la classe.
*   **Retours**: `dict` - Un dictionnaire des composants contextuels atomiques (ex: `{'tree': '...', 'arch': '...', 'ltm': '...', 'repo_map': '...'}`).
*   **Logique interne**:
    *   Vérifie si les composants ont déjà été préparés. Si `self.components` est vide, elle appelle `prepare_content()` pour les générer.
    *   Retourne le dictionnaire `self.components`, qui peut ensuite être utilisé par des sessions de modèle qui supportent l'injection de blocs contextuels séparés (comme DeepSeek).

#### `get_context_payload(self)`

*   **Signature**: `get_context_payload(self)`
*   **Arguments**:
    *   `self`: L'instance de la classe.
*   **Retours**: `str` - La chaîne de caractères fusionnée des composants contextuels.
*   **Logique interne**:
    *   Vérifie si le payload fusionné a déjà été préparé. Si `self.content_payload` est vide, elle appelle `prepare_content()` pour le générer.
    *   Retourne `self.content_payload`, principalement utilisé pour les systèmes de caching qui nécessitent un unique bloc de texte (comme le `CachedContent` de Google Gemini).

#### `get_or_create_cache(self, api_key, model_name)`

*   **Signature**: `get_or_create_cache(self, api_key, model_name)`
*   **Arguments**:
    *   `self`: L'instance de la classe.
    *   `api_key` (str): La clé API à utiliser pour configurer le service GenAI.
    *   `model_name` (str): Le nom du modèle pour lequel le cache est destiné (ex: "gemini-pro").
*   **Retours**: `str` ou `None` - Le nom de ressource du cache créé ou récupéré (ex: "cachedContents/xxxxxxxx"), ou `None` en cas d'échec de création ou si le modèle est blacklisté.
*   **Logique interne**:
    *   Implémente un "circuit breaker": si le `model_name` est dans `self.blacklisted_models`, la méthode retourne immédiatement `None`.
    *   Vérifie si un cache existe déjà pour la paire `(api_key, model_name)` dans `self.cache_map`. Si oui, son nom est retourné directement.
    *   Si le cache n'existe pas, elle appelle `prepare_content()` pour s'assurer que le `self.content_payload` est à jour.
    *   Configure l'API GenAI avec la `api_key` fournie.
    *   Crée un `caching.CachedContent` via `genai.caching.CachedContent.create()` en utilisant le `model_name`, un `display_name` formaté, une instruction système générique, le `self.content_payload` (fusionné) et la durée de vie `self.ttl_minutes`.
    *   Stocke le nom de ressource du cache créé dans `self.cache_map`.
    *   Gère les exceptions liées à la création du cache, en particulier les erreurs "429" (quota dépassé ou Tier Gratuit ne supportant pas le caching) pour ajouter le `model_name` à `self.blacklisted_models`.

### Instance Globale

`GlobalCacheManager = MultiModelCacheManager()`

Une instance globale de `MultiModelCacheManager` est créée à l'initialisation du module. Cela permet aux autres parties de l'application d'importer et d'utiliser facilement une instance unique et centralisée du gestionnaire de cache, assurant la cohérence du contexte et l'efficacité du caching.

## 3. Exemple d'usage

```python
import os
from features.CacheManager import GlobalCacheManager
# Supposons que config.py est un fichier contenant vos paramètres d'application, incluant les clés API
# Pour cet exemple, nous simulons la présence de APP_SETTINGS
class MockAppSettings:
    def get(self, section, default=None):
        if section == "api_keys":
            return {"gemini": os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")}
        if section == "system_settings":
            return {"rag_database_path": "db/knowledge_base_hybrid"}
        return default
APP_SETTINGS = MockAppSettings()

# Assurez-vous d'avoir configuré votre clé API Gemini dans les variables d'environnement
# ou directement dans APP_SETTINGS pour que l'exemple fonctionne.
# export GEMINI_API_KEY="AIzaSy..."

gemini_api_key = APP_SETTINGS.get("api_keys", {}).get("gemini")
model_to_cache_gemini = "gemini-pro" 

if gemini_api_key and gemini_api_key != "YOUR_GEMINI_API_KEY":
    print(f"Tentative de création/récupération du cache pour Gemini avec le modèle {model_to_cache_gemini}...")

    # 1. Obtenir le nom du cache (le crée si nécessaire)
    # C'est ici que prepare_content() sera appelé pour la première fois si les composants ne sont pas prêts.
    cache_name = GlobalCacheManager.get_or_create_cache(gemini_api_key, model_to_cache_gemini)

    if cache_name:
        print(f"✅ Cache Gemini récupéré/créé : {cache_name}")

        # Utiliser le cache avec l'API GenAI
        import google.generativeai as genai
        genai.configure(api_key=gemini_api_key)
        
        try:
            model = genai.GenerativeModel.from_cached_content(cache_name)
            # Les appels au modèle utiliseront le contenu pré-caché comme contexte
            print("\nAppel au modèle Gemini avec le cache...")
            response = model.generate_content("Dis-moi qui tu es en te basant sur le contexte fourni. Limite ta réponse à 50 mots.")
            print("Réponse Gemini (avec cache):")
            print(response.text)
        except Exception as e:
            print(f"Erreur lors de l'utilisation du cache Gemini: {e}")
            print("Le cache a pu être créé mais non utilisable (problème d'accès ou autre).")
    else:
        print(f"❌ Impossible de créer ou récupérer le cache pour {model_to_cache_gemini}.")
        if model_to_cache_gemini in GlobalCacheManager.blacklisted_models:
            print(f"Le modèle {model_to_cache_gemini} est blacklisté (souvent lié aux quotas du Free Tier).")
        # Dans ce cas, on pourrait appeler le modèle sans cache, en passant le payload manuellement
        # import google.generativeai as genai
        # genai.configure(api_key=gemini_api_key)
        # model = genai.GenerativeModel(model_to_cache_gemini)
        # full_context = GlobalCacheManager.get_context_payload()
        # response = model.generate_content(f"Contexte: {full_context}\n\nQuestion: Dis-moi qui tu es.")
        # print("Réponse Gemini (sans cache):")
        # print(response.text)
else:
    print("⚠️ Clé API Gemini non trouvée ou non configurée. Exemple de cache Gemini ignoré.")

# Exemple d'utilisation des composants atomiques (pour des modèles comme DeepSeek ou autres, qui peuvent prendre des blocs séparés)
print("\n--- Récupération des composants atomiques du contexte ---")
components = GlobalCacheManager.get_components() # Appelera prepare_content() si pas déjà fait
if components:
    for key, value in components.items():
        if value:
            print(f"Composant '{key}': Taille = {len(value)} caractères")
            # Afficher un extrait pour vérifier le contenu
            if len(value) > 100:
                print(f"  Contenu (extrait): {value[:100]}...")
            else:
                print(f"  Contenu: {value}")
        else:
            print(f"Composant '{key}': Vide ou non généré.")
else:
    print("Aucun composant atomique n'a pu être généré.")
```
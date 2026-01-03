import logging
import datetime
import os
import json
import threading
from pathlib import Path
import google.generativeai as genai
from google.generativeai import caching
from config import get_path
from features.Decorators import trace_action

log = logging.getLogger("Features.CacheManager")

class MultiModelCacheManager:
    """
    Gère les caches contextuels pour plusieurs modèles et plusieurs clés.
    Structure: { (api_key, model_name): "caches/xxxxx" }
    V5 : Architecture Atomique (Composants séparés).
    """
    def __init__(self):
        self.cache_map = {} 
        self.content_payload = None 
        self.components = {} # NOUVEAU : Stockage atomique des blocs
        self.ttl_minutes = 60
        # Liste des modèles pour lesquels le cache est impossible (Quota 0 ou erreur)
        self.blacklisted_models = set()
        
        # Cache arborescence avec hash Merkle
        self._tree_cache = None
        self._tree_hash = None
        self._tree_lock = threading.Lock()  # Thread-safe pour tree cache
        self._components_lock = threading.Lock()  # Thread-safe pour components
        
        # Cache pour le hash du projet avec mtimes (évite les recalculs Merkle)
        self._project_hash_cache = None
        self._project_hash_mtimes = {}  # {path: mtime}
        self._project_hash_timestamp = 0
        self._project_hash_lock = threading.Lock()  # Protection thread-safe

    @trace_action(source="CacheManager")
    def prepare_content(self):
        """
        Génère les composants du contexte (Arborescence, Architecture, LTM).
        Ne les fusionne pas immédiatement pour permettre l'injection atomique.
        """
        log.info("📦 Préparation des composants contextuels (Mode Atomique)...")
        
        # 1. ARBORESCENCE (COMPLÈTE - Toutes les infos essentielles pour DeepSeek)
        try:
            with self._tree_lock:
                # Vérifier si le cache est valide
                project_hash = self._get_project_hash()
                if self._tree_cache and self._tree_hash == project_hash:
                    with self._components_lock:
                        self.components['tree'] = self._tree_cache
                    log.debug("✅ Arborescence récupérée depuis le cache")
                else:
                    # Générer l'arborescence
                    tree = self._get_complete_tree(os.getcwd(), ignore_dirs={
                        '.git', '__pycache__', 'venv', 'env', 'node_modules', '.vs', '.vscode', '.idea', '.cursor',
                        'logs', 'backups', 'audio_cache'
                    })
                    tree_str = f"--- ARBORESCENCE PROJET ---\n{tree}"
                    self._tree_cache = tree_str
                    self._tree_hash = project_hash
                    with self._components_lock:
                        self.components['tree'] = tree_str
                    log.info(f"✅ Arborescence générée: {len(tree)} caractères")
        except Exception as e: 
            log.warning(f"Erreur Tree: {e}")
            with self._components_lock:
                self.components['tree'] = ""

        with self._components_lock:
            # 2. ARCHITECTURE MAP (Lourd & Stable) - CONDENSÉE pour payload
            try:
                arch_path = get_path("config/architecture_map.json")
                if os.path.exists(arch_path):
                    with open(arch_path, 'r', encoding='utf-8') as f:
                        arch_data = json.load(f)
                        # Condensation intelligente pour réduire la taille du payload
                        condensed_arch = self._condense_architecture_map(arch_data)
                        # Minification + Tri pour stabilité binaire parfaite
                        arch_str = json.dumps(condensed_arch, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
                        self.components['arch'] = f"--- CARTOGRAPHIE TECHNIQUE ---\n{arch_str}"
                        log.info(f"✅ Architecture Map chargée: {len(arch_str)} caractères")
                else:
                    self.components['arch'] = ""
                    log.info("ℹ️ Architecture Map non trouvée (config/architecture_map.json)")
            except Exception as e:
                log.warning(f"Erreur Architecture: {e}")
                self.components['arch'] = ""

            # 3. REPO MAP (Structure du Projet) - Utilise le cache persistant
            try:
                from features.context.repo_map import get_cached_repo_map
                from config import APP_SETTINGS
                
                # Récupérer le chemin de la base de données RAG
                db_path = APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid")
                if not os.path.isabs(db_path):
                    db_path = get_path(db_path)
                
                # get_cached_repo_map() utilise le cache persistant et lance la régénération en arrière-plan si nécessaire
                repo_map = get_cached_repo_map(db_path_base=db_path, max_chars=None)
                if repo_map:
                    self.components['repo_map'] = f"--- 🗺️ REPO MAP (Structure du Projet) ---\n{repo_map}"
                    log.info(f"✅ Repo Map générée: {len(repo_map)} caractères")
                else:
                    self.components['repo_map'] = ""
                    log.info("ℹ️ Repo Map vide")
            except Exception as e:
                log.warning(f"Erreur Repo Map: {e}")
                self.components['repo_map'] = ""
            
            # Log de comparaison repo_map vs arch
            repo_map_size = len(self.components.get('repo_map', ''))
            arch_size = len(self.components.get('arch', ''))
            if repo_map_size > 0:
                log.info(f"📊 Utilisation Repo Map ({repo_map_size} chars) au lieu de Architecture Map ({arch_size} chars)")
            elif arch_size > 0:
                log.info(f"📊 Utilisation Architecture Map ({arch_size} chars) - Repo Map non disponible")
            else:
                log.info("⚠️ Ni Repo Map ni Architecture Map disponibles")

            # 4. HISTORIQUE LTM (Variable)
            try:
                from features.SemanticMemory import GlobalMemoryManager
                if GlobalMemoryManager:
                    # On récupère le bloc compressé (si dispo)
                    self.components['ltm'] = GlobalMemoryManager.get_compressed_history_block()
                    log.info(f"✅ LTM chargé: {len(self.components['ltm'])} caractères")
                else:
                    self.components['ltm'] = ""
                    log.info("ℹ️ LTM non disponible (GlobalMemoryManager non initialisé)")
            except Exception as e:
                log.warning(f"Erreur LTM: {e}")
                self.components['ltm'] = ""

            # 5. DÉDUPLICATION INTER-SECTIONS (Conservative)
            # Détecter et supprimer les signatures dupliquées entre Repo Map et LTM
            try:
                self._deduplicate_components()
            except Exception as e:
                log.warning(f"Erreur déduplication: {e}")

            # Assemblage pour retro-compatibilité (Gemini Cache unique)
            parts = [self.components.get('tree'), self.components.get('arch'), self.components.get('ltm')]
            self.content_payload = "\n\n".join([p for p in parts if p])

    def _get_optimized_tree(self, root_path, max_depth=3, ignore_dirs=None):
        """Génère une vue arborescente compacte et nettoyée."""
        if ignore_dirs is None: ignore_dirs = set()
        lines = []
        root_path = Path(root_path)
        
        for root, dirs, files in os.walk(root_path):
            # Filtrage in-place des dossiers ignorés
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            # Calcul de la profondeur relative
            try:
                rel_path = Path(root).relative_to(root_path)
                level = len(rel_path.parts)
            except ValueError:
                level = 0

            if level > max_depth: continue
            
            indent = '  ' * level
            folder_name = os.path.basename(root) or "./"
            lines.append(f"{indent}{folder_name}/")
            
            subindent = '  ' * (level + 1)
            # Affichage compact
            if len(files) > 20:
                lines.append(f"{subindent}(... {len(files)} fichiers ...)")
            else:
                for f in sorted(files):
                    if f.endswith(('.pyc', '.log', '.zip', '.sqlite', '.git')): continue
                    lines.append(f"{subindent}{f}")
                    
        return "\n".join(lines)

    def _get_complete_tree(self, root_path, ignore_dirs=None):
        """
        Génère une arborescence COMPLÈTE du projet en respectant .gitignore.
        Affiche tous les fichiers et dossiers pertinents, sans limite de profondeur.
        Utilise .gitignore pour filtrer les fichiers et dossiers ignorés.
        """
        from features.gitignore_parser import load_gitignore_patterns, should_ignore_path, PATHSPEC_AVAILABLE
        
        root_path_str = str(root_path)
        
        # Vérifier si pathspec est disponible
        if not PATHSPEC_AVAILABLE:
            log.warning(f"⚠️ Package 'pathspec' non installé. Installez-le avec: pip install pathspec>=0.11.0")
            gitignore_spec = None
        else:
            gitignore_spec = load_gitignore_patterns(root_path_str)
        
        if gitignore_spec:
            log.info(f"✅ .gitignore chargé pour l'arborescence (root: {root_path_str})")
        else:
            if PATHSPEC_AVAILABLE:
                log.info(f"⚠️ .gitignore non disponible, utilisation du fallback (root: {root_path_str})")
            else:
                log.warning(f"⚠️ .gitignore non disponible (pathspec non installé), utilisation du fallback (root: {root_path_str})")
        
        # Fallback : liste basique si .gitignore non disponible
        if ignore_dirs is None: 
            ignore_dirs = {'.git', '__pycache__', 'venv', 'env', 'node_modules', 
                          '.vs', '.vscode', '.idea', '.cursor', 'logs', 'backups', 'audio_cache'}
        
        lines = []
        root_path = Path(root_path)
        
        # Fichiers à ignorer (extensions inutiles pour le contexte)
        ignored_file_extensions = {
            '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe',
            '.log', '.tmp', '.cache', '.swp', '.swo', '.DS_Store',
            '.sqlite', '.sqlite3', '.db', '.index', '.pkl'
        }
        
        # Compteurs pour le logging
        dirs_ignored_gitignore = 0
        dirs_ignored_fallback = 0
        files_ignored_gitignore = 0
        files_ignored_extensions = 0
        total_dirs_scanned = 0
        total_files_scanned = 0
        
        for root, dirs, files in os.walk(root_path):
            total_dirs_scanned += 1
            total_files_scanned += len(files)
            # Vérifier si le dossier actuel est ignoré selon .gitignore
            if gitignore_spec and should_ignore_path(str(root), root_path_str, gitignore_spec):
                # Ne pas afficher ce dossier ni ses enfants
                dirs[:] = []  # Empêcher de descendre
                dirs_ignored_gitignore += 1
                continue
            
            # Vérifier aussi la liste hardcodée (fallback)
            folder_name = os.path.basename(root) or "./"
            if folder_name in ignore_dirs:
                # Ne pas afficher ce dossier ni ses enfants
                dirs[:] = []  # Empêcher de descendre
                dirs_ignored_fallback += 1
                continue
            
            # Calcul de la profondeur relative pour l'indentation
            try:
                rel_path = Path(root).relative_to(root_path)
                level = len(rel_path.parts)
            except ValueError:
                level = 0
            
            # Filtrage in-place des dossiers ignorés selon .gitignore
            if gitignore_spec:
                original_dirs_count = len(dirs)
                dirs[:] = [d for d in dirs if not should_ignore_path(
                    os.path.join(str(root), d), root_path_str, gitignore_spec
                )]
                dirs_ignored_gitignore += (original_dirs_count - len(dirs))
            else:
                # Fallback : utiliser la liste hardcodée
                original_dirs_count = len(dirs)
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                dirs_ignored_fallback += (original_dirs_count - len(dirs))
            
            # Trier pour cohérence
            dirs.sort()
            
            # Indentation
            indent = '  ' * level
            folder_name = os.path.basename(root) or "./"
            lines.append(f"{indent}{folder_name}/")
            
            # Afficher TOUS les fichiers (pas de limite)
            subindent = '  ' * (level + 1)
            for f in sorted(files):
                file_path = os.path.join(str(root), f)
                
                # Ignorer selon .gitignore
                if gitignore_spec and should_ignore_path(file_path, root_path_str, gitignore_spec):
                    files_ignored_gitignore += 1
                    continue
                
                # Ignorer seulement les fichiers vraiment inutiles (extensions)
                if any(f.endswith(ext) for ext in ignored_file_extensions):
                    files_ignored_extensions += 1
                    continue
                    
                lines.append(f"{subindent}{f}")
        
        # Log des statistiques de filtrage
        log.info(
            f"📊 Arborescence générée: {len(lines)} lignes, "
            f"{total_dirs_scanned} dossiers scannés, {total_files_scanned} fichiers scannés. "
            f"Ignorés: {dirs_ignored_gitignore + dirs_ignored_fallback} dossiers "
            f"({dirs_ignored_gitignore} via .gitignore, {dirs_ignored_fallback} via fallback), "
            f"{files_ignored_gitignore + files_ignored_extensions} fichiers "
            f"({files_ignored_gitignore} via .gitignore, {files_ignored_extensions} via extensions)"
        )
                    
        return "\n".join(lines)

    def _get_project_hash(self, force_recalculate=False):
        """Calcule le hash du projet via UN SEUL arbre Merkle (optimisé).
        Utilise les mtimes pour éviter de reconstruire les arbres Merkle inutilement.
        
        Args:
            force_recalculate: Si True, force le recalcul même si le cache est valide
        
        Returns:
            Hash SHA256 du projet
        """
        from features.context.merkle_sync import MerkleTreeSync
        from features.Documentation import calculate_file_hash
        from config.settings import APP_SETTINGS
        from config.paths import get_path
        import hashlib
        import time
        
        with self._project_hash_lock:
            # Vérifier si on peut utiliser le cache (évite les reconstructions Merkle)
            if not force_recalculate and self._project_hash_cache:
                cache_config = APP_SETTINGS.get("repo_map_cache", {})
                watch_dirs = cache_config.get("watch_directories", ["features/", "ai_core/", "worker/"])
                watch_files = cache_config.get("watch_files", ["config/architecture_map.json"])
                
                # Vérifier les mtimes pour détecter les changements (rapide, pas de scan)
                all_paths = list(watch_dirs) + list(watch_files)
                paths_changed = False
                
                for path in all_paths:
                    abs_path = get_path(path) if not os.path.isabs(path) else path
                    if os.path.exists(abs_path):
                        try:
                            current_mtime = os.path.getmtime(abs_path)
                            cached_mtime = self._project_hash_mtimes.get(abs_path)
                            if cached_mtime != current_mtime:
                                paths_changed = True
                                break
                        except Exception:
                            paths_changed = True
                            break
                
                # Si rien n'a changé, retourner le cache (évite les reconstructions Merkle)
                if not paths_changed:
                    return self._project_hash_cache
            
            # Recalculer le hash (seulement si nécessaire)
            hasher = hashlib.sha256()
            
            # OPTIMISATION : Construire UN SEUL arbre Merkle pour la racine du projet
            project_root = os.path.dirname(get_path("."))  # Racine du projet
            
            # Enregistrer le mtime de la racine
            try:
                self._project_hash_mtimes[project_root] = os.path.getmtime(project_root)
            except Exception:
                pass
            
            # 1. Arbre Merkle pour TOUT le projet (une seule construction au lieu de 3)
            try:
                merkle = MerkleTreeSync(project_root)
                # build_tree() utilise maintenant les exclusions depuis settings
                root = merkle.build_tree()
                if root and root.hash:
                    hasher.update(root.hash.encode())
                    log.debug(f"✅ Arbre Merkle projet: {len(merkle.node_map)} nœuds")
            except Exception as e:
                log.warning(f"Erreur construction Merkle projet: {e}")
            
            # 2. Ajouter les fichiers surveillés individuellement (si en dehors de l'arbre)
            cache_config = APP_SETTINGS.get("repo_map_cache", {})
            watch_files = cache_config.get("watch_files", ["config/architecture_map.json"])
            for file_path in watch_files:
                abs_file = get_path(file_path) if not os.path.isabs(file_path) else file_path
                if os.path.exists(abs_file):
                    try:
                        # Enregistrer le mtime
                        self._project_hash_mtimes[abs_file] = os.path.getmtime(abs_file)
                        
                        # Le fichier est déjà dans l'arbre Merkle, mais on peut l'ajouter pour cohérence
                        # OU on peut le skip car il est déjà inclus dans le hash racine
                        file_hash = calculate_file_hash(abs_file)
                        if file_hash:
                            hasher.update(file_hash.encode())
                    except Exception as e:
                        log.debug(f"Erreur hash fichier {file_path}: {e}")
            
            project_hash = hasher.hexdigest()
            self._project_hash_cache = project_hash
            self._project_hash_timestamp = time.time()
            
            return project_hash

    def prepare_tree_only(self):
        """Prépare uniquement l'arborescence avec cache Merkle."""
        with self._tree_lock:
            try:
                # Calculer le hash du projet (comme Repo Map)
                project_hash = self._get_project_hash()
                
                # Vérifier si le cache est valide
                if self._tree_cache and self._tree_hash == project_hash:
                    log.debug("✅ Arborescence récupérée depuis le cache")
                    with self._components_lock:
                        self.components['tree'] = self._tree_cache
                    return
                
                # Générer l'arborescence
                tree = self._get_complete_tree(os.getcwd(), ignore_dirs={
                    '.git', '__pycache__', 'venv', 'env', 'node_modules', 
                    '.vs', '.vscode', '.idea', '.cursor',
                    'logs', 'backups', 'audio_cache'
                })
                tree_str = f"--- ARBORESCENCE PROJET ---\n{tree}"
                
                # Mettre en cache
                self._tree_cache = tree_str
                self._tree_hash = project_hash
                with self._components_lock:
                    self.components['tree'] = tree_str
                
                log.info(f"✅ Arborescence préchauffée: {len(tree)} caractères")
            except Exception as e:
                log.warning(f"Erreur préchauffage tree: {e}")
                with self._components_lock:
                    self.components['tree'] = ""

    def _condense_architecture_map(self, arch_data):
        """
        Condense l'architecture map pour réduire la taille du payload.
        Garde les informations essentielles, supprime les détails redondants.
        """
        condensed = {
            "metadata": arch_data.get("metadata", {}),
            "domains": arch_data.get("domains", {})
        }
        
        # Condensation du graph : garder seulement l'essentiel
        graph = arch_data.get("graph", {})
        condensed_graph = {}
        
        for file_path, file_data in graph.items():
            # Extraire seulement les infos essentielles
            definitions = file_data.get("definitions", {})
            classes = definitions.get("classes", [])[:5]  # Limiter à 5 classes
            functions = definitions.get("functions", [])[:8]  # Limiter à 8 fonctions
            globals_list = definitions.get("globals", [])[:5]  # Limiter à 5 globals
            
            condensed_file = {
                "type": file_data.get("type", "module")
            }
            
            # Ajouter definitions seulement si non vide
            if classes or functions or globals_list:
                condensed_file["def"] = {}
                if classes:
                    condensed_file["def"]["c"] = classes  # "c" pour classes (minification)
                if functions:
                    condensed_file["def"]["f"] = functions  # "f" pour functions
                if globals_list:
                    condensed_file["def"]["g"] = globals_list  # "g" pour globals
            
            # Ajouter dependencies seulement si non vide (limiter à 5)
            deps = file_data.get("dependencies", [])[:5]
            if deps:
                condensed_file["deps"] = deps  # "deps" au lieu de "dependencies"
            
            # Ajouter used_by seulement si non vide (limiter à 5)
            used_by = file_data.get("used_by", [])[:5]
            if used_by:
                condensed_file["used"] = used_by  # "used" au lieu de "used_by"
            
            # Ajouter metrics seulement si significatives
            metrics = file_data.get("metrics", {})
            if metrics.get("loc", 0) > 0 or metrics.get("complexity", 0) > 0:
                condensed_file["m"] = {  # "m" pour metrics
                    "l": metrics.get("loc", 0),  # "l" pour loc
                    "c": metrics.get("complexity", 0)  # "c" pour complexity
                }
            
            # Garder docstring seulement si très courte (< 100 chars) et tronquer
            docstring = file_data.get("docstring")
            if docstring:
                # Tronquer et nettoyer
                clean_doc = docstring.strip().replace('\n', ' ')[:100]
                if clean_doc:
                    condensed_file["doc"] = clean_doc  # "doc" au lieu de "docstring"
            
            # Ne garder que si le fichier a au moins une info utile
            if len(condensed_file) > 1:  # Plus que juste "type"
                condensed_graph[file_path] = condensed_file
        
        condensed["graph"] = condensed_graph
        
        return condensed
    
    def _deduplicate_components(self):
        """
        Déduplication conservative entre sections (Repo Map et LTM).
        Détecte les signatures exactes dupliquées et les supprime du LTM (Repo Map prioritaire).
        """
        repo_map = self.components.get('repo_map', '')
        ltm = self.components.get('ltm', '')
        
        if not repo_map or not ltm:
            return  # Pas de déduplication possible
        
        # 1. Extraire les signatures de la Repo Map (patterns: def function_name, class ClassName)
        import re
        repo_signatures = set()
        
        # Pattern pour fonctions: def nom_fonction(
        func_pattern = r'def\s+(\w+)\s*\('
        for match in re.finditer(func_pattern, repo_map):
            repo_signatures.add(f"def {match.group(1)}(")
        
        # Pattern pour classes: class NomClasse
        class_pattern = r'class\s+(\w+)\s*(?:\(|:)'
        for match in re.finditer(class_pattern, repo_map):
            repo_signatures.add(f"class {match.group(1)}")
        
        if not repo_signatures:
            return  # Aucune signature trouvée dans Repo Map
        
        # 2. Trouver et supprimer les mentions de ces signatures dans le LTM
        # On cherche les lignes du LTM qui contiennent ces signatures
        ltm_lines = ltm.split('\n')
        filtered_ltm_lines = []
        removed_count = 0
        
        for line in ltm_lines:
            should_keep = True
            # Vérifier si la ligne contient une signature dupliquée
            for sig in repo_signatures:
                # Chercher la signature dans la ligne (avec tolérance pour préfixes/suffixes)
                # Exemple: "[file.py] def ma_fonction(" ou "- def ma_fonction("
                if sig in line:
                    # Vérifier que c'est bien une mention de signature (pas juste un mot dans du texte)
                    # Pattern: signature au début de la ligne ou après un préfixe comme "- ", "[", "•"
                    if re.search(r'(?:^|\s|\[|-|\•)\s*' + re.escape(sig), line):
                        should_keep = False
                        removed_count += 1
                        break
            
            if should_keep:
                filtered_ltm_lines.append(line)
        
        # 3. Mettre à jour le LTM si des doublons ont été supprimés
        if removed_count > 0:
            self.components['ltm'] = '\n'.join(filtered_ltm_lines)
            log.debug(f"Déduplication: {removed_count} signatures dupliquées supprimées du LTM")

    @trace_action(source="CacheManager")
    def get_components(self):
        """
        [NOUVEAU] Retourne le dictionnaire des composants séparés.
        Utilisé par DeepSeekSession pour l'assemblage atomique des blocs.
        """
        if not self.components:
            self.prepare_content()
        with self._components_lock:
            return self.components.copy()  # Retourne une copie pour thread-safety
    
    def invalidate_project_hash_cache(self):
        """Invalide le cache du hash du projet (force le recalcul au prochain appel)."""
        with self._project_hash_lock:
            self._project_hash_cache = None
            self._project_hash_mtimes = {}
            self._project_hash_timestamp = 0

    @trace_action(source="CacheManager")
    def get_context_payload(self):
        """
        Récupère le socle de connaissance fusionné (String).
        Pour Gemini ou le Prefix Caching simple.
        """
        if not self.content_payload:
            self.prepare_content()
        return self.content_payload
 
    @trace_action(source="CacheManager")
    def get_or_create_cache(self, api_key, model_name):
        """
        Récupère ou crée un cache spécifique pour une paire (Clé, Modèle).
        """
        if not api_key or not model_name: return None
        
        # 0. CIRCUIT BREAKER
        if model_name in self.blacklisted_models:
            return None
        
        map_key = (api_key, model_name)
        if map_key in self.cache_map:
            return self.cache_map[map_key]

        log.info(f"⚡ Création Cache JIT pour {model_name}...")
        try:
            self.prepare_content()
            genai.configure(api_key=api_key)
            
            safe_model = "".join(c for c in model_name if c.isalnum())
            
            # NOTE: Pour Gemini, on utilise le payload fusionné.
            # Les outils sont passés lors de l'appel API, pas ici.
            cache = caching.CachedContent.create(
                model=model_name,
                display_name=f"Cache_{safe_model}_{api_key[-4:]}", 
                system_instruction="Tu es l'IA du projet AiModding. Voici ta base de connaissance.",
                contents=[self.content_payload],
                ttl=datetime.timedelta(minutes=self.ttl_minutes)
            )
            
            self.cache_map[map_key] = cache.name
            log.info(f"✅ Cache activé : {cache.name}")
            return cache.name
            
        except Exception as e:
            err_str = str(e)
            if "429" in err_str and ("limit=0" in err_str or "TotalCachedContentStorageTokensPerModelFreeTier" in err_str):
                log.warning(f"⚠️ Caching non supporté pour {model_name} (Free Tier). Passage en mode Standard.")
                self.blacklisted_models.add(model_name)
            else:
                log.error(f"❌ Échec création cache ({model_name}): {e}")
            
            return None

GlobalCacheManager = MultiModelCacheManager()
import logging
import datetime
import os
import json
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

    @trace_action(source="CacheManager")
    def prepare_content(self):
        """
        Génère les composants du contexte (Arborescence, Architecture, LTM).
        Ne les fusionne pas immédiatement pour permettre l'injection atomique.
        """
        log.info("📦 Préparation des composants contextuels (Mode Atomique)...")
        
        # 1. ARBORESCENCE (COMPLÈTE - Toutes les infos essentielles pour DeepSeek)
        try:
            # Arborescence complète : pas de limite de profondeur, tous les fichiers affichés
            # Ignore seulement les dossiers vraiment inutiles (cache, dépendances, système, logs, backups)
            tree = self._get_complete_tree(os.getcwd(), ignore_dirs={
                '.git', '__pycache__', 'venv', 'env', 'node_modules', '.vs', '.vscode', '.idea', '.cursor',
                'logs', 'backups', 'audio_cache'
            })
            self.components['tree'] = f"--- ARBORESCENCE PROJET ---\n{tree}"
        except Exception as e: 
            log.warning(f"Erreur Tree: {e}")
            self.components['tree'] = ""

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
            else:
                self.components['arch'] = ""
        except Exception as e:
            log.warning(f"Erreur Architecture: {e}")
            self.components['arch'] = ""

        # 3. REPO MAP (Structure du Projet) - Nouveau composant statique
        try:
            from features.context.repo_map import get_repo_map_generator
            from config import APP_SETTINGS
            
            # Récupérer le chemin de la base de données RAG
            db_path = APP_SETTINGS.get("system_settings", {}).get("rag_database_path", "db/knowledge_base_hybrid")
            if not os.path.isabs(db_path):
                db_path = get_path(db_path)
            
            repo_map_gen = get_repo_map_generator(db_path)
            repo_map = repo_map_gen.get_repo_map()  # Sans limite pour le cache
            if repo_map:
                self.components['repo_map'] = f"--- 🗺️ REPO MAP (Structure du Projet) ---\n{repo_map}"
            else:
                self.components['repo_map'] = ""
        except Exception as e:
            log.warning(f"Erreur Repo Map: {e}")
            self.components['repo_map'] = ""

        # 4. HISTORIQUE LTM (Variable)
        try:
            from features.SemanticMemory import GlobalMemoryManager
            if GlobalMemoryManager:
                # On récupère le bloc compressé (si dispo)
                self.components['ltm'] = GlobalMemoryManager.get_compressed_history_block()
            else:
                self.components['ltm'] = ""
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
        from features.gitignore_parser import load_gitignore_patterns, should_ignore_path
        
        root_path_str = str(root_path)
        gitignore_spec = load_gitignore_patterns(root_path_str)
        
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
        
        for root, dirs, files in os.walk(root_path):
            # Vérifier si le dossier actuel est ignoré selon .gitignore
            if gitignore_spec and should_ignore_path(str(root), root_path_str, gitignore_spec):
                # Ne pas afficher ce dossier ni ses enfants
                dirs[:] = []  # Empêcher de descendre
                continue
            
            # Vérifier aussi la liste hardcodée (fallback)
            folder_name = os.path.basename(root) or "./"
            if folder_name in ignore_dirs:
                # Ne pas afficher ce dossier ni ses enfants
                dirs[:] = []  # Empêcher de descendre
                continue
            
            # Calcul de la profondeur relative pour l'indentation
            try:
                rel_path = Path(root).relative_to(root_path)
                level = len(rel_path.parts)
            except ValueError:
                level = 0
            
            # Filtrage in-place des dossiers ignorés selon .gitignore
            if gitignore_spec:
                dirs[:] = [d for d in dirs if not should_ignore_path(
                    os.path.join(str(root), d), root_path_str, gitignore_spec
                )]
            else:
                # Fallback : utiliser la liste hardcodée
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
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
                    continue
                
                # Ignorer seulement les fichiers vraiment inutiles (extensions)
                if any(f.endswith(ext) for ext in ignored_file_extensions):
                    continue
                    
                lines.append(f"{subindent}{f}")
                    
        return "\n".join(lines)

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
        return self.components

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
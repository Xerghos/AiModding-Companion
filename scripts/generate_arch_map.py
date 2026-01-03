import os
import ast
import json
import logging
import time
import sys
import re

# Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger("ArchMapGenerator")

# IGNORED_DIRS conservé comme fallback si .gitignore non disponible
IGNORED_DIRS = {'.git', '__pycache__', 'venv', 'env', 'node_modules', 'dist', 'build', '.vs', '.ia_history', '_OLD', 'tests', 'DOC_CLI_FRAMEWORKS_DEPENDANCES', 'Documentation'}
IGNORED_FILES = {} # On inclut __init__.py cette fois pour la complétude

def get_project_root():
    current = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(current)

# --- ANALYSE MÉTRIQUES & SANTÉ ---

def analyze_file_metrics(file_path):
    """Lit le fichier brut pour extraire LOC, TODOs et ratio commentaires."""
    metrics = {
        "loc": 0,
        "comments": 0,
        "todos": [],
        "fixmes": []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        metrics["loc"] = len(lines)
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped: continue
            
            if stripped.startswith('#'):
                metrics["comments"] += 1
                
            # Détection dette technique
            if "# TODO" in line or "#TODO" in line:
                comment = line.split("TODO", 1)[1].strip().strip(':').strip()
                metrics["todos"].append(f"L{i+1}: {comment}")
                
            if "# FIXME" in line or "#FIXME" in line:
                comment = line.split("FIXME", 1)[1].strip().strip(':').strip()
                metrics["fixmes"].append(f"L{i+1}: {comment}")

    except Exception as e:
        log.warning(f"Erreur métriques {file_path}: {e}")
        
    return metrics

# --- ANALYSE AST (STRUCTURE & COMPLEXITÉ) ---

class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.stats = {
            "classes": {},
            "functions": [],
            "globals": [],
            "imports": set(),
            "complexity": 0
        }
        self.current_class = None

    def visit_Import(self, node):
        for alias in node.names:
            self.stats["imports"].add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.stats["imports"].add(node.module)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        # Héritage
        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        
        class_info = {
            "name": node.name,
            "lineno": node.lineno,
            "docstring": ast.get_docstring(node),
            "bases": bases,
            "methods": []
        }
        
        prev_class = self.current_class
        self.current_class = class_info # Context Switch
        
        self.generic_visit(node)
        
        self.stats["classes"][node.name] = class_info
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        # Calcul complexité (McCabe simplifié : +1 pour if/for/while)
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler)):
                complexity += 1
        
        func_info = {
            "name": node.name,
            "lineno": node.lineno,
            "args": [a.arg for a in node.args.args],
            "docstring": ast.get_docstring(node),
            "complexity": complexity,
            "decorators": [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
        }

        if self.current_class:
            self.current_class["methods"].append(func_info)
        else:
            self.stats["functions"].append(func_info)
            
        self.stats["complexity"] += complexity # Cumul global module
        self.generic_visit(node)

    def visit_Assign(self, node):
        # Détection constantes globales (MAJUSCULES)
        if not self.current_class: # Niveau module uniquement
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    self.stats["globals"].append(target.id)
        self.generic_visit(node)

# --- MOTEUR PRINCIPAL ---

def analyze_file_ast(file_path):
    analyzer = CodeAnalyzer()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=file_path)
        
        # Docstring module
        module_doc = ast.get_docstring(tree)
        analyzer.visit(tree)
        
        return {
            "module_doc": module_doc,
            "structure": analyzer.stats
        }
    except Exception as e:
        log.warning(f"⚠️ Erreur AST {os.path.basename(file_path)}: {e}")
        return {"module_doc": None, "structure": analyzer.stats}

def resolve_dependencies(imports, current_file_path, root_path, all_files_set):
    """Mappe les imports python vers les fichiers réels du projet."""
    resolved = []
    current_dir = os.path.dirname(current_file_path)
    
    for imp in imports:
        # 1. Conversion dot notation -> path
        base_path = imp.replace('.', '/')
        
        # Candidats possibles (fichier.py ou package/__init__.py)
        candidates = [
            base_path + '.py',
            os.path.join(base_path, '__init__.py')
        ]
        
        for cand in candidates:
            # Check absolu (depuis racine projet)
            abs_check = os.path.join(root_path, cand)
            if os.path.exists(abs_check):
                # On garde le chemin relatif normalisé
                rel = os.path.relpath(abs_check, root_path).replace('\\', '/')
                if rel in all_files_set and rel != current_file_path:
                    resolved.append(rel)
                    
    return list(set(resolved))

def generate_ultimate_graph():
    root = get_project_root()
    log.info(f"🚀 Démarrage du Cartographe ULTIME sur : {root}")
    
    # Charger .gitignore pour filtrer les fichiers
    try:
        from features.gitignore_parser import load_gitignore_patterns, should_ignore_path
        from pathspec import PathSpec
        gitignore_spec = load_gitignore_patterns(root)
        if gitignore_spec:
            log.info("✅ Filtrage .gitignore activé")
        else:
            log.info("⚠️ .gitignore non disponible, utilisation du fallback")
    except ImportError as e:
        log.warning(f"⚠️ Module gitignore_parser non disponible: {e}")
        log.warning("⚠️ Le scan sera plus lent (pas de filtrage .gitignore)")
        gitignore_spec = None
        should_ignore_path = None
    
    # Dossiers par défaut à exclure (fallback si gitignore échoue)
    default_excluded_dirs = IGNORED_DIRS.union({'.git', '__pycache__', 'venv', 'env', 'node_modules', 
                             'dist', 'build', '.idea', '.vscode', '.cursor', 'db', 'logs'})
    
    # 1. Recensement
    all_files = []
    all_files_set = set() # Pour lookup rapide
    
    def should_exclude_directory(dirname: str, parent_path: str, project_root: str, 
                                  gitignore_spec, default_excluded_dirs: set) -> bool:
        """Vérifie si un dossier doit être exclu."""
        # 1. Vérifier les dossiers par défaut
        if dirname in default_excluded_dirs:
            return True
        
        # 2. Vérifier .gitignore
        if gitignore_spec and should_ignore_path:
            rel_path = os.path.relpath(os.path.join(parent_path, dirname), project_root).replace('\\', '/')
            if should_ignore_path(rel_path, project_root, gitignore_spec):
                return True
        
        return False
    
    for r, d, f in os.walk(root):
        # Filtrer les dossiers à exclure AVANT de descendre
        d[:] = [x for x in d if not should_exclude_directory(x, r, root, gitignore_spec, default_excluded_dirs)]
        
        for file in f:
            if file.endswith('.py') and file not in IGNORED_FILES:
                full_path = os.path.join(r, file)
                rel_path = os.path.relpath(full_path, root).replace('\\', '/')
                
                # Vérifier si le fichier doit être exclu
                if gitignore_spec and should_ignore_path:
                    if should_ignore_path(rel_path, root, gitignore_spec):
                        continue
                
                # Vérifier les extensions par défaut
                if file.endswith(('.pyc', '.pyo', '.pyd', '.log', '.tmp', '.cache')):
                    continue
                
                all_files.append(rel_path)
                all_files_set.add(rel_path)

    log.info(f"📊 Scan terminé : {len(all_files)} fichiers trouvés (filtrage .gitignore: {'✅' if gitignore_spec else '❌'})")
    log.info(f"📂 {len(all_files)} fichiers identifiés. Analyse Rayons-X en cours...")

    graph = {}
    
    # 2. Analyse Profonde
    for rel_path in all_files:
        abs_path = os.path.join(root, rel_path)
        
        # A. Métriques Brutes (Lignes, TODOs)
        metrics = analyze_file_metrics(abs_path)
        
        # B. Structure Intelligente (AST)
        ast_data = analyze_file_ast(abs_path)
        structure = ast_data["structure"]
        
        # C. Résolution des liens
        direct_deps = resolve_dependencies(structure["imports"], rel_path, root, all_files_set)
        
        # D. Construction de la Data Card
        graph[rel_path] = {
            "type": "module",
            "docstring": ast_data["module_doc"],
            "metrics": {
                "loc": metrics["loc"],
                "complexity": structure["complexity"],
                "todo_count": len(metrics["todos"]),
                "fixme_count": len(metrics["fixmes"])
            },
            "technical_debt": {
                "todos": metrics["todos"],
                "fixmes": metrics["fixmes"]
            },
            "definitions": {
                "classes": list(structure["classes"].keys()),
                "functions": [f["name"] for f in structure["functions"]],
                "globals": structure["globals"]
            },
            "dependencies": direct_deps,
            "used_by": [] # Sera rempli à la passe 2
        }

    # 3. Passe 2 : Rétroliens (Used By)
    for file, data in graph.items():
        for dep in data["dependencies"]:
            if dep in graph:
                if file not in graph[dep]["used_by"]:
                    graph[dep]["used_by"].append(file)

    # 4. Génération Domains (Compatibilité ContextLoader)
    domains = {}
    for f in all_files:
        top = f.split('/')[0] if '/' in f else 'root'
        if top not in domains: domains[top] = {"primary": [], "related": []}
        domains[top]["primary"].append(f)

    # 5. Sauvegarde
    output_data = {
        "metadata": {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "file_count": len(all_files),
            "version": "Ultimate Graph V2"
        },
        "graph": graph,
        "domains": domains
    }

    target_file = os.path.join(root, "config", "architecture_map.json")
    try:
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
        
        # Rapport Console
        log.info(f"✅ Cartographie terminée ({len(all_files)} fichiers).")
        log.info(f"💾 Sauvegardé dans : {target_file}")
        
        # Top Complexité
        complex_files = sorted(graph.items(), key=lambda x: x[1]['metrics']['complexity'], reverse=True)[:3]
        log.info("\n🏆 Top 3 Complexité Cyclomatique :")
        for f, data in complex_files:
            log.info(f"  - {f} : Score {data['metrics']['complexity']} ({data['metrics']['loc']} lignes)")
            
        return True

    except Exception as e:
        log.error(f"❌ Erreur écriture : {e}")
        return False

if __name__ == "__main__":
    generate_ultimate_graph()
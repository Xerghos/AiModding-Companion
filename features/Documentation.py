"""
PATCHED: features/Documentation.py
Delegation: update_architecture calls external script 'scripts/generate_arch_map.py'
"""
import os
import time
import logging
import traceback
import hashlib
import json
import subprocess
import sys
import threading
from config.settings import APP_SETTINGS
from features.UnifiedLogger import UnifiedLogger
from config import get_path, get_logger, SUPPORTED_FILE_EXTENSIONS, charger_json_robuste, sauvegarder_json
from features.Shared import log_action
from features.ai_helper import call_ai_robust

# Import optionnel pour le QualityManager
try:
    from quality import run_quality_process
except ImportError:
    run_quality_process = None

log = get_logger("features.Documentation")
HASH_FILE = "doc_hashes.json"

# [NOUVEAU] Compteurs globaux thread-safe pour suivre les tâches de documentation
_doc_progress_trackers = {}
_doc_progress_lock = threading.Lock()
_doc_batch_counter = 0

# --- WRAPPER EXTERNE (RECÂBLAGE) ---
def execute_update_architecture(session, action_log_path, result_queue, **kwargs):
    """
    Wrapper qui délègue l'analyse au script dédié : scripts/generate_arch_map.py
    """
    try:
        project_root = get_path(".")
        script_path = os.path.join(project_root, "scripts", "generate_arch_map.py")
        
        # Vérification présence script
        if not os.path.exists(script_path):
            return f"❌ Script introuvable : {script_path}. Veuillez le restaurer dans le dossier 'scripts'."

        log_action("update_architecture", "Execution script externe", "config/architecture_map.json", action_log_path)
        
        if result_queue:
            result_queue.put({"type": "ui_update", "widget": "message", "text": "--- ARCHITECTE: Exécution du script de cartographie... ---"})

        # Exécution du script dans un sous-processus
        # On utilise sys.executable pour s'assurer qu'on utilise le même interpréteur Python (venv)
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            # Le script est censé écrire dans config/architecture_map.json
            return f"✅ Architecture mise à jour via script externe.\n\nLogs:\n{result.stderr[:500]}"
        else:
            log.error(f"Echec script arch: {result.stderr}")
            return f"❌ Le script a échoué (Code {result.returncode}).\nErreur: {result.stderr}"

    except Exception as e:
        log.error(f"Erreur wrapper update_architecture: {traceback.format_exc()}")
        return f"❌ Erreur interne lors de l'appel au script : {e}"

# --- FONCTIONS EXISTANTES (DeepDoc) ---

def _calculate_file_hash(file_path):
    """Calcule le hash SHA256 du contenu d'un fichier."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception:
        return None

def _lister_fichiers_cibles(cible, strict_mode=True):
    """Helper pour récupérer les fichiers physiques."""
    abs_path = get_path(cible)
    fichiers = []
    
    if os.path.isfile(abs_path):
        fichiers.append(abs_path)
    elif os.path.isdir(abs_path):
        for root, _, files in os.walk(abs_path):
            # Exclusion Hardcodée système
            if any(x in root for x in ["Documentation", ".git", "__pycache__", "venv", "env", "_OLD", ".vs"]): 
                continue
            
            for f in files:
                if f.endswith(SUPPORTED_FILE_EXTENSIONS):
                    if f in ["app_settings.json", "doc_hashes.json", "action_log.json", "architecture_map.json"]:
                        continue
                    fichiers.append(os.path.join(root, f))
    return fichiers

def task_documenter_fichier_atomique(file_rel_path, doc_session, response_queue, context_map, batch_id=None):
    """
    Tâche exécutée dans un thread pour documenter UN fichier.
    Version Sécurisée V2 : Filtrage strict des outputs (taille, mots-clés interdits).
    
    Args:
        batch_id: Identifiant unique du batch de documentation pour suivre la progression.
    """
    full_path = get_path(file_rel_path)
    if not os.path.exists(full_path):
        response_queue.put({"type": "error", "text": f"Fichier introuvable: {file_rel_path}"})
        if batch_id:
            _decrement_doc_counter(batch_id, response_queue)
        return

    try:
        # 1. Lecture du code source
        with open(full_path, 'r', encoding='utf-8') as f:
            source_code = f.read()

        # 2. Prompt optimisé pour la documentation (Directif)
        prompt = (
            f"Génère la documentation technique complète pour le fichier `{file_rel_path}`.\n"
            f"Format attendu : MARKDOWN pur.\n"
            f"Structure requise :\n"
            f"1. En-tête (Titre, Description concise, Dépendances)\n"
            f"2. Classes & Fonctions (Signatures, Arguments, Retours, Logique interne)\n"
            f"3. Exemple d'usage si pertinent.\n"
            f"--- CODE SOURCE ---\n"
            f"{source_code}\n"
            f"--- FIN CODE ---\n"
            f"IMPORTANT : Ne réponds RIEN D'AUTRE que le contenu du fichier Markdown. "
            f"Interdiction d'écrire 'Voici le fichier', 'Opération terminée' ou des politesses."
        )

        UnifiedLogger.write("DOC_WORKER", "START", f"Génération doc pour {file_rel_path}...")
        
        # 3. Appel IA (Mode Writer, force_text=True pour éviter les appels d'outils parasites)
        doc_content = call_ai_robust(doc_session, prompt, force_text=True)
        
        # --- FILTRAGE STRICT (Anti-Déchets) ---
        clean_content = str(doc_content).strip()
        
        # A. Nettoyage des balises Markdown parasites
        if clean_content.startswith("```markdown"): clean_content = clean_content.replace("```markdown", "", 1)
        elif clean_content.startswith("```md"): clean_content = clean_content.replace("```md", "", 1)
        
        if clean_content.startswith("```"): clean_content = clean_content.replace("```", "", 1)
        if clean_content.endswith("```"): clean_content = clean_content[:-3]
        
        clean_content = clean_content.strip()

        # B. Vérification de taille minimale (Anti-phrase courte)
        if len(clean_content) < 50:
            error_msg = f"⚠️ Doc ignorée (Trop courte - {len(clean_content)} chars): '{clean_content[:50]}...'"
            UnifiedLogger.write("DOC_WORKER", "REJECT", error_msg)
            return

        # C. Vérification des phrases parasites (Hallucinations fréquentes)
        forbidden_phrases = [
            "opération terminée", 
            "voici la documentation", 
            "je ne peux pas", 
            "unable to generate",
            "as an ai",
            "comme une ia"
        ]
        
        # On vérifie seulement le début du fichier (les 200 premiers chars) pour les phrases de chat
        start_content = clean_content.lower()[:200]
        if any(phrase in start_content for phrase in forbidden_phrases):
             error_msg = f"⚠️ Doc ignorée (Phrase interdite détectée)"
             UnifiedLogger.write("DOC_WORKER", "REJECT", error_msg)
             return

        # --- ÉCRITURE SÉCURISÉE ---
        safe_name = file_rel_path.replace('/', '_').replace('\\', '_')
        if not safe_name.endswith('.md'): safe_name += ".md"
        
        target_path = get_path(f"Documentation/Reference/{safe_name}")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(clean_content)
            
        UnifiedLogger.write("DOC_WORKER", "SUCCESS", f"Doc générée: {safe_name}")
        
        # [CORRECTION] Feedback Visuel : Envoi explicite du message à l'UI
        response_queue.put({"type": "ui_update", "widget": "message", "text": f"✅ Doc générée : {os.path.basename(file_rel_path)}"})
        # On garde le message interne doc_progress pour d'autres usages éventuels
        response_queue.put({"type": "doc_progress", "file": file_rel_path, "status": "ok"})
        
        # Décrémentation du compteur et vérification si c'est la dernière tâche
        if batch_id:
            _decrement_doc_counter(batch_id, response_queue)

    except Exception as e:
        UnifiedLogger.write("DOC_WORKER", "ERROR", f"Echec doc {file_rel_path}: {e}")
        log_trace = traceback.format_exc()
        UnifiedLogger.write("DOC_WORKER", "TRACE", log_trace)
        response_queue.put({"type": "error", "text": f"Erreur {file_rel_path}: {str(e)[:50]}"})
        
        # Même en cas d'erreur, on décrémente le compteur
        if batch_id:
            _decrement_doc_counter(batch_id, response_queue)

def _decrement_doc_counter(batch_id, response_queue):
    """Décrémente le compteur de tâches restantes et envoie le message final si nécessaire."""
    global _doc_progress_trackers, _doc_progress_lock
    
    with _doc_progress_lock:
        if batch_id not in _doc_progress_trackers:
            return
        
        tracker = _doc_progress_trackers[batch_id]
        tracker['remaining'] -= 1
        
        if tracker['remaining'] == 0:
            # C'est la dernière tâche, on envoie le message final
            total = tracker['total']
            response_queue.put({"type": "ui_update", "widget": "message", "text": f"✅ Documentation atomique terminée. {total} fichiers traités."})
            # Nettoyage du tracker
            del _doc_progress_trackers[batch_id]

def execute_generer_documentation(cible, mode, session, action_log_path, result_queue, task_queue, **kwargs):
    """
    Handler pour 'generer_documentation'.
    Gère le mode atomique avec vérification de hash, existence de la doc et exclusions utilisateur.
    """
    fichiers = _lister_fichiers_cibles(cible)
    if not fichiers:
        return f"Aucun fichier éligible trouvé dans : {cible}"

    if mode == "atomique":
        if result_queue:
            result_queue.put({"type": "ui_update", "widget": "message", "text": f"--- DeepDoc: Initialisation... ---"})
        
        # 1. Chargement de la Map Architecture (Contexte)
        map_path = get_path("config/architecture_map.json")
        arch_map = "{}"
        if os.path.exists(map_path):
            try:
                with open(map_path, 'r', encoding='utf-8') as f: arch_map = f.read()
            except: pass

        # 2. Chargement des Exclusions Utilisateur (Paramètres App)
        # [CORRECTION] On récupère la bonne clé utilisée dans settings.py (code_analysis -> ignored_folders)
        ignored_patterns = APP_SETTINGS.get("code_analysis", {}).get("ignored_folders", [])
        
        # Fallback de compatibilité (si la config n'a pas migré)
        if not ignored_patterns:
            ignored_patterns = APP_SETTINGS.get("ignored_files", [])
            if not ignored_patterns:
                 ignored_patterns = APP_SETTINGS.get("system_settings", {}).get("ignored_files", [])
        
        UnifiedLogger.write("DOC_WRAPPER", "CONFIG", f"Patterns ignorés: {ignored_patterns}")

        # 3. Chargement des Hashs existants
        hash_path = get_path(HASH_FILE)
        hashes = charger_json_robuste(hash_path)
        if not isinstance(hashes, dict): hashes = {}

        count = 0
        skipped = 0
        dirty = False 
        
        # [NOUVEAU] Génération d'un identifiant unique pour ce batch de documentation
        global _doc_batch_counter, _doc_progress_trackers, _doc_progress_lock
        with _doc_progress_lock:
            _doc_batch_counter += 1
            batch_id = _doc_batch_counter

        for f_abs in fichiers:
            try:
                f_rel = os.path.relpath(f_abs, get_path("."))
                
                # --- A. FILTRE D'EXCLUSION UTILISATEUR (CORRIGÉ V2) ---
                # On vérifie si un SEGMENT du chemin correspond exactement à un pattern
                is_ignored = False
                if ignored_patterns:
                    # Normalisation pour comparaison
                    f_rel_norm = f_rel.replace('\\', '/')
                    path_segments = f_rel_norm.split('/')  # Sépare en segments de chemin
                    
                    for pat in ignored_patterns:
                        pat = pat.strip().replace('\\', '/')
                        if not pat: continue
                        # Vérification STRICTE : le pattern doit être un segment complet du chemin
                        # Ex: "tests" matche "tests/file.py" mais PAS "my_tests/file.py"
                        if pat in path_segments:
                            is_ignored = True
                            UnifiedLogger.write("DOC_WRAPPER", "DEBUG", f"Ignoré par pattern '{pat}': {f_rel}")
                            break
                
                if is_ignored:
                    skipped += 1
                    continue

                curr_hash = _calculate_file_hash(f_abs)
                
                # --- B. VERIFICATION EXISTENCE DOC ---
                # On calcule le chemin théorique du fichier de documentation
                safe_name = f_rel.replace('/', '_').replace('\\', '_')
                if not safe_name.endswith('.md'): safe_name += ".md"
                doc_path = get_path(f"Documentation/Reference/{safe_name}")
                
                doc_exists = os.path.exists(doc_path)

                # --- C. CONDITION DE SAUT ---
                # On ne saute QUE SI : Le hash correspond ET le fichier de doc existe physiquement
                if curr_hash and hashes.get(f_rel) == curr_hash and doc_exists:
                    skipped += 1
                    continue

                # Si on est ici, c'est qu'il faut générer (Code changé OU Doc manquante)
                if task_queue:
                    task_payload = {
                        'type': 'doc_atomic_task',
                        'file_rel': f_rel,
                        'context_map': arch_map,
                        'batch_id': batch_id  # Passage de l'ID du batch pour suivi
                    }
                    task_queue.put(task_payload)
                    
                    # Mise à jour Optimiste du hash
                    hashes[f_rel] = curr_hash 
                    dirty = True
                    
                    count += 1
                    time.sleep(0.01) # Anti-flood
            except Exception as e:
                UnifiedLogger.write("DOC_WRAPPER", "ERROR", f"Erreur boucle {f_abs}: {e}")
        
        # Initialisation du compteur après avoir compté toutes les tâches
        if count > 0:
            with _doc_progress_lock:
                _doc_progress_trackers[batch_id] = {
                    'remaining': count,
                    'total': count
                }
        
        # 4. Sauvegarde des Hashs mis à jour
        if dirty:
            try:
                sauvegarder_json(hash_path, hashes)
                UnifiedLogger.write("DOC_WRAPPER", "INFO", "Doc Hashes mis à jour.")
            except Exception as e:
                UnifiedLogger.write("DOC_WRAPPER", "ERROR", f"Echec save hashes: {e}")

        if count > 0:
            return f"🚀 DeepDoc lancé : {count} fichiers en cours de traitement ({skipped} ignorés/à jour).\n⚠️ Les fichiers seront documentés de manière asynchrone. Suivez les notifications pour le suivi en temps réel."
        else:
            return f"✅ DeepDoc : Aucun fichier à traiter ({skipped} ignorés/à jour)."

    else:
        # Mode Résumé
        prompt = f"Génère un README pour le dossier {cible}."
        return call_ai_robust(session, prompt, mode="writer")
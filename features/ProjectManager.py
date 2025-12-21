import os
import json
import datetime
import logging
import re

# Imports Configuration Modulaire
from config.paths import get_path
from config.logs import get_logger
from config.settings import (
    ROADMAP_FILE, FULL_ROADMAP_FILE, ROADMAP_BACKUP_DIR,
    charger_json_robuste, sauvegarder_json
)

# Imports Features & Core
from features.Shared import log_action
from ai_core.sessions import call_ai_robust
from ai_core.factory import SessionFactory
from features.Decorators import trace_action

# Import Backup Manager (Robuste)
try:
    import features.core_backup as backup_manager
except ImportError:
    try:
        from features import core_backup as backup_manager
    except ImportError:
        backup_manager = None

# Import pour l'analyse de contexte (Documentation)
import features.Documentation as Documentation

log = get_logger("features.ProjectManager")

# --- 1. Mise à jour Roadmap (Legacy Wrapper) ---
@trace_action(source="ProjectManager")
def execute_mettre_a_jour_roadmap(instruction=None, session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Wrapper de compatibilité.
    """
    return execute_generer_roadmap_synthetique(instruction, session, action_log_path, result_queue, **kwargs)

# --- 2. Fonctions Principales ---

@trace_action(source="ProjectManager")
def execute_generer_roadmap_synthetique(instruction=None, session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Met à jour roadmap.md.
    Sécurisé par Backup Global + Force Text.
    """
    # Gestion des args optionnels
    instr = instruction or kwargs.get('instruction', 'Mise à jour standard basée sur les logs récents.')

    project_root = get_path(".")
    roadmap_main = os.path.join(project_root, ROADMAP_FILE)
    
    if not os.path.exists(roadmap_main):
        with open(roadmap_main, 'w', encoding='utf-8') as f: f.write("# Roadmap\n\nCréation.")

    # [SÉCURITÉ] Sauvegarde avant modif
    if backup_manager:
        backup_manager.create_backup(comment="AUTO: Avant Roadmap Update")

    # Session writer sans outils
    writer_session = SessionFactory.create_session(model_type="writer", enable_tools=False)

    # Lecture des logs (Fallback si path manquant)
    log_path = action_log_path or get_path("action_log.json")
    logs = charger_json_robuste(log_path)[-15:]
    logs_str = "\n".join([f"- {a.get('timestamp')}: {a.get('commande')} ({a.get('fichier_cible')})" for a in logs])

    try:
        if result_queue:
            result_queue.put({"type": "ui_update", "widget": "status", "text": "📝 Mise à jour Roadmap..."})

        # Lecture partielle pour contexte
        with open(roadmap_main, 'r', encoding='utf-8') as f: 
            full_content = f.read()
            context_content = full_content[-2000:] if len(full_content) > 2000 else full_content
        
        prompt = (
            f"Tu es CHEF DE PROJET.\n"
            f"Mets à jour la Roadmap Synthétique. Consigne : {instr}\n"
            f"Activité récente :\n{logs_str}\n\n"
            f"RÈGLE CRITIQUE : Ne répète PAS le texte ci-dessous. Génère UNIQUEMENT le nouveau bloc de mise à jour (Markdown) à ajouter à la fin.\n"
            f"--- FIN DU CONTENU ACTUEL (CONTEXTE) ---\n{context_content}"
        )
        
        # [FIX ANTI-BOUCLE] Force Text
        new_block = call_ai_robust(writer_session, prompt, force_text=True)
        
        # Nettoyage
        if context_content.strip() in new_block: 
            new_block = new_block.replace(context_content.strip(), "")

        timestamp = f"\n\n--- MAJ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} ---\n\n"
        
        with open(roadmap_main, 'a', encoding='utf-8') as f: 
            f.write(timestamp + new_block)
        
        if log_path:
            log_action("generer_roadmap_synthetique", instr, "Roadmap", log_path)
        
        # Feedback
        if result_queue:
            result_queue.put({'type': 'file_content', 'path': roadmap_main, 'content': new_block}) 
            
        return f"✅ Roadmap mise à jour avec succès (Ajout de {len(new_block)} chars)."
        
    except Exception as e:
        return f"❌ Erreur Roadmap : {e}"

@trace_action(source="ProjectManager")
def execute_synthese_historique(filtre=None, session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Génère une synthèse légère (JSON) de l'activité.
    Corrigé : Chemins par défaut internes.
    """
    # Définition des chemins internes (l'IA ne les connaît pas)
    history_path = get_path("full_chat_history.json")
    synthesis_path = get_path("synthese_activite.json")
    log_path = action_log_path or get_path("action_log.json")

    filtre_txt = filtre or kwargs.get('filtre', 'Aucun')

    if result_queue:
        result_queue.put({"type": "ui_update", "widget": "message", "text": "--- Génération Synthèse... ---"})
    
    hist_data = charger_json_robuste(history_path)
    # On prend les derniers messages (ex: 20 derniers)
    hist_data = hist_data[-20:] if isinstance(hist_data, list) else []
    
    act_data = charger_json_robuste(log_path)
    act_data = act_data[-20:] if isinstance(act_data, list) else []
    
    context_str = "--- PROMPTS RÉCENTS ---\n" + "\n".join([f"- {h.get('content', '')[:100]}..." for h in hist_data if h.get('role')=='user'])
    context_str += "\n--- ACTIONS TECHNIQUES ---\n" + "\n".join([f"- {a.get('commande')} sur {a.get('fichier_cible')}" for a in act_data])

    prompt = (
        f"Fais une synthèse exécutive très courte (5 puces max) de l'activité récente.\n"
        f"Filtre/Focus : {filtre_txt}\n\n"
        f"{context_str}"
    )
    
    # Session Router ou Writer
    synth_session = SessionFactory.create_session(model_type="router", enable_tools=False)
    response = call_ai_robust(synth_session, prompt, force_text=True, disposable=True)
    
    # Sauvegarde du résultat
    data = {"terme": filtre_txt, "synthese": response, "date": datetime.datetime.now().isoformat()}
    sauvegarder_json(synthesis_path, data)
    
    return f"📋 **Synthèse Historique :**\n{response}"

@trace_action(source="ProjectManager")
def regenerer_plan_technique_atomique(instruction=None, session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Génère/Update PLAN_TECHNIQUE_ATOMIQUE.md.
    """
    instr = instruction or kwargs.get('instruction', 'Mise à jour standard.')
    project_root = get_path(".")
    plan_path = os.path.join(project_root, "PLAN_TECHNIQUE_ATOMIQUE.md")
    
    # [SÉCURITÉ]
    if backup_manager:
        backup_manager.create_backup(comment="AUTO: Avant Plan Technique")
    
    if result_queue:
        result_queue.put({"type": "ui_update", "widget": "message", "text": "--- PLAN ATOMIQUE: Analyse... ---"})
    
    architect_session = SessionFactory.create_session(model_type="architect", enable_tools=False)
    
    try:
        # Appel à Documentation
        arch_map_content = Documentation._analyse_globale_architecture(project_root, None) # Pas de queue ici pour ne pas spammer
    except Exception as e:
        log.error(f"Echec analyse architecture: {e}")
        arch_map_content = "Analyse architecturale indisponible."
    
    try:
        all_files_abs = Documentation._lister_fichiers_cibles(project_root)
        all_files_rel = [os.path.relpath(f, project_root) for f in all_files_abs]
    except:
        all_files_rel = ["(Liste fichiers indisponible)"]
    
    old_content = ""
    if os.path.exists(plan_path):
        with open(plan_path, 'r', encoding='utf-8') as f:
            old_content = f.read()

    prompt = (
        f"Tu es l'Architecte en Chef. Génère le 'PLAN_TECHNIQUE_ATOMIQUE.md'.\n\n"
        f"### CONTEXTE\n{arch_map_content[:15000]}\n\n"
        f"### FICHIERS\n{', '.join(all_files_rel)[:5000]}\n\n"
        f"### ANCIEN PLAN\n{old_content[:10000]}\n\n"
        f"### MANDAT\n{instr}\n"
        f"RÈGLE CRITIQUE : Tu dois METTRE À JOUR le plan technique existant. Synchronise-le avec le contexte actuel."
    )

    if result_queue:
        result_queue.put({"type": "ui_update", "widget": "message", "text": "--- PLAN ATOMIQUE: Rédaction... ---"})
    
    new_plan_content = call_ai_robust(architect_session, prompt, force_text=True)
    
    try:
        os.makedirs(os.path.dirname(plan_path), exist_ok=True) 
        with open(plan_path, 'w', encoding='utf-8') as f: f.write(new_plan_content)
        
        if action_log_path:
            log_action("regenerer_plan_atomique", instr, "PLAN_TECHNIQUE_ATOMIQUE.md", action_log_path)
        
        if result_queue:
            result_queue.put({'type': 'file_content', 'path': plan_path, 'content': new_plan_content})
        
        return "✅ PLAN_TECHNIQUE_ATOMIQUE.md mis à jour avec succès."
    except Exception as e:
        return f"Erreur Sauvegarde Plan : {e}"

@trace_action(source="ProjectManager")
def execute_generer_changelog_append_only(session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    Met à jour changelogs.md en mode "append-only".
    """
    
    def _extraire_phases_terminees(contenu_plan):
        phases = {}
        # Regex assouplie pour capturer les sections
        bloc_terminees_match = re.search(r"### ✅ PHASES TERMINÉES(.*?)### 🚧", contenu_plan, re.DOTALL)
        if not bloc_terminees_match: return phases

        bloc_terminees = bloc_terminees_match.group(1)
        phases_match = re.finditer(r"####\s+(Phase\s+\d+.*?)\s+\*\*État\s*:\s*\[TERMINÉ\]\*\*\s+(.*?)(?=\n####|\Z)", bloc_terminees, re.DOTALL)
        
        for match in phases_match:
            titre_phase = match.group(1).strip()
            contenu_phase = match.group(2)
            taches = re.findall(r"\[x\]\s+(.*)", contenu_phase)
            if taches:
                phases[titre_phase] = [t.strip() for t in taches]
        return phases

    def _generer_entree_changelog(version, titre_phase, taches):
        date_jour = datetime.datetime.now().strftime("%Y-%m-%d")
        entree = f"## [{version}] - {date_jour} - {titre_phase}\n\n"
        entree += "### Nouveautés basées sur le Plan Technique\n"
        for tache in taches:
            entree += f"* {tache}\n"
        entree += "\n---\n\n"
        return entree

    plan_path = get_path("PLAN_TECHNIQUE_ATOMIQUE.md")
    changelog_path = get_path("changelogs.md")

    if not os.path.exists(plan_path):
        return "❌ Plan technique introuvable, impossible de générer le changelog."

    try:
        with open(plan_path, "r", encoding="utf-8") as f: contenu_plan = f.read()
        
        if not os.path.exists(changelog_path):
             with open(changelog_path, "w", encoding="utf-8") as f: f.write("# Changelog\n\n")

        with open(changelog_path, "r", encoding="utf-8") as f: contenu_changelog = f.read()
            
    except Exception as e:
        return f"❌ Erreur lecture fichiers : {e}"

    version_match = re.search(r"\(v(\d+\.\d+)\)", contenu_plan)
    version = f"V{version_match.group(1)}" if version_match else "V_AUTO"

    phases_terminees = _extraire_phases_terminees(contenu_plan)
    
    if not phases_terminees:
        return "ℹ️ Aucune nouvelle phase terminée détectée dans le plan."

    nouvelles_entrees_str = ""
    nouveautes_trouvees = 0
    for titre_phase, taches in phases_terminees.items():
        if titre_phase not in contenu_changelog:
            nouvelles_entrees_str += _generer_entree_changelog(version, titre_phase, taches)
            nouveautes_trouvees += 1

    if nouveautes_trouvees == 0:
        return "✅ Changelog déjà à jour."
        
    if backup_manager:
        backup_manager.create_backup(comment="AUTO: Avant Changelog Update")

    nouveau_contenu = nouvelles_entrees_str + contenu_changelog
    
    try:
        with open(changelog_path, "w", encoding="utf-8") as f: f.write(nouveau_contenu)
        
        if action_log_path:
            log_action("generer_changelog_append_only", f"Ajout {nouveautes_trouvees} phases", "changelogs.md", action_log_path)
        
        if result_queue:
            result_queue.put({'type': 'file_content', 'path': changelog_path, 'content': nouveau_contenu})
        
        return f"✅ Changelog mis à jour avec {nouveautes_trouvees} nouvelle(s) phase(s)."
    except Exception as e:
        return f"❌ Erreur écriture changelog : {e}"
import json
import os
import logging
from config import get_path, get_logger
from features.Decorators import trace_action

# Utilisation du logger unifié si possible, sinon logger standard
log = get_logger("Features.ContextLoader")

ARCHITECTURE_MAP_FILE = "config/architecture_map.json"

@trace_action(source="ContextLoader")
def _load_architecture_map():
    """Charge le fichier de mapping architectural."""
    map_path = get_path(ARCHITECTURE_MAP_FILE)
    if not os.path.exists(map_path):
        log.error(f"Fichier de mapping introuvable : {map_path}")
        return {}
    
    try:
        with open(map_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # [CORRECTION V18] Support du nouveau format Graphique
            if "domains" in data:
                return data["domains"] # On retourne la vue simplifiée pour compatibilité
            return data # Ancien format (si script pas encore lancé)
    except Exception as e:
        log.error(f"Erreur lecture mapping architecture : {e}")
        return {}

@trace_action(source="ContextLoader")
def charger_contexte_domaine(domaine, session=None, action_log_path=None, result_queue=None, **kwargs):
    """
    [RENOMMÉ] Charge le contenu des fichiers liés à un domaine architectural spécifique.
    Permet à l'IA de récupérer un contexte ciblé et pertinent.
    """
    arch_map = _load_architecture_map()
    
    if domaine not in arch_map:
        domaines_dispo = ", ".join(arch_map.keys())
        return f"❌ Domaine '{domaine}' inconnu. Domaines disponibles : {domaines_dispo}"
    
    info_domaine = arch_map[domaine]
    description = info_domaine.get("description", "Pas de description.")
    primary_files = info_domaine.get("primary_files", [])
    related_files = info_domaine.get("related_files", [])
    
    # Construction du rapport de contexte
    context_report = f"=== CONTEXTE ARCHITECTURAL : {domaine.upper()} ===\n"
    context_report += f"Description : {description}\n\n"
    
    # Chargement des fichiers primaires (Contenu complet)
    context_report += "--- FICHIERS PRIMAIRES (Cœur du domaine) ---\n"
    count_primary = 0
    for rel_path in primary_files:
        abs_path = get_path(rel_path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Petite protection contre les fichiers énormes
                    if len(content) > 50000:
                        content = content[:50000] + "\n... [TRONQUÉ > 50k chars] ..."
                    context_report += f"\n>>> FICHIER : {rel_path}\n{content}\n"
                    count_primary += 1
            except Exception as e:
                context_report += f"\n>>> FICHIER : {rel_path} (Erreur lecture: {e})\n"
        else:
             context_report += f"\n>>> FICHIER : {rel_path} (Introuvable)\n"

    # Listage des fichiers liés (Juste les noms pour info, ou contenu partiel si besoin)
    context_report += "\n--- FICHIERS LIÉS (Dépendances / Utilisateurs) ---\n"
    for rel_path in related_files:
        context_report += f"- {rel_path}\n"
        
    context_report += f"\n=== FIN DU CONTEXTE ({count_primary} fichiers chargés) ==="
    
    # Feedback UI
    if result_queue:
        result_queue.put({"type": "ui_update", "widget": "message", "text": f"📚 Contexte chargé : {domaine} ({count_primary} fichiers)"})
    
    return context_report

# Pour test direct
if __name__ == "__main__":
    print(charger_contexte_domaine("logging"))
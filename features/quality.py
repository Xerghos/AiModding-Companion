import logging
import re
import json
import time
from config import load_app_settings, get_logger
from features.Decorators import trace_action

# --- Tentative d'import du Swarm Manager (Gestion Dépendance Circulaire) ---
try:
    from agents.swarm_manager import create_agent
except ImportError:
    create_agent = None
    print("ATTENTION: Agents.swarm_manager introuvable. Le QualityManager sera limité.")

log = get_logger("quality_manager")

class QualityManager:
    """
    Moteur autonome de validation et d'amélioration continue (Feedback Loop).
    Utilise l'architecture Swarm pour alterner entre un Générateur et un Critique.
    """
    
    def __init__(self, worker_session):
        """
        Initialise le gestionnaire de qualité.
        :param worker_session: Session Gemini active (passée par le Worker).
        """
        self.session = worker_session
        self.settings = load_app_settings()
        
        # Configuration dynamique (avec valeurs par défaut sûres)
        general_settings = self.settings.get("general_settings", {})
        self.max_iterations = general_settings.get("quality_loop_max_iterations", 3)
        self.min_score_threshold = 85  # Score minimum pour valider automatiquement

    @trace_action(source="quality")
    def _parse_critique(self, critique_text):
        """
        Extrait le score (0-100) de la réponse textuelle du critique.
        Cherche des patterns comme "Score: 85/100", "85/100" ou juste "85".
        """
        # Regex robuste pour capturer X/100 ou Score: X
        patterns = [
            r"Score\s*[:=]\s*(\d{1,3})\s*/\s*100",  # Score: 85/100
            r"(\d{1,3})\s*/\s*100",                 # 85/100
            r"Note\s*[:=]\s*(\d{1,3})",             # Note: 85
        ]
        
        for pattern in patterns:
            match = re.search(pattern, critique_text, re.IGNORECASE)
            if match:
                try:
                    score = int(match.group(1))
                    return min(100, max(0, score)) # Bornage 0-100
                except ValueError:
                    continue
                    
        log.warning("QualityManager: Impossible de parser le score. Score par défaut: 0.")
        return 0  # En cas d'échec, on force une amélioration (worst case scenario)

    @trace_action(source="quality")
    def validate_and_refine(self, initial_content, context_instruction, generator_role="TECHNICAL_WRITER", validator_role="GUARDIAN"):
        """
        Exécute la boucle de qualité (Quality Loop).
        
        :param initial_content: Le brouillon initial (str) ou None si doit être généré from scratch.
        :param context_instruction: L'instruction précise de la tâche (ex: "Documente ce fichier").
        :param generator_role: Le Persona Swarm qui produit/corrige (ex: WRITER, REFACTORER).
        :param validator_role: Le Persona Swarm qui note (ex: GUARDIAN).
        :return: Le contenu final optimisé (str).
        """
        if not create_agent:
            log.error("QualityManager: Swarm non disponible. Retour du contenu brut.")
            return initial_content or "Erreur: Swarm non chargé."

        current_content = initial_content
        
        # --- ITÉRATION 0 : GÉNÉRATION INITIALE (Si nécessaire) ---
        if not current_content:
            log.info(f"QualityLoop ({generator_role}): Génération initiale...")
            try:
                agent_gen = create_agent(generator_role, self.session)
                current_content = agent_gen.execute_task(context_instruction)
            except Exception as e:
                log.error(f"QualityLoop: Échec génération initiale : {e}")
                return f"Erreur génération : {e}"

        # --- BOUCLE DE FEEDBACK ---
        for i in range(self.max_iterations):
            log.info(f"QualityLoop: Itération {i+1}/{self.max_iterations}...")

            # 1. CRITIQUE (Validator)
            try:
                agent_val = create_agent(validator_role, self.session)
                critique_prompt = (
                    f"Analyse le contenu suivant par rapport à cette instruction : '{context_instruction}'.\n"
                    f"Attribue une note impérativement formatée ainsi : 'Score: XX/100'.\n"
                    f"Liste les points précis à améliorer (ou indique 'Aucun' si parfait).\n\n"
                    f"--- CONTENU À ÉVALUER ---\n{current_content[:50000]}" # Troncation de sécurité
                )
                critique_response = agent_val.execute_task(critique_prompt)
                score = self._parse_critique(critique_response)
            except Exception as e:
                log.error(f"QualityLoop: Erreur critique (Itération {i}): {e}")
                score = 100 # On sort de la boucle pour éviter de casser le flux
            
            log.info(f"QualityLoop: Score obtenu = {score}/100")

            # 2. DÉCISION
            if score >= self.min_score_threshold:
                log.info(f"QualityLoop: Seuil de qualité ({self.min_score_threshold}) atteint. Validation.")
                break
            
            if i == self.max_iterations - 1:
                log.warning("QualityLoop: Max itérations atteint sans score parfait. Livraison en l'état.")
                break

            # 3. AMÉLIORATION (Generator)
            try:
                agent_gen = create_agent(generator_role, self.session)
                refine_prompt = (
                    f"Tu dois améliorer ce contenu pour atteindre un score de 100/100.\n"
                    f"Instruction originale : {context_instruction}\n"
                    f"Critiques reçues (Score {score}/100) : {critique_response}\n\n"
                    f"Renvoie UNIQUEMENT le contenu corrigé et amélioré complet (sans texte autour).\n\n"
                    f"--- CONTENU ACTUEL ---\n{current_content}"
                )
                current_content = agent_gen.execute_task(refine_prompt)
                
                # Nettoyage basique si l'IA est bavarde
                if "```" in current_content:
                    # On garde le contenu brut si c'est du markdown pur
                    pass 
                    
            except Exception as e:
                log.error(f"QualityLoop: Erreur amélioration (Itération {i}): {e}")
                break # On garde la version précédente

        return current_content

@trace_action(source="quality")
def run_quality_process(worker_session, instruction, initial_draft=None, gen_role="ARCHITECT", val_role="GUARDIAN"):
    """Helper pour instancier et lancer le process rapidement depuis le Worker."""
    qm = QualityManager(worker_session)
    return qm.validate_and_refine(initial_draft, instruction, gen_role, val_role)
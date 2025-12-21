import logging
import re
import time
from config.logs import get_logger
from ai_core.sessions import call_ai_robust
from features.Decorators import trace_action

# Import dynamique pour éviter les cycles
try:
    from agents.swarm_manager import create_agent
except ImportError:
    create_agent = None

log = get_logger("features.QualityEngine")

class QualityLoop:
    """
    Moteur de validation itérative multi-agents (V2).
    Orchestre un dialogue entre un Agent 'Générateur' et un Agent 'Critique'.
    """
    
    def __init__(self, session, max_iterations=3, min_score=85):
        self.session = session # Session 'Worker' parente
        self.max_iterations = max_iterations
        self.min_score = min_score

    def _parse_score(self, review_text):
        """Extrait le score (0-100) de la critique."""
        patterns = [
            r"Score\s*[:=]\s*(\d{1,3})\s*/\s*100",
            r"Note\s*[:=]\s*(\d{1,3})",
            r"(\d{1,3})/100"
        ]
        for p in patterns:
            match = re.search(p, review_text, re.IGNORECASE)
            if match:
                try:
                    s = int(match.group(1))
                    return min(100, max(0, s))
                except: pass
        return 0 # Punition si format non respecté

    @trace_action(source="QualityEngine")
    def run_cycle(self, task_prompt, generator_role="CODER", validator_role="REVIEWER"):
        """
        Lance la boucle de qualité.
        """
        if not create_agent:
            return "❌ Erreur: Swarm Manager non disponible."

        log.info(f"🔄 Début Quality Loop: {generator_role} vs {validator_role}")
        
        # 1. Génération Initiale
        log.info(f"1️⃣ Génération par {generator_role}...")
        gen_agent = create_agent(generator_role, self.session)
        current_content = gen_agent.execute_task(task_prompt)
        
        # Extraction texte si objet réponse
        if hasattr(current_content, 'text'): current_content = current_content.text
        else: current_content = str(current_content)

        # 2. Boucle d'Amélioration
        for i in range(self.max_iterations):
            log.info(f"🔄 Itération {i+1}/{self.max_iterations}...")
            
            # A. Critique (Validator)
            val_agent = create_agent(validator_role, self.session)
            review_prompt = (
                f"Tâche originale : {task_prompt}\n"
                f"Contenu à évaluer :\n---\n{current_content[:20000]}\n---\n"
                f"Consigne : Evalue la qualité, la sécurité et la justesse.\n"
                f"Format obligatoire : Commence ta réponse par 'Score: XX/100'. Puis liste les défauts."
            )
            
            review = val_agent.execute_task(review_prompt)
            if hasattr(review, 'text'): review = review.text
            else: review = str(review)
            
            score = self._parse_score(review)
            log.info(f"📊 Score obtenu : {score}/100")
            
            # B. Décision
            if score >= self.min_score:
                log.info("✅ Qualité validée.")
                return f"✅ **Qualité Validée ({score}/100)**\n\n{current_content}"
            
            if i == self.max_iterations - 1:
                log.warning("⚠️ Max itérations atteint. Livraison en l'état.")
                return f"⚠️ **Limite Itérations ({score}/100)**\n\n{current_content}\n\n*Notes du Reviewer :*\n{review[:500]}..."

            # C. Correction (Generator)
            log.info(f"🛠️ Correction par {generator_role}...")
            fix_prompt = (
                f"Le Reviewer a noté ton travail {score}/100.\n"
                f"Ses critiques : {review}\n"
                f"Tâche : Réécris le contenu pour corriger ces points et viser 100/100.\n"
                f"Renvoie UNIQUEMENT le contenu corrigé."
            )
            current_content = gen_agent.execute_task(fix_prompt)
            if hasattr(current_content, 'text'): current_content = current_content.text
            else: current_content = str(current_content)

        return current_content

# --- Helper d'appel rapide ---
def execute_quality_cycle(prompt, session, gen_role="CODER", val_role="REVIEWER"):
    engine = QualityLoop(session)
    return engine.run_cycle(prompt, gen_role, val_role)
"""
Module de gestion avancée du contexte avec PriomptiPy.
Allocation dynamique du budget de tokens par priorité.
"""

import logging
from typing import Dict, List, Optional
from config import get_logger
from features.Decorators import trace_action

log = get_logger("features.context.context_manager")

# Import PriomptiPy avec gestion d'erreur
try:
    from priomptipy import Scope, SystemMessage, UserMessage, Isolate, render
    PRIOMPTIPY_AVAILABLE = True
except ImportError:
    PRIOMPTIPY_AVAILABLE = False
    Scope = None
    SystemMessage = None
    UserMessage = None
    Isolate = None
    render = None


class ContextManager:
    """
    Gestionnaire de contexte intelligent utilisant PriomptiPy.
    
    Utilise PriomptiPy pour prioriser les éléments du prompt.
    """
    
    def __init__(self, max_tokens: int = 32000):
        """
        Args:
            max_tokens: Budget maximum de tokens
        """
        self.max_tokens = max_tokens
        self.enabled = PRIOMPTIPY_AVAILABLE
        
        if not self.enabled:
            log.warning("PriomptiPy non disponible. Gestion de contexte basique.")
    
    @trace_action(source="context_manager")
    def build_context(self, 
                     system_instruction: str,
                     active_file: Optional[str] = None,
                     rag_context: Optional[str] = None,
                     chat_history: Optional[List] = None,
                     errors: Optional[List[str]] = None) -> str:
        """
        Construit le contexte optimisé avec priorités.
        
        Priorités:
        - Haute: Instruction système, fichier actif
        - Moyenne: Historique récent, erreurs compilation
        - Basse: Snippets RAG lointains, historique ancien
        
        Args:
            system_instruction: Instruction système
            active_file: Contenu du fichier actif
            rag_context: Contexte RAG
            chat_history: Historique de conversation
            errors: Liste d'erreurs de compilation
        
        Returns:
            Contexte formaté
        """
        if not self.enabled:
            return self._build_context_simple(
                system_instruction, active_file, rag_context, chat_history, errors
            )
        
        try:
            # Construire la structure PriomptiPy
            components = []
            
            # Priorité Haute: Instruction système (absolue)
            components.append(
                Scope(
                    children=[SystemMessage(content=system_instruction)],
                    absolute_priority=100
                )
            )
            
            # Priorité Haute: Fichier actif
            if active_file:
                components.append(
                    Scope(
                        children=[UserMessage(content=f"--- FICHIER ACTIF ---\n{active_file}")],
                        absolute_priority=90
                    )
            )
            
            # Priorité Moyenne: Erreurs
            if errors:
                error_text = "\n".join([f"- {e}" for e in errors])
                components.append(
                    Scope(
                        children=[UserMessage(content=f"--- ERREURS ---\n{error_text}")],
                        absolute_priority=50
                    )
                )
            
            # Priorité Moyenne: Historique récent (limité)
            if chat_history:
                recent_history = chat_history[-4:] if len(chat_history) > 4 else chat_history
                history_text = "\n".join([
                    f"[{msg.get('role', 'user')}]: {msg.get('content', '')[:500]}"
                    for msg in recent_history
                ])
                components.append(
                    Isolate(
                        children=[UserMessage(content=f"--- HISTORIQUE RÉCENT ---\n{history_text}")],
                        max_tokens=2000,
                        absolute_priority=40
                    )
                )
            
            # Priorité Basse: RAG (limité)
            if rag_context:
                components.append(
                    Isolate(
                        children=[UserMessage(content=f"--- CONTEXTE RAG ---\n{rag_context}")],
                        max_tokens=5000,
                        absolute_priority=20
                    )
                )
            
            # Rendre le contexte avec budget
            rendered = render(components, max_tokens=self.max_tokens)
            return rendered
        
        except Exception as e:
            log.error(f"Erreur construction contexte PriomptiPy: {e}, fallback simple")
            return self._build_context_simple(
                system_instruction, active_file, rag_context, chat_history, errors
            )
    
    def _build_context_simple(self,
                              system_instruction: str,
                              active_file: Optional[str] = None,
                              rag_context: Optional[str] = None,
                              chat_history: Optional[List] = None,
                              errors: Optional[List[str]] = None) -> str:
        """
        Fallback: construction simple du contexte sans PriomptiPy.
        """
        parts = []
        
        parts.append(f"--- INSTRUCTION SYSTÈME ---\n{system_instruction}\n")
        
        if active_file:
            parts.append(f"--- FICHIER ACTIF ---\n{active_file[:3000]}\n")
        
        if errors:
            error_text = "\n".join([f"- {e}" for e in errors])
            parts.append(f"--- ERREURS ---\n{error_text}\n")
        
        if chat_history:
            recent = chat_history[-4:] if len(chat_history) > 4 else chat_history
            history_text = "\n".join([
                f"[{msg.get('role', 'user')}]: {msg.get('content', '')[:500]}"
                for msg in recent
            ])
            parts.append(f"--- HISTORIQUE ---\n{history_text}\n")
        
        if rag_context:
            parts.append(f"--- CONTEXTE RAG ---\n{rag_context[:5000]}\n")
        
        return "\n".join(parts)


# Instance globale
_context_manager_instance: Optional[ContextManager] = None

def get_context_manager(max_tokens: int = 32000) -> ContextManager:
    """Retourne l'instance singleton du gestionnaire de contexte."""
    global _context_manager_instance
    if _context_manager_instance is None:
        _context_manager_instance = ContextManager(max_tokens)
    return _context_manager_instance
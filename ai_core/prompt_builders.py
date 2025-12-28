"""
Constructeurs de prompts pour gemini-cli bridge.
Gère la construction des prompts système et utilisateur pour l'intégration CLI.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from features.UnifiedLogger import UnifiedLogger


@dataclass
class PromptBuildMeta:
    """Métadonnées de construction de prompt."""
    total_chars: int
    truncated: Dict[str, int]
    sizes: Dict[str, int]


def _truncate(text: str, max_length: int) -> Tuple[str, int]:
    """
    Tronque un texte à une longueur maximale.
    
    Args:
        text: Texte à tronquer
        max_length: Longueur maximale
    
    Returns:
        Tuple (texte_tronqué, nombre_caractères_tronqués)
    """
    if len(text) <= max_length:
        return text, 0
    return text[:max_length], len(text) - max_length


def build_cli_system_md(
    system_instruction: Optional[str] = None,
    language: str = "fr",
    extra: Optional[str] = None
) -> str:
    """
    Construit le fichier system.md pour gemini-cli.
    
    Args:
        system_instruction: Instruction système de base
        language: Langue (fr/en)
        extra: Contenu additionnel
    
    Returns:
        Contenu du fichier system.md
    """
    parts = []
    
    if system_instruction:
        parts.append(system_instruction)
    
    if extra:
        parts.append(extra)
    
    return "\n\n".join(parts) if parts else ""


def build_cli_prompt(
    message: str,
    rag_context: Optional[Any] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    cache_components: Optional[Dict[str, Any]] = None,
    max_history_turns: int = 10,
    limits: Optional[Dict[str, int]] = None
) -> Tuple[str, PromptBuildMeta]:
    """
    Construit le prompt complet pour gemini-cli.
    
    Args:
        message: Message utilisateur
        rag_context: Contexte RAG
        history: Historique des messages
        cache_components: Composants du cache (arch, tree, ltm, etc.)
        max_history_turns: Nombre max de tours d'historique
        limits: Limites de troncature
    
    Returns:
        Tuple (prompt_complet, métadonnées)
    """
    if limits is None:
        limits = {}
    
    parts = []
    truncated = {}
    sizes = {}
    
    # Ajouter les composants du cache
    if cache_components:
        if cache_components.get("arch"):
            arch_text = str(cache_components["arch"])
            arch_truncated, arch_trunc = _truncate(arch_text, limits.get("arch", 10000))
            parts.append(f"--- CARTOGRAPHIE TECHNIQUE ---\n{arch_truncated}")
            if arch_trunc > 0:
                truncated["arch"] = arch_trunc
            sizes["arch"] = len(arch_text)
        
        if cache_components.get("tree"):
            tree_text = str(cache_components["tree"])
            tree_truncated, tree_trunc = _truncate(tree_text, limits.get("tree", 5000))
            parts.append(f"--- ARBORESCENCE PROJET ---\n{tree_truncated}")
            if tree_trunc > 0:
                truncated["tree"] = tree_trunc
            sizes["tree"] = len(tree_text)
        
        if cache_components.get("ltm"):
            ltm_text = str(cache_components["ltm"])
            ltm_truncated, ltm_trunc = _truncate(ltm_text, limits.get("ltm", 3000))
            parts.append(f"--- 📜 MÉMOIRE LONG TERME (Résumé Consolidé) ---\n{ltm_truncated}")
            if ltm_trunc > 0:
                truncated["ltm"] = ltm_trunc
            sizes["ltm"] = len(ltm_text)
    
    # Ajouter le contexte RAG
    if rag_context:
        if isinstance(rag_context, dict):
            if rag_context.get("docs"):
                docs_text = str(rag_context["docs"])
                docs_truncated, docs_trunc = _truncate(docs_text, limits.get("rag", 5000))
                parts.append(f"--- 📂 CONTEXTE RAG PERTINENT ---\n{docs_truncated}")
                if docs_trunc > 0:
                    truncated["rag"] = docs_trunc
                sizes["rag"] = len(docs_text)
        else:
            rag_text = str(rag_context)
            rag_truncated, rag_trunc = _truncate(rag_text, limits.get("rag", 5000))
            parts.append(f"--- 📂 CONTEXTE RAG PERTINENT ---\n{rag_truncated}")
            if rag_trunc > 0:
                truncated["rag"] = rag_trunc
            sizes["rag"] = len(rag_text)
    
    # Ajouter l'historique
    if history:
        history_parts = []
        history_turns = history[-max_history_turns:] if len(history) > max_history_turns else history
        
        for msg in history_turns:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                history_parts.append(f"User: {content}")
            elif role in ("assistant", "model"):
                history_parts.append(f"Assistant: {content}")
        
        if history_parts:
            history_text = "\n".join(history_parts)
            history_truncated, history_trunc = _truncate(history_text, limits.get("history", 8000))
            parts.append(f"--- HISTORIQUE RÉCENT ---\n{history_truncated}")
            if history_trunc > 0:
                truncated["history"] = history_trunc
            sizes["history"] = len(history_text)
    
    # Ajouter le message utilisateur
    if message:
        msg_truncated, msg_trunc = _truncate(message, limits.get("message", 6000))
        parts.append(f"--- MESSAGE ACTUEL ---\n\n{msg_truncated}")
        if msg_trunc > 0:
            truncated["message"] = msg_trunc
        sizes["message"] = len(message)
    
    prompt = "\n\n".join(parts)
    total_chars = len(prompt)
    
    meta = PromptBuildMeta(
        total_chars=total_chars,
        truncated=truncated,
        sizes=sizes
    )
    
    return prompt, meta


def build_cli_prompt_split(
    message: str,
    rag_context: Optional[Any] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    cache_components: Optional[Dict[str, Any]] = None,
    max_history_turns: int = 10,
    limits: Optional[Dict[str, int]] = None,
    defer_message: bool = False
) -> Tuple[str, str, PromptBuildMeta]:
    """
    Construit le prompt en deux parties : statique et dynamique.
    
    Args:
        message: Message utilisateur
        rag_context: Contexte RAG
        history: Historique des messages
        cache_components: Composants du cache
        max_history_turns: Nombre max de tours d'historique
        limits: Limites de troncature
        defer_message: Si True, ne pas inclure le message dans la partie statique
    
    Returns:
        Tuple (partie_statique, partie_dynamique, métadonnées)
    """
    if limits is None:
        limits = {}
    
    static_parts = []
    dynamic_parts = []
    truncated = {}
    sizes = {}
    
    # Partie statique : composants du cache (arch, tree, ltm)
    if cache_components:
        if cache_components.get("arch"):
            arch_text = str(cache_components["arch"])
            arch_truncated, arch_trunc = _truncate(arch_text, limits.get("arch", 10000))
            static_parts.append(f"--- CARTOGRAPHIE TECHNIQUE ---\n{arch_truncated}")
            if arch_trunc > 0:
                truncated["arch"] = arch_trunc
            sizes["arch"] = len(arch_text)
        
        if cache_components.get("tree"):
            tree_text = str(cache_components["tree"])
            tree_truncated, tree_trunc = _truncate(tree_text, limits.get("tree", 5000))
            static_parts.append(f"--- ARBORESCENCE PROJET ---\n{tree_truncated}")
            if tree_trunc > 0:
                truncated["tree"] = tree_trunc
            sizes["tree"] = len(tree_text)
        
        if cache_components.get("ltm"):
            ltm_text = str(cache_components["ltm"])
            ltm_truncated, ltm_trunc = _truncate(ltm_text, limits.get("ltm", 3000))
            static_parts.append(f"--- 📜 MÉMOIRE LONG TERME (Résumé Consolidé) ---\n{ltm_truncated}")
            if ltm_trunc > 0:
                truncated["ltm"] = ltm_trunc
            sizes["ltm"] = len(ltm_text)
    
    # Partie dynamique : RAG, historique, message
    if rag_context:
        if isinstance(rag_context, dict):
            if rag_context.get("docs"):
                docs_text = str(rag_context["docs"])
                docs_truncated, docs_trunc = _truncate(docs_text, limits.get("rag", 5000))
                dynamic_parts.append(f"--- 📂 CONTEXTE RAG PERTINENT ---\n{docs_truncated}")
                if docs_trunc > 0:
                    truncated["rag"] = docs_trunc
                sizes["rag"] = len(docs_text)
        else:
            rag_text = str(rag_context)
            rag_truncated, rag_trunc = _truncate(rag_text, limits.get("rag", 5000))
            dynamic_parts.append(f"--- 📂 CONTEXTE RAG PERTINENT ---\n{rag_truncated}")
            if rag_trunc > 0:
                truncated["rag"] = rag_trunc
            sizes["rag"] = len(rag_text)
    
    if history:
        history_parts = []
        history_turns = history[-max_history_turns:] if len(history) > max_history_turns else history
        
        for msg in history_turns:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                history_parts.append(f"User: {content}")
            elif role in ("assistant", "model"):
                history_parts.append(f"Assistant: {content}")
        
        if history_parts:
            history_text = "\n".join(history_parts)
            history_truncated, history_trunc = _truncate(history_text, limits.get("history", 8000))
            dynamic_parts.append(f"--- HISTORIQUE RÉCENT ---\n{history_truncated}")
            if history_trunc > 0:
                truncated["history"] = history_trunc
            sizes["history"] = len(history_text)
    
    if message and not defer_message:
        msg_truncated, msg_trunc = _truncate(message, limits.get("message", 6000))
        dynamic_parts.append(f"--- MESSAGE ACTUEL ---\n\n{msg_truncated}")
        if msg_trunc > 0:
            truncated["message"] = msg_trunc
        sizes["message"] = len(message)
    
    static_part = "\n\n".join(static_parts) if static_parts else ""
    dynamic_part = "\n\n".join(dynamic_parts) if dynamic_parts else ""
    
    total_chars = len(static_part) + len(dynamic_part)
    
    meta = PromptBuildMeta(
        total_chars=total_chars,
        truncated=truncated,
        sizes=sizes
    )
    
    return static_part, dynamic_part, meta
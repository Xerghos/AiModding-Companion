import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PromptBuildMeta:
    total_chars: int
    truncated: Dict[str, bool]
    sizes: Dict[str, int]


def _truncate(text: str, max_chars: int) -> Tuple[str, bool]:
    if not text:
        return "", False
    if max_chars <= 0:
        return "", True
    if len(text) <= max_chars:
        return text, False
    # On garde le début (le plus informatif pour sections structurées) + marqueur.
    marker = f"\n\n...[TRONQUÉ: {len(text) - max_chars} caractères]..."
    keep = max(0, max_chars - len(marker))
    return text[:keep] + marker, True


def sanitize_system_instruction_for_cli(system_instruction: Optional[str]) -> str:
    """
    Nettoie le system prompt issu du Swarm/Agent pour éviter les comportements indésirables
    côté Gemini CLI (qui n’a pas de tool-calling intégré dans notre app).
    """
    if not system_instruction:
        return ""

    s = str(system_instruction)

    # 1) Retirer le manuel d’outils (souvent très long et inadapté au mode CLI stateless)
    #    Exemple bloc: --- 🛠️ MANUEL DES OUTILS AUTORISÉS --- ... (jusqu’au prochain --- ou fin)
    s = re.sub(r"\n---\s*🛠️\s*MANUEL[\s\S]*?(?=\n---|\Z)", "\n", s, flags=re.MULTILINE)

    # 2) Retirer les lignes qui incitent explicitement à appeler des outils
    s = re.sub(r"^.*(!native_tool|native_tool|JSON natif|POUR UTILISER UN OUTIL).*?$", "", s, flags=re.MULTILINE | re.IGNORECASE)

    # 3) Nettoyage espaces multiples
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def build_cli_system_md(system_instruction: Optional[str], *, language: str = "fr", extra: str = "") -> str:
    """
    Contenu du fichier `.gemini/system.md` utilisé via `GEMINI_SYSTEM_MD`.
    Objectif: remplacer le system prompt intégré du CLI (souvent orienté \"commande\")
    par un comportement de chat cohérent avec AiModding-Companion.
    """
    base = sanitize_system_instruction_for_cli(system_instruction)

    lang = (language or "fr").strip().lower()
    lang_line = "Réponds en français." if lang.startswith("fr") else f"Respond in {language}."

    guardrails = (
        "IMPORTANT:\n"
        "- Tu es un assistant conversationnel (pas un interpréteur de commandes).\n"
        f"- {lang_line}\n"
        "- N’invente pas d’outils, n’appelle pas de commandes, n’utilise pas de formats de tool-calling.\n"
        "- Si une demande nécessite des actions sur le code, propose les étapes au lieu d’exécuter des commandes.\n"
    )

    extra_block = (extra or "").strip()
    if extra_block:
        extra_block = f"\n\n---\n\n{extra_block}\n"

    if base:
        return f"{base}\n\n---\n\n{guardrails}{extra_block}\n"
    return guardrails + (extra_block + "\n" if extra_block else "\n")


def _format_history(history: List[Dict[str, Any]], max_turns: int) -> str:
    if not history:
        return ""
    # max_turns = nombre d’échanges (user+assistant) => 2*max_turns messages
    tail = history[-(max_turns * 2):]
    lines: List[str] = []
    for msg in tail:
        role = (msg.get("role") or "user").strip().lower()
        content = msg.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        if role == "assistant":
            lines.append(f"Assistant: {content}")
        else:
            lines.append(f"User: {content}")
    return "\n".join(lines).strip()


def _detect_query_type(query: str) -> str:
    """
    Détecte le type de requête pour adapter l'allocation de contexte.
    
    Retourne: "code", "concept", "debug", "refactor", "general"
    """
    query_lower = query.lower()
    
    # Mots-clés pour chaque type
    code_keywords = ['écris', 'écrire', 'code', 'fonction', 'classe', 'méthode', 'implémenter', 'créer', 'ajouter']
    concept_keywords = ['explique', 'expliquer', 'comment', 'pourquoi', 'qu\'est-ce', 'définir', 'concept']
    debug_keywords = ['erreur', 'bug', 'ne fonctionne pas', 'problème', 'corriger', 'fix', 'débugger', 'debug']
    refactor_keywords = ['refactoriser', 'refactor', 'améliorer', 'optimiser', 'réorganiser', 'restructurer']
    
    # Compter les occurrences de chaque type
    code_score = sum(1 for kw in code_keywords if kw in query_lower)
    concept_score = sum(1 for kw in concept_keywords if kw in query_lower)
    debug_score = sum(1 for kw in debug_keywords if kw in query_lower)
    refactor_score = sum(1 for kw in refactor_keywords if kw in query_lower)
    
    # Déterminer le type dominant
    scores = {
        'code': code_score,
        'concept': concept_score,
        'debug': debug_score,
        'refactor': refactor_score
    }
    max_score = max(scores.values())
    
    if max_score > 0:
        # Retourner le type avec le score le plus élevé
        for qtype, score in scores.items():
            if score == max_score:
                return qtype
    
    # Par défaut, analyser la longueur et la structure
    if len(query) < 30:
        return "general"
    elif '?' in query or query_lower.startswith(('pourquoi', 'comment', 'qu\'est')):
        return "concept"
    else:
        return "code"


def build_cli_prompt(
    *,
    message: str,
    rag_context: Optional[str],
    history: List[Dict[str, Any]],
    cache_components: Optional[Dict[str, str]] = None,
    max_history_turns: int = 3,
    limits: Optional[Dict[str, int]] = None,
    defer_message: bool = False,
) -> Tuple[str, PromptBuildMeta]:
    """
    Builder stateless (texte) pour `gemini prompt`.
    Produit un prompt structuré façon DeepSeek: instructions + arch/tree + RAG + historique + message.
    """
    # Détecter le type de requête pour allocation adaptative
    query_type = _detect_query_type(message if isinstance(message, str) else str(message))
    
    # Allocation de base
    limits = limits or {}
    total_max = int(limits.get("total", 24000))
    base_arch_max = int(limits.get("arch", 7000))
    base_tree_max = int(limits.get("tree", 7000))
    base_ltm_max = int(limits.get("ltm", 5000))
    base_rag_max = int(limits.get("rag", 8000))
    base_history_max = int(limits.get("history", 6000))
    message_max = int(limits.get("message", 6000))
    
    # Allocation adaptative selon le type de requête
    # Ajuster les limites pour prioriser les sections pertinentes
    if query_type == "code":
        # Plus de Repo Map/Arch, moins de LTM
        arch_max = int(base_arch_max * 1.2)
        tree_max = int(base_tree_max * 1.1)
        ltm_max = int(base_ltm_max * 0.7)
        rag_max = base_rag_max
        history_max = base_history_max
    elif query_type == "concept":
        # Plus de LTM, moins de Tree
        arch_max = base_arch_max
        tree_max = int(base_tree_max * 0.7)
        ltm_max = int(base_ltm_max * 1.3)
        rag_max = base_rag_max
        history_max = int(base_history_max * 1.1)
    elif query_type == "debug":
        # Plus de RAG Docs, moins d'Arch
        arch_max = int(base_arch_max * 0.8)
        tree_max = base_tree_max
        ltm_max = base_ltm_max
        rag_max = int(base_rag_max * 1.3)
        history_max = base_history_max
    elif query_type == "refactor":
        # Plus de Repo Map et RAG, moins de LTM
        arch_max = int(base_arch_max * 1.1)
        tree_max = base_tree_max
        ltm_max = int(base_ltm_max * 0.8)
        rag_max = int(base_rag_max * 1.1)
        history_max = base_history_max
    else:  # general
        # Allocation équilibrée
        arch_max = base_arch_max
        tree_max = base_tree_max
        ltm_max = base_ltm_max
        rag_max = base_rag_max
        history_max = base_history_max

    comps = cache_components or {}
    # Utiliser repo_map si disponible, sinon arch
    repo_map = comps.get("repo_map") or ""
    arch = comps.get("arch") or "" if not repo_map else ""
    tree = comps.get("tree") or ""
    ltm = comps.get("ltm") or ""

    # Sécurisation si rag_context est un dict (bug fix sequence item 5)
    rag_safe = rag_context
    if isinstance(rag_safe, dict):
        if rag_safe.get("docs"):
            rag_safe = str(rag_safe["docs"]).strip()
        else:
            rag_safe = str(rag_safe)

    # Troncatures par bloc (avec repo_map si disponible)
    if repo_map:
        repo_map_t, repo_map_tr = _truncate(repo_map, arch_max)
        arch_t, arch_tr = "", False
    else:
        repo_map_t, repo_map_tr = "", False
        arch_t, arch_tr = _truncate(arch, arch_max)
    tree_t, tree_tr = _truncate(tree, tree_max)
    ltm_t, ltm_tr = _truncate(ltm, ltm_max)
    rag_t, rag_tr = _truncate(rag_safe or "", rag_max)
    hist_raw = _format_history(history, max_turns=max_history_turns)
    hist_t, hist_tr = _truncate(hist_raw, history_max)
    if defer_message:
        msg_t, msg_tr = "", False
    else:
        msg_t, msg_tr = _truncate(message if isinstance(message, str) else str(message), message_max)

    parts: List[str] = []

    # Note: le system prompt principal est fourni via GEMINI_SYSTEM_MD, ici on met juste la structure
    parts.append("=== CONTEXTE PROJET (AUTOMATIQUE) ===")
    if repo_map_t:
        parts.append(repo_map_t)
    elif arch_t:
        parts.append(arch_t)
    if tree_t:
        parts.append(tree_t)
    if ltm_t:
        parts.append(ltm_t)

    if rag_t:
        parts.append("=== 📂 RAG CONTEXT (DOCS) ===")
        parts.append(rag_t)

    if hist_t:
        parts.append("=== HISTORIQUE RÉCENT ===")
        parts.append(hist_t)

    parts.append("=== MESSAGE ACTUEL ===")
    if not defer_message:
        parts.append(msg_t)

    prompt = "\n\n".join([p for p in parts if p]).strip()

    # Contrôle total (si on dépasse, on coupe depuis les sections les moins critiques)
    truncated: Dict[str, bool] = {
        "repo_map": repo_map_tr,
        "arch": arch_tr,
        "tree": tree_tr,
        "ltm": ltm_tr,
        "rag": rag_tr,
        "history": hist_tr,
        "message": msg_tr,
        "total": False,
    }

    if len(prompt) > total_max:
        prompt, total_tr = _truncate(prompt, total_max)
        truncated["total"] = total_tr

    sizes: Dict[str, int] = {
        "repo_map": len(repo_map_t),
        "arch": len(arch_t),
        "tree": len(tree_t),
        "ltm": len(ltm_t),
        "rag": len(rag_t),
        "history": len(hist_t),
        "message": len(msg_t),
    }

    meta = PromptBuildMeta(
        total_chars=len(prompt),
        truncated=truncated,
        sizes=sizes,
    )

    return prompt, meta



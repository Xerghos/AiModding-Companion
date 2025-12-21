import os
import time
import logging
from bs4 import BeautifulSoup
from config.paths import get_path
from config.logs import get_logger
from features.UnifiedLogger import UnifiedLogger
from features.Decorators import trace_action

# --- Gestionnaire de Session Navigateur (Singleton) ---
_PLAYWRIGHT = None
_BROWSER = None
_PAGE = None

log = get_logger("Features.WebSurfer")

def _ensure_playwright():
    """Charge Playwright à la demande."""
    global _PLAYWRIGHT, _BROWSER, _PAGE
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError("Le module 'playwright' n'est pas installé. Lancez 'pip install playwright' et 'playwright install'.")

    if _PAGE and not _PAGE.is_closed():
        return _PAGE
    
    UnifiedLogger.write("WEBSURFER", "START", "Démarrage du navigateur (Headless)...")
    _PLAYWRIGHT = sync_playwright().start()
    
    # Mode Headless par défaut pour la prod, False pour le debug si besoin
    _BROWSER = _PLAYWRIGHT.chromium.launch(headless=True) 
    
    # User-Agent générique pour éviter les blocages basiques
    context = _BROWSER.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    _PAGE = context.new_page()
    return _PAGE

def _clean_html_text(html_content):
    """Nettoie le HTML pour ne garder que le texte utile (Token-friendly)."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Suppression du bruit
        for script in soup(["script", "style", "nav", "footer", "header", "svg", "noscript"]):
            script.extract()
            
        text = soup.get_text(separator="\n")
        
        # Nettoyage des lignes vides et espaces multiples
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return clean_text
    except Exception as e:
        log.error(f"Erreur nettoyage HTML: {e}")
        return str(html_content)[:2000]

# --- COMMANDES (Standardisées V2) ---

@trace_action(source="WebSurfer")
def handle_web_search(query, session=None, result_queue=None, action_log_path=None, task_queue=None, **kwargs):
    """
    Effectue une recherche Google.
    :param query: Mots-clés.
    """
    try:
        page = _ensure_playwright()
        UnifiedLogger.write("WEBSURFER", "SEARCH", f"Recherche : {query}")
        
        if result_queue:
            result_queue.put({"type": "ui_update", "widget": "status", "text": f"Surf: Recherche '{query}'..."})
        
        # Navigation Google
        page.goto(f"https://www.google.com/search?q={query}")
        page.wait_for_load_state("domcontentloaded")
        
        # Gestion basique cookie banner (Tentative)
        try: 
            page.click("button:has-text('Tout refuser')", timeout=500)
            page.click("div[role='button']:has-text('Tout refuser')", timeout=500)
        except: pass
        
        # Extraction des résultats (Sélecteurs Google standards)
        results = []
        elements = page.query_selector_all(".g")
        
        for el in elements[:6]: # Top 6
            title_el = el.query_selector("h3")
            link_el = el.query_selector("a")
            snippet_el = el.query_selector(".VwiC3b") # Snippet textuel
            
            if title_el and link_el:
                title = title_el.inner_text()
                link = link_el.get_attribute('href')
                snippet = snippet_el.inner_text() if snippet_el else ""
                
                if link and not link.startswith("/search"):
                    results.append(f"### {title}\n- **Lien**: {link}\n- **Extrait**: {snippet}\n")
        
        if not results:
            return "Aucun résultat pertinent trouvé ou blocage Google détecté."
            
        return f"## Résultats Recherche : {query}\n\n" + "\n".join(results)
        
    except Exception as e:
        UnifiedLogger.write("WEBSURFER", "ERROR", f"Search failed: {e}")
        return f"Erreur WebSurfer (Search): {e}"

@trace_action(source="WebSurfer")
def handle_web_navigate(url, session=None, result_queue=None, action_log_path=None, task_queue=None, **kwargs):
    """
    Navigue vers une URL, extrait le texte et le résume si nécessaire.
    """
    # Lazy Import pour éviter cycle
    from ai_core.sessions import call_ai_robust
    
    try:
        page = _ensure_playwright()
        UnifiedLogger.write("WEBSURFER", "NAV", f"Navigation : {url}")
        
        if result_queue:
            result_queue.put({"type": "ui_update", "widget": "status", "text": f"Surf: Lecture {url[:30]}..."})
        
        try:
            page.goto(url, timeout=20000) # 20s timeout
            page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            return f"Impossible d'accéder à la page (Timeout ou Erreur): {e}"
        
        title = page.title()
        raw_html = page.content()
        clean_text = _clean_html_text(raw_html)
        
        # Limite de taille pour l'IA
        MAX_CHARS = 15000 
        
        content_preview = clean_text[:MAX_CHARS]
        
        # Si le texte est très long, on demande un résumé à l'IA
        summary = ""
        if len(clean_text) > 4000 and session:
            UnifiedLogger.write("WEBSURFER", "SUMMARIZE", "Contenu long, génération résumé...")
            prompt_summary = (
                f"Voici le contenu brut d'une page web ({title}). "
                f"Fais un résumé structuré des points clés techniques et informatifs en français :\n\n"
                f"{clean_text[:30000]}" # On envoie plus au modèle qu'on affiche
            )
            try:
                summary = call_ai_robust(session, prompt_summary, mode="fast", disposable=True)
                summary = f"\n\n### 🤖 Résumé IA :\n{summary}"
            except Exception as e:
                summary = f"\n(Résumé indisponible : {e})"
        
        return (
            f"# Page : {title}\n"
            f"**URL**: {url}\n"
            f"{summary}\n\n"
            f"### Extrait du contenu brut :\n"
            f"{content_preview}..."
            f"\n\n(Fin de l'extrait - Total: {len(clean_text)} chars)"
        )

    except Exception as e:
        UnifiedLogger.write("WEBSURFER", "ERROR", f"Navigate failed: {e}")
        return f"Erreur WebSurfer (Navigate): {e}"

@trace_action(source="WebSurfer")
def handle_web_screenshot(filename=None, session=None, result_queue=None, action_log_path=None, task_queue=None, **kwargs):
    """
    Prend une capture d'écran.
    """
    try:
        page = _ensure_playwright()
        
        # Dossier screenshots
        screen_dir = get_path("screenshots")
        os.makedirs(screen_dir, exist_ok=True)
        
        safe_name = filename if filename else f"web_capture_{int(time.time())}.png"
        if not safe_name.endswith(".png"): safe_name += ".png"
        
        target_path = os.path.join(screen_dir, safe_name)
        
        page.screenshot(path=target_path)
        UnifiedLogger.write("WEBSURFER", "SCREEN", f"Capture : {target_path}")
        
        return f"✅ Capture d'écran sauvegardée : {target_path}"
    except Exception as e:
        return f"Erreur WebSurfer (Screen): {e}"

@trace_action(source="WebSurfer")
def close():
    """Ferme le navigateur (à appeler à la fermeture de l'app)."""
    global _BROWSER, _PLAYWRIGHT
    try:
        if _BROWSER: _BROWSER.close()
        if _PLAYWRIGHT: _PLAYWRIGHT.stop()
        UnifiedLogger.write("WEBSURFER", "STOP", "Navigateur fermé.")
    except: pass
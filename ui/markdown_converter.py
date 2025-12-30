"""
Module de conversion Markdown vers HTML avec syntax highlighting.
"""
import markdown
from markdown.extensions import codehilite, fenced_code, tables, toc
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.formatters import HtmlFormatter
import logging

log = logging.getLogger("ui.markdown_converter")

# CSS pour thème dark
DARK_THEME_CSS = """
<style>
body {
    background-color: #1E1E1E;
    color: #CCCCCC;
    font-family: 'Segoe UI', Arial, sans-serif;
    line-height: 1.6;
    padding: 20px;
    margin: 0;
}
h1, h2, h3, h4, h5, h6 {
    color: #007ACC;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
}
h1 { font-size: 2em; border-bottom: 2px solid #2D2D30; padding-bottom: 0.3em; }
h2 { font-size: 1.5em; border-bottom: 1px solid #2D2D30; padding-bottom: 0.3em; }
h3 { font-size: 1.3em; }
code {
    background-color: #2D2D30;
    color: #CE9178;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 0.9em;
}
pre {
    background-color: #2D2D30;
    border: 1px solid #3E3E42;
    border-radius: 5px;
    padding: 15px;
    overflow-x: auto;
    margin: 1em 0;
}
pre code {
    background-color: transparent;
    color: inherit;
    padding: 0;
}
blockquote {
    border-left: 4px solid #007ACC;
    margin: 1em 0;
    padding-left: 1em;
    color: #858585;
    font-style: italic;
}
a {
    color: #4EC9B0;
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
    color: #0098FF;
}
ul, ol {
    margin: 1em 0;
    padding-left: 2em;
}
li {
    margin: 0.5em 0;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
}
th, td {
    border: 1px solid #3E3E42;
    padding: 8px 12px;
    text-align: left;
}
th {
    background-color: #2D2D30;
    color: #007ACC;
    font-weight: bold;
}
tr:nth-child(even) {
    background-color: #252526;
}
hr {
    border: none;
    border-top: 1px solid #3E3E42;
    margin: 2em 0;
}
img {
    max-width: 100%;
    height: auto;
    border-radius: 5px;
}
</style>
"""


def markdown_to_html(markdown_text, theme="dark"):
    """
    Convertit du Markdown en HTML avec syntax highlighting.
    
    Args:
        markdown_text: Texte Markdown à convertir
        theme: Thème à appliquer ("dark" ou "light") - actuellement seul "dark" est implémenté
    
    Returns:
        HTML string avec styles CSS intégrés
    """
    if not markdown_text:
        return "<p>Aucun contenu à afficher.</p>"
    
    try:
        # Configuration des extensions Markdown
        extensions = [
            'fenced_code',      # Blocs de code avec ```
            'codehilite',       # Syntax highlighting avec Pygments
            'tables',           # Tableaux
            'toc',              # Table des matières
            'nl2br',            # Retours à la ligne
            'sane_lists',       # Listes améliorées
        ]
        
        # Configuration pour codehilite (syntax highlighting)
        extension_configs = {
            'codehilite': {
                'css_class': 'highlight',
                'use_pygments': True,
                'noclasses': False,
            }
        }
        
        # Conversion Markdown vers HTML
        md = markdown.Markdown(
            extensions=extensions,
            extension_configs=extension_configs
        )
        
        html_body = md.convert(markdown_text)
        
        # Ajouter le CSS du thème
        if theme == "dark":
            css = DARK_THEME_CSS
        else:
            # Pour l'instant, on utilise toujours le thème dark
            css = DARK_THEME_CSS
        
        # Construire le HTML complet
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    {css}
</head>
<body>
    {html_body}
</body>
</html>
"""
        return html
        
    except Exception as e:
        log.error(f"Erreur lors de la conversion Markdown: {e}")
        return f"<p style='color: #F44336;'>Erreur lors de la conversion Markdown: {str(e)}</p>"

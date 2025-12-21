import tkinter as tk
import logging
from pygments import lex
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, guess_lexer
from pygments.token import Token, Comment, Keyword, Name, String, Error, \
     Number, Operator, Generic, Literal, Punctuation
from pygments.util import ClassNotFound
from features.Decorators import trace_action

# Palette de Couleurs (Thème Sombre Riche - Type Monokai)
SYNTAX_COLORS = {
    Token:                  '#F8F8F2',
    Keyword:                '#F92672',
    Keyword.Constant:       '#AE81FF',
    Keyword.Declaration:    '#66D9EF',
    Keyword.Namespace:      '#F92672',
    Keyword.Pseudo:         '#AE81FF',
    Keyword.Type:           '#66D9EF',
    Name:                   '#F8F8F2',
    Name.Attribute:         '#A6E22E',
    Name.Builtin:           '#66D9EF',
    Name.Builtin.Pseudo:    '#AE81FF',
    Name.Class:             '#A6E22E',
    Name.Constant:          '#AE81FF',
    Name.Decorator:         '#A6E22E',
    Name.Entity:            '#F8F8F2',
    Name.Exception:         '#A6E22E',
    Name.Function:          '#A6E22E',
    Name.Label:             '#F8F8F2',
    Name.Namespace:         '#F8F8F2',
    Name.Other:             '#F8F8F2',
    Name.Tag:               '#F92672',
    Name.Variable:          '#F8F8F2',
    Name.Variable.Class:    '#F8F8F2',
    Name.Variable.Global:   '#F8F8F2',
    Name.Variable.Instance: '#F8F8F2',
    Literal:                '#E6DB74',
    String:                 '#E6DB74',
    String.Doc:             '#75715E',
    String.Escape:          '#AE81FF',
    String.Interpol:        '#E6DB74',
    String.Other:           '#E6DB74',
    String.Regex:           '#E6DB74',
    String.Symbol:          '#E6DB74',
    Number:                 '#AE81FF',
    Operator:               '#F92672',
    Operator.Word:          '#F92672',
    Punctuation:            '#F8F8F2',
    Comment:                '#75715E',
    Comment.Single:         '#75715E',
    Comment.Multiline:      '#75715E',
    Comment.Preproc:        '#75715E',
    Generic.Deleted:        '#F92672',
    Generic.Emph:           '#F8F8F2',
    Generic.Error:          '#F8F8F2',
    Generic.Heading:        '#F8F8F2',
    Generic.Inserted:       '#A6E22E',
    Generic.Output:         '#F8F8F2',
    Generic.Prompt:         '#F8F8F2',
    Generic.Strong:         '#F8F8F2',
    Generic.Subheading:     '#F8F8F2',
    Generic.Traceback:      '#F9267B',
    Error:                  '#F92672',
}

DEFAULT_COLOR = "#F8F8F2"

@trace_action(source="syntax")
def get_lexer(filename=None, lang_name=None, code_content=None):
    """
    Obtient le 'lexer' Pygments par nom de fichier, langage ou devinette.
    """
    if lang_name:
        try:
            return get_lexer_by_name(lang_name)
        except ClassNotFound:
            pass
    if filename:
        try:
            return get_lexer_for_filename(filename)
        except ClassNotFound:
            pass
            
    try:
        return guess_lexer(code_content if code_content else (filename if filename else ""))
    except ClassNotFound:
        return get_lexer_by_name("text")

@trace_action(source="syntax")
def configure_tags(textbox):
    """
    Applique la configuration de couleur pour chaque tag de token.
    """
    for token, color in SYNTAX_COLORS.items():
        tag_name = str(token)
        textbox.tag_config(tag_name, foreground=color)
    
    textbox.tag_config(str(Token.Literal), foreground=SYNTAX_COLORS.get(String, DEFAULT_COLOR))
    textbox.tag_config(str(Token.Name), foreground=SYNTAX_COLORS.get(Name, DEFAULT_COLOR))

@trace_action(source="syntax")
def apply_highlighting_to_editor(textbox, code, lexer):
    """
    Applique la coloration à un éditeur ENTIER.
    """
    configure_tags(textbox)
    textbox.configure(state=tk.NORMAL)
    textbox.delete("1.0", tk.END)
    
    for token_type, token_string in lex(code, lexer):
        tag_name = str(token_type)
        textbox.insert(tk.END, token_string, (tag_name,))
    
    textbox.configure(state=tk.NORMAL)

@trace_action(source="syntax")
def highlight_code_block_in_chat(textbox, code_content, lexer):
    """
    Insère un bloc de code coloré dans le CHAT (mode append).
    """
    configure_tags(textbox)
    textbox.insert(tk.END, "\n" + ("-"*80) + "\n")
    
    for token_type, token_string in lex(code_content, lexer):
        tag_name = str(token_type)
        textbox.insert(tk.END, token_string, (tag_name,))
    
    textbox.insert(tk.END, "\n" + ("-"*80) + "\n\n")
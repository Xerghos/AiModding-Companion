#!/usr/bin/env python3
"""
Script d'analyse des problèmes de digestibilité dans les payloads.
"""
import json
import re
import os
from pathlib import Path

def analyze_payload_file(filepath):
    """Analyse un fichier payload pour identifier les problèmes."""
    if not os.path.exists(filepath):
        print(f"[ERREUR] Fichier introuvable : {filepath}")
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    issues = {
        'double_escaped_quotes': 0,
        'double_escaped_newlines': 0,
        'unicode_escapes': 0,
        'empty_messages': 0,
        'duplicate_content': 0,
        'total_size': 0,
        'arch_json_size': 0,
        'rag_context_size': 0
    }
    
    if 'messages' in data:
        for msg in data['messages']:
            content = msg.get('content', '')
            issues['total_size'] += len(content)
            
            # Messages vides
            if not content or not content.strip():
                issues['empty_messages'] += 1
                continue
            
            # Échappements doubles
            issues['double_escaped_quotes'] += content.count('\\"')
            issues['double_escaped_newlines'] += content.count('\\n')
            
            # Échappements Unicode
            unicode_escapes = re.findall(r'\\u[0-9a-fA-F]{4}', content)
            issues['unicode_escapes'] += len(unicode_escapes)
            
            # JSON architecture (détection)
            if 'CARTOGRAPHIE TECHNIQUE' in content:
                issues['arch_json_size'] = len(content)
                # Compter les échappements dans le JSON
                json_part = content.split('\n', 1)[1] if '\n' in content else content
                issues['double_escaped_quotes'] += json_part.count('\\"')
            
            # RAG context (détection)
            if 'RAG CONTEXT' in content:
                issues['rag_context_size'] = len(content)
    
    return issues

def analyze_history_file(filepath):
    """Analyse le fichier d'historique."""
    if not os.path.exists(filepath):
        print(f"[ERREUR] Fichier introuvable : {filepath}")
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    issues = {
        'unicode_escapes': 0,
        'empty_messages': 0,
        'duplicate_content': 0,
        'total_size': 0,
        'messages_with_escapes': 0
    }
    
    for msg in data:
        content = msg.get('content', '')
        issues['total_size'] += len(content)
        
        if not content or not content.strip():
            issues['empty_messages'] += 1
            continue
        
        # Échappements Unicode
        unicode_escapes = re.findall(r'\\u[0-9a-fA-F]{4}', content)
        if unicode_escapes:
            issues['messages_with_escapes'] += 1
            issues['unicode_escapes'] += len(unicode_escapes)
    
    return issues

if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 80)
    print("ANALYSE DES PROBLEMES DE DIGESTIBILITE DES PAYLOADS")
    print("=" * 80)
    
    # Analyse du payload
    print("\n[ANALYSE] debug_deepseek_payload.json")
    print("-" * 80)
    payload_issues = analyze_payload_file("debug_deepseek_payload.json")
    if payload_issues:
        print(f"Taille totale : {payload_issues['total_size']:,} caractères")
        print(f"Guillemets échappés (\\\") : {payload_issues['double_escaped_quotes']:,}")
        print(f"Sauts de ligne échappés (\\n) : {payload_issues['double_escaped_newlines']:,}")
        print(f"Échappements Unicode (\\uXXXX) : {payload_issues['unicode_escapes']:,}")
        print(f"Messages vides : {payload_issues['empty_messages']}")
        print(f"Taille JSON architecture : {payload_issues['arch_json_size']:,} caractères")
        print(f"Taille RAG context : {payload_issues['rag_context_size']:,} caractères")
    
    # Analyse de l'historique
    print("\n[ANALYSE] full_chat_history.json")
    print("-" * 80)
    history_issues = analyze_history_file("full_chat_history.json")
    if history_issues:
        print(f"Taille totale : {history_issues['total_size']:,} caractères")
        print(f"Échappements Unicode (\\uXXXX) : {history_issues['unicode_escapes']:,}")
        print(f"Messages avec échappements : {history_issues['messages_with_escapes']}")
        print(f"Messages vides : {history_issues['empty_messages']}")
    
    print("\n" + "=" * 80)


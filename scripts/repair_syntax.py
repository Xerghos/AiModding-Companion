import os

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_IMPORT = "from features.Decorators import trace_action"

def repair_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    import_needs_moving = False
    parenthesis_depth = 0
    cleaned_lines = []
    
    # --- PASSE 1 : Détection et Extraction ---
    for line in lines:
        stripped = line.strip()
        
        # Comptage basique des parenthèses pour savoir si on est dans un bloc
        # (Ignore les cas complexes comme les strings, mais suffisant pour des imports)
        open_p = line.count('(')
        close_p = line.count(')')
        
        # Si on tombe sur la ligne coupable
        if TARGET_IMPORT in line:
            # Si on est à l'intérieur d'un bloc (profondeur > 0) ou si la ligne commence par une indentation
            if parenthesis_depth > 0 or line.startswith("    ") or line.startswith("\t"):
                print(f"🔧 Réparation {os.path.basename(filepath)} : Import coincé détecté.")
                import_needs_moving = True
                continue # On NE L'AJOUTE PAS ici (suppression)
        
        # Mise à jour de la profondeur APRES avoir vérifié la ligne courante
        # (Si la ligne contient '(', la profondeur augmente pour la suite)
        parenthesis_depth += (open_p - close_p)
        cleaned_lines.append(line)
        
    if not import_needs_moving:
        return # Fichier sain

    # --- PASSE 2 : Réinsertion Propre ---
    # On cherche le meilleur endroit pour remettre l'import (après le dernier import existant)
    last_import_idx = 0
    for i, line in enumerate(cleaned_lines):
        if line.startswith("import ") or (line.startswith("from ") and "features.Decorators" not in line):
            last_import_idx = i
            
    # Insertion
    cleaned_lines.insert(last_import_idx + 1, f"{TARGET_IMPORT}\n")
    
    # --- SAUVEGARDE ---
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(cleaned_lines)
    except Exception as e:
        print(f"❌ Erreur écriture {filepath}: {e}")

def main():
    print(f"🚑 Démarrage de la réparation syntaxique dans : {PROJECT_ROOT}")
    count = 0
    for root, _, files in os.walk(PROJECT_ROOT):
        # On évite les dossiers système
        if "venv" in root or "__pycache__" in root: continue
        
        for file in files:
            if file.endswith(".py") and file != "repair_syntax.py":
                repair_file(os.path.join(root, file))
                count += 1
    print(f"🏁 Scan terminé ({count} fichiers).")

if __name__ == "__main__":
    main()
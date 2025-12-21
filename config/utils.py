import json
import os
from .paths import get_path
from .constants import HISTORY_FILE, CONTEXT_FILE

def charger_json_robuste(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"Erreur chargement JSON {file_path}: {e}")
            return []
    return []

def sauvegarder_json(file_path, data):
    def default_serializer(obj):
        if hasattr(obj, 'to_dict'): return obj.to_dict()
        if hasattr(obj, 'to_json'): return obj.to_json()
        if hasattr(obj, '__dict__'): return obj.__dict__
        return str(obj) 
        
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=default_serializer) 
        return True
    except Exception as e:
        print(f"Erreur sauvegarde JSON {file_path}: {e}")
        return False

def charger_historique_robuste_worker(file_path=None):
    path = file_path if file_path else get_path(HISTORY_FILE)
    data = charger_json_robuste(path)
    if isinstance(data, list): return [e for e in data if isinstance(e, dict)]
    return []

def sauvegarder_historique_worker(data, file_path=None):
    path = file_path if file_path else get_path(HISTORY_FILE)
    sauvegarder_json(path, data)

def charger_liens_contexte_worker(file_path=None):
    path = file_path if file_path else get_path(CONTEXT_FILE)
    data = charger_json_robuste(path)
    return data if isinstance(data, list) else []

def sauvegarder_liens_contexte_worker(data, file_path=None):
    path = file_path if file_path else get_path(CONTEXT_FILE)
    return sauvegarder_json(path, data)
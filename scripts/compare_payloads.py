"""
Script de comparaison des payloads gemini-cli vs CodeAssistClient.
Utilise les logs existants (codeassist_final_*.json) comme référence
et génère un payload avec CodeAssistClient pour identifier les différences.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_core.code_assist_converter import to_generate_content_request
from config.tools_schema import TOOLS_SCHEMA


def load_reference_payload(log_file: str) -> Dict[str, Any]:
    """
    Charge un payload de référence depuis un fichier de log.
    
    Args:
        log_file: Chemin vers le fichier codeassist_final_*.json
        
    Returns:
        Le payload de référence (structure complète)
    """
    with open(log_file, 'r', encoding='utf-8') as f:
        log_data = json.load(f)
    
    # Extraire le payload
    payload = log_data.get("payload", {})
    
    # Extraire les métadonnées utiles
    meta = {
        "timestamp": log_data.get("timestamp"),
        "model": log_data.get("model"),
        "session_type": log_data.get("session_type")
    }
    
    return payload, meta


def extract_inputs_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait les inputs nécessaires pour reconstruire le payload.
    
    Args:
        payload: Payload de référence
        
    Returns:
        Dict avec model, messages, system_instruction, tools, etc.
    """
    request = payload.get("request", {})
    
    # Extraire le modèle
    model = payload.get("model", "")
    
    # Extraire les messages (contents)
    contents = request.get("contents", [])
    messages = []
    for content in contents:
        role = content.get("role", "user")
        parts = content.get("parts", [])
        # Concaténer tous les text parts
        text_parts = [p.get("text", "") for p in parts if p.get("text")]
        content_text = "\n".join(text_parts)
        if content_text.strip():
            messages.append({
                "role": "user" if role == "user" else "assistant",
                "content": content_text
            })
    
    # Extraire systemInstruction
    system_instruction = None
    if "systemInstruction" in request:
        sys_inst = request["systemInstruction"]
        sys_parts = sys_inst.get("parts", [])
        sys_texts = [p.get("text", "") for p in sys_parts if p.get("text")]
        if sys_texts:
            system_instruction = "\n".join(sys_texts)
    
    # Extraire tools
    tools = request.get("tools", [])
    
    # Extraire toolConfig
    tool_config = request.get("toolConfig", {})
    function_calling_mode = "AUTO"
    if tool_config and "functionCallingConfig" in tool_config:
        function_calling_mode = tool_config["functionCallingConfig"].get("mode", "AUTO")
    
    # Extraire generationConfig
    gen_config = request.get("generationConfig", {})
    temperature = gen_config.get("temperature", 0.7)
    max_tokens = gen_config.get("maxOutputTokens")
    
    # Extraire session_id
    session_id = request.get("session_id")
    
    # Extraire project_id
    project_id = payload.get("project")
    
    return {
        "model": model,
        "messages": messages,
        "system_instruction": system_instruction,
        "tools": tools,
        "function_calling_mode": function_calling_mode,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "session_id": session_id,
        "project_id": project_id
    }


def generate_codeassist_payload(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Génère un payload avec CodeAssistClient pour les mêmes inputs.
    
    Args:
        inputs: Inputs extraits du payload de référence
        
    Returns:
        Payload généré par CodeAssistClient
    """
    # Convertir les tools au format attendu par CodeAssistClient
    tools = inputs.get("tools", [])
    
    # Si tools est vide mais qu'on a TOOLS_SCHEMA, l'utiliser
    if not tools and TOOLS_SCHEMA:
        tools = TOOLS_SCHEMA
    
    # Générer le payload
    ca_payload = to_generate_content_request(
        model=inputs["model"],
        messages=inputs["messages"],
        system_instruction=inputs["system_instruction"],
        tools=tools,
        function_calling_mode=inputs.get("function_calling_mode", "AUTO"),
        temperature=inputs.get("temperature", 0.7),
        max_tokens=inputs.get("max_tokens"),
        session_id=inputs.get("session_id"),
        project_id=inputs.get("project_id")
    )
    
    return ca_payload


def compare_payloads(reference: Dict[str, Any], generated: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare deux payloads et identifie les différences.
    
    Args:
        reference: Payload de référence (gemini-cli)
        generated: Payload généré (CodeAssistClient)
        
    Returns:
        Dict avec les différences identifiées
    """
    differences = {
        "missing_fields": [],
        "extra_fields": [],
        "different_values": [],
        "structure_differences": []
    }
    
    # Comparer la structure de base
    ref_request = reference.get("request", {})
    gen_request = generated.get("request", {})
    
    # Comparer les champs principaux
    ref_fields = set(ref_request.keys())
    gen_fields = set(gen_request.keys())
    
    # Champs manquants dans generated
    missing = ref_fields - gen_fields
    if missing:
        differences["missing_fields"].extend(list(missing))
    
    # Champs supplémentaires dans generated
    extra = gen_fields - ref_fields
    if extra:
        differences["extra_fields"].extend(list(extra))
    
    # Comparer les champs communs
    common_fields = ref_fields & gen_fields
    for field in common_fields:
        ref_value = ref_request[field]
        gen_value = gen_request[field]
        
        if ref_value != gen_value:
            # Comparaison plus fine
            if isinstance(ref_value, dict) and isinstance(gen_value, dict):
                # Comparer récursivement
                sub_diff = _compare_dicts(ref_value, gen_value, f"{field}.")
                if sub_diff:
                    differences["different_values"].extend(sub_diff)
            elif isinstance(ref_value, list) and isinstance(gen_value, list):
                # Comparer les listes
                if len(ref_value) != len(gen_value):
                    differences["different_values"].append({
                        "field": field,
                        "reference": f"List with {len(ref_value)} items",
                        "generated": f"List with {len(gen_value)} items"
                    })
                else:
                    for i, (ref_item, gen_item) in enumerate(zip(ref_value, gen_value)):
                        if ref_item != gen_item:
                            differences["different_values"].append({
                                "field": f"{field}[{i}]",
                                "reference": str(ref_item)[:200],
                                "generated": str(gen_item)[:200]
                            })
            else:
                differences["different_values"].append({
                    "field": field,
                    "reference": str(ref_value)[:200],
                    "generated": str(gen_value)[:200]
                })
    
    return differences


def _compare_dicts(ref: Dict, gen: Dict, prefix: str = "") -> List[Dict]:
    """Compare récursivement deux dictionnaires."""
    differences = []
    ref_keys = set(ref.keys())
    gen_keys = set(gen.keys())
    
    # Clés manquantes
    for key in ref_keys - gen_keys:
        differences.append({
            "field": f"{prefix}{key}",
            "issue": "missing_in_generated",
            "reference": str(ref[key])[:200]
        })
    
    # Clés supplémentaires
    for key in gen_keys - ref_keys:
        differences.append({
            "field": f"{prefix}{key}",
            "issue": "extra_in_generated",
            "generated": str(gen[key])[:200]
        })
    
    # Comparer les valeurs communes
    for key in ref_keys & gen_keys:
        if ref[key] != gen[key]:
            if isinstance(ref[key], dict) and isinstance(gen[key], dict):
                sub_diff = _compare_dicts(ref[key], gen[key], f"{prefix}{key}.")
                differences.extend(sub_diff)
            else:
                differences.append({
                    "field": f"{prefix}{key}",
                    "issue": "different_value",
                    "reference": str(ref[key])[:200],
                    "generated": str(gen[key])[:200]
                })
    
    return differences


def save_comparison_report(reference_file: str, differences: Dict[str, Any], 
                          reference_payload: Dict, generated_payload: Dict,
                          inputs: Dict[str, Any], output_file: str):
    """
    Sauvegarde un rapport de comparaison détaillé.
    
    Args:
        reference_file: Fichier de référence utilisé
        differences: Différences identifiées
        reference_payload: Payload de référence
        generated_payload: Payload généré
        inputs: Inputs extraits
        output_file: Fichier de sortie
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "reference_file": reference_file,
        "summary": {
            "missing_fields_count": len(differences.get("missing_fields", [])),
            "extra_fields_count": len(differences.get("extra_fields", [])),
            "different_values_count": len(differences.get("different_values", []))
        },
        "differences": differences,
        "inputs_extracted": inputs,
        "reference_payload": reference_payload,
        "generated_payload": generated_payload
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"[OK] Rapport sauvegarde: {output_file}")


def main():
    """Fonction principale."""
    if len(sys.argv) < 2:
        print("Usage: python compare_payloads.py <codeassist_final_*.json>")
        print("\nExemple:")
        print("  python compare_payloads.py logs/codeassist_final_gemini-3-flash-preview_26-Dec_23h46_56.json")
        sys.exit(1)
    
    reference_file = sys.argv[1]
    
    if not os.path.exists(reference_file):
        print(f"[ERROR] Fichier non trouve: {reference_file}")
        sys.exit(1)
    
    print(f"[*] Chargement du payload de reference: {reference_file}")
    reference_payload, meta = load_reference_payload(reference_file)
    
    print(f"[*] Extraction des inputs du payload de reference...")
    inputs = extract_inputs_from_payload(reference_payload)
    
    print(f"[*] Generation du payload avec CodeAssistClient...")
    generated_payload = generate_codeassist_payload(inputs)
    
    print(f"[*] Comparaison des payloads...")
    differences = compare_payloads(reference_payload, generated_payload)
    
    # Afficher le résumé
    print("\n" + "="*80)
    print("RESUME DES DIFFERENCES")
    print("="*80)
    print(f"Champs manquants dans generated: {len(differences['missing_fields'])}")
    if differences['missing_fields']:
        for field in differences['missing_fields']:
            print(f"  - {field}")
    
    print(f"\nChamps supplementaires dans generated: {len(differences['extra_fields'])}")
    if differences['extra_fields']:
        for field in differences['extra_fields']:
            print(f"  - {field}")
    
    print(f"\nValeurs differentes: {len(differences['different_values'])}")
    if differences['different_values']:
        for diff in differences['different_values'][:10]:  # Limiter à 10 pour l'affichage
            field = diff.get('field', 'unknown')
            if 'issue' in diff:
                print(f"  - {field}: {diff['issue']}")
            else:
                ref_val = diff.get('reference', '')[:100]
                gen_val = diff.get('generated', '')[:100]
                print(f"    {field}: {ref_val} vs {gen_val}")
        if len(differences['different_values']) > 10:
            print(f"  ... et {len(differences['different_values']) - 10} autres differences")
    
    # Sauvegarder le rapport détaillé
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%d-%b_%Hh%M_%S")
    output_file = logs_dir / f"payload_comparison_{timestamp}.json"
    
    save_comparison_report(
        reference_file,
        differences,
        reference_payload,
        generated_payload,
        inputs,
        str(output_file)
    )
    
    print("\n" + "="*80)
    if len(differences['missing_fields']) == 0 and len(differences['different_values']) == 0:
        print("[OK] Les payloads sont identiques (structure et valeurs)")
    else:
        print("[WARN] Des differences ont ete identifiees. Voir le rapport detaille.")
    print("="*80)


if __name__ == "__main__":
    main()


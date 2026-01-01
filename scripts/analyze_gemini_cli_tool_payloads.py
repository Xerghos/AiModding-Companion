"""
Analyse approfondie des payloads capturés de gemini-cli pour extraire les patterns.
Compare avec nos payloads et génère des recommandations.

Usage:
    python scripts/analyze_gemini_cli_tool_payloads.py [--compare] [--detailed]

Options:
    --compare: Compare avec nos payloads d'erreur 400
    --detailed: Affiche une analyse détaillée de chaque payload
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
import sys
from datetime import datetime

# Configuration
LOGS_DIR = Path(__file__).parent.parent / "logs"
REPORT_DIR = LOGS_DIR / "analysis_reports"
REPORT_DIR.mkdir(exist_ok=True)


def load_payloads(pattern: str = "gemini_cli_tool_call_*.json") -> List[Dict[str, Any]]:
    """Charge tous les payloads correspondant au pattern."""
    payloads = []
    for file_path in sorted(LOGS_DIR.glob(pattern)):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data["_source_file"] = file_path.name
                payloads.append(data)
        except Exception as e:
            print(f"⚠️  Erreur chargement {file_path.name}: {e}")
    return payloads


def analyze_single_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyse un payload individuel."""
    payload = data.get("payload", {})
    analysis = data.get("analysis", {})
    
    result = {
        "timestamp": data.get("timestamp"),
        "source_file": data.get("_source_file"),
        "model": analysis.get("model"),
        "session_id": analysis.get("session_id"),
        "is_tool_call": data.get("is_tool_call", False),
        "functionCall_count": len(analysis.get("functionCall_details", [])),
        "functionResponse_count": len(analysis.get("functionResponse_details", [])),
        "functionCall_ids": [fc.get("id") for fc in analysis.get("functionCall_details", []) if fc.get("id")],
        "functionResponse_ids": [fr.get("id") for fr in analysis.get("functionResponse_details", []) if fr.get("id")],
        "has_thoughtSignature": analysis.get("has_thoughtSignature", False),
        "thoughtSignature_locations": analysis.get("thoughtSignature_locations", []),
        "id_correlations": analysis.get("id_correlations", []),
        "sequence_valid": analysis.get("sequence_valid", False),
        "contents_structure": analysis.get("contents_structure", []),
        "functionCall_details": analysis.get("functionCall_details", []),
        "functionResponse_details": analysis.get("functionResponse_details", [])
    }
    
    return result


def aggregate_patterns(payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrège les patterns sur tous les payloads."""
    patterns = {
        "total_payloads": len(payloads),
        "tool_call_payloads": 0,
        "functionCall_stats": {
            "total": 0,
            "with_id": 0,
            "without_id": 0,
            "with_thoughtSignature": 0,
            "without_thoughtSignature": 0,
            "id_patterns": defaultdict(int)
        },
        "functionResponse_stats": {
            "total": 0,
            "with_id": 0,
            "without_id": 0,
            "output_format": {"output": 0, "content": 0, "result": 0, "unknown": 0}
        },
        "id_correlation_stats": {
            "matches": 0,
            "mismatches": 0,
            "missing": 0,
            "both_present": 0,
            "both_absent": 0,
            "only_functionCall": 0,
            "only_functionResponse": 0
        },
        "sequence_stats": {
            "valid": 0,
            "invalid": 0
        },
        "session_id_stats": {
            "present": 0,
            "absent": 0
        },
        "model_distribution": defaultdict(int),
        "contents_length_distribution": defaultdict(int)
    }
    
    for payload_data in payloads:
        analysis = payload_data.get("analysis", {})
        
        if payload_data.get("is_tool_call"):
            patterns["tool_call_payloads"] += 1
        
        # Stats functionCall
        for fc in analysis.get("functionCall_details", []):
            patterns["functionCall_stats"]["total"] += 1
            if fc.get("has_id"):
                patterns["functionCall_stats"]["with_id"] += 1
                # Analyser le pattern de l'ID
                fc_id = fc.get("id", "")
                if len(fc_id) == 36 and fc_id.count('-') == 4:
                    patterns["functionCall_stats"]["id_patterns"]["uuid_v4"] += 1
                elif fc_id.startswith("temp_"):
                    patterns["functionCall_stats"]["id_patterns"]["temp_prefix"] += 1
                else:
                    patterns["functionCall_stats"]["id_patterns"]["other"] += 1
            else:
                patterns["functionCall_stats"]["without_id"] += 1
            
            if fc.get("has_thoughtSignature"):
                patterns["functionCall_stats"]["with_thoughtSignature"] += 1
            else:
                patterns["functionCall_stats"]["without_thoughtSignature"] += 1
        
        # Stats functionResponse
        for fr in analysis.get("functionResponse_details", []):
            patterns["functionResponse_stats"]["total"] += 1
            if fr.get("has_id"):
                patterns["functionResponse_stats"]["with_id"] += 1
            else:
                patterns["functionResponse_stats"]["without_id"] += 1
            
            if fr.get("has_output"):
                patterns["functionResponse_stats"]["output_format"]["output"] += 1
            elif fr.get("has_content"):
                patterns["functionResponse_stats"]["output_format"]["content"] += 1
            elif fr.get("has_result"):
                patterns["functionResponse_stats"]["output_format"]["result"] += 1
            else:
                patterns["functionResponse_stats"]["output_format"]["unknown"] += 1
        
        # Stats corrélation ID
        for corr in analysis.get("id_correlations", []):
            if corr.get("match") is True:
                patterns["id_correlation_stats"]["matches"] += 1
            elif corr.get("match") is False:
                patterns["id_correlation_stats"]["mismatches"] += 1
            else:
                patterns["id_correlation_stats"]["missing"] += 1
            
            if corr.get("both_present"):
                patterns["id_correlation_stats"]["both_present"] += 1
            elif corr.get("both_absent"):
                patterns["id_correlation_stats"]["both_absent"] += 1
            elif corr.get("only_functionCall"):
                patterns["id_correlation_stats"]["only_functionCall"] += 1
            elif corr.get("only_functionResponse"):
                patterns["id_correlation_stats"]["only_functionResponse"] += 1
        
        # Stats séquence
        if analysis.get("sequence_valid"):
            patterns["sequence_stats"]["valid"] += 1
        else:
            patterns["sequence_stats"]["invalid"] += 1
        
        # Stats session_id
        if analysis.get("session_id"):
            patterns["session_id_stats"]["present"] += 1
        else:
            patterns["session_id_stats"]["absent"] += 1
        
        # Distribution modèles
        model = analysis.get("model", "unknown")
        patterns["model_distribution"][model] += 1
        
        # Distribution longueur contents
        contents_count = analysis.get("contents_count", 0)
        patterns["contents_length_distribution"][contents_count] += 1
    
    return patterns


def compare_with_our_payloads(gemini_cli_payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compare les payloads gemini-cli avec nos payloads d'erreur."""
    comparison = {
        "our_payloads_found": False,
        "our_payloads_count": 0,
        "differences": [],
        "similarities": [],
        "recommendations": []
    }
    
    # Charger nos payloads d'erreur
    our_payloads = load_payloads("error_400_payload_*.json")
    
    if not our_payloads:
        comparison["recommendations"].append(
            "Aucun payload d'erreur 400 trouvé pour comparaison"
        )
        return comparison
    
    comparison["our_payloads_found"] = True
    comparison["our_payloads_count"] = len(our_payloads)
    
    # Comparer les structures
    for cli_payload in gemini_cli_payloads[:3]:  # Comparer avec les 3 premiers
        cli_analysis = cli_payload.get("analysis", {})
        
        for our_payload in our_payloads[:3]:  # Comparer avec les 3 premiers
            our_analysis = our_payload.get("analysis", {})
            
            # Comparer functionCall
            cli_fc_count = len(cli_analysis.get("functionCall_details", []))
            our_fc_count = len(our_analysis.get("functionCall_details", []))
            
            if cli_fc_count != our_fc_count:
                comparison["differences"].append(
                    f"Nombre functionCall: gemini-cli={cli_fc_count}, nous={our_fc_count}"
                )
            
            # Comparer IDs
            cli_fc_ids = [fc.get("id") for fc in cli_analysis.get("functionCall_details", []) if fc.get("id")]
            our_fc_ids = [fc.get("id") for fc in our_analysis.get("functionCall_details", []) if fc.get("id")]
            
            if len(cli_fc_ids) != len(our_fc_ids):
                comparison["differences"].append(
                    f"Présence IDs functionCall: gemini-cli={len(cli_fc_ids)}/{cli_fc_count}, "
                    f"nous={len(our_fc_ids)}/{our_fc_count}"
                )
            
            # Comparer thoughtSignature
            cli_has_ts = cli_analysis.get("has_thoughtSignature", False)
            our_has_ts = our_analysis.get("has_thoughtSignature", False)
            
            if cli_has_ts != our_has_ts:
                comparison["differences"].append(
                    f"thoughtSignature: gemini-cli={cli_has_ts}, nous={our_has_ts}"
                )
            else:
                comparison["similarities"].append(
                    f"thoughtSignature: même comportement ({cli_has_ts})"
                )
            
            # Comparer format functionResponse
            cli_fr_details = cli_analysis.get("functionResponse_details", [])
            our_fr_details = our_analysis.get("functionResponse_details", [])
            
            if cli_fr_details and our_fr_details:
                cli_format = "output" if cli_fr_details[0].get("has_output") else "content" if cli_fr_details[0].get("has_content") else "unknown"
                our_format = "output" if our_fr_details[0].get("has_output") else "content" if our_fr_details[0].get("has_content") else "unknown"
                
                if cli_format != our_format:
                    comparison["differences"].append(
                        f"Format functionResponse: gemini-cli={cli_format}, nous={our_format}"
                    )
                else:
                    comparison["similarities"].append(
                        f"Format functionResponse: même format ({cli_format})"
                    )
    
    # Générer recommandations basées sur les différences
    if any("IDs functionCall" in d for d in comparison["differences"]):
        comparison["recommendations"].append(
            "⚠️  Vérifier la gestion des IDs dans functionCall - différence détectée avec gemini-cli"
        )
    
    if any("thoughtSignature" in d for d in comparison["differences"]):
        comparison["recommendations"].append(
            "⚠️  Vérifier la gestion de thoughtSignature - différence détectée avec gemini-cli"
        )
    
    return comparison


def generate_recommendations(patterns: Dict[str, Any], comparison: Optional[Dict[str, Any]] = None) -> List[str]:
    """Génère des recommandations basées sur l'analyse."""
    recommendations = []
    
    # Recommandations basées sur les patterns
    fc_stats = patterns["functionCall_stats"]
    if fc_stats["without_id"] > 0:
        recommendations.append(
            f"✅ CONFIRMÉ: Certains functionCall n'ont pas d'ID ({fc_stats['without_id']}/{fc_stats['total']}) - "
            "C'est normal pour Gemini 3, ne pas générer d'ID côté client"
        )
    
    if fc_stats["with_thoughtSignature"] == 0 and patterns["total_payloads"] > 0:
        recommendations.append(
            "⚠️  Aucun thoughtSignature détecté dans les payloads gemini-cli - "
            "Peut-être filtré par cloudcode-pa ou absent dans les réponses"
        )
    
    fr_stats = patterns["functionResponse_stats"]
    if fr_stats["output_format"]["output"] > 0:
        recommendations.append(
            f"✅ CONFIRMÉ: Format 'output' utilisé ({fr_stats['output_format']['output']} fois) - "
            "Continuer à utiliser 'output' au lieu de 'content'"
        )
    
    corr_stats = patterns["id_correlation_stats"]
    if corr_stats["matches"] > 0:
        recommendations.append(
            f"✅ Corrélations ID valides détectées ({corr_stats['matches']}) - "
            "La corrélation ID fonctionne correctement dans gemini-cli"
        )
    
    if corr_stats["both_absent"] > 0:
        recommendations.append(
            f"✅ CONFIRMÉ: Cas où functionCall ET functionResponse n'ont pas d'ID ({corr_stats['both_absent']}) - "
            "C'est acceptable, ne pas générer d'ID dans ce cas"
        )
    
    if patterns["sequence_stats"]["invalid"] > 0:
        recommendations.append(
            f"⚠️  {patterns['sequence_stats']['invalid']} séquence(s) invalide(s) détectée(s) - "
            "Vérifier la structure des messages dans contents"
        )
    
    # Recommandations basées sur la comparaison
    if comparison and comparison.get("our_payloads_found"):
        for rec in comparison.get("recommendations", []):
            recommendations.append(f"🔍 COMPARAISON: {rec}")
    
    return recommendations


def print_detailed_analysis(payloads: List[Dict[str, Any]]):
    """Affiche une analyse détaillée de chaque payload."""
    print("\n" + "=" * 80)
    print("ANALYSE DÉTAILLÉE PAR PAYLOAD")
    print("=" * 80 + "\n")
    
    for idx, payload_data in enumerate(payloads, 1):
        analysis = payload_data.get("analysis", {})
        
        print(f"--- Payload #{idx}: {payload_data.get('_source_file', 'unknown')} ---")
        print(f"Timestamp: {payload_data.get('timestamp')}")
        print(f"Model: {analysis.get('model', 'unknown')}")
        print(f"Session ID: {analysis.get('session_id', 'ABSENT')}")
        print(f"Contents: {analysis.get('contents_count', 0)} messages")
        print(f"Séquence valide: {analysis.get('sequence_valid', False)}")
        print()
        
        # Détails functionCall
        for fc in analysis.get("functionCall_details", []):
            print(f"  functionCall[{fc['message_index']}][{fc['part_index']}]:")
            print(f"    - Name: {fc['name']}")
            print(f"    - ID: {fc['id'] if fc['has_id'] else 'ABSENT'}")
            print(f"    - thoughtSignature: {'PRÉSENT' if fc['has_thoughtSignature'] else 'ABSENT'}")
            print(f"    - Args keys: {fc['args_keys']}")
            print(f"    - Tous les champs: {fc['all_keys']}")
            print()
        
        # Détails functionResponse
        for fr in analysis.get("functionResponse_details", []):
            print(f"  functionResponse[{fr['message_index']}][{fr['part_index']}]:")
            print(f"    - Name: {fr['name']}")
            print(f"    - ID: {fr['id'] if fr['has_id'] else 'ABSENT'}")
            print(f"    - Format: {'output' if fr['has_output'] else 'content' if fr['has_content'] else 'result' if fr['has_result'] else 'UNKNOWN'}")
            print(f"    - Output type: {fr['output_type']}")
            print(f"    - Output length: {fr['output_length']}")
            print(f"    - Tous les champs: {fr['all_keys']}")
            print()
        
        # Corrélations ID
        for corr in analysis.get("id_correlations", []):
            status = "✅ MATCH" if corr.get("match") is True else "❌ MISMATCH" if corr.get("match") is False else "⚠️  MANQUANT"
            print(f"  Corrélation ID: {status}")
            print(f"    - functionCall.id: {corr.get('functionCall_id', 'ABSENT')}")
            print(f"    - functionResponse.id: {corr.get('functionResponse_id', 'ABSENT')}")
            print()
        
        print()


def main():
    """Fonction principale."""
    compare_mode = "--compare" in sys.argv
    detailed_mode = "--detailed" in sys.argv
    
    print("=" * 80)
    print("ANALYSE DES PAYLOADS GEMINI-CLI")
    print("=" * 80)
    print()
    
    # Charger les payloads
    print("📂 Chargement des payloads...")
    payloads = load_payloads("gemini_cli_tool_call_*.json")
    
    if not payloads:
        print("❌ Aucun payload trouvé dans logs/gemini_cli_tool_call_*.json")
        print("   Exécutez d'abord: mitmdump -s scripts/capture_gemini_cli_mitmproxy.py")
        return
    
    print(f"✅ {len(payloads)} payload(s) chargé(s)\n")
    
    # Analyser chaque payload
    analyzed_payloads = [analyze_single_payload(p) for p in payloads]
    
    # Agrégation des patterns
    print("📊 Agrégation des patterns...")
    patterns = aggregate_patterns(payloads)
    
    # Comparaison avec nos payloads
    comparison = None
    if compare_mode:
        print("🔍 Comparaison avec nos payloads...")
        comparison = compare_with_our_payloads(payloads)
    
    # Génération des recommandations
    recommendations = generate_recommendations(patterns, comparison)
    
    # Affichage des résultats
    print("\n" + "=" * 80)
    print("RÉSULTATS DE L'ANALYSE")
    print("=" * 80 + "\n")
    
    print(f"📈 Statistiques générales:")
    print(f"  - Total payloads: {patterns['total_payloads']}")
    print(f"  - Payloads tool call: {patterns['tool_call_payloads']}")
    print()
    
    print(f"🔧 functionCall:")
    fc_stats = patterns["functionCall_stats"]
    print(f"  - Total: {fc_stats['total']}")
    print(f"  - Avec ID: {fc_stats['with_id']} ({fc_stats['with_id']/fc_stats['total']*100:.1f}%)" if fc_stats['total'] > 0 else "  - Avec ID: 0")
    print(f"  - Sans ID: {fc_stats['without_id']} ({fc_stats['without_id']/fc_stats['total']*100:.1f}%)" if fc_stats['total'] > 0 else "  - Sans ID: 0")
    print(f"  - Avec thoughtSignature: {fc_stats['with_thoughtSignature']}")
    print(f"  - Patterns ID: {dict(fc_stats['id_patterns'])}")
    print()
    
    print(f"📤 functionResponse:")
    fr_stats = patterns["functionResponse_stats"]
    print(f"  - Total: {fr_stats['total']}")
    print(f"  - Avec ID: {fr_stats['with_id']} ({fr_stats['with_id']/fr_stats['total']*100:.1f}%)" if fr_stats['total'] > 0 else "  - Avec ID: 0")
    print(f"  - Sans ID: {fr_stats['without_id']} ({fr_stats['without_id']/fr_stats['total']*100:.1f}%)" if fr_stats['total'] > 0 else "  - Sans ID: 0")
    print(f"  - Format: {dict(fr_stats['output_format'])}")
    print()
    
    print(f"🔗 Corrélations ID:")
    corr_stats = patterns["id_correlation_stats"]
    print(f"  - Matches: {corr_stats['matches']}")
    print(f"  - Mismatches: {corr_stats['mismatches']}")
    print(f"  - Missing: {corr_stats['missing']}")
    print(f"  - Les deux présents: {corr_stats['both_present']}")
    print(f"  - Les deux absents: {corr_stats['both_absent']}")
    print()
    
    print(f"📋 Séquences:")
    print(f"  - Valides: {patterns['sequence_stats']['valid']}")
    print(f"  - Invalides: {patterns['sequence_stats']['invalid']}")
    print()
    
    print(f"🆔 Session ID:")
    print(f"  - Présent: {patterns['session_id_stats']['present']}")
    print(f"  - Absent: {patterns['session_id_stats']['absent']}")
    print()
    
    print(f"🤖 Modèles utilisés:")
    for model, count in patterns['model_distribution'].items():
        print(f"  - {model}: {count}")
    print()
    
    # Comparaison
    if comparison and comparison.get("our_payloads_found"):
        print("=" * 80)
        print("COMPARAISON AVEC NOS PAYLOADS")
        print("=" * 80 + "\n")
        print(f"Payloads gemini-cli: {len(payloads)}")
        print(f"Payloads d'erreur 400: {comparison['our_payloads_count']}")
        print()
        
        if comparison.get("differences"):
            print("❌ DIFFÉRENCES:")
            for diff in comparison["differences"]:
                print(f"  - {diff}")
            print()
        
        if comparison.get("similarities"):
            print("✅ SIMILARITÉS:")
            for sim in comparison["similarities"][:5]:  # Limiter à 5
                print(f"  - {sim}")
            print()
    
    # Recommandations
    print("=" * 80)
    print("RECOMMANDATIONS")
    print("=" * 80 + "\n")
    for rec in recommendations:
        print(f"  {rec}")
    print()
    
    # Analyse détaillée
    if detailed_mode:
        print_detailed_analysis(payloads)
    
    # Sauvegarder le rapport
    timestamp = datetime.now().strftime("%d-%b_%Hh%M_%S")
    report_file = REPORT_DIR / f"gemini_cli_analysis_{timestamp}.json"
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "patterns": patterns,
        "comparison": comparison,
        "recommendations": recommendations,
        "analyzed_payloads": analyzed_payloads
    }
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Rapport complet sauvegardé: {report_file}")
    print()


if __name__ == "__main__":
    main()

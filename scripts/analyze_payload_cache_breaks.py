#!/usr/bin/env python3
"""
Script d'analyse des cassures de cache entre deux payloads.
Détecte les différences qui invalident le cache implicite Gemini/DeepSeek.
Génère des rapports détaillés dans logs/.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
import difflib

# Ajouter le répertoire racine au path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.paths import get_path


class PayloadCacheAnalyzer:
    """Analyseur de cassures de cache entre payloads."""
    
    def __init__(self, payload1_path: str, payload2_path: str):
        self.payload1_path = payload1_path
        self.payload2_path = payload2_path
        self.payload1 = None
        self.payload2 = None
        self.differences = []
        self.cache_breaks = []
        
    def load_payloads(self) -> Tuple[bool, Optional[str]]:
        """Charge les deux payloads depuis les fichiers JSON."""
        try:
            with open(self.payload1_path, 'r', encoding='utf-8') as f:
                self.payload1 = json.load(f)
            with open(self.payload2_path, 'r', encoding='utf-8') as f:
                self.payload2 = json.load(f)
            return True, None
        except Exception as e:
            return False, str(e)
    
    def extract_payload_data(self, payload_obj: Dict) -> Dict:
        """
        Extrait uniquement le payload réel (sans métadonnées comme timestamp).
        Le cache Gemini compare uniquement les messages dans payload.messages.
        
        Note: Le timestamp dans les métadonnées (niveau racine) NE CASSE PAS le cache
        car il n'est pas inclus dans payload.messages qui est ce qui est envoyé à l'API.
        """
        if 'payload' in payload_obj:
            return payload_obj['payload']
        return payload_obj
    
    def categorize_messages(self, messages: List[Dict]) -> Dict[str, List[Dict]]:
        """Catégorise les messages par rôle."""
        categorized = {
            'system': [],
            'user': [],
            'assistant': []
        }
        for msg in messages:
            role = msg.get('role', '').lower()
            if role in categorized:
                categorized[role].append(msg)
        return categorized
    
    def normalize_content(self, content: str) -> str:
        """Normalise le contenu pour la comparaison (supprime espaces superflus)."""
        # Garde la structure mais normalise les espaces
        lines = content.split('\n')
        normalized_lines = [line.rstrip() for line in lines]
        # Supprime les lignes vides en fin de fichier
        while normalized_lines and not normalized_lines[-1]:
            normalized_lines.pop()
        return '\n'.join(normalized_lines)
    
    def compare_system_messages(self, sys1: List[Dict], sys2: List[Dict]) -> List[Dict]:
        """
        Compare les messages système (CRITIQUE pour le cache).
        Retourne la liste des différences détectées.
        """
        breaks = []
        
        if len(sys1) != len(sys2):
            breaks.append({
                'type': 'SYSTEM_COUNT_MISMATCH',
                'severity': 'CRITICAL',
                'description': f'Nombre différent de messages système: {len(sys1)} vs {len(sys2)}',
                'payload1_count': len(sys1),
                'payload2_count': len(sys2)
            })
        
        min_len = min(len(sys1), len(sys2))
        
        for i in range(min_len):
            msg1 = sys1[i]
            msg2 = sys2[i]
            content1 = self.normalize_content(msg1.get('content', ''))
            content2 = self.normalize_content(msg2.get('content', ''))
            
            if content1 != content2:
                # Analyser le type de différence
                diff_type = self._analyze_system_content_diff(content1, content2)
                
                breaks.append({
                    'type': 'SYSTEM_CONTENT_MISMATCH',
                    'severity': 'CRITICAL',
                    'index': i,
                    'description': f'Message système #{i+1} différent',
                    'diff_type': diff_type,
                    'content1_preview': content1[:200] + ('...' if len(content1) > 200 else ''),
                    'content2_preview': content2[:200] + ('...' if len(content2) > 200 else ''),
                    'size1': len(content1),
                    'size2': len(content2)
                })
        
        return breaks
    
    def _analyze_system_content_diff(self, content1: str, content2: str) -> str:
        """Analyse le type de différence dans le contenu système."""
        # Détecter les blocs RAG dynamiques
        if 'DOCS TECHNIQUE (RAG Hybride)' in content1 or 'DOCS TECHNIQUE (RAG Hybride)' in content2:
            if content1 != content2:
                return 'RAG_DOCS_DYNAMIC'
        
        # Détecter les changements de Repo Map
        if 'REPO MAP' in content1 or 'REPO MAP' in content2:
            if content1 != content2:
                return 'REPO_MAP_CHANGED'
        
        # Détecter les changements de LTM
        if 'MÉMOIRE LONG TERME' in content1 or 'MÉMOIRE LONG TERME' in content2:
            if content1 != content2:
                return 'LTM_CHANGED'
        
        # Détecter les changements d'arborescence
        if 'ARBORESCENCE PROJET' in content1 or 'ARBORESCENCE PROJET' in content2:
            if content1 != content2:
                return 'TREE_CHANGED'
        
        # Détecter les changements de cartographie technique
        if 'CARTOGRAPHIE TECHNIQUE' in content1 or 'CARTOGRAPHIE TECHNIQUE' in content2:
            if content1 != content2:
                return 'ARCH_MAP_CHANGED'
        
        # Différence générique
        return 'GENERIC_CONTENT_DIFF'
    
    def compare_histories(self, hist1: List[Dict], hist2: List[Dict]) -> List[Dict]:
        """Compare les historiques conversationnels (moins critique pour cache système)."""
        breaks = []
        
        if len(hist1) != len(hist2):
            breaks.append({
                'type': 'HISTORY_LENGTH_MISMATCH',
                'severity': 'INFO',
                'description': f'Longueur d\'historique différente: {len(hist1)} vs {len(hist2)}',
                'payload1_length': len(hist1),
                'payload2_length': len(hist2)
            })
        
        # Comparer les derniers messages (les plus récents)
        min_len = min(len(hist1), len(hist2))
        if min_len > 0:
            # Comparer les 3 derniers messages
            compare_count = min(3, min_len)
            for i in range(compare_count):
                idx1 = len(hist1) - compare_count + i
                idx2 = len(hist2) - compare_count + i
                msg1 = hist1[idx1]
                msg2 = hist2[idx2]
                
                if msg1.get('role') != msg2.get('role'):
                    breaks.append({
                        'type': 'HISTORY_ROLE_MISMATCH',
                        'severity': 'WARNING',
                        'index': idx1,
                        'description': f'Rôle différent dans l\'historique à l\'index {idx1}',
                        'role1': msg1.get('role'),
                        'role2': msg2.get('role')
                    })
                
                content1 = self.normalize_content(msg1.get('content', ''))
                content2 = self.normalize_content(msg2.get('content', ''))
                
                if content1 != content2:
                    breaks.append({
                        'type': 'HISTORY_CONTENT_MISMATCH',
                        'severity': 'INFO',
                        'index': idx1,
                        'description': f'Contenu historique différent à l\'index {idx1}',
                        'size1': len(content1),
                        'size2': len(content2)
                    })
        
        return breaks
    
    def generate_diff_text(self, content1: str, content2: str, context_lines: int = 3) -> str:
        """Génère un diff textuel pour visualiser les différences."""
        lines1 = content1.split('\n')
        lines2 = content2.split('\n')
        
        diff = difflib.unified_diff(
            lines1, lines2,
            lineterm='',
            n=context_lines
        )
        
        return '\n'.join(diff)
    
    def analyze(self) -> Dict[str, Any]:
        """Effectue l'analyse complète des deux payloads."""
        success, error = self.load_payloads()
        if not success:
            return {
                'success': False,
                'error': error
            }
        
        payload1_data = self.extract_payload_data(self.payload1)
        payload2_data = self.extract_payload_data(self.payload2)
        
        messages1 = payload1_data.get('messages', [])
        messages2 = payload2_data.get('messages', [])
        
        categorized1 = self.categorize_messages(messages1)
        categorized2 = self.categorize_messages(messages2)
        
        # Analyser les messages système (CRITIQUE pour cache)
        system_breaks = self.compare_system_messages(
            categorized1['system'],
            categorized2['system']
        )
        
        # Analyser l'historique (moins critique mais informatif)
        history_breaks = self.compare_histories(
            categorized1['user'] + categorized1['assistant'],
            categorized2['user'] + categorized2['assistant']
        )
        
        # Calculer les statistiques
        total_system_chars1 = sum(len(msg.get('content', '')) for msg in categorized1['system'])
        total_system_chars2 = sum(len(msg.get('content', '')) for msg in categorized2['system'])
        
        critical_breaks = [b for b in system_breaks if b.get('severity') == 'CRITICAL']
        
        return {
            'success': True,
            'payload1_path': self.payload1_path,
            'payload2_path': self.payload2_path,
            'timestamp1': self.payload1.get('timestamp', 'N/A'),
            'timestamp2': self.payload2.get('timestamp', 'N/A'),
            'model1': payload1_data.get('model', 'N/A'),
            'model2': payload2_data.get('model', 'N/A'),
            'stats': {
                'system_messages1': len(categorized1['system']),
                'system_messages2': len(categorized2['system']),
                'total_system_chars1': total_system_chars1,
                'total_system_chars2': total_system_chars2,
                'history_messages1': len(categorized1['user']) + len(categorized1['assistant']),
                'history_messages2': len(categorized2['user']) + len(categorized2['assistant'])
            },
            'cache_breaks': {
                'system': system_breaks,
                'history': history_breaks,
                'critical_count': len(critical_breaks),
                'total_count': len(system_breaks) + len(history_breaks)
            },
            'cache_impact': {
                'will_invalidate_cache': len(critical_breaks) > 0,
                'reason': 'Messages système différents' if len(critical_breaks) > 0 else 'Pas de cassure détectée'
            }
        }
    
    def generate_report(self, analysis: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """Génère un rapport markdown détaillé."""
        if not output_path:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            output_path = get_path(f"logs/payload_cache_analysis_{timestamp}.md")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Analyse des Cassures de Cache entre Payloads\n\n")
            f.write(f"**Généré le:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            if not analysis.get('success'):
                f.write(f"## ❌ Erreur\n\n{analysis.get('error')}\n")
                return output_path
            
            # Métadonnées
            f.write("## Métadonnées\n\n")
            f.write(f"- **Payload 1:** `{Path(analysis['payload1_path']).name}` (Timestamp: {analysis['timestamp1']})\n")
            f.write(f"- **Payload 2:** `{Path(analysis['payload2_path']).name}` (Timestamp: {analysis['timestamp2']})\n")
            f.write(f"- **Modèle 1:** {analysis['model1']}\n")
            f.write(f"- **Modèle 2:** {analysis['model2']}\n\n")
            f.write("> **Note:** Le timestamp dans les métadonnées du fichier JSON ne casse PAS le cache car il n'est pas inclus dans le payload envoyé à l'API (uniquement dans `payload.messages`).\n\n")
            
            # Statistiques
            stats = analysis['stats']
            f.write("## Statistiques\n\n")
            f.write(f"- Messages système: {stats['system_messages1']} → {stats['system_messages2']}\n")
            f.write(f"- Caractères système: {stats['total_system_chars1']} → {stats['total_system_chars2']}\n")
            f.write(f"- Messages historique: {stats['history_messages1']} → {stats['history_messages2']}\n\n")
            
            # Impact cache
            cache_impact = analysis['cache_impact']
            if cache_impact['will_invalidate_cache']:
                f.write("## ⚠️ IMPACT CACHE: **INVALIDATION DÉTECTÉE**\n\n")
                f.write(f"**Raison:** {cache_impact['reason']}\n\n")
            else:
                f.write("## ✅ Pas de cassure de cache détectée\n\n")
            
            # Détails des cassures
            breaks = analysis['cache_breaks']
            f.write(f"## Détails des Cassures\n\n")
            f.write(f"- **Cassures critiques:** {breaks['critical_count']}\n")
            f.write(f"- **Total cassures:** {breaks['total_count']}\n\n")
            
            # Messages système
            if breaks['system']:
                f.write("### 🔴 Messages Système (CRITIQUE pour cache)\n\n")
                for i, break_info in enumerate(breaks['system'], 1):
                    severity = break_info.get('severity', 'UNKNOWN')
                    severity_emoji = '🔴' if severity == 'CRITICAL' else '🟡' if severity == 'WARNING' else '🔵'
                    
                    f.write(f"#### {severity_emoji} Cassure #{i}: {break_info['type']}\n\n")
                    f.write(f"- **Sévérité:** {severity}\n")
                    f.write(f"- **Description:** {break_info['description']}\n")
                    
                    if 'diff_type' in break_info:
                        f.write(f"- **Type de différence:** {break_info['diff_type']}\n")
                    
                    if 'size1' in break_info and 'size2' in break_info:
                        size_diff = break_info['size2'] - break_info['size1']
                        f.write(f"- **Taille:** {break_info['size1']} → {break_info['size2']} chars (Δ{size_diff:+d})\n")
                    
                    if 'content1_preview' in break_info:
                        f.write(f"\n**Preview Payload 1:**\n```\n{break_info['content1_preview']}\n```\n\n")
                        f.write(f"**Preview Payload 2:**\n```\n{break_info['content2_preview']}\n```\n\n")
                    
                    f.write("\n")
            
            # Historique
            if breaks['history']:
                f.write("### 📝 Historique Conversationnel (Moins critique)\n\n")
                for i, break_info in enumerate(breaks['history'], 1):
                    severity = break_info.get('severity', 'INFO')
                    f.write(f"#### {i}. {break_info['type']} ({severity})\n\n")
                    f.write(f"- {break_info['description']}\n\n")
            
            # Recommandations
            f.write("## 💡 Recommandations\n\n")
            
            has_rag_breaks = any(b.get('diff_type') == 'RAG_DOCS_DYNAMIC' for b in breaks['system'])
            has_repo_breaks = any(b.get('diff_type') == 'REPO_MAP_CHANGED' for b in breaks['system'])
            has_ltm_breaks = any(b.get('diff_type') == 'LTM_CHANGED' for b in breaks['system'])
            
            if has_rag_breaks:
                f.write("- ⚠️ **RAG Docs dynamique détecté:** Le bloc RAG Docs change entre requêtes, cassant le cache.\n")
                f.write("  → **Solution:** Ne pas injecter RAG Docs dans les messages système pour les sessions avec cache.\n")
                f.write("  → **Implémentation:** Retirer le bloc RAG Docs des messages système dans `_build_payload_messages()` pour DeepSeek/Gemini avec cache.\n\n")
            
            if has_repo_breaks:
                f.write("- ⚠️ **Repo Map changeante:** La Repo Map est régénérée à chaque requête.\n")
                f.write("  → **Solution:** S'assurer que la Repo Map est vraiment mise en cache dans CacheManager.\n")
                f.write("  → **Implémentation:** Vérifier que `CacheManager.prepare_content()` n'est pas appelé à chaque requête, ou que la Repo Map est stable entre appels.\n\n")
            
            if has_ltm_breaks:
                f.write("- ⚠️ **LTM changeante:** La mémoire long terme change entre requêtes.\n")
                f.write("  → **Solution:** Stabiliser la consolidation LTM pour éviter les changements fréquents.\n")
                f.write("  → **Implémentation:** S'assurer que la consolidation LTM n'est pas déclenchée entre chaque requête.\n\n")
            
            if not breaks['system']:
                f.write("- ✅ Aucune cassure critique détectée dans les messages système.\n\n")
            
            # Note sur le timestamp
            f.write("## 📝 Notes Techniques\n\n")
            f.write("- Le timestamp dans les métadonnées du fichier JSON (niveau racine) **ne casse PAS** le cache car il n'est pas inclus dans `payload.messages` qui est ce qui est réellement envoyé à l'API.\n")
            f.write("- Le cache Gemini/DeepSeek compare uniquement les messages dans le payload (role + content), pas les métadonnées externes.\n\n")
        
        return output_path


def find_latest_payloads(logs_dir: str, pattern: str = "payload_*.json", limit: int = 2) -> List[str]:
    """Trouve les N derniers fichiers payload dans le répertoire logs."""
    logs_path = Path(logs_dir)
    if not logs_path.exists():
        return []
    
    payload_files = sorted(
        logs_path.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    return [str(p) for p in payload_files[:limit]]


def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Analyse les cassures de cache entre deux payloads'
    )
    parser.add_argument(
        'payload1',
        nargs='?',
        help='Chemin vers le premier payload JSON'
    )
    parser.add_argument(
        'payload2',
        nargs='?',
        help='Chemin vers le deuxième payload JSON'
    )
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Compare automatiquement les 2 derniers payloads trouvés dans logs/'
    )
    parser.add_argument(
        '--output',
        help='Chemin de sortie pour le rapport (par défaut: logs/payload_cache_analysis_TIMESTAMP.md)'
    )
    
    args = parser.parse_args()
    
    if args.auto:
        logs_dir = get_path("logs")
        payloads = find_latest_payloads(logs_dir)
        if len(payloads) < 2:
            print(f"[ERROR] Moins de 2 payloads trouves dans {logs_dir}")
            sys.exit(1)
        payload1_path = payloads[0]  # Le plus récent
        payload2_path = payloads[1]  # L'avant-dernier
        print(f"[INFO] Comparaison automatique:")
        print(f"   Payload 1 (recent): {Path(payload1_path).name}")
        print(f"   Payload 2 (precedent): {Path(payload2_path).name}")
    elif args.payload1 and args.payload2:
        payload1_path = args.payload1
        payload2_path = args.payload2
    else:
        parser.print_help()
        sys.exit(1)
    
    # Vérifier que les fichiers existent
    if not os.path.exists(payload1_path):
        print(f"[ERROR] Fichier introuvable: {payload1_path}")
        sys.exit(1)
    if not os.path.exists(payload2_path):
        print(f"[ERROR] Fichier introuvable: {payload2_path}")
        sys.exit(1)
    
    # Analyser
    print("[INFO] Analyse en cours...")
    analyzer = PayloadCacheAnalyzer(payload1_path, payload2_path)
    analysis = analyzer.analyze()
    
    if not analysis.get('success'):
        print(f"[ERROR] Erreur: {analysis.get('error')}")
        sys.exit(1)
    
    # Générer le rapport
    print("[INFO] Generation du rapport...")
    report_path = analyzer.generate_report(analysis, args.output)
    
    # Afficher le résumé
    cache_impact = analysis['cache_impact']
    breaks = analysis['cache_breaks']
    
    print("\n" + "="*60)
    print("RESUME DE L'ANALYSE")
    print("="*60)
    
    if cache_impact['will_invalidate_cache']:
        print(f"[CRITICAL] INVALIDATION DE CACHE DETECTEE")
        print(f"   Raison: {cache_impact['reason']}")
    else:
        print(f"[OK] Pas de cassure de cache")
    
    print(f"\n[STATS] Statistiques:")
    print(f"   - Cassures critiques: {breaks['critical_count']}")
    print(f"   - Total cassures: {breaks['total_count']}")
    print(f"   - Messages systeme: {analysis['stats']['system_messages1']} -> {analysis['stats']['system_messages2']}")
    
    print(f"\n[INFO] Rapport genere: {report_path}")
    print("="*60)


if __name__ == '__main__':
    main()


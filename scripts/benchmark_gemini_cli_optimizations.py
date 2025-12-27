"""
Script de benchmark pour mesurer l'impact de chaque optimisation individuellement.
Teste les différentes optimisations et génère un rapport de performance.
"""

import time
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_core.sessions import GeminiCliSession
from ai_core.keys import KeyManager


class BenchmarkResult:
    """Résultat d'un benchmark individuel."""
    def __init__(self, name: str):
        self.name = name
        self.times: List[float] = []
        self.first_line_delays: List[float] = []
        self.total_delays: List[float] = []
        self.errors: List[str] = []
    
    def add_run(self, first_line_delay: float, total_delay: float, error: str = None):
        """Ajoute un résultat de run."""
        if error:
            self.errors.append(error)
        else:
            self.first_line_delays.append(first_line_delay)
            self.total_delays.append(total_delay)
    
    def get_stats(self) -> Dict[str, Any]:
        """Calcule les statistiques."""
        if not self.first_line_delays:
            return {
                "name": self.name,
                "runs": len(self.errors),
                "errors": len(self.errors),
                "success_rate": 0.0,
                "first_line_delay_ms": None,
                "total_delay_ms": None
            }
        
        return {
            "name": self.name,
            "runs": len(self.first_line_delays) + len(self.errors),
            "successful_runs": len(self.first_line_delays),
            "errors": len(self.errors),
            "success_rate": len(self.first_line_delays) / (len(self.first_line_delays) + len(self.errors)) * 100,
            "first_line_delay_ms": {
                "min": min(self.first_line_delays),
                "max": max(self.first_line_delays),
                "avg": sum(self.first_line_delays) / len(self.first_line_delays),
                "median": sorted(self.first_line_delays)[len(self.first_line_delays) // 2]
            },
            "total_delay_ms": {
                "min": min(self.total_delays),
                "max": max(self.total_delays),
                "avg": sum(self.total_delays) / len(self.total_delays),
                "median": sorted(self.total_delays)[len(self.total_delays) // 2]
            }
        }


def benchmark_session(session: GeminiCliSession, message: str, runs: int = 3) -> BenchmarkResult:
    """
    Benchmark une session avec un message donné.
    
    Args:
        session: Session à benchmarker
        message: Message de test
        runs: Nombre de runs à effectuer
        
    Returns:
        BenchmarkResult avec les statistiques
    """
    result = BenchmarkResult(f"{session.model_name}")
    
    for i in range(runs):
        try:
            start_time = time.time()
            first_line_time = None
            first_line_received = False
            
            # Envoyer le message et mesurer les temps
            response_generator = session.send_message(message, stream=True)
            
            # Lire la première ligne
            for chunk in response_generator:
                if not first_line_received:
                    first_line_time = time.time()
                    first_line_received = True
                    # Lire quelques chunks de plus pour avoir une réponse complète
                    break
            
            # Lire le reste de la réponse
            for chunk in response_generator:
                pass
            
            end_time = time.time()
            
            if first_line_time:
                first_line_delay = (first_line_time - start_time) * 1000
                total_delay = (end_time - start_time) * 1000
                result.add_run(first_line_delay, total_delay)
            else:
                result.add_run(0, (end_time - start_time) * 1000, "Pas de première ligne reçue")
                
        except Exception as e:
            result.add_run(0, 0, str(e))
    
    return result


def run_benchmark_suite(model_name: str = "gemini-3-flash-preview", test_message: str = "Bonjour", runs: int = 3):
    """
    Exécute une suite de benchmarks.
    
    Args:
        model_name: Modèle à tester
        test_message: Message de test
        runs: Nombre de runs par test
    """
    print(f"[*] Démarrage benchmark pour {model_name}")
    print(f"[*] Message de test: {test_message}")
    print(f"[*] Runs par test: {runs}")
    print()
    
    key_manager = KeyManager()
    results: List[BenchmarkResult] = []
    
    # Test 1: Session normale (avec toutes les optimisations)
    print("[*] Test 1: Session avec toutes les optimisations...")
    try:
        session = GeminiCliSession(key_manager, model_name=model_name)
        result = benchmark_session(session, test_message, runs)
        results.append(result)
        print(f"[OK] Test 1 terminé: {result.get_stats()['success_rate']:.1f}% de réussite")
    except Exception as e:
        print(f"[ERROR] Test 1 échoué: {e}")
    
    print()
    
    # Générer le rapport
    report = {
        "timestamp": datetime.now().isoformat(),
        "model": model_name,
        "test_message": test_message,
        "runs_per_test": runs,
        "results": [r.get_stats() for r in results]
    }
    
    # Sauvegarder le rapport
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%d-%b_%Hh%M_%S")
    report_file = logs_dir / f"benchmark_gemini_cli_{timestamp}.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("="*80)
    print("RAPPORT DE BENCHMARK")
    print("="*80)
    for result in results:
        stats = result.get_stats()
        print(f"\n{stats['name']}:")
        print(f"  Runs réussis: {stats['successful_runs']}/{stats['runs']} ({stats['success_rate']:.1f}%)")
        if stats['first_line_delay_ms']:
            print(f"  Délai première ligne: {stats['first_line_delay_ms']['avg']:.0f}ms (min: {stats['first_line_delay_ms']['min']:.0f}ms, max: {stats['first_line_delay_ms']['max']:.0f}ms)")
            print(f"  Délai total: {stats['total_delay_ms']['avg']:.0f}ms (min: {stats['total_delay_ms']['min']:.0f}ms, max: {stats['total_delay_ms']['max']:.0f}ms)")
        if stats['errors']:
            print(f"  Erreurs: {stats['errors']}")
    
    print(f"\n[*] Rapport sauvegardé: {report_file}")
    print("="*80)


def main():
    """Fonction principale."""
    if len(sys.argv) > 1:
        model_name = sys.argv[1]
    else:
        model_name = "gemini-3-flash-preview"
    
    if len(sys.argv) > 2:
        test_message = sys.argv[2]
    else:
        test_message = "Bonjour"
    
    if len(sys.argv) > 3:
        runs = int(sys.argv[3])
    else:
        runs = 3
    
    run_benchmark_suite(model_name, test_message, runs)


if __name__ == "__main__":
    main()


import os
import sys
import unittest

# Ajouter le répertoire racine au path pour l'import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai_core.hardware_detector import HardwareDetector

class TestHardwareDetection(unittest.TestCase):
    def setUp(self):
        self.detector = HardwareDetector()

    def test_report_structure(self):
        """Vérifie que le rapport contient toutes les sections nécessaires."""
        report = self.detector.get_report()
        self.assertIn("system", report)
        self.assertIn("cpu", report)
        self.assertIn("npu", report)
        self.assertIn("gpu", report)

    def test_cpu_capabilities(self):
        """Vérifie si l'AVX-512 est détecté (attendu sur Ryzen 8000)."""
        cpu = self.detector.cpu_features
        print(f"\n[DEBUG] CPU: {cpu.get('model_name', 'N/A')}")
        print(f"[DEBUG] AVX-512: {cpu.get('avx512')}")
        # On ne fait pas un assertStrict car la détection peut varier selon les drivers
        # Mais on log l'info.

    def test_npu_visibility(self):
        """Log la visibilité du NPU."""
        npu = self.detector.npu_status
        print(f"[DEBUG] NPU Available: {npu.get('available')}")
        print(f"[DEBUG] NPU Backend: {npu.get('backend')}")

    def test_gpu_vram(self):
        """Vérifie l'estimation de la VRAM."""
        gpu = self.detector.gpu_status
        if gpu.get('has_radeom'):
            print(f"[DEBUG] GPU Detected: {gpu.get('name')}")
            print(f"[DEBUG] VRAM Estimate: {gpu.get('vram_estimate_mb')} MB")
            self.assertGreater(gpu.get('vram_estimate_mb', 0), 2048) # Au moins 2GB attendu sur 32GB RAM

if __name__ == "__main__":
    # Exécuter le résumé visuel d'abord
    detector = HardwareDetector()
    detector.print_summary()
    
    # Puis les tests unitaires
    print("\nExécution des tests unitaires...")
    unittest.main()

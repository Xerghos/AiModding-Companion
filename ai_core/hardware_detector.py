import os
import sys
import platform
import logging
import subprocess
import json
import shutil
import winreg
from typing import Dict, Any, Optional

import psutil

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HardwareDetector:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HardwareDetector, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.system_info = self._get_system_info()
        self.cpu_features = self._detect_cpu_features()
        self.providers = self._get_onnx_providers()
        self.npu_status = self._detect_npu()
        self.gpu_status = self._detect_gpu()
        self._initialized = True

    def _get_system_info(self) -> Dict[str, str]:
        return {
            "os": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version
        }

    def _get_registry_value(self, key_path, value_name):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                return value
        except Exception:
            return None

    def _get_onnx_providers(self):
        try:
            import onnxruntime as ort
            return ort.get_available_providers()
        except ImportError:
            return []

    def _detect_cpu_features(self) -> Dict[str, Any]:
        features = {
            "avx512": False,
            "architecture": "Unknown",
            "model_name": "Unknown",
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True)
        }

        cpu_name = self._get_registry_value(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString")
        if cpu_name:
            features["model_name"] = cpu_name.strip()
            if any(k in cpu_name for k in ["8845HS", "8645HS", "7840HS", "7940HS", "Zen 4", "Ryzen 8000"]):
                features["avx512"] = True
                features["architecture"] = "Zen 4 (Hawk Point/Phoenix)"
        return features

    def _detect_npu(self) -> Dict[str, Any]:
        status = {"available": False, "backend": "None"}
        if 'VitisAIExecutionProvider' in self.providers:
            status["available"] = True
            status["backend"] = "VitisAIExecutionProvider"
        return status

    def _detect_gpu(self) -> Dict[str, Any]:
        status = {
            "has_vulkan": False,
            "has_radeon": True, # On sait qu'il y a un Radeon 780M
            "vram_estimate_mb": 0,
            "name": "AMD Radeon 780M (Hawk Point iGPU)",
            "dml_available": 'DmlExecutionProvider' in self.providers
        }

        # Estimation RAM (48% de la RAM totale)
        mem = psutil.virtual_memory()
        status["vram_estimate_mb"] = int((mem.total * 0.48) / (1024**2))

        if shutil.which("vulkaninfo") or os.path.exists(r"C:\Windows\System32\vulkan-1.dll"):
            status["has_vulkan"] = True
        
        return status

    def get_report(self) -> Dict[str, Any]:
        return {
            "system": self.system_info,
            "cpu": self.cpu_features,
            "npu": self.npu_status,
            "gpu": self.gpu_status,
            "onnx_providers": self.providers
        }

    def print_summary(self):
        print("\n=== RAPPORT DÉTECTION MATÉRIELLE (V3 - Hawk Point) ===")
        print(f"OS: {self.system_info['os']} {self.system_info['release']}")
        
        cpu = self.cpu_features
        print(f"\n[CPU] {cpu.get('model_name', 'Unknown')}")
        print(f"  - Architecture: {cpu['architecture']}")
        print(f"  - AVX-512 Supporté: {'✅ OUI (Double-Pumped)' if cpu['avx512'] else '❌ NON'}")
        
        npu = self.npu_status
        print(f"\n[NPU] Ryzen AI")
        if npu['available']:
            print(f"  - Statut: ✅ OPÉRATIONNEL ({npu['backend']})")
        else:
            print(f"  - Statut: ⚠️ INDISPONIBLE (Drivers IPU/NPU manquants)")

        gpu = self.gpu_status
        print(f"\n[GPU] iGPU Radeon 780M")
        print(f"  - DirectML (DML): {'✅ PRÊT (Indexation GPU possible)' if gpu['dml_available'] else '❌ NON'}")
        print(f"  - VRAM Estimée: ~{gpu['vram_estimate_mb']} MB (Shared)")
        print(f"  - Vulkan: {'✅ Disponible' if gpu['has_vulkan'] else '⚠️ DLL Manquante'}")
        print("======================================================\n")

if __name__ == "__main__":
    detector = HardwareDetector()
    detector.print_summary()

#!/usr/bin/env python3
"""
Détecteur matériel V3 - Optimisé pour Ryzen AI Hawk Point
Utilise l'environnement conda 'ryzen-ai-1.6.1' pour détection NPU/iGPU
"""

import os
import sys
import platform
import logging
import subprocess
import json
import shutil
import winreg
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RyzenAIDetector:
    """Détecteur spécialisé pour Ryzen AI Hawk Point avec support multi-environnement"""
    
    def __init__(self):
        self.system_info = self._get_system_info()
        self.cpu_features = self._detect_cpu_features()
        self.ryzen_env_status = self._check_ryzen_ai_env()
        self.providers = self._get_onnx_providers()
        self.npu_status = self._detect_npu()
        self.gpu_status = self._detect_gpu()
        self.memory_status = self._analyze_memory()
        
    def _get_system_info(self) -> Dict[str, str]:
        """Récupère les informations système"""
        return {
            "os": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version
        }
    
    def _get_registry_value(self, key_path: str, value_name: str) -> Optional[str]:
        """Lit une valeur du registre Windows"""
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                return value
        except Exception:
            return None
    
    def _detect_cpu_features(self) -> Dict[str, Any]:
        """Détecte les caractéristiques CPU"""
        features = {
            "avx512": False,
            "architecture": "Unknown",
            "model_name": "Unknown",
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "is_ryzen_hawk_point": False
        }
        
        # Lecture du nom du processeur depuis le registre
        cpu_name = self._get_registry_value(
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", 
            "ProcessorNameString"
        )
        
        if cpu_name:
            cpu_name = cpu_name.strip()
            features["model_name"] = cpu_name
            
            # Détection Ryzen Hawk Point (8845HS, 8645HS, etc.)
            if any(k in cpu_name for k in ["8845HS", "8645HS", "7840HS", "7940HS", "Zen 4", "Ryzen 8000"]):
                features["avx512"] = True
                features["architecture"] = "Zen 4 (Hawk Point/Phoenix)"
                features["is_ryzen_hawk_point"] = True
        
        return features
    
    def _check_ryzen_ai_env(self) -> Dict[str, Any]:
        """Vérifie si l'environnement Ryzen AI est disponible"""
        status = {
            "available": False,
            "path": None,
            "conda_envs": [],
            "active_env": None,
            "conda_found": False
        }
        
        # Chercher conda dans les chemins courants
        conda_paths = [
            "C:\\ProgramData\\Anaconda3\\Scripts\\conda.exe",
            "C:\\ProgramData\\Anaconda3\\condabin\\conda.bat",
            "C:\\Users\\Xerghos\\Anaconda3\\Scripts\\conda.exe",
            "C:\\Users\\Xerghos\\miniconda3\\Scripts\\conda.exe",
            "C:\\ProgramData\\Miniconda3\\Scripts\\conda.exe",
            "conda.exe"  # Dans PATH
        ]
        
        conda_exe = None
        for path in conda_paths:
            if os.path.exists(path):
                conda_exe = path
                status["conda_found"] = True
                break
        
        if not conda_exe:
            # Essayer de trouver conda via where
            try:
                result = subprocess.run(
                    ["where", "conda"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    conda_exe = result.stdout.strip().split('\n')[0]
                    status["conda_found"] = True
            except Exception:
                pass
        
        if not conda_exe:
            logger.warning("Conda non trouve dans les chemins standards")
            return status
        
        try:
            # Liste des environnements conda
            result = subprocess.run(
                [conda_exe, "info", "--envs", "--json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                envs = data.get("envs", [])
                status["conda_envs"] = envs
                
                # Chercher ryzen-ai-1.6.1
                for env_path in envs:
                    if "ryzen-ai-1.6.1" in env_path:
                        status["available"] = True
                        status["path"] = env_path
                        break
                
                # Environnement actif
                status["active_env"] = data.get("active_prefix")
        
        except Exception as e:
            logger.warning(f"Erreur verification environnement Conda: {e}")
        
        return status
    
    def _run_in_ryzen_env(self, python_code: str) -> tuple[bool, str, str]:
        """Exécute du code Python dans l'environnement Ryzen AI"""
        if not self.ryzen_env_status["available"]:
            return False, "", "Environnement Ryzen AI non disponible"
        
        try:
            # Créer un script temporaire
            temp_script = Path("temp_ryzen_check.py")
            temp_script.write_text(python_code)
            
            # Exécuter dans l'environnement Ryzen AI
            cmd = f'conda run -n ryzen-ai-1.6.1 python "{temp_script}"'
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            # Nettoyer
            temp_script.unlink(missing_ok=True)
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except Exception as e:
            return False, "", str(e)
    
    def _get_onnx_providers(self) -> List[str]:
        """Récupère les providers ONNX Runtime depuis l'environnement Ryzen AI"""
        python_code = '''
import sys
try:
    import onnxruntime as ort
    providers = ort.get_available_providers()
    print("|".join(providers))
except Exception as e:
    print(f"ERROR:{e}")
    sys.exit(1)
'''
        
        success, stdout, stderr = self._run_in_ryzen_env(python_code)
        
        if success and stdout and "|" in stdout:
            return stdout.strip().split("|")
        else:
            logger.warning(f"Impossible de récupérer les providers ONNX: {stderr}")
            return []
    
    def _detect_npu(self) -> Dict[str, Any]:
        """Détecte le NPU Ryzen AI"""
        status = {
            "available": False,
            "backend": "None",
            "env_ready": self.ryzen_env_status["available"],
            "cache_path": None
        }
        
        # Vérifier si VitisAIExecutionProvider est disponible
        if 'VitisAIExecutionProvider' in self.providers:
            status["available"] = True
            status["backend"] = "VitisAIExecutionProvider"
            
            # Configurer le cache NPU
            cache_path = Path("C:/ProgramData/RyzenAI/Cache")
            try:
                cache_path.mkdir(parents=True, exist_ok=True)
                status["cache_path"] = str(cache_path)
            except Exception as e:
                logger.warning(f"Impossible de créer le cache NPU: {e}")
        
        return status
    
    def _detect_gpu(self) -> Dict[str, Any]:
        """Détecte l'iGPU Radeon 780M"""
        status = {
            "has_vulkan": False,
            "has_radeon": True,  # On sait qu'il y a un Radeon 780M
            "vram_estimate_mb": 0,
            "name": "AMD Radeon 780M (Hawk Point iGPU)",
            "dml_available": 'DmlExecutionProvider' in self.providers,
            "rdna3": True
        }
        
        # Estimation VRAM (48% de la RAM totale pour iGPU)
        mem = psutil.virtual_memory()
        status["vram_estimate_mb"] = int((mem.total * 0.48) / (1024**2))
        
        # Vérifier Vulkan
        if shutil.which("vulkaninfo") or os.path.exists(r"C:\Windows\System32\vulkan-1.dll"):
            status["has_vulkan"] = True
        
        return status
    
    def _analyze_memory(self) -> Dict[str, Any]:
        """Analyse la mémoire pour l'indexation"""
        mem = psutil.virtual_memory()
        
        # Allocation mémoire optimale pour l'indexation
        total_gb = mem.total / (1024**3)
        
        # Recommandations basées sur la RAM totale
        if total_gb >= 32:
            recommendations = {
                "npu_batch_size": 64,
                "gpu_batch_size": 128,
                "cpu_batch_size": 32,
                "max_files_per_batch": 1000,
                "memory_profile": "high_performance"
            }
        elif total_gb >= 16:
            recommendations = {
                "npu_batch_size": 32,
                "gpu_batch_size": 64,
                "cpu_batch_size": 16,
                "max_files_per_batch": 500,
                "memory_profile": "balanced"
            }
        else:
            recommendations = {
                "npu_batch_size": 16,
                "gpu_batch_size": 32,
                "cpu_batch_size": 8,
                "max_files_per_batch": 200,
                "memory_profile": "conservative"
            }
        
        return {
            "total_gb": round(total_gb, 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "percent_used": mem.percent,
            "recommendations": recommendations
        }
    
    def get_report(self) -> Dict[str, Any]:
        """Retourne un rapport complet"""
        return {
            "system": self.system_info,
            "cpu": self.cpu_features,
            "ryzen_env": self.ryzen_env_status,
            "npu": self.npu_status,
            "gpu": self.gpu_status,
            "memory": self.memory_status,
            "onnx_providers": self.providers,
            "recommended_backend": self._recommend_backend()
        }
    
    def _recommend_backend(self) -> str:
        """Recommande le backend optimal basé sur la détection"""
        if self.npu_status["available"] and self.npu_status["env_ready"]:
            return "npu_vitisai"
        elif self.gpu_status["dml_available"]:
            return "gpu_directml"
        elif self.cpu_features["avx512"]:
            return "cpu_avx512"
        else:
            return "cpu_fallback"
    
    def print_summary(self):
        """Affiche un résumé formaté"""
        print("\n=== RAPPORT DETECTION MATERIELLE V3 (Ryzen AI Hawk Point) ===")
        print(f"OS: {self.system_info['os']} {self.system_info['release']}")
        
        # CPU
        cpu = self.cpu_features
        print(f"\n[CPU] {cpu.get('model_name', 'Unknown')}")
        print(f"  - Architecture: {cpu['architecture']}")
        print(f"  - AVX-512: {'OUI (Double-Pumped)' if cpu['avx512'] else 'NON'}")
        print(f"  - Cores: {cpu['physical_cores']}P/{cpu['logical_cores']}L")
        
        # Environnement Ryzen AI
        env = self.ryzen_env_status
        print(f"\n[ENVIRONNEMENT] Ryzen AI 1.6.1")
        print(f"  - Disponible: {'OUI' if env['available'] else 'NON'}")
        if env['available']:
            print(f"  - Chemin: {env['path']}")
        
        # NPU
        npu = self.npu_status
        print(f"\n[NPU] Ryzen AI XDNA")
        if npu['available']:
            print(f"  - Statut: OPERATIONNEL ({npu['backend']})")
            if npu['cache_path']:
                print(f"  - Cache: {npu['cache_path']}")
        else:
            print(f"  - Statut: INDISPONIBLE")
        
        # GPU
        gpu = self.gpu_status
        print(f"\n[GPU] iGPU Radeon 780M")
        print(f"  - DirectML (DML): {'PRET' if gpu['dml_available'] else 'NON'}")
        print(f"  - VRAM Estimee: ~{gpu['vram_estimate_mb']} MB (Shared)")
        print(f"  - Vulkan: {'Disponible' if gpu['has_vulkan'] else 'DLL Manquante'}")
        print(f"  - RDNA 3: {'OUI' if gpu['rdna3'] else 'NON'}")
        
        # Mémoire
        mem = self.memory_status
        print(f"\n[MEMOIRE] {mem['total_gb']} GB Total")
        print(f"  - Disponible: {mem['available_gb']} GB")
        print(f"  - Profil: {mem['recommendations']['memory_profile']}")
        
        # Recommandation
        backend = self._recommend_backend()
        print(f"\n[RECOMMANDATION] Backend optimal: {backend.upper()}")
        
        print("============================================================\n")


if __name__ == "__main__":
    detector = RyzenAIDetector()
    detector.print_summary()
    
    # Sauvegarder le rapport
    report = detector.get_report()
    with open("hardware_report_v3.json", "w") as f:
        json.dump(report, f, indent=2)
    print("Rapport sauvegarde dans hardware_report_v3.json")
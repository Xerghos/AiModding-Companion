#!/usr/bin/env python3
"""
Routeur intelligent pour décision de backend optimal
Basé sur la détection matérielle et la charge de travail
"""

import os
import time
import logging
import psutil
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BackendDecision(Enum):
    """Décision de backend"""
    NPU_VITISAI = "npu_vitisai"      # NPU pour indexation chirurgicale
    GPU_DIRECTML = "gpu_directml"    # iGPU pour indexation massive
    CPU_AVX512 = "cpu_avx512"        # CPU optimisé pour fallback
    CPU_FALLBACK = "cpu_fallback"    # CPU standard

@dataclass
class WorkloadMetrics:
    """Métriques de charge de travail"""
    file_count: int = 0
    total_size_mb: float = 0
    avg_file_size_kb: float = 0
    estimated_tokens: int = 0
    memory_pressure: float = 0  # 0-1, pression mémoire
    
    @classmethod
    def from_file_list(cls, file_paths: list) -> 'WorkloadMetrics':
        """Calcule les métriques à partir d'une liste de fichiers"""
        total_size = 0
        for file_path in file_paths:
            try:
                total_size += os.path.getsize(file_path)
            except:
                continue
        
        file_count = len(file_paths)
        avg_size = total_size / max(file_count, 1) / 1024  # KB
        
        # Estimation tokens (approximative: 1 token ≈ 4 caractères)
        estimated_tokens = int(total_size / 4)
        
        # Pression mémoire
        mem = psutil.virtual_memory()
        memory_pressure = 1.0 - (mem.available / mem.total)
        
        return cls(
            file_count=file_count,
            total_size_mb=total_size / (1024**2),
            avg_file_size_kb=avg_size,
            estimated_tokens=estimated_tokens,
            memory_pressure=memory_pressure
        )

class HardwareRouter:
    """Routeur intelligent pour décision de backend"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HardwareRouter, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Import dynamique pour éviter les dépendances circulaires
        try:
            from .hardware_detector_v3 import RyzenAIDetector
            self.detector = RyzenAIDetector()
            self.hardware_report = self.detector.get_report()
        except ImportError:
            # Fallback si le détecteur n'est pas disponible
            self.detector = None
            self.hardware_report = {
                "npu": {"available": False},
                "gpu": {"dml_available": False},
                "cpu": {"avx512": False},
                "memory": {"total_gb": 0}
            }
        
        self.last_decision = None
        self.decision_history = []
        
        self._initialized = True
        logger.info("Hardware Router initialise")
    
    def decide_backend(self, workload: WorkloadMetrics) -> BackendDecision:
        """Prend la décision de backend optimale"""
        
        # Règles de décision (priorité décroissante)
        
        # 1. Si NPU disponible ET charge légère → NPU
        if (self.hardware_report["npu"]["available"] and 
            workload.file_count <= 100 and
            workload.memory_pressure < 0.7):
            decision = BackendDecision.NPU_VITISAI
            reason = "NPU optimal pour indexation chirurgicale"
        
        # 2. Si iGPU disponible ET charge lourde → GPU
        elif (self.hardware_report["gpu"]["dml_available"] and
              workload.file_count > 100 and
              workload.memory_pressure < 0.8):
            decision = BackendDecision.GPU_DIRECTML
            reason = "iGPU optimal pour indexation massive"
        
        # 3. Si CPU AVX-512 disponible → CPU optimisé
        elif self.hardware_report["cpu"]["avx512"]:
            decision = BackendDecision.CPU_AVX512
            reason = "CPU AVX-512 pour fallback optimise"
        
        # 4. Fallback CPU standard
        else:
            decision = BackendDecision.CPU_FALLBACK
            reason = "Fallback CPU standard"
        
        # Enregistrer la décision
        self.last_decision = {
            "decision": decision.value,
            "reason": reason,
            "workload": {
                "file_count": workload.file_count,
                "total_size_mb": workload.total_size_mb,
                "memory_pressure": workload.memory_pressure
            },
            "timestamp": time.time()
        }
        self.decision_history.append(self.last_decision)
        
        logger.info(f"Decision backend: {decision.value} - {reason}")
        return decision
    
    def get_backend_config(self, decision: BackendDecision) -> Dict[str, Any]:
        """Retourne la configuration pour le backend décidé"""
        
        configs = {
            BackendDecision.NPU_VITISAI: {
                "backend": "npu_vitisai",
                "batch_size": 64,
                "model": "nomic-embed-text-v1.5-int8",
                "use_cache": True,
                "static_shape": True,
                "providers": ["VitisAIExecutionProvider", "CPUExecutionProvider"],
                "optimizations": {
                    "graph_caching": True,
                    "parallel_execution": True,
                    "quantization": "int8"
                }
            },
            BackendDecision.GPU_DIRECTML: {
                "backend": "gpu_directml",
                "batch_size": 128,
                "model": "all-MiniLM-L6-v2",
                "use_cache": True,
                "providers": ["DmlExecutionProvider", "CPUExecutionProvider"],
                "optimizations": {
                    "memory_efficient": True,
                    "mixed_precision": True
                }
            },
            BackendDecision.CPU_AVX512: {
                "backend": "cpu_avx512",
                "batch_size": 32,
                "model": "all-MiniLM-L6-v2",
                "use_cache": True,
                "providers": ["CPUExecutionProvider"],
                "optimizations": {
                    "avx512": True,
                    "parallel": True,
                    "quantization": "int8"
                }
            },
            BackendDecision.CPU_FALLBACK: {
                "backend": "cpu_fallback",
                "batch_size": 16,
                "model": "all-MiniLM-L6-v2",
                "use_cache": False,
                "providers": ["CPUExecutionProvider"],
                "optimizations": {}
            }
        }
        
        return configs[decision]
    
    def get_recommendation_summary(self) -> Dict[str, Any]:
        """Retourne un résumé des recommandations"""
        return {
            "hardware_detected": {
                "npu_available": self.hardware_report["npu"]["available"],
                "gpu_available": self.hardware_report["gpu"]["dml_available"],
                "cpu_avx512": self.hardware_report["cpu"]["avx512"],
                "memory_gb": self.hardware_report["memory"]["total_gb"]
            },
            "last_decision": self.last_decision,
            "decision_count": len(self.decision_history),
            "optimal_scenarios": {
                "npu": "Indexation chirurgicale (<100 fichiers, basse pression memoire)",
                "gpu": "Indexation massive (>100 fichiers, moyenne pression memoire)",
                "cpu_avx512": "Fallback haute performance",
                "cpu_fallback": "Fallback standard"
            }
        }
    
    def print_decision_tree(self):
        """Affiche l'arbre de décision"""
        print("\n=== ARBRE DE DECISION BACKEND ===")
        print(f"Hardware detecte:")
        print(f"  - NPU: {'DISPONIBLE' if self.hardware_report['npu']['available'] else 'INDISPONIBLE'}")
        print(f"  - iGPU: {'DISPONIBLE' if self.hardware_report['gpu']['dml_available'] else 'INDISPONIBLE'}")
        print(f"  - CPU AVX-512: {'OUI' if self.hardware_report['cpu']['avx512'] else 'NON'}")
        print(f"  - Memoire: {self.hardware_report['memory']['total_gb']} GB")
        
        print("\nRegles de decision:")
        print("  1. NPU si: fichiers <= 100 ET pression memoire < 70%")
        print("  2. iGPU si: fichiers > 100 ET pression memoire < 80%")
        print("  3. CPU AVX-512 si disponible")
        print("  4. CPU fallback sinon")
        
        if self.last_decision:
            print(f"\nDerniere decision: {self.last_decision['decision']}")
            print(f"Raison: {self.last_decision['reason']}")
        
        print("==================================\n")


# Singleton global
_hardware_router = None

def get_hardware_router() -> HardwareRouter:
    """Retourne l'instance singleton du Hardware Router"""
    global _hardware_router
    if _hardware_router is None:
        _hardware_router = HardwareRouter()
    return _hardware_router


if __name__ == "__main__":
    # Test du Hardware Router
    print("=== TEST HARDWARE ROUTER ===")
    
    router = get_hardware_router()
    router.print_decision_tree()
    
    # Test avec différentes charges de travail
    test_workloads = [
        ("Legere", WorkloadMetrics(file_count=50, total_size_mb=10, memory_pressure=0.3)),
        ("Moyenne", WorkloadMetrics(file_count=200, total_size_mb=100, memory_pressure=0.5)),
        ("Lourde", WorkloadMetrics(file_count=1000, total_size_mb=500, memory_pressure=0.9)),
    ]
    
    for name, workload in test_workloads:
        decision = router.decide_backend(workload)
        config = router.get_backend_config(decision)
        
        print(f"\nCharge {name}:")
        print(f"  - Fichiers: {workload.file_count}")
        print(f"  - Taille: {workload.total_size_mb:.1f} MB")
        print(f"  - Pression memoire: {workload.memory_pressure:.1%}")
        print(f"  -> Decision: {decision.value}")
        print(f"  -> Batch size: {config['batch_size']}")
    
    # Resume
    summary = router.get_recommendation_summary()
    print(f"\nTotal decisions: {summary['decision_count']}")
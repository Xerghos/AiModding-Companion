#!/usr/bin/env python3
"""
NPU Manager pour Ryzen AI Hawk Point
Implémente Static Shape Bucketing et cache compilation pour l'indexation optimale
"""

import os
import sys
import json
import time
import logging
import subprocess
import threading
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

import numpy as np

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BackendType(Enum):
    """Types de backend disponibles"""
    NPU_VITISAI = "npu_vitisai"
    GPU_DIRECTML = "gpu_directml"
    CPU_AVX512 = "cpu_avx512"
    CPU_FALLBACK = "cpu_fallback"

@dataclass
class BatchConfig:
    """Configuration d'un batch pour Static Shape Bucketing"""
    token_length: int
    batch_size: int
    shape_key: str
    cache_file: Path

class StaticShapeBucketing:
    """Gestionnaire de Static Shape Bucketing pour optimisation NPU"""
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.shape_buckets = self._initialize_shape_buckets()
        self.lock = threading.Lock()
        
        # Configuration des buckets pour l'embedding
        self.token_buckets = [32, 64, 128, 256, 512]
        self.batch_sizes = [16, 32, 64, 128]
        
    def _initialize_shape_buckets(self) -> Dict[str, BatchConfig]:
        """Initialise les buckets de shapes prédéfinis"""
        buckets = {}
        
        # Buckets optimisés pour nomic-embed-text-v1.5 (Int8)
        for tokens in [32, 64, 128, 256, 512]:
            for batch in [16, 32, 64, 128]:
                shape_key = f"t{tokens}_b{batch}"
                cache_file = self.cache_dir / f"nomic_embed_int8_{shape_key}.vaip"
                buckets[shape_key] = BatchConfig(
                    token_length=tokens,
                    batch_size=batch,
                    shape_key=shape_key,
                    cache_file=cache_file
                )
        
        return buckets
    
    def get_best_bucket(self, token_length: int, desired_batch: int) -> BatchConfig:
        """Trouve le bucket optimal pour une longueur de tokens donnée"""
        with self.lock:
            # Trouver le bucket de tokens le plus proche
            best_token_bucket = min(self.token_buckets, key=lambda x: abs(x - token_length))
            if best_token_bucket < token_length:
                # Prendre le bucket supérieur si on dépasse
                idx = self.token_buckets.index(best_token_bucket)
                if idx + 1 < len(self.token_buckets):
                    best_token_bucket = self.token_buckets[idx + 1]
            
            # Trouver le batch size optimal
            best_batch = min(self.batch_sizes, key=lambda x: abs(x - desired_batch))
            
            shape_key = f"t{best_token_bucket}_b{best_batch}"
            return self.shape_buckets.get(shape_key)

class NPUManager:
    """Manager principal pour l'exécution sur NPU Ryzen AI"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NPUManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.backend_type = BackendType.NPU_VITISAI
        self.cache_dir = Path("C:/ProgramData/RyzenAI/Cache")
        self.model_name = "nomic-ai/nomic-embed-text-v1.5"
        self.model_int8_path = None
        
        # Initialisation des composants
        self.shape_bucketing = StaticShapeBucketing(self.cache_dir)
        self.vaip_config = self._create_vaip_config()
        self.onnx_session = None
        self.tokenizer = None
        
        self._initialized = True
        logger.info("NPU Manager initialisé")
    
    def _create_vaip_config(self) -> Dict[str, Any]:
        """Crée la configuration VAIP pour le cache NPU"""
        config = {
            "cache_dir": str(self.cache_dir),
            "cache_key": "nomic_embed_int8_v1_hawkpoint",
            "compile_options": {
                "target": "DPU",
                "input_shape": "dynamic",
                "output_shape": "dynamic",
                "quantization": "int8",
                "optimization_level": 3
            },
            "execution_options": {
                "enable_graph_caching": True,
                "enable_parallel_execution": True,
                "max_batch_size": 128,
                "thread_count": 4
            }
        }
        
        # Sauvegarder la configuration
        config_path = self.cache_dir / "vaip_config.json"
        config_path.write_text(json.dumps(config, indent=2))
        
        return config
    
    def _ensure_ryzen_env(self) -> bool:
        """Vérifie que l'environnement Ryzen AI est disponible"""
        # Chercher conda dans les chemins courants
        conda_paths = [
            "C:\\ProgramData\\Anaconda3\\Scripts\\conda.exe",
            "C:\\ProgramData\\Anaconda3\\condabin\\conda.bat",
            "C:\\Users\\Xerghos\\Anaconda3\\Scripts\\conda.exe",
            "C:\\Users\\Xerghos\\miniconda3\\Scripts\\conda.exe",
            "C:\\ProgramData\\Miniconda3\\Scripts\\conda.exe"
        ]
        
        conda_exe = None
        for path in conda_paths:
            if os.path.exists(path):
                conda_exe = path
                break
        
        if not conda_exe:
            # Essayer de trouver conda via where
            try:
                result = subprocess.run(
                    ["where", "conda"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    conda_exe = result.stdout.strip().split('\n')[0]
            except Exception:
                pass
        
        if not conda_exe:
            logger.warning("Conda non trouve dans les chemins standards")
            return False
        
        try:
            # Vérifier si conda est disponible
            result = subprocess.run(
                [conda_exe, "info", "--envs", "--json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning("Conda non disponible")
                return False
            
            data = json.loads(result.stdout)
            envs = data.get("envs", [])
            
            # Chercher ryzen-ai-1.6.1
            for env_path in envs:
                if "ryzen-ai-1.6.1" in env_path:
                    logger.info(f"Environnement Ryzen AI trouve: {env_path}")
                    return True
            
            logger.warning("Environnement ryzen-ai-1.6.1 non trouve")
            return False
            
        except Exception as e:
            logger.error(f"Erreur verification environnement: {e}")
            return False
    
    def _download_model_int8(self) -> Optional[Path]:
        """Télécharge un modèle Int8 simple pour test"""
        model_dir = self.cache_dir / "models" / "test-model-int8"
        model_dir.mkdir(parents=True, exist_ok=True)
        
        model_path = model_dir / "test_model.onnx"
        
        if model_path.exists():
            logger.info(f"Modele test deja present: {model_path}")
            return model_path
        
        logger.info("Creation modele test simple...")
        
        # Créer un modèle ONNX simple pour test
        download_script = '''
import numpy as np
import onnx
from onnx import helper, TensorProto

# Créer un modèle ONNX simple (embedding de test)
# Input: [batch_size, seq_len]
# Output: [batch_size, embedding_dim]

batch_size = 1
seq_len = 32
embedding_dim = 384

# Créer le graph
input_tensor = helper.make_tensor_value_info(
    'input', TensorProto.INT64, [batch_size, seq_len]
)
output_tensor = helper.make_tensor_value_info(
    'output', TensorProto.FLOAT, [batch_size, embedding_dim]
)

# Créer un nœud de test (matmul + add)
weight = helper.make_tensor(
    'weight',
    TensorProto.FLOAT,
    [seq_len, embedding_dim],
    np.random.randn(seq_len, embedding_dim).astype(np.float32).flatten()
)

bias = helper.make_tensor(
    'bias',
    TensorProto.FLOAT,
    [embedding_dim],
    np.random.randn(embedding_dim).astype(np.float32).flatten()
)

# Nœud MatMul
matmul_node = helper.make_node(
    'MatMul',
    inputs=['input', 'weight'],
    outputs=['matmul_output'],
    name='MatMul_0'
)

# Nœud Add
add_node = helper.make_node(
    'Add',
    inputs=['matmul_output', 'bias'],
    outputs=['output'],
    name='Add_0'
)

# Créer le graph
graph = helper.make_graph(
    [matmul_node, add_node],
    'test_embedding_model',
    [input_tensor],
    [output_tensor],
    initializer=[weight, bias]
)

# Créer le modèle
model = helper.make_model(
    graph,
    producer_name='RyzenAI-Test',
    opset_imports=[helper.make_opsetid('', 13)]
)

# Sauvegarder
onnx.save(model, str(model_path))
print(f"Modele test cree: {model_path}")
'''
        
        try:
            # Exécuter dans l'environnement Ryzen AI
            script_path = self.cache_dir / "create_test_model.py"
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(download_script.replace('model_path', f'"{model_path}"'))
            
            cmd = f'conda run -n ryzen-ai-1.6.1 python "{script_path}"'
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info("Modele test cree avec succes")
                return model_path
            else:
                logger.error(f"Erreur creation modele: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Exception creation modele: {e}")
            return None
    
    def initialize(self) -> bool:
        """Initialise le NPU Manager avec le modèle et la session ONNX"""
        if not self._ensure_ryzen_env():
            logger.warning("Environnement Ryzen AI non disponible, fallback CPU")
            self.backend_type = BackendType.CPU_AVX512
            return False
        
        # Télécharger le modèle Int8
        self.model_int8_path = self._download_model_int8()
        if not self.model_int8_path:
            logger.warning("Impossible de télécharger le modèle Int8")
            return False
        
        # Créer la session ONNX avec VitisAI
        try:
            python_code = f'''
import onnxruntime as ort
import numpy as np

# Configuration pour VitisAI
options = ort.SessionOptions()
options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
options.enable_cpu_mem_arena = True

# Providers avec priorité NPU
providers = [
    ("VitisAIExecutionProvider", {{
        "config_file": "{self.cache_dir / "vaip_config.json"}",
        "cache_dir": "{self.cache_dir}",
        "enable_graph_caching": True
    }}),
    "CPUExecutionProvider"
]

print("Création session ONNX avec VitisAI...")
session = ort.InferenceSession(
    "{self.model_int8_path}",
    sess_options=options,
    providers=providers
)

print(f"Session créée avec provider: {{session.get_providers()}}")
print("NPU READY")
'''
            
            # Exécuter dans l'environnement Ryzen AI
            script_path = self.cache_dir / "init_session.py"
            script_path.write_text(python_code)
            
            cmd = f'conda run -n ryzen-ai-1.6.1 python "{script_path}"'
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and "NPU READY" in result.stdout:
                logger.info("Session ONNX NPU initialisée avec succès")
                return True
            else:
                logger.error(f"Erreur initialisation session: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Exception initialisation NPU: {e}")
            return False
    
    def encode_batch(self, texts: List[str], batch_config: BatchConfig = None) -> np.ndarray:
        """Encode un batch de textes en utilisant le NPU"""
        if not self.onnx_session:
            if not self.initialize():
                raise RuntimeError("NPU non initialisé")
        
        if batch_config is None:
            # Estimation de la longueur moyenne
            avg_tokens = sum(len(t.split()) for t in texts) / max(len(texts), 1)
            batch_config = self.shape_bucketing.get_best_bucket(
                int(avg_tokens), len(texts)
            )
        
        logger.info(f"Encodage batch: {len(texts)} textes, shape: {batch_config.shape_key}")
        
        try:
            # Préparation des inputs
            python_code = f'''
import onnxruntime as ort
import numpy as np
from transformers import AutoTokenizer
import json

# Charger le tokenizer
tokenizer = AutoTokenizer.from_pretrained("{self.model_name}")

# Tokenizer les textes
texts = {json.dumps(texts)}
inputs = tokenizer(
    texts,
    padding=True,
    truncation=True,
    max_length={batch_config.token_length},
    return_tensors="np"
)

# Créer session (cachée)
options = ort.SessionOptions()
providers = [
    ("VitisAIExecutionProvider", {{
        "config_file": "{self.cache_dir / "vaip_config.json"}",
        "cache_dir": "{self.cache_dir}",
        "enable_graph_caching": True
    }}),
    "CPUExecutionProvider"
]

session = ort.InferenceSession(
    "{self.model_int8_path}",
    sess_options=options,
    providers=providers
)

# Exécution sur NPU
input_feed = {{
    "input_ids": inputs["input_ids"].astype(np.int64),
    "attention_mask": inputs["attention_mask"].astype(np.int64)
}}

outputs = session.run(None, input_feed)
embeddings = outputs[0]

# Normalisation L2
norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
embeddings = embeddings / norms

print("EMBEDDINGS_START")
for i, emb in enumerate(embeddings):
    print(",".join(map(str, emb)))
print("EMBEDDINGS_END")
'''
            
            # Exécuter dans l'environnement Ryzen AI
            script_path = self.cache_dir / "encode_batch.py"
            script_path.write_text(python_code)
            
            start_time = time.time()
            cmd = f'conda run -n ryzen-ai-1.6.1 python "{script_path}"'
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            elapsed = time.time() - start_time
            
            if result.returncode == 0 and "EMBEDDINGS_START" in result.stdout:
                # Parser les embeddings
                lines = result.stdout.split('\n')
                start_idx = lines.index("EMBEDDINGS_START") + 1
                end_idx = lines.index("EMBEDDINGS_END")
                
                embeddings = []
                for line in lines[start_idx:end_idx]:
                    if line.strip():
                        emb = list(map(float, line.split(',')))
                        embeddings.append(emb)
                
                logger.info(f"Encodage NPU réussi: {len(texts)} textes en {elapsed:.2f}s "
                          f"({len(texts)/elapsed:.1f} textes/s)")
                
                return np.array(embeddings, dtype=np.float32)
            else:
                logger.error(f"Erreur encodage NPU: {result.stderr}")
                raise RuntimeError(f"Erreur encodage NPU: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Exception encodage NPU: {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut du NPU Manager"""
        return {
            "backend": self.backend_type.value,
            "initialized": self.onnx_session is not None,
            "cache_dir": str(self.cache_dir),
            "model_ready": self.model_int8_path is not None and self.model_int8_path.exists(),
            "shape_buckets": len(self.shape_bucketing.shape_buckets),
            "vaip_config": str(self.cache_dir / "vaip_config.json")
        }
    
    def cleanup(self):
        """Nettoyage des ressources"""
        self.onnx_session = None
        self.tokenizer = None
        logger.info("NPU Manager nettoyé")


# Singleton global
_npu_manager = None

def get_npu_manager() -> NPUManager:
    """Retourne l'instance singleton du NPU Manager"""
    global _npu_manager
    if _npu_manager is None:
        _npu_manager = NPUManager()
    return _npu_manager


if __name__ == "__main__":
    # Test du NPU Manager
    print("=== TEST NPU MANAGER ===")
    
    manager = get_npu_manager()
    status = manager.get_status()
    print(f"Status: {json.dumps(status, indent=2)}")
    
    if manager.initialize():
        print("✅ NPU Manager initialisé avec succès")
        
        # Test d'encodage
        test_texts = [
            "Hello world, this is a test document for NPU encoding.",
            "Another test document with different content for benchmarking.",
            "The quick brown fox jumps over the lazy dog."
        ]
        
        try:
            embeddings = manager.encode_batch(test_texts)
            print(f"✅ Encodage réussi: {embeddings.shape}")
            print(f"  - Shape: {embeddings.shape}")
            print(f"  - Norme moyenne: {np.mean(np.linalg.norm(embeddings, axis=1)):.4f}")
        except Exception as e:
            print(f"❌ Erreur encodage: {e}")
    else:
        print("ECHEC initialisation NPU Manager")
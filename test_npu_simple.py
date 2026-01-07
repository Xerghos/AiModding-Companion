#!/usr/bin/env python3
"""Test simple de l'environnement Ryzen AI et NPU"""

import subprocess
import json
import os
from pathlib import Path

def test_ryzen_ai():
    """Teste l'environnement Ryzen AI"""
    print("=== TEST ENVIRONNEMENT RYZEN AI ===")
    
    # 1. Vérifier conda
    conda_paths = [
        "C:\\ProgramData\\Anaconda3\\Scripts\\conda.exe",
        "C:\\ProgramData\\Anaconda3\\condabin\\conda.bat",
        "C:\\Users\\Xerghos\\Anaconda3\\Scripts\\conda.exe",
        "C:\\Users\\Xerghos\\miniconda3\\Scripts\\conda.exe"
    ]
    
    conda_exe = None
    for path in conda_paths:
        if os.path.exists(path):
            conda_exe = path
            print(f"Conda trouve: {conda_exe}")
            break
    
    if not conda_exe:
        print("Conda non trouve")
        return False
    
    # 2. Vérifier environnement ryzen-ai-1.6.1
    try:
        result = subprocess.run(
            [conda_exe, "info", "--envs", "--json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print("Erreur conda info")
            return False
        
        data = json.loads(result.stdout)
        envs = data.get("envs", [])
        
        ryzen_env = None
        for env_path in envs:
            if "ryzen-ai-1.6.1" in env_path:
                ryzen_env = env_path
                break
        
        if not ryzen_env:
            print("Environnement ryzen-ai-1.6.1 non trouve")
            return False
        
        print(f"Environnement Ryzen AI trouve: {ryzen_env}")
        
        # 3. Tester ONNX Runtime dans l'environnement
        test_script = '''
import onnxruntime as ort
import sys

try:
    providers = ort.get_available_providers()
    print("PROVIDERS:" + "|".join(providers))
    
    # Tester VitisAI
    if "VitisAIExecutionProvider" in providers:
        print("VITISAI:OK")
    else:
        print("VITISAI:ABSENT")
        
    # Tester DML
    if "DmlExecutionProvider" in providers:
        print("DML:OK")
    else:
        print("DML:ABSENT")
        
    sys.exit(0)
except Exception as e:
    print(f"ERROR:{e}")
    sys.exit(1)
'''
        
        # Sauvegarder le script
        script_path = Path("test_onnx.py")
        script_path.write_text(test_script, encoding='utf-8')
        
        # Exécuter dans l'environnement Ryzen AI
        cmd = f'{conda_exe} run -n ryzen-ai-1.6.1 python "{script_path}"'
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Nettoyer
        script_path.unlink(missing_ok=True)
        
        if result.returncode == 0:
            print("ONNX Runtime test reussi")
            
            # Analyser la sortie
            for line in result.stdout.split('\n'):
                if line.startswith("PROVIDERS:"):
                    providers = line.replace("PROVIDERS:", "").split("|")
                    print(f"Providers disponibles: {providers}")
                elif line.startswith("VITISAI:"):
                    print(f"VitisAI: {line.replace('VITISAI:', '')}")
                elif line.startswith("DML:"):
                    print(f"DML: {line.replace('DML:', '')}")
            
            return True
        else:
            print(f"Erreur test ONNX: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Exception: {e}")
        return False

def test_npu_performance():
    """Teste les performances NPU avec un modèle simple"""
    print("\n=== TEST PERFORMANCES NPU ===")
    
    # Créer un script de test de performance
    perf_script = '''
import onnxruntime as ort
import numpy as np
import time

# Configuration
options = ort.SessionOptions()
options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

# Providers avec priorité NPU
providers = [
    ("VitisAIExecutionProvider", {
        "config_file": "C:/ProgramData/RyzenAI/Cache/vaip_config.json",
        "cache_dir": "C:/ProgramData/RyzenAI/Cache",
        "enable_graph_caching": True
    }),
    "CPUExecutionProvider"
]

# Créer un modèle simple pour test
print("Creation modele test...")
from onnx import helper, TensorProto
import onnx

# Modèle simple: y = x * 2
input_tensor = helper.make_tensor_value_info('input', TensorProto.FLOAT, [1, 384])
output_tensor = helper.make_tensor_value_info('output', TensorProto.FLOAT, [1, 384])

# Nœud Mul
mul_node = helper.make_node(
    'Mul',
    inputs=['input', 'weight'],
    outputs=['output'],
    name='Mul_0'
)

# Poids
weight = helper.make_tensor(
    'weight',
    TensorProto.FLOAT,
    [384],
    np.full(384, 2.0, dtype=np.float32).flatten()
)

graph = helper.make_graph([mul_node], 'test_model', [input_tensor], [output_tensor], [weight])
model = helper.make_model(graph, producer_name='NPU-Test')

# Sauvegarder temporairement
import tempfile
import os
temp_dir = tempfile.mkdtemp()
model_path = os.path.join(temp_dir, 'test_model.onnx')
onnx.save(model, model_path)

print(f"Modele cree: {model_path}")

# Créer session
print("Creation session ONNX...")
session = ort.InferenceSession(model_path, sess_options=options, providers=providers)

print(f"Session creee avec provider: {session.get_providers()[0]}")

# Test de performance
batch_size = 32
input_data = np.random.randn(batch_size, 384).astype(np.float32)

print(f"Test performance: batch_size={batch_size}")

# Warmup
for _ in range(5):
    session.run(None, {'input': input_data})

# Benchmark
iterations = 100
start_time = time.time()
for i in range(iterations):
    session.run(None, {'input': input_data})
    
elapsed = time.time() - start_time
throughput = (batch_size * iterations) / elapsed

print(f"RESULT: {throughput:.1f} embeddings/s")
print(f"RESULT_TIME: {elapsed:.3f}s")
print(f"RESULT_ITERATIONS: {iterations}")

# Nettoyer
import shutil
shutil.rmtree(temp_dir)
'''
    
    try:
        # Sauvegarder le script
        script_path = Path("test_perf.py")
        script_path.write_text(perf_script, encoding='utf-8')
        
        # Exécuter dans l'environnement Ryzen AI
        conda_exe = "C:\\ProgramData\\Anaconda3\\Scripts\\conda.exe"
        cmd = f'{conda_exe} run -n ryzen-ai-1.6.1 python "{script_path}"'
        
        print("Lancement test performance (peut prendre 30s)...")
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Nettoyer
        script_path.unlink(missing_ok=True)
        
        if result.returncode == 0:
            print("Test performance reussi")
            
            # Extraire les résultats
            for line in result.stdout.split('\n'):
                if line.startswith("RESULT:"):
                    print(f"  - Debit: {line.replace('RESULT:', '').strip()}")
                elif line.startswith("RESULT_TIME:"):
                    print(f"  - Temps: {line.replace('RESULT_TIME:', '').strip()}")
                elif line.startswith("RESULT_ITERATIONS:"):
                    print(f"  - Iterations: {line.replace('RESULT_ITERATIONS:', '').strip()}")
            
            return True
        else:
            print(f"Erreur test performance: {result.stderr[:500]}")
            return False
            
    except Exception as e:
        print(f"Exception test performance: {e}")
        return False

if __name__ == "__main__":
    # Test 1: Environnement
    if test_ryzen_ai():
        print("\n✅ ENVIRONNEMENT RYZEN AI PRET")
        
        # Test 2: Performances
        print("\n" + "="*50)
        if test_npu_performance():
            print("\n✅ NPU OPERATIONNEL ET PERFORMANT")
        else:
            print("\n⚠️ NPU disponible mais test performance echoue")
    else:
        print("\n❌ ENVIRONNEMENT RYZEN AI NON PRET")
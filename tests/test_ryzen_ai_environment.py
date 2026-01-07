#!/usr/bin/env python3
"""
Test complet de l'environnement Ryzen AI 1.6.1
Valide que le NPU, l'iGPU et le CPU sont prêts pour l'indexation
"""

import sys
import os
import json
import subprocess
from pathlib import Path

def run_command(cmd):
    """Exécute une commande et retourne la sortie"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def test_environment():
    """Teste l'environnement Ryzen AI"""
    print("TEST ENVIRONNEMENT RYZEN AI 1.6.1")
    print("=" * 60)
    
    tests = []
    
    # 1. Test activation environnement
    print("\n1. Activation environnement 'ryzen-ai-1.6.1'...")
    success, out, err = run_command("conda activate ryzen-ai-1.6.1 && conda info --envs")
    if success and "ryzen-ai-1.6.1" in out:
        print(" Environnement activé")
        tests.append(("Environnement", True))
    else:
        print(f" Échec activation: {err}")
        tests.append(("Environnement", False))
        return tests
    
    # 2. Test ONNX Runtime avec Vitis AI
    print("\n2. Test ONNX Runtime avec Vitis AI...")
    test_code = """
import onnxruntime as ort
providers = ort.get_available_providers()
print("PROVIDERS:", providers)
print("VITIS_AI:", 'VitisAIExecutionProvider' in providers)
print("DML:", 'DmlExecutionProvider' in providers)
"""
    
    success, out, err = run_command(f'conda activate ryzen-ai-1.6.1 && python -c "{test_code}"')
    if success:
        print(f" ONNX Runtime chargé")
        if 'VitisAIExecutionProvider' in out:
            print("  - VitisAIExecutionProvider:  DISPONIBLE")
            tests.append(("NPU VitisAI", True))
        else:
            print("  - VitisAIExecutionProvider:  ABSENT")
            tests.append(("NPU VitisAI", False))
        
        if 'DmlExecutionProvider' in out:
            print("  - DmlExecutionProvider:  DISPONIBLE (iGPU)")
            tests.append(("iGPU DirectML", True))
        else:
            print("  - DmlExecutionProvider:  ABSENT")
            tests.append(("iGPU DirectML", False))
    else:
        print(f" Échec ONNX Runtime: {err}")
        tests.append(("ONNX Runtime", False))
    
    # 3. Test CPU AVX-512
    print("\n3. Test CPU AVX-512...")
    test_code = """
import platform
import psutil
import winreg

def get_cpu_name():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0")
        name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        return name.strip()
    except:
        return platform.processor()

cpu_name = get_cpu_name()
print("CPU:", cpu_name)
print("AVX512_SUPPORT:", "8845HS" in cpu_name or "Zen 4" in cpu_name or "Ryzen 8000" in cpu_name)
"""
    
    success, out, err = run_command(f'python -c "{test_code}"')
    if success:
        if "AVX512_SUPPORT: True" in out:
            print(" CPU AVX-512 supporté")
            tests.append(("CPU AVX-512", True))
        else:
            print(" CPU sans AVX-512 détecté")
            tests.append(("CPU AVX-512", False))
    else:
        print(f" Échec détection CPU: {err}")
        tests.append(("CPU Détection", False))
    
    # 4. Test mémoire disponible
    print("\n4. Test mémoire système...")
    test_code = """
import psutil
mem = psutil.virtual_memory()
total_gb = mem.total / (1024**3)
available_gb = mem.available / (1024**3)
print(f"TOTAL_GB: {total_gb:.1f}")
print(f"AVAILABLE_GB: {available_gb:.1f}")
print(f"VRAM_ESTIMATE_GB: {(mem.total * 0.48) / (1024**3):.1f}")
"""
    
    success, out, err = run_command(f'python -c "{test_code}"')
    if success:
        lines = out.split('\n')
        for line in lines:
            if line.startswith("TOTAL_GB:"):
                total = float(line.split(":")[1].strip())
                print(f" Mémoire totale: {total:.1f} GB")
                tests.append(("Mémoire", total >= 16))
            elif line.startswith("VRAM_ESTIMATE_GB:"):
                vram = float(line.split(":")[1].strip())
                print(f" VRAM estimée: {vram:.1f} GB (partagée)")
    
    # 5. Test cache NPU
    print("\n5. Test cache NPU...")
    cache_path = Path("C:/ProgramData/RyzenAI/Cache")
    if cache_path.exists():
        print(f" Cache NPU trouvé: {cache_path}")
        tests.append(("Cache NPU", True))
    else:
        print(f"  Cache NPU absent, création...")
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
            print(f" Cache NPU créé: {cache_path}")
            tests.append(("Cache NPU", True))
        except Exception as e:
            print(f" Échec création cache: {e}")
            tests.append(("Cache NPU", False))
    
    return tests

def main():
    """Fonction principale"""
    print("VALIDATION ENVIRONNEMENT RYZEN AI HAWK POINT")
    print("=" * 60)
    
    tests = test_environment()
    
    # Résumé
    print("\n" + "=" * 60)
    print(" RÉSUMUM DES TESTS")
    print("=" * 60)
    
    passed = 0
    total = len(tests)
    
    for name, result in tests:
        status = "PASS" if result else "FAIL"
        print(f"{status} {name}")
        if result:
            passed += 1
    
    print(f"\n Score: {passed}/{total} tests réussis")
    
    if passed == total:
        print("\nENVIRONNEMENT PRET POUR L'INDEXATION NPU/iGPU !")
        print("\nProchaines etapes:")
        print("1. Creer vaip_config.json pour le cache NPU")
        print("2. Telecharger modele nomic-embed-text-v1.5 (Int8)")
        print("3. Implementer NPU Manager avec Static Shape Bucketing")
        return 0
    elif passed >= total - 1:
        print("\n  Environnement presque prêt, quelques ajustements nécessaires")
        return 1
    else:
        print("\n Environnement nécessite des corrections importantes")
        return 2

if __name__ == "__main__":
    sys.exit(main())
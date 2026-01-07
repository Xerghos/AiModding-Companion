#!/usr/bin/env python3
"""Test simple d'ONNX Runtime dans l'environnement Ryzen AI"""

import sys

try:
    import onnxruntime as ort
    print("ONNX Runtime version:", ort.__version__)
    
    providers = ort.get_available_providers()
    print("Providers disponibles:")
    for p in providers:
        print(f"  - {p}")
        
    # Vérifier spécifiquement VitisAI et DML
    has_vitisai = "VitisAIExecutionProvider" in providers
    has_dml = "DmlExecutionProvider" in providers
    
    print(f"\nVitisAIExecutionProvider: {'PRESENT' if has_vitisai else 'ABSENT'}")
    print(f"DmlExecutionProvider: {'PRESENT' if has_dml else 'ABSENT'}")
    
except Exception as e:
    print(f"Erreur: {e}")
    sys.exit(1)
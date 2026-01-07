# Plan Atomique d'Optimisation Matérielle Hétérogène

## Contexte
Basé sur le plan GPU/NPU/CPU existant, ce plan implémente une architecture intelligente exploitant les trois composants matériels du Ryzen 7 8845HS:
- CPU Zen 4 avec AVX-512
- iGPU RDNA 3 avec Vulkan
- NPU XDNA avec ONNX Runtime

## Objectifs
1. Router automatiquement les tâches vers le silicium le plus adapté
2. Optimiser l'indexation massive sur iGPU
3. Utiliser le NPU pour l'indexation chirurgicale et l'analyse temps réel
4. Maintenir un fallback robuste sur CPU

## Architecture

### Décision de Routage
```
if file_count > 100 and has_vulkan_gpu() and vram_available():
    backend = "vulkan_batch"
elif has_npu() and file_count <= 100:
    backend = "npu_static"
else:
    backend = "cpu_avx512"
```

### Composants

#### 1. Détection Matérielle (ai_core/hardware_detector.py)
- Détection NPU via VitisAIExecutionProvider
- Détection GPU Vulkan via llama.cpp
- Vérification AVX-512
- Monitoring VRAM iGPU

#### 2. Routeur Intelligent (ai_core/hardware_router.py)
- Logique de décision basée sur charge et capacités
- Estimation temps d'exécution
- Fallback automatique

#### 3. Backend NPU (ai_core/npu_backend.py)
- Modèle nomic-embed-text-v1.5 quantifié INT8
- Static Shape Bucketing (128, 256, 512 tokens)
- Cache de compilation persistant
- Configuration vaip_config.json

#### 4. Backend GPU Vulkan (ai_core/vulkan_backend.py)
- Intégration llama.cpp serveur
- Paramètres optimaux -ub 512 pour RDNA 3
- Monitoring VRAM partagée
- Batching adaptatif

#### 5. Optimisation CPU (features/context/database.py)
- Recompilation sqlite-vec avec /arch:AVX512
- Optimisation PyTorch AVX-512
- Quantification INT8 améliorée

#### 6. Micro-modèle NPU (ai_core/npu_micro_model.py)
- Modèle léger SmolLM2-135M
- Analyse code temps réel
- Détection contexte
- Consommation < 2W

#### 7. Pipeline Zero-Copy (ai_core/shared_pipeline.py)
- Shared memory multiprocessing
- Élimination copies mémoire
- Intégration directe avec sqlite-vec

#### 8. Configuration (config/hardware_settings.py)
- Paramètres matériels
- Seuils de décision
- Options de fallback

## Plan d'Exécution

### Phase 1: Fondations (Semaine 1)
1. Créer hardware_detector.py
2. Créer hardware_router.py
3. Optimiser database.py pour AVX-512
4. Tests unitaires de base

### Phase 2: NPU (Semaine 2)
1. Créer npu_backend.py
2. Implémenter Static Shape Bucketing
3. Créer npu_micro_model.py
4. Tests NPU avec fallback

### Phase 3: GPU Vulkan (Semaine 3)
1. Créer vulkan_backend.py
2. Intégrer llama.cpp serveur
3. Implémenter monitoring VRAM
4. Tests performance GPU

### Phase 4: Intégration (Semaine 4)
1. Créer shared_pipeline.py
2. Intégrer tous les backends
3. Tests end-to-end
4. Benchmarks comparatifs

## Dépendances
- onnxruntime avec VitisAIExecutionProvider
- llama-cpp-python avec support Vulkan
- cpuinfo, psutil
- Drivers AMD Ryzen AI à jour

## Métriques de Succès
- Réduction temps d'indexation > 50%
- Utilisation NPU pour tâches légères
- Fallback robuste sans crash
- Monitoring VRAM efficace

## Risques et Atténuation
- Driver NPU instable → Fallback CPU
- VRAM limitée → Ajustement batch size
- Compatibilité Windows → Tests sur Win10/11
- Performance → Benchmarks réguliers
# PLAN MAÎTRE FUSIONNÉ : Architecture "Ryzen AI Omniscient" (SOTA 2026)

## 1. Vision & Objectifs Stratégiques

### 1.1 Vision Globale
Transformer AiModding-Companion en une application IA locale "State-of-the-Art" optimisée pour l'architecture **AMD "Hawk Point" (Ryzen 7 PRO 8845HS / 32GB RAM)**. L'objectif est d'atteindre une **latence zéro** et une **confidentialité totale** en exploitant intelligemment les 3 coprocesseurs, avec une spécialisation stricte pour éviter les goulots d'étranglement mémoire (RAM partagée).

### 1.2 Architecture Hétérogène "Hawk Point"
Le Ryzen 7 PRO 8845HS offre un **potentiel théorique de 38 TOPS** (Tera Operations Per Second) réparti entre :

- **NPU (XDNA, 16 TOPS)** : "Always-on" Intelligence. Embeddings RAG, classification rapide, et surveillance contextuelle basse consommation.
- **iGPU (Radeon 780M, 12 TFLOPS)** : "Heavy Lifting". Génération de tokens (LLM) et raisonnement visuel (VLM) via Vulkan/ROCm.
- **CPU (Zen 4, 8 cœurs/16 threads, 5.1 GHz)** : Orchestration, I/O, pré-traitement (tokenization), et logique métier complexe.

### 1.3 Paradigme de l'Omniscience Décentralisée
L'application doit évoluer d'une simple interface de chat vers un **système multi-agents coordonné** avec une boucle cognitive complète :

**Percevoir (Vision/Audio) → Mémoriser (Embedding) → Raisonner (SLM) → Agir (Function Calling)**

## 2. Architecture Technique Unifiée

### 2.1 Décision de Routage Matériel Intelligent
```
if file_count > 100 and has_vulkan_gpu() and vram_available():
    backend = "vulkan_batch"  # iGPU pour indexation massive
elif has_npu() and file_count <= 100:
    backend = "npu_static"    # NPU pour indexation chirurgicale
else:
    backend = "cpu_avx512"    # CPU avec AVX-512 optimisé
```

### 2.2 Stack Logicielle Optimisée

#### A. Génération (LLM) : `llama-cpp-python` + Vulkan
- Backend Vulkan mature pour RDNA 3
- Format GGUF avec quantification Q4_K_M
- Paramètres optimaux : `-ng 99`, `-b 512`, `-ub 512` pour RDNA 3

#### B. Embeddings & NPU : `onnxruntime` + VitisAIExecutionProvider
- Modèles Int8 quantifiés via AMD Quark
- Configuration `vaip_config.json` pour désactiver vectorisation
- Cache `.xmodel` pour éviter recompilation
- Static Shape Bucketing (128, 256, 512 tokens)

#### C. Base Vectorielle : `SQLite-vec` AVX-512
- Recompilation avec `/arch:AVX512` pour Zen 4
- Support Matryoshka (stockage dimensions tronquées)
- Recherche cosine similarity optimisée

### 2.3 Modèles Sélectionnés (SOTA 2026)

#### Embeddings (NPU) :
- **Principal** : `nomic-embed-text-v1.5` (137M, Int8, MTEB 62.3)
- **Français** : `intfloat/multilingual-e5-small` (118M, Int8, SOTA français)
- **Premium** : `qwen3-embedding-0.6b` (600M, Int8, MTEB 70.58)

#### SLM (iGPU) :
- **Cerveau** : `Qwen 3 vl 7B Instruct` (GGUF Q4_K_M, 10-15 tok/s)
- **Vitesse** : `Llama 3.2 3B Instruct` (GGUF Q4_K_M, 30-40 tok/s)
- **Code** : `Qwen2.5-Coder-7B-Instruct` (GGUF Q4_K_M, SOTA code)
- **Raisonnement** : `DeepSeek-R1-Distill-Qwen-1.5B` (Chain-of-Thought natif)

#### Vision (iGPU) :
- **Heavy** : `Qwen3-VL-8B` (OCR, résolution dynamique)
- **Light** : `Moondream2` (latence < 1s)

## 3. Roadmap d'Implémentation Détaillée

### Phase 1 : Socle Hardware & Détection [PRIORITÉ ABSOLUE]

#### 1.1 Setup Environnement Système
- [ ] **Pré-requis Système** :
    - [ ] Vérifier Windows 11 24H2 (critique pour mises à jour NPU)
    - [ ] Installer AMD Adrenalin 25.12.1+ et Ryzen AI Software 1.2+
    - [ ] Vérifier activation "IPU Control" dans BIOS
    - [ ] Installer Vulkan SDK

- [ ] **Scripts d'Installation** :
    - [ ] Créer `scripts/setup_ryzen_ai.ps1` pour installer dépendances
    - [ ] Créer `scripts/check_ryzen_drivers.py` : Script diagnostic complet

#### 1.2 Détection Matérielle Unifiée
- [ ] **Créer `ai_core/hardware_detector.py`** :
    - [ ] Détection NPU via VitisAIExecutionProvider
    - [ ] Détection GPU Vulkan via llama.cpp
    - [ ] Vérification AVX-512 via cpuinfo
    - [ ] Monitoring VRAM iGPU partagée

#### 1.3 Preuves de Concept
- [ ] **Tests NPU** :
    - [ ] Créer `tests/test_npu_hello_world.py`
    - [ ] Valider instantiation VitisAIExecutionProvider
    - [ ] Test inférence simple avec modèle test

- [ ] **Tests iGPU Vulkan** :
    - [ ] Créer `tests/bench_igpu_vulkan.py`
    - [ ] Mesure tokens/sec avec Qwen2.5-7B-GGUF
    - [ ] Validation déchargement complet (`n_gpu_layers=-1`)

### Phase 2 : Pipeline RAG & Embeddings NPU

#### 2.1 Acquisition Modèles
- [ ] **Script Téléchargement** :
    - [ ] Étendre `scripts/download_models.py` pour récupérer modèles sélectionnés
    - [ ] Vérification intégrité fichiers (checksums)
    - [ ] Gestion cache local

#### 2.2 Core Implementation NPU
- [ ] **NPU Manager** :
    - [ ] Créer `ai_core/hardware/npu_manager.py` :
        - Classe Singleton pour gestion chargement/déchargement
        - Gestion session ONNX avec VitisAIExecutionProvider
        - Static Shape Bucketing (128, 256, 512 tokens)
        - Cache compilation `.xmodel`
        - Fallback automatique CPU

- [ ] **Vector Store** :
    - [ ] Implémenter `features/rag/vector_store_sqlite.py` :
        - Wrapper autour de `sqlite-vec` recompilé AVX-512
        - Support Matryoshka (stockage 256 dim, génération 768 dim)
        - Recherche cosine similarity optimisée

#### 2.3 Routeur Matériel Intelligent
- [ ] **Créer `ai_core/hardware_router.py`** :
    - [ ] Logique décision basée charge et capacités
    - [ ] Estimation temps d'exécution par backend
    - [ ] Fallback automatique en cascade

### Phase 3 : Moteur Génératif Hybride

#### 3.1 GPU Manager
- [ ] **Créer `ai_core/hardware/gpu_manager.py`** :
    - [ ] Wrapper autour de `llama_cpp.Llama`
    - [ ] Configuration automatique VRAM (cible < 12GB)
    - [ ] Support déchargement complet (`n_gpu_layers=-1`)
    - [ ] Monitoring tokens/sec et consommation VRAM
    - [ ] Paramètres optimaux `-ub 512` pour RDNA 3

#### 3.2 Hybrid Router
- [ ] **Implémenter `ai_core/orchestration/hybrid_router.py`** :
    - [ ] Classification automatique type tâche
    - [ ] Sélection modèle basée complexité
    - [ ] Détection fonction calling nécessaire
    - [ ] Gestion file d'attente et priorisation

#### 3.3 Optimisation CPU AVX-512
- [ ] **Modifier `features/context/database.py`** :
    - [ ] Intégration sqlite-vec recompilé AVX-512
    - [ ] Optimisation PyTorch pour AVX-512
    - [ ] Quantification INT8 améliorée

### Phase 4 : Fonctionnalités "Omniscient"

#### 4.1 Contexte Actif
- [ ] **File Watcher** :
    - [ ] Implémenter `features/context/file_watcher.py`
    - [ ] Surveillance fichiers modifiés (debounced)
    - [ ] Déclenchement indexation NPU en arrière-plan

- [ ] **Context Vision** :
    - [ ] Implémenter `ai_core/hardware/context_vision.py`
    - [ ] Capture état écran/IDE via `mss`
    - [ ] Analyse par modèle Vision
    - [ ] Détection erreurs terminal/UI

#### 4.2 Micro-modèle NPU "Always-On"
- [ ] **Créer `ai_core/npu_micro_model.py`** :
    - [ ] Modèle léger SmolLM2-135M quantifié Int8
    - [ ] Analyse code en temps réel
    - [ ] Détection changement contexte IDE
    - [ ] Consommation < 2W

#### 4.3 Pipeline "Zero-Copy"
- [ ] **Créer `ai_core/shared_pipeline.py`** :
    - [ ] `multiprocessing.shared_memory` pour tampon circulaire
    - [ ] Écriture directe embeddings depuis NPU/GPU
    - [ ] Lecture directe par sqlite-vec

#### 4.4 Observabilité & Monitoring
- [ ] **Hardware Monitor UI** :
    - [ ] Ajouter widget "Hardware Monitor" dans barre d'état
    - [ ] Indicateurs NPU, iGPU VRAM, Tokens/s
    - [ ] Graphique historique performance

- [ ] **Configuration Centralisée** :
    - [ ] Créer `config/hardware_settings.py`
    - [ ] Paramètres matériels configurables
    - [ ] Seuils décision et options fallback

### Phase 5 : Fonctionnalités Avancées (Future)

#### 5.1 Interaction Audio
- [ ] **ASR (Moonshine)** : Intégration reconnaissance vocale
- [ ] **TTS (Piper)** : Intégration synthèse vocale

#### 5.2 Optimisations Avancées
- [ ] **Décodage Spéculatif** : Modèle spéculatif SmolLM2-135M
- [ ] **Adaptateurs LoRA Dynamiques** : Chargement selon tâche
- [ ] **Quantification Binaire** : Recherche ultra-rapide

## 4. TODOs d'Implémentation Prioritaire

### TODO 1 : Infrastructure de Détection Matérielle
- [ ] Créer `ai_core/hardware_detector.py` avec détection NPU/GPU/AVX-512
- [ ] Implémenter monitoring VRAM iGPU partagée
- [ ] Créer tests unitaires validation détection
- [ ] Intégrer avec système logging existant

### TODO 2 : NPU Manager avec Static Shape Bucketing
- [ ] Créer `ai_core/hardware/npu_manager.py` (Singleton)
- [ ] Implémenter Static Shape Bucketing (128, 256, 512 tokens)
- [ ] Configuration `vaip_config.json` pour désactiver vectorisation
- [ ] Cache compilation `.xmodel` et préchauffage
- [ ] Fallback robuste vers CPU AVX-512

### TODO 3 : Routeur Intelligent et GPU Manager
- [ ] Créer `ai_core/hardware_router.py` avec logique décision
- [ ] Implémenter `ai_core/hardware/gpu_manager.py` wrapper llama.cpp
- [ ] Configuration paramètres optimaux `-ub 512` pour RDNA 3
- [ ] Monitoring performance temps réel
- [ ] Intégration avec factory existante

## 5. Performances Attendues

### Embedding (NPU) :
- Nomic-Embed-Text-v1.5 (Int8) : 30-50ms latence, ~0.5 Go mémoire
- Débit élevé pour indexation batch

### Génération (iGPU) :
- Qwen 2.5 7B : 10-15 tokens/seconde, ~5.5 Go mémoire
- Llama 3.2 3B : 30-40 tokens/seconde, ~2.5 Go mémoire

### Consommation Ressources :
- NPU : < 5W, always-on
- iGPU : 15-30W selon modèle
- Mémoire totale : 16-32 Go (dans limites 32 Go)

## 6. Notes Techniques Critiques

### Pré-requis Système :
- Windows 11 24H2 **CRITIQUE** pour NPU
- Drivers AMD Adrenalin 25.12.1+ et Ryzen AI Software 1.2+
- BIOS avec "IPU Control" activé

### Optimisations :
- **Matryoshka** : Toujours activer (768→256 dim = réduction DB 3x)
- **Quantification** : Q4_K_M pour SLM, Int8 pour NPU
- **Cache** : Mettre en cache modèles fréquents, décharger inactifs

### Pièges Courants :
- Fallback CPU silencieux (vérifier logs)
- Préfixes embedding requis (multilingual-e5-small)
- VRAM saturation (surveiller, réduire contexte si nécessaire)
- Bande passante mémoire (LPDDR5x vs DDR5 impact performance)

## 7. Métriques de Succès
- Réduction temps d'indexation > 50%
- Utilisation NPU pour tâches légères (>80%)
- Fallback robuste sans crash (100% disponibilité)
- Monitoring VRAM efficace (alertes précoces)
- Performance génération > 10 tokens/s (Qwen 7B)
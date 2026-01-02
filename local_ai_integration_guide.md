# Guide d'Intégration d'IA Locales pour AiModding-Companion

## 1. Architecture Actuelle de l'Application

### 1.1 Structure des Sessions IA
L'application utilise un système de factory (`SmartSessionFactory`) qui gère plusieurs types de sessions :
- **GeminiSession** : Sessions Google Gemini via API
- **DeepSeekSession** : Sessions DeepSeek avec support context caching
- **GroqSession** : Sessions Groq pour modèles Llama/Mixtral
- **LiteLLMSession** : Proxy universel via LiteLLM
- **GeminiCliSession** : Pont vers gemini-cli avec OAuth

### 1.2 Configuration Actuelle
- **Fournisseurs supportés** : Google Gemini, DeepSeek, Groq, OpenAI, Anthropic, Mistral, HuggingFace
- **Système de clés** : KeyManager centralisé avec gestion par keyring
- **Proxy LiteLLM** : Déjà implémenté pour l'orchestration multi-providers

## 2. Frameworks d'IA Locaux à Intégrer

### 2.1 Ollama
**Avantages** :
- Exécution locale sur macOS, Linux et Windows
- Support de nombreux modèles (Llama, Mistral, Gemma, etc.)
- API REST simple
- Gestion automatique des modèles

**Intégration Python** :
```python
import requests

class OllamaSession:
    def __init__(self, model_name="llama3.2:latest", base_url="http://localhost:11434"):
        self.base_url = base_url
        self.model = model_name
    
    def generate(self, prompt, stream=False):
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": stream
            }
        )
        return response.json()
```

### 2.2 Llama.cpp
**Avantages** :
- Performance optimisée en C++
- Support GGUF format (quantization)
- Faible empreinte mémoire
- Multi-platform (CPU/GPU)

**Intégration via Python bindings** :
```python
from llama_cpp import Llama

class LlamaCppSession:
    def __init__(self, model_path, n_ctx=2048):
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=4,
            n_gpu_layers=0  # 0 = CPU only
        )
    
    def generate(self, prompt):
        output = self.llm(
            prompt,
            max_tokens=512,
            temperature=0.7
        )
        return output["choices"][0]["text"]
```

### 2.3 Transformers (Hugging Face)
**Avantages** :
- Large bibliothèque de modèles
- Support PyTorch/TensorFlow
- Quantization avancée
- Fine-tuning facile

**Intégration** :
```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

class TransformersSession:
    def __init__(self, model_name="microsoft/phi-2"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto"
        )
    
    def generate(self, prompt):
        inputs = self.tokenizer(prompt, return_tensors="pt")
        outputs = self.model.generate(**inputs, max_length=512)
        return self.tokenizer.decode(outputs[0])
```

## 3. Modèles d'IA Locaux Recommandés

### 3.1 Modèles Légers (≤ 4GB)
- **Phi-3-mini** (3.8B) : Excellent rapport qualité/taille
- **Gemma-2B** : Google, bon pour le code
- **Qwen2.5-Coder-1.5B** : Spécialisé code
- **TinyLlama-1.1B** : Très léger, rapide

### 3.2 Modèles Moyens (4-8GB)
- **Llama-3.2-3B** : Bon équilibre
- **Mistral-7B** : Performances solides
- **Qwen2.5-7B** : Multilingue avancé
- **DeepSeek-Coder-6.7B** : Spécialisé programmation

### 3.3 Modèles Avancés (8GB+)
- **Llama-3.1-8B** : Très performant
- **Qwen2.5-14B** : Capacités étendues
- **Mixtral-8x7B** (MoE) : Expert mixture

## 4. Stratégie d'Intégration Technique

### 4.1 Extension de la Factory
```python
class LocalAISession:
    """Classe de base pour toutes les sessions IA locales"""
    
    def __init__(self, model_type, config):
        self.model_type = model_type
        self.config = config
        self.provider = self._detect_provider()
    
    def _detect_provider(self):
        # Détection automatique du provider
        if "ollama" in self.model_type:
            return "ollama"
        elif "llama.cpp" in self.model_type:
            return "llama_cpp"
        elif "transformers" in self.model_type:
            return "transformers"
        return "unknown"

class SmartSessionFactory:
    def create_local_session(self, model_type, local_config=None):
        """Crée une session IA locale"""
        # Vérifier si le modèle local est disponible
        if not self._check_local_model_available(model_type):
            raise ValueError(f"Modèle local {model_type} non disponible")
        
        # Créer la session appropriée
        if "ollama" in model_type:
            return OllamaLocalSession(model_type, local_config)
        elif "llama.cpp" in model_type:
            return LlamaCppLocalSession(model_type, local_config)
        elif "transformers" in model_type:
            return TransformersLocalSession(model_type, local_config)
```

### 4.2 Configuration dans settings.py
```json
"local_ai_engine": {
    "enabled": true,
    "default_provider": "ollama",
    "models": {
        "fast_local": "phi-3-mini:latest",
        "coder_local": "qwen2.5-coder-1.5b:latest",
        "smart_local": "llama3.2:3b",
        "reasoning_local": "mistral:7b"
    },
    "providers": {
        "ollama": {
            "base_url": "http://localhost:11434",
            "timeout": 30
        },
        "llama_cpp": {
            "models_dir": "./models/gguf",
            "n_threads": 4,
            "n_gpu_layers": 0
        },
        "transformers": {
            "cache_dir": "./models/huggingface",
            "device": "auto"
        }
    }
}
```

## 5. Optimisation des Performances

### 5.1 Quantization
- **GGUF format** : 4-bit, 5-bit, 8-bit quantization
- **GPTQ** : Quantization post-training pour GPU
- **AWQ** : Activation-aware quantization
- **BitsAndBytes** : 4/8-bit quantization pour transformers

### 5.2 Gestion Mémoire
```python
class MemoryOptimizedSession:
    def __init__(self, model_config):
        # Chargement progressif
        self.model = self._load_model_with_memory_optimization(model_config)
    
    def _load_model_with_memory_optimization(self, config):
        if config["quantization"] == "4bit":
            from transformers import BitsAndBytesConfig
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16
            )
            return AutoModelForCausalLM.from_pretrained(
                config["model_name"],
                quantization_config=quantization_config,
                device_map="auto"
            )
```

### 5.3 Cache et Batching
- **KV Cache** : Réutilisation du cache d'attention
- **Dynamic batching** : Regroupement des requêtes
- **Speculative decoding** : Génération plus rapide

## 6. Considérations de Sécurité et Confidentialité

### 6.1 Avantages des IA Locales
- **Données restent sur l'appareil** : Pas de transmission à des serveurs externes
- **Conformité RGPD** : Meilleur contrôle des données personnelles
- **Auditabilité** : Traçabilité complète des traitements
- **Indépendance** : Fonctionnement hors ligne possible

### 6.2 Meilleures Pratiques
1. **Isolation des modèles** : Exécution dans des conteneurs/sandbox
2. **Validation des entrées** : Protection contre les injections de prompt
3. **Monitoring des ressources** : Détection d'utilisation anormale
4. **Mises à jour de sécurité** : Maintenance régulière des modèles

## 7. Stratégie de Fallback Hybride

### 7.1 Architecture Hybride Cloud/Local
```python
class HybridAIManager:
    def __init__(self):
        self.local_available = self._check_local_availability()
        self.cloud_fallback = True
    
    def generate_response(self, prompt, use_local=True):
        if use_local and self.local_available:
            try:
                return self._local_generate(prompt)
            except Exception as e:
                if self.cloud_fallback:
                    return self._cloud_generate(prompt)
                raise e
        else:
            return self._cloud_generate(prompt)
```

### 7.2 Priorisation Intelligente
- **Tâches simples** → IA locale (rapide, confidentiel)
- **Tâches complexes** → IA cloud (puissante, coûteuse)
- **Données sensibles** → IA locale obligatoire
- **Traitement batch** → IA locale pour économie

## 8. MLOps pour IA Locales

### 8.1 Gestion des Modèles
- **Registry de modèles** : Catalogue des modèles disponibles localement
- **Versioning** : Gestion des versions de modèles
- **Mises à jour** : Mise à jour automatique des modèles

### 8.2 Monitoring
- **Performance** : Latence, précision, utilisation mémoire
- **Qualité** : Évaluation continue des réponses
- **Coûts** : Comparaison coût local vs cloud

### 8.3 Maintenance
- **Nettoyage cache** : Gestion automatique du cache
- **Rotation logs** : Conservation limitée des logs
- **Sauvegardes** : Backup des configurations

## 9. Dépendances à Ajouter

### 9.1 Requirements.txt
```txt
# IA Locales
ollama>=0.1.0
llama-cpp-python>=0.2.0
transformers>=4.40.0
torch>=2.0.0
accelerate>=0.27.0
bitsandbytes>=0.42.0

# Optimisation
optimum>=1.17.0
onnxruntime>=1.17.0

# Utilitaires
psutil>=5.9.0
pynvml>=11.5.0  # Monitoring GPU
```

### 9.2 Installation Ollama
```bash
# Windows (PowerShell)
winget install Ollama.Ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama
```

## 10. Roadmap d'Implémentation

### Phase 1 : Support Ollama (2-3 jours)
1. ✅ Créer `LocalAISession` base class
2. ✅ Implémenter `OllamaLocalSession`
3. ✅ Étendre `SmartSessionFactory`
4. ✅ Ajouter configuration dans settings.py
5. ✅ Tester avec phi-3-mini

### Phase 2 : Support Llama.cpp (3-4 jours)
1. ✅ Implémenter `LlamaCppLocalSession`
2. ✅ Gestion format GGUF
3. ✅ Optimisation mémoire
4. ✅ Support quantization

### Phase 3 : Support Transformers (4-5 jours)
1. ✅ Implémenter `TransformersLocalSession`
2. ✅ Gestion GPU/CPU
3. ✅ Support quantization 4/8-bit
4. ✅ Cache Hugging Face

### Phase 4 : Optimisation (2-3 jours)
1. ✅ Système de cache local
2. ✅ Fallback hybride
3. ✅ Monitoring performances
4. ✅ Documentation utilisateur

## 11. Métriques de Succès

### 11.1 Performance
- **Latence** : < 2s pour les réponses simples
- **Utilisation mémoire** : < 4GB pour les modèles légers
- **Disponibilité** : 99% uptime local

### 11.2 Qualité
- **Précision** : Comparable aux modèles cloud pour les tâches courantes
- **Cohérence** : Réponses stables et prévisibles
- **Utilité** : Valeur ajoutée mesurable

### 11.3 Coûts
- **Économie** : Réduction > 50% des coûts cloud
- **ROI** : Retour sur investissement < 6 mois
- **Maintenance** : Coûts opérationnels < 20% du budget

## 12. Risques et Atténuation

### 12.1 Risques Techniques
- **Compatibilité** : Tester sur différentes configurations
- **Performance** : Benchmarks avant déploiement
- **Stabilité** : Monitoring intensif initial

### 12.2 Risques Opérationnels
- **Formation** : Documentation complète pour les utilisateurs
- **Support** : Plan de support dédié
- **Évolution** : Roadmap de mise à jour claire

## 13. Conclusion

L'intégration d'IA locales dans AiModding-Companion offre :
- **Confidentialité améliorée** : Données restent sur l'appareil
- **Coûts réduits** : Élimination des frais d'API cloud
- **Performance** : Latence réduite pour les tâches simples
- **Indépendance** : Fonctionnement hors ligne possible
- **Flexibilité** : Choix entre cloud et local selon les besoins

L'architecture existante avec `SmartSessionFactory` et `LiteLLMProxy` fournit une base solide pour cette extension. L'approche progressive (Ollama → Llama.cpp → Transformers) minimise les risques tout en maximisant la valeur ajoutée.
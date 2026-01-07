"""
Gestionnaire NPU pour l'architecture Ryzen AI.
Implémente le Static Shape Bucketing et le cache de compilation.
"""

import os
import json
import logging
import threading
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    ort = None

logger = logging.getLogger(__name__)

class NPUManager:
    """Singleton pour la gestion du NPU avec optimisation Static Shape Bucketing."""
    
    _instance = None
    _lock = threading.Lock()
    
    # Buckets de taille fixe pour le NPU (en tokens)
    BUCKET_SIZES = [128, 256, 512, 1024]
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(NPUManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.sessions: Dict[str, ort.InferenceSession] = {}
        self.cache_dir = self._get_cache_dir()
        self.vaip_config = self._load_vaip_config()
        self.providers = ['VitisAIExecutionProvider', 'CPUExecutionProvider']
        
        # Créer le dossier de cache
        os.makedirs(self.cache_dir, exist_ok=True)
        
        logger.info(f"NPU Manager initialisé. Cache dir: {self.cache_dir}")
    
    def _get_cache_dir(self) -> str:
        """Retourne le dossier de cache pour les modèles compilés."""
        cache_path = os.environ.get("VAIP_CACHE_DIR", "C:\\ProgramData\\RyzenAI\\Cache")
        return os.path.join(cache_path, "compiled_models")
    
    def _load_vaip_config(self) -> Dict[str, Any]:
        """Charge ou crée la configuration VAIP pour le NPU."""
        config_path = os.path.join(self.cache_dir, "vaip_config.json")
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        
        # Configuration par défaut optimisée pour Hawk Point
        config = {
            "cache_dir": self.cache_dir,
            "cache_key": "nomic_embed_int8_v1_hawkpoint",
            "vaiml_config": {
                "optimize_level": 2,
                "convert_nchw_to_nhwc": False,
                "preferred_data_storage": "unvectorized",
                "enable_f32_to_bf16_conversion": False
            }
        }
        
        # Sauvegarder la configuration
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Configuration VAIP créée: {config_path}")
        return config
    
    def _get_bucket_for_length(self, sequence_length: int) -> int:
        """Retourne la taille de bucket appropriée pour une longueur de séquence."""
        for bucket in self.BUCKET_SIZES:
            if sequence_length <= bucket:
                return bucket
        return self.BUCKET_SIZES[-1]  # Retourne le plus grand bucket
    
    def _pad_sequence(self, tokens: List[int], target_length: int) -> np.ndarray:
        """Pad une séquence de tokens à la longueur cible."""
        if len(tokens) >= target_length:
            return np.array(tokens[:target_length], dtype=np.int64)
        
        padded = np.zeros(target_length, dtype=np.int64)
        padded[:len(tokens)] = tokens
        return padded
    
    def load_model(self, model_path: str, model_name: str = "default") -> bool:
        """
        Charge un modèle ONNX sur le NPU avec cache de compilation.
        
        Args:
            model_path: Chemin vers le fichier ONNX
            model_name: Nom unique pour le modèle (pour le cache)
            
        Returns:
            True si chargement réussi, False sinon
        """
        try:
            if not ONNX_AVAILABLE:
                logger.error("ONNX Runtime non disponible")
                return False
            
            # Vérifier si le modèle existe
            if not os.path.exists(model_path):
                logger.error(f"Modèle non trouvé: {model_path}")
                return False
            
            # Clé de cache basée sur le modèle et la configuration
            cache_key = f"{model_name}_{hash(json.dumps(self.vaip_config, sort_keys=True))}"
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.xmodel")
            
            # Options de session
            sess_options = ort.SessionOptions()
            sess_options.enable_cpu_mem_arena = False  # Important pour NPU
            
            # Configurer le cache de compilation
            if "cache_dir" in self.vaip_config:
                sess_options.add_session_config_entry("cache.dir", self.vaip_config["cache_dir"])
            if "cache_key" in self.vaip_config:
                sess_options.add_session_config_entry("cache.key", self.vaip_config["cache_key"])
            
            logger.info(f"Chargement du modèle {model_name} sur NPU...")
            
            # Créer la session avec fallback automatique
            session = ort.InferenceSession(
                model_path,
                sess_options=sess_options,
                providers=self.providers
            )
            
            # Vérifier quel provider est utilisé
            session_provider = session.get_providers()[0]
            logger.info(f"Modèle {model_name} chargé avec provider: {session_provider}")
            
            # Warmup du modèle
            self._warmup_model(session, model_name)
            
            self.sessions[model_name] = session
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle {model_name}: {e}")
            return False
    
    def _warmup_model(self, session: ort.InferenceSession, model_name: str):
        """Effectue un warmup du modèle pour éviter la latence de première exécution."""
        try:
            # Créer des entrées factices pour chaque bucket
            input_info = session.get_inputs()
            
            for bucket_size in self.BUCKET_SIZES[:2]:  # Warmup seulement 2 premiers buckets
                dummy_inputs = {}
                for input in input_info:
                    if "input_ids" in input.name.lower():
                        # Pour les modèles de texte
                        shape = list(input.shape)
                        if -1 in shape:  # Dimension dynamique
                            shape[shape.index(-1)] = bucket_size
                        dummy_inputs[input.name] = np.random.randint(0, 1000, shape, dtype=np.int64)
                    elif "attention_mask" in input.name.lower():
                        shape = list(input.shape)
                        if -1 in shape:
                            shape[shape.index(-1)] = bucket_size
                        dummy_inputs[input.name] = np.ones(shape, dtype=np.int64)
                    else:
                        # Pour les autres entrées
                        dummy_inputs[input.name] = np.random.randn(*input.shape).astype(np.float32)
                
                # Exécution de warmup
                _ = session.run(None, dummy_inputs)
            
            logger.info(f"Warmup réussi pour {model_name}")
            
        except Exception as e:
            logger.warning(f"Warmup échoué pour {model_name}: {e}")
    
    def infer(self, model_name: str, inputs: Dict[str, np.ndarray]) -> Optional[Dict[str, np.ndarray]]:
        """
        Exécute l'inférence sur le NPU.
        
        Args:
            model_name: Nom du modèle chargé
            inputs: Dictionnaire des entrées
            
        Returns:
            Dictionnaire des sorties ou None en cas d'erreur
        """
        try:
            if model_name not in self.sessions:
                logger.error(f"Modèle {model_name} non chargé")
                return None
            
            session = self.sessions[model_name]
            
            # Préparer les entrées avec padding si nécessaire
            prepared_inputs = self._prepare_inputs(session, inputs)
            
            # Exécuter l'inférence
            outputs = session.run(None, prepared_inputs)
            
            # Convertir en dictionnaire
            output_names = [output.name for output in session.get_outputs()]
            result = {name: output for name, output in zip(output_names, outputs)}
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur d'inférence pour {model_name}: {e}")
            return None
    
    def _prepare_inputs(self, session: ort.InferenceSession, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Prépare les entrées avec padding pour le Static Shape Bucketing."""
        prepared = {}
        
        for input_info in session.get_inputs():
            input_name = input_info.name
            
            if input_name not in inputs:
                continue
            
            input_data = inputs[input_name]
            
            # Vérifier si c'est une entrée de séquence qui nécessite du padding
            if "input_ids" in input_name.lower() and len(input_data.shape) == 2:
                batch_size, seq_len = input_data.shape
                
                # Trouver le bucket approprié
                target_length = self._get_bucket_for_length(seq_len)
                
                if seq_len != target_length:
                    # Appliquer le padding
                    padded = np.zeros((batch_size, target_length), dtype=input_data.dtype)
                    padded[:, :seq_len] = input_data
                    prepared[input_name] = padded
                else:
                    prepared[input_name] = input_data
            else:
                prepared[input_name] = input_data
        
        return prepared
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Retourne les informations sur un modèle chargé."""
        if model_name not in self.sessions:
            return None
        
        session = self.sessions[model_name]
        
        info = {
            "provider": session.get_providers()[0],
            "inputs": [{"name": i.name, "shape": i.shape, "type": i.type} 
                      for i in session.get_inputs()],
            "outputs": [{"name": o.name, "shape": o.shape, "type": o.type} 
                       for o in session.get_outputs()],
            "bucket_sizes": self.BUCKET_SIZES
        }
        
        return info
    
    def unload_model(self, model_name: str):
        """Décharge un modèle de la mémoire NPU."""
        if model_name in self.sessions:
            del self.sessions[model_name]
            logger.info(f"Modèle {model_name} déchargé")
    
    def cleanup(self):
        """Nettoie toutes les ressources."""
        self.sessions.clear()
        logger.info("NPU Manager nettoyé")


# Singleton global
npu_manager = NPUManager()
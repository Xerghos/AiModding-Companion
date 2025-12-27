"""
Pool de processus pré-chauffés pour GeminiCliSession.
Maintient des processus gemini-cli prêts à être utilisés pour réduire le délai de démarrage.

Note: La réutilisation complète de processus nécessiterait des named pipes ou sockets
pour maintenir des processus "vivants" qui peuvent recevoir plusieurs requêtes.
Cette implémentation fournit une structure de base qui peut être étendue.
"""

import subprocess
import threading
import time
import os
import sys
from typing import Optional, Dict, Any, List
from queue import Queue, Empty
from threading import Lock


class GeminiCliProcessPool:
    """
    Pool de processus pré-chauffés pour gemini-cli.
    Maintient un processus prêt pour la première requête.
    """
    
    def __init__(self, cli_path: str, model_name: str, workdir: str, env: Dict[str, str], pool_size: int = 1):
        """
        Initialise le pool de processus.
        
        Args:
            cli_path: Chemin vers l'exécutable gemini-cli
            model_name: Nom du modèle
            workdir: Répertoire de travail
            env: Variables d'environnement
            pool_size: Taille du pool (nombre de processus à maintenir)
        """
        self.cli_path = cli_path
        self.model_name = model_name
        self.workdir = workdir
        self.env = env
        self.pool_size = pool_size
        
        self._pool: Queue = Queue(maxsize=pool_size)
        self._lock = Lock()
        self._initialized = False
        
    def initialize(self):
        """Initialise le pool en pré-chauffant les processus."""
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            # Pré-chauffer un processus en arrière-plan
            def prewarm_thread():
                try:
                    # Créer un processus test pour pré-chauffer Node.js et les modules
                    test_cmd = [
                        self.cli_path,
                        "--model",
                        self.model_name,
                        "--output-format",
                        "text",
                        "--prompt",
                        "test",
                    ]
                    
                    process = subprocess.Popen(
                        test_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.PIPE,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        bufsize=65536,
                        cwd=self.workdir or os.getcwd(),
                        env=self.env
                    )
                    
                    # Écrire un message minimal et fermer
                    try:
                        process.stdin.write("test\n")
                        process.stdin.close()
                    except Exception:
                        pass
                    
                    # Attendre que le processus se termine (ou timeout)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    
                except Exception:
                    # Ne pas bloquer si le pré-chauffage échoue
                    pass
            
            # Lancer le thread de pré-chauffage
            thread = threading.Thread(target=prewarm_thread, daemon=True)
            thread.start()
            
            self._initialized = True
    
    def get_process(self, cmd: List[str]) -> subprocess.Popen:
        """
        Obtient un processus du pool ou en crée un nouveau.
        
        Args:
            cmd: Commande à exécuter
            
        Returns:
            Processus subprocess.Popen
        """
        # Pour l'instant, créer toujours un nouveau processus
        # La réutilisation nécessiterait des named pipes/sockets
        # Cette méthode peut être étendue plus tard pour réutiliser les processus
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=65536,
            cwd=self.workdir or os.getcwd(),
            env=self.env
        )
    
    def return_process(self, process: subprocess.Popen):
        """
        Retourne un processus au pool (pour réutilisation future).
        
        Args:
            process: Processus à retourner
        """
        # Pour l'instant, ne rien faire car on ne peut pas réutiliser un processus
        # après avoir fermé stdin. Cette méthode peut être étendue plus tard.
        try:
            if process.poll() is None:
                process.kill()
        except Exception:
            pass
    
    def shutdown(self):
        """Ferme tous les processus du pool."""
        with self._lock:
            while not self._pool.empty():
                try:
                    process = self._pool.get_nowait()
                    try:
                        if process.poll() is None:
                            process.kill()
                    except Exception:
                        pass
                except Empty:
                    break


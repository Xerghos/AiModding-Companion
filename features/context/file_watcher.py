"""
Module de surveillance de fichiers avec watchdog pour détection réactive des changements.
"""

import os
import logging
import threading
import queue
import time
from typing import Callable, Optional, List, Dict
from config import get_logger
from features.Decorators import trace_action

log = get_logger("features.context.file_watcher")

# Import watchdog avec gestion d'erreur
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None
    FileSystemEvent = None


class CodeFileHandler(FileSystemEventHandler):
    """Handler pour les événements de fichiers système."""
    
    def __init__(self, dirty_queue: queue.Queue, file_extensions: tuple = ('.py', '.js', '.ts', '.java', '.cpp', '.h')):
        super().__init__()
        self.dirty_queue = dirty_queue
        self.file_extensions = file_extensions
        self.last_events: Dict[str, float] = {}  # path -> timestamp
        self.debounce_seconds = 0.5  # Éviter les événements multiples rapides
    
    def _should_process(self, file_path: str) -> bool:
        """Vérifie si le fichier doit être traité."""
        # Vérifier l'extension
        if not any(file_path.lower().endswith(ext) for ext in self.file_extensions):
            return False
        
        # Débounce: ignorer les événements trop rapprochés
        now = time.time()
        last_time = self.last_events.get(file_path, 0)
        if now - last_time < self.debounce_seconds:
            return False
        
        self.last_events[file_path] = now
        return True
    
    def on_modified(self, event: FileSystemEvent):
        """Appelé quand un fichier est modifié."""
        if event.is_directory:
            return
        
        file_path = os.path.abspath(event.src_path)
        if self._should_process(file_path):
            log.debug(f"📝 Fichier modifié détecté: {file_path}")
            self.dirty_queue.put(('modified', file_path))
    
    def on_created(self, event: FileSystemEvent):
        """Appelé quand un fichier est créé."""
        if event.is_directory:
            return
        
        file_path = os.path.abspath(event.src_path)
        if self._should_process(file_path):
            log.debug(f"➕ Fichier créé détecté: {file_path}")
            self.dirty_queue.put(('created', file_path))
    
    def on_deleted(self, event: FileSystemEvent):
        """Appelé quand un fichier est supprimé."""
        if event.is_directory:
            return
        
        file_path = os.path.abspath(event.src_path)
        log.debug(f"🗑️ Fichier supprimé détecté: {file_path}")
        self.dirty_queue.put(('deleted', file_path))


class FileWatcher:
    """
    Surveille les changements de fichiers en temps réel avec watchdog.
    Place les fichiers modifiés dans une file d'attente pour traitement asynchrone.
    """
    
    def __init__(self, root_path: str, callback: Optional[Callable] = None, 
                 file_extensions: tuple = ('.py', '.js', '.ts', '.java', '.cpp', '.h')):
        """
        Args:
            root_path: Chemin racine à surveiller
            callback: Fonction appelée pour chaque fichier modifié (action, file_path)
            file_extensions: Extensions de fichiers à surveiller
        """
        if not WATCHDOG_AVAILABLE:
            raise ImportError("watchdog n'est pas installé. Installez-le avec: pip install watchdog")
        
        self.root_path = os.path.abspath(root_path)
        self.callback = callback
        self.file_extensions = file_extensions
        self.dirty_queue = queue.Queue()
        self.observer: Optional[Observer] = None
        self.handler: Optional[CodeFileHandler] = None
        self.processing_thread: Optional[threading.Thread] = None
        self.running = False
    
    @trace_action(source="file_watcher")
    def start(self):
        """Démarre la surveillance."""
        if self.running:
            log.warning("FileWatcher déjà en cours d'exécution")
            return
        
        if not os.path.exists(self.root_path):
            raise ValueError(f"Chemin racine introuvable: {self.root_path}")
        
        self.handler = CodeFileHandler(self.dirty_queue, self.file_extensions)
        self.observer = Observer()
        self.observer.schedule(self.handler, self.root_path, recursive=True)
        self.observer.start()
        
        # Démarrer le thread de traitement
        self.running = True
        self.processing_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.processing_thread.start()
        
        log.info(f"✅ FileWatcher démarré: surveillance de {self.root_path}")
    
    def stop(self):
        """Arrête la surveillance."""
        self.running = False
        
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
        
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        
        log.info("FileWatcher arrêté")
    
    def _process_queue(self):
        """Traite la file d'attente des fichiers modifiés."""
        while self.running:
            try:
                # Timeout pour permettre de vérifier self.running
                try:
                    action, file_path = self.dirty_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Appeler le callback si défini
                if self.callback:
                    try:
                        self.callback(action, file_path)
                    except Exception as e:
                        log.error(f"Erreur callback FileWatcher: {e}")
                
                self.dirty_queue.task_done()
                
            except Exception as e:
                log.error(f"Erreur traitement queue FileWatcher: {e}")
    
    def get_dirty_files(self, timeout: float = 0.1) -> List[tuple]:
        """
        Récupère les fichiers modifiés depuis la queue.
        
        Args:
            timeout: Timeout pour la récupération
        
        Returns:
            Liste de tuples (action, file_path)
        """
        dirty_files = []
        
        while True:
            try:
                action, file_path = self.dirty_queue.get(timeout=timeout)
                dirty_files.append((action, file_path))
            except queue.Empty:
                break
        
        return dirty_files
    
    def is_running(self) -> bool:
        """Vérifie si le watcher est en cours d'exécution."""
        return self.running and self.observer and self.observer.is_alive()


# Instance globale (optionnelle)
_global_watcher: Optional[FileWatcher] = None

def get_global_watcher(root_path: str, callback: Optional[Callable] = None) -> FileWatcher:
    """Retourne ou crée l'instance globale du FileWatcher."""
    global _global_watcher
    
    if _global_watcher is None or not _global_watcher.is_running():
        _global_watcher = FileWatcher(root_path, callback)
        _global_watcher.start()
    
    return _global_watcher
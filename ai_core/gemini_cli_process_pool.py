import subprocess
import threading
import time
import os
import queue
from typing import Optional, List, Tuple
from features.UnifiedLogger import UnifiedLogger

class HotGeminiProcess:
    """
    Représente un processus gemini-cli pré-chauffé.
    Le processus est démarré, le contexte statique est écrit dans stdin,
    et il reste en attente du message utilisateur (ou de la fermeture de stdin).
    """
    def __init__(self, cmd: List[str], cwd: str, env: dict, static_prompt: str):
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self.static_prompt = static_prompt
        self.process: Optional[subprocess.Popen] = None
        self.stdin_thread: Optional[threading.Thread] = None
        self.creation_time = time.time()
        self.status = "init" # init, ready, used, failed
        self.error: Optional[Exception] = None
        
        # Démarrage immédiat
        self._start()

    def _start(self):
        try:
            self.process = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=65536,
                cwd=self.cwd,
                env=self.env
            )
            
            # Lancer l'écriture du contexte statique en arrière-plan
            self.stdin_thread = threading.Thread(target=self._prefill_stdin, daemon=True)
            self.stdin_thread.start()
            
        except Exception as e:
            self.status = "failed"
            self.error = e
            UnifiedLogger.write("AI_CORE", "ERROR", f"Pool: Echec démarrage process: {e}")

    def _prefill_stdin(self):
        """Écrit la partie statique du prompt et laisse le pipe ouvert."""
        try:
            if not self.process or not self.process.stdin:
                return

            # Écriture du contexte statique
            if self.static_prompt:
                self.process.stdin.write(self.static_prompt)
                # On ajoute un séparateur si nécessaire, mais on ne ferme PAS stdin
                if not self.static_prompt.endswith("\n"):
                    self.process.stdin.write("\n\n")
                # FLUSH RETIRÉ : Le flush() bloque ~7.5s car Node.js ne lit pas encore les données
                # Le flush automatique se fera lors de la fermeture stdin dans use()
                # Cela élimine la latence excessive observée lors du pré-chauffage
                # self.process.stdin.flush()  # ← RETIRÉ pour éviter blocage
            
            # Délai minimum pour laisser gemini-cli s'initialiser (détection readiness)
            # Cela évite les erreurs "No input provided via stdin" en s'assurant que
            # Node.js est prêt à lire stdin avant de marquer le processus comme ready
            time.sleep(0.5)  # 500ms pour laisser le temps à gemini-cli de s'initialiser
            
            self.status = "ready"
            # UnifiedLogger.write("AI_CORE", "DEBUG", f"Pool: Process PID {self.process.pid} pré-chargé ({len(self.static_prompt)} chars)")
            
        except Exception as e:
            self.status = "failed"
            self.error = e
            # UnifiedLogger.write("AI_CORE", "DEBUG", f"Pool: Erreur pré-chargement stdin: {e}")

    def use(self, user_message: str) -> subprocess.Popen:
        """
        Utilise le processus pour envoyer le message utilisateur.
        Finalise l'écriture stdin et retourne le processus Popen pour lecture.
        """
        if self.status == "failed":
            raise self.error or Exception("Process failed silently")
            
        # Si le thread d'écriture n'a pas fini (très gros contexte), on attend un peu
        if self.stdin_thread and self.stdin_thread.is_alive():
            self.stdin_thread.join(timeout=5.0)
            
        try:
            if self.process.poll() is not None:
                raise Exception(f"Processus mort prématurément (Code: {self.process.returncode})")

            # Écriture du message utilisateur et fermeture
            # UnifiedLogger.write("AI_CORE", "DEBUG", f"Pool: Injection message utilisateur ({len(user_message)} chars) dans PID {self.process.pid}")
            
            self.process.stdin.write(user_message)
            self.process.stdin.close() # C'est ici que Node.js reçoit EOF et commence le traitement
            self.status = "used"
            
            return self.process
            
        except Exception as e:
            self.status = "failed"
            self.error = e
            # Nettoyage
            try:
                self.process.kill()
            except: pass
            raise e

    def kill(self):
        """Force l'arrêt du processus."""
        if self.process and self.process.poll() is None:
            try:
                self.process.kill()
                self.process.wait()
            except: pass

class GeminiCliProcessPool:
    """
    Gère un pool de processus 'HotGeminiProcess'.
    Maintient un processus prêt pour la prochaine requête.
    """
    def __init__(self):
        self._pool_lock = threading.Lock()
        self._next_process: Optional[HotGeminiProcess] = None
        self._current_config = None # (cmd, cwd, env_hash, static_hash)

    def _get_config_hash(self, cmd, cwd, env, static_prompt):
        """Génère une signature unique pour la configuration actuelle."""
        # On simplifie pour éviter de hasher tout l'environnement
        import hashlib
        env_str = str(sorted(env.keys())) # On suppose que si les clés changent, c'est important
        sig = f"{str(cmd)}-{cwd}-{env_str}-{len(static_prompt)}-{hash(static_prompt)}"
        return sig

    def prepare_next(self, cmd: List[str], cwd: str, env: dict, static_prompt: str):
        """
        Lance la préparation du prochain processus en arrière-plan.
        Idéalement appelé après avoir consommé un processus ou au démarrage.
        """
        def _prepare():
            with self._pool_lock:
                # Vérifier si on a déjà un process prêt compatible
                cfg_sig = self._get_config_hash(cmd, cwd, env, static_prompt)
                
                if self._next_process and self._current_config == cfg_sig:
                    if self._next_process.status in ["ready", "init"] and self._next_process.process.poll() is None:
                        return # Déjà prêt
                    
                # Nettoyage ancien si invalide/incompatible
                if self._next_process:
                    self._next_process.kill()
                
                # Création nouveau
                self._current_config = cfg_sig
                self._next_process = HotGeminiProcess(cmd, cwd, env, static_prompt)
                
        threading.Thread(target=_prepare, daemon=True).start()

    def get_process(self, cmd: List[str], cwd: str, env: dict, static_prompt: str) -> HotGeminiProcess:
        """
        Récupère un processus prêt ou en crée un nouveau (bloquant si création nécessaire).
        """
        with self._pool_lock:
            cfg_sig = self._get_config_hash(cmd, cwd, env, static_prompt)
            
            # Cas idéal : Processus prêt et compatible
            if self._next_process and self._current_config == cfg_sig:
                proc = self._next_process
                
                # Vérification TTL : processus ne doit pas être trop vieux (30s max)
                age = time.time() - proc.creation_time
                if age > 30.0:
                    UnifiedLogger.write("AI_CORE", "DEBUG", f"Pool: Processus expiré (age={age:.1f}s), création sync...")
                    proc.kill()
                    self._next_process = None
                    return HotGeminiProcess(cmd, cwd, env, static_prompt)
                
                self._next_process = None # On le consomme
                
                # Vérification santé
                if proc.status == "failed" or (proc.process and proc.process.poll() is not None):
                    UnifiedLogger.write("AI_CORE", "WARNING", "Pool: Processus pré-chauffé mort, création sync...")
                    return HotGeminiProcess(cmd, cwd, env, static_prompt)
                
                UnifiedLogger.write("AI_CORE", "DEBUG", f"Pool: Utilisation processus pré-chauffé 🔥 (age={age:.1f}s)")
                return proc
            
            # Cas fallback : Pas de process prêt ou config différente
            UnifiedLogger.write("AI_CORE", "DEBUG", "Pool: Cold start (pas de process prêt/compatible) ❄️")
            return HotGeminiProcess(cmd, cwd, env, static_prompt)

# Instance globale du pool
GLOBAL_CLI_POOL = GeminiCliProcessPool()
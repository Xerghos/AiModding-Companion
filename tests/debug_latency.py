"""
Script de diagnostic de latence pour le bridge Gemini CLI via Python.

Objectif: Identifier la source de la latence excessive (17s) lors de la communication
entre Python et gemini-cli (Node.js) via subprocess.Popen et stdin.

Usage:
    python tests/debug_latency.py
"""

import subprocess
import time
import tempfile
import os
import sys
import shutil
from pathlib import Path
from typing import Tuple, Dict, Optional
import threading
from queue import Queue, Empty


def generate_test_payload(size_chars: int = 20000) -> str:
    """Génère un texte de test de taille donnée."""
    base_text = (
        "Ceci est un texte de test pour diagnostiquer la latence du bridge Gemini CLI. "
        "Le problème observé est qu'une requête avec un payload d'environ 20ko prend "
        "17 secondes à répondre via l'application Python, alors que le même payload "
        "copié-collé manuellement dans le terminal gemini-cli répond en 1 seconde.\n\n"
    )
    # Répéter pour atteindre la taille désirée
    repetitions = (size_chars // len(base_text)) + 1
    full_text = base_text * repetitions
    return full_text[:size_chars]


def find_gemini_cli() -> Optional[str]:
    """Trouve le chemin du CLI gemini."""
    candidates = ["gemini"]
    if sys.platform == "win32":
        candidates.extend(["gemini.cmd", "gemini.exe", "gemini.ps1"])
    
    for cmd in candidates:
        path = shutil.which(cmd)
        if path:
            return path
    
    # Fallback Windows
    if sys.platform == "win32":
        npm_paths = [
            os.path.join(os.environ.get("APPDATA", ""), "npm", "gemini.cmd"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "npm", "gemini.cmd"),
            os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Roaming", "npm", "gemini.cmd"),
        ]
        for npm_path in npm_paths:
            if os.path.exists(npm_path):
                return npm_path
    
    return None


def test_variant_a_pipe_stdin(cmd: list, cwd: str, env: dict, payload: str) -> Dict[str, float]:
    """
    Variante A (Actuelle): stdin.write() + stdin.close()
    Reproduit exactement le comportement de gemini_cli_process_pool.py
    """
    print("\n" + "="*80)
    print("VARIANTE A: Pipe stdin (méthode actuelle)")
    print("="*80)
    
    timings = {}
    
    try:
        # 1. Démarrage du processus
        start_process = time.time()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=65536,
            cwd=cwd,
            env=env
        )
        process_created = time.time()
        timings['process_creation'] = (process_created - start_process) * 1000
        
        print(f"✓ Processus créé en {timings['process_creation']:.2f}ms (PID: {process.pid})")
        
        # 2. Écriture dans stdin
        start_write = time.time()
        if process.stdin:
            process.stdin.write(payload)
            write_done = time.time()
            timings['stdin_write'] = (write_done - start_write) * 1000
            
            print(f"✓ Écriture stdin terminée en {timings['stdin_write']:.2f}ms ({len(payload)} chars)")
            
            # 3. Flush
            start_flush = time.time()
            process.stdin.flush()
            flush_done = time.time()
            timings['stdin_flush'] = (flush_done - start_flush) * 1000
            
            print(f"✓ Flush stdin terminé en {timings['stdin_flush']:.2f}ms")
            
            # 4. Fermeture stdin (EOF envoyé à Node.js)
            start_close = time.time()
            process.stdin.close()
            stdin_closed = time.time()
            timings['stdin_close'] = (stdin_closed - start_close) * 1000
            
            print(f"✓ Stdin fermé en {timings['stdin_close']:.2f}ms")
            print(f"  → C'est à ce moment que Node.js devrait recevoir EOF et commencer le traitement")
        else:
            raise Exception("stdin n'est pas disponible")
        
        # 5. Attente première ligne stdout avec gestion timeout
        print("\n⏳ Attente première ligne stdout...")
        first_line_time = None
        stdout_lines = []
        timeout_seconds = 30  # Timeout généreux pour le diagnostic
        
        # Utiliser un thread pour la lecture avec timeout
        stdout_queue = Queue()
        stdout_finished = [False]
        stdout_error = [None]
        
        def read_stdout():
            try:
                for line in process.stdout:
                    stdout_queue.put(line)
                stdout_finished[0] = True
            except Exception as e:
                stdout_error[0] = e
                stdout_finished[0] = True
        
        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stdout_thread.start()
        
        stdout_start = time.time()
        timeout_reached = False
        
        # Attendre la première ligne avec timeout
        while first_line_time is None and not stdout_finished[0]:
            try:
                line = stdout_queue.get(timeout=0.5)
                if first_line_time is None:
                    first_line_time = time.time()
                    timings['time_to_first_line'] = (first_line_time - stdin_closed) * 1000
                    print(f"✓ Première ligne reçue après {timings['time_to_first_line']:.2f}ms")
                    print(f"  Contenu: {line[:100] if len(line) > 100 else line.strip()}...")
                
                stdout_lines.append(line)
                if len(stdout_lines) >= 3:
                    break
            except Empty:
                elapsed = time.time() - stdout_start
                if elapsed > timeout_seconds:
                    timeout_reached = True
                    break
                continue
        
        # Si aucune ligne reçue, attendre un peu puis terminer
        if first_line_time is None:
            if timeout_reached:
                print(f"⚠️ Timeout après {timeout_seconds}s, aucune ligne reçue")
                timings['time_to_first_line'] = timeout_seconds * 1000
                timings['error'] = f"Timeout: aucune ligne reçue dans les {timeout_seconds}s"
            else:
                print("⚠️ Processus terminé sans sortie stdout")
                timings['time_to_first_line'] = (time.time() - stdin_closed) * 1000
                timings['error'] = "Processus terminé sans sortie"
            
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        else:
            # Attendre quelques lignes supplémentaires puis terminer
            try:
                stdout_thread.join(timeout=5)
            except:
                pass
            
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        
        timings['total_time'] = (time.time() - start_process) * 1000
        timings['process_exit_code'] = process.returncode
        
        # Lire stderr si disponible
        if process.stderr:
            stderr_lines = list(process.stderr)
            if stderr_lines:
                timings['stderr'] = ''.join(stderr_lines)
        
        print(f"\n📊 Résumé:")
        print(f"  - Temps total: {timings['total_time']:.2f}ms")
        print(f"  - Temps création processus: {timings['process_creation']:.2f}ms")
        print(f"  - Temps écriture stdin: {timings['stdin_write']:.2f}ms")
        print(f"  - Temps flush: {timings['stdin_flush']:.2f}ms")
        print(f"  - Temps fermeture stdin: {timings['stdin_close']:.2f}ms")
        print(f"  - ⏱️  TEMPS CRITIQUE - stdin.close() → première ligne: {timings['time_to_first_line']:.2f}ms")
        
        if 'error' in timings:
            print(f"  - ❌ Erreur: {timings['error']}")
        
    except Exception as e:
        timings['error'] = str(e)
        print(f"❌ Erreur: {e}")
        if 'process' in locals() and process.poll() is None:
            process.kill()
    
    return timings


def test_variant_b_file_redirection(cmd: list, cwd: str, env: dict, payload: str) -> Dict[str, float]:
    """
    Variante B: Écriture dans un fichier temporaire, puis redirection stdin
    """
    print("\n" + "="*80)
    print("VARIANTE B: Fichier temporaire + redirection stdin")
    print("="*80)
    
    timings = {}
    temp_file = None
    
    try:
        # 1. Création fichier temporaire
        start_file = time.time()
        temp_file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.txt')
        temp_path = temp_file.name
        temp_file.write(payload)
        temp_file.flush()
        temp_file.close()
        file_created = time.time()
        timings['file_write'] = (file_created - start_file) * 1000
        
        print(f"✓ Fichier temporaire créé en {timings['file_write']:.2f}ms ({len(payload)} chars)")
        print(f"  Chemin: {temp_path}")
        
        # 2. Ouvrir le fichier pour stdin
        start_process = time.time()
        with open(temp_path, 'r', encoding='utf-8') as stdin_file:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=stdin_file,  # Redirection du fichier vers stdin
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=65536,
                cwd=cwd,
                env=env
            )
            process_created = time.time()
            timings['process_creation'] = (process_created - start_process) * 1000
            
            print(f"✓ Processus créé en {timings['process_creation']:.2f}ms (PID: {process.pid})")
            print(f"  → stdin est directement connecté au fichier (EOF automatique à la fin)")
            
            # 3. Attente première ligne stdout avec timeout
            print("\n⏳ Attente première ligne stdout...")
            first_line_time = None
            stdout_lines = []
            timeout_seconds = 30
            
            stdin_closed = process_created  # Le fichier se ferme automatiquement
            
            # Lecture avec timeout
            stdout_queue = Queue()
            stdout_finished = [False]
            stdout_error = [None]
            
            def read_stdout():
                try:
                    for line in process.stdout:
                        stdout_queue.put(line)
                    stdout_finished[0] = True
                except Exception as e:
                    stdout_error[0] = e
                    stdout_finished[0] = True
            
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stdout_thread.start()
            
            stdout_start = time.time()
            timeout_reached = False
            
            while first_line_time is None and not stdout_finished[0]:
                try:
                    line = stdout_queue.get(timeout=0.5)
                    if first_line_time is None:
                        first_line_time = time.time()
                        timings['time_to_first_line'] = (first_line_time - stdin_closed) * 1000
                        print(f"✓ Première ligne reçue après {timings['time_to_first_line']:.2f}ms")
                        print(f"  Contenu: {line[:100] if len(line) > 100 else line.strip()}...")
                    
                    stdout_lines.append(line)
                    if len(stdout_lines) >= 3:
                        break
                except Empty:
                    elapsed = time.time() - stdout_start
                    if elapsed > timeout_seconds:
                        timeout_reached = True
                        break
                    continue
            
            if first_line_time is None:
                if timeout_reached:
                    print(f"⚠️ Timeout après {timeout_seconds}s")
                    timings['time_to_first_line'] = timeout_seconds * 1000
                    timings['error'] = f"Timeout: aucune ligne reçue dans les {timeout_seconds}s"
                else:
                    timings['time_to_first_line'] = (time.time() - stdin_closed) * 1000
                    timings['error'] = "Processus terminé sans sortie"
                
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
            else:
                stdout_thread.join(timeout=5)
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        
        timings['total_time'] = (time.time() - start_process) * 1000
        timings['process_exit_code'] = process.returncode
        
        print(f"\n📊 Résumé:")
        print(f"  - Temps écriture fichier: {timings['file_write']:.2f}ms")
        print(f"  - Temps création processus: {timings['process_creation']:.2f}ms")
        print(f"  - ⏱️  TEMPS CRITIQUE - processus créé → première ligne: {timings['time_to_first_line']:.2f}ms")
        
        if 'error' in timings:
            print(f"  - ❌ Erreur: {timings['error']}")
        
    except Exception as e:
        timings['error'] = str(e)
        print(f"❌ Erreur: {e}")
        if 'process' in locals() and process.poll() is None:
            process.kill()
    finally:
        # Nettoyage fichier temporaire
        if temp_file and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                print(f"✓ Fichier temporaire supprimé")
            except:
                pass
    
    return timings


def test_variant_c_prompt_arg(cmd: list, cwd: str, env: dict, payload: str) -> Dict[str, float]:
    """
    Variante C: Passer le texte via argument --prompt (si taille le permet)
    Note: Windows cmd.exe a une limite ~8191 chars pour les arguments
    """
    print("\n" + "="*80)
    print("VARIANTE C: Argument --prompt (limité à 6000 chars pour sécurité)")
    print("="*80)
    
    # Tronquer pour éviter dépassement limite Windows
    max_arg_size = 6000
    if len(payload) > max_arg_size:
        truncated_payload = payload[:max_arg_size] + "... [tronqué pour test]"
        print(f"⚠️ Payload tronqué de {len(payload)} à {len(truncated_payload)} chars (limite Windows)")
    else:
        truncated_payload = payload
    
    timings = {}
    
    try:
        # Construire la commande avec --prompt
        cmd_with_prompt = cmd + ["--prompt", truncated_payload]
        
        # 1. Démarrage du processus
        start_process = time.time()
        process = subprocess.Popen(
            cmd_with_prompt,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=None,  # Pas de stdin
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=65536,
            cwd=cwd,
            env=env
        )
        process_created = time.time()
        timings['process_creation'] = (process_created - start_process) * 1000
        
        print(f"✓ Processus créé en {timings['process_creation']:.2f}ms (PID: {process.pid})")
        print(f"  → Pas de stdin, tout passe par --prompt")
        
        # 2. Attente première ligne stdout avec timeout
        print("\n⏳ Attente première ligne stdout...")
        first_line_time = None
        stdout_lines = []
        timeout_seconds = 30
        
        stdout_queue = Queue()
        stdout_finished = [False]
        stdout_error = [None]
        
        def read_stdout():
            try:
                for line in process.stdout:
                    stdout_queue.put(line)
                stdout_finished[0] = True
            except Exception as e:
                stdout_error[0] = e
                stdout_finished[0] = True
        
        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stdout_thread.start()
        
        stdout_start = time.time()
        timeout_reached = False
        
        while first_line_time is None and not stdout_finished[0]:
            try:
                line = stdout_queue.get(timeout=0.5)
                if first_line_time is None:
                    first_line_time = time.time()
                    timings['time_to_first_line'] = (first_line_time - process_created) * 1000
                    print(f"✓ Première ligne reçue après {timings['time_to_first_line']:.2f}ms")
                    print(f"  Contenu: {line[:100] if len(line) > 100 else line.strip()}...")
                
                stdout_lines.append(line)
                if len(stdout_lines) >= 3:
                    break
            except Empty:
                elapsed = time.time() - stdout_start
                if elapsed > timeout_seconds:
                    timeout_reached = True
                    break
                continue
        
        if first_line_time is None:
            if timeout_reached:
                print(f"⚠️ Timeout après {timeout_seconds}s")
                timings['time_to_first_line'] = timeout_seconds * 1000
                timings['error'] = f"Timeout: aucune ligne reçue dans les {timeout_seconds}s"
            else:
                timings['time_to_first_line'] = (time.time() - process_created) * 1000
                timings['error'] = "Processus terminé sans sortie"
            
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        else:
            stdout_thread.join(timeout=5)
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        
        timings['total_time'] = (time.time() - start_process) * 1000
        timings['process_exit_code'] = process.returncode
        
        print(f"\n📊 Résumé:")
        print(f"  - Temps création processus: {timings['process_creation']:.2f}ms")
        print(f"  - ⏱️  TEMPS CRITIQUE - processus créé → première ligne: {timings['time_to_first_line']:.2f}ms")
        
        if 'error' in timings:
            print(f"  - ❌ Erreur: {timings['error']}")
        
    except Exception as e:
        timings['error'] = str(e)
        print(f"❌ Erreur: {e}")
        if 'process' in locals() and process.poll() is None:
            process.kill()
    
    return timings


def test_variant_a2_pool_exact_reproduction(cmd: list, cwd: str, env: dict, static_prompt: str, dynamic_prompt: str) -> Dict[str, float]:
    """
    Variante A2: Reproduction EXACTE du comportement du pool
    - Écriture contexte statique dans un thread (avec flush)
    - Attente que le thread termine
    - Écriture message dynamique (SANS flush) puis close
    """
    print("\n" + "="*80)
    print("VARIANTE A2: Reproduction EXACTE du pool (static + dynamic, deux écritures)")
    print("="*80)
    
    timings = {}
    stdin_written = [False]
    
    try:
        # 1. Démarrage du processus
        start_process = time.time()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=65536,
            cwd=cwd,
            env=env
        )
        process_created = time.time()
        timings['process_creation'] = (process_created - start_process) * 1000
        
        print(f"✓ Processus créé en {timings['process_creation']:.2f}ms (PID: {process.pid})")
        print(f"  Contexte statique: {len(static_prompt)} chars")
        print(f"  Message dynamique: {len(dynamic_prompt)} chars")
        
        # 2. Écriture du contexte statique dans un thread (comme _prefill_stdin)
        def prefill_stdin():
            try:
                if process.stdin and static_prompt:
                    start_static_write = time.time()
                    process.stdin.write(static_prompt)
                    if not static_prompt.endswith("\n"):
                        process.stdin.write("\n\n")
                    static_write_done = time.time()
                    timings['static_write'] = (static_write_done - start_static_write) * 1000
                    
                    start_static_flush = time.time()
                    process.stdin.flush()  # ← FLUSH ICI (comme dans le pool)
                    static_flush_done = time.time()
                    timings['static_flush'] = (static_flush_done - start_static_flush) * 1000
                    stdin_written[0] = True
                    
                    print(f"✓ Contexte statique écrit: write={timings['static_write']:.2f}ms, flush={timings['static_flush']:.2f}ms")
                elif process.stdin:
                    # Pas de contexte statique, on marque juste comme fait
                    stdin_written[0] = True
            except Exception as e:
                timings['static_error'] = str(e)
                print(f"❌ Erreur écriture statique: {e}")
        
        if static_prompt:
            stdin_thread = threading.Thread(target=prefill_stdin, daemon=True)
            start_static = time.time()
            stdin_thread.start()
            
            # 3. Attendre que le thread termine (comme dans use())
            stdin_thread.join(timeout=30.0)
            static_done = time.time()
            timings['static_total'] = (static_done - start_static) * 1000
            
            if not stdin_written[0]:
                raise Exception("Thread d'écriture statique n'a pas terminé")
        else:
            # Pas de contexte statique, on passe directement à l'écriture dynamique
            stdin_written[0] = True
            timings['static_write'] = 0
            timings['static_flush'] = 0
            timings['static_total'] = 0
        
        if process.poll() is not None:
            raise Exception(f"Processus mort après écriture statique (Code: {process.returncode})")
        
        # 4. Écriture du message utilisateur (comme dans use()) - SANS FLUSH
        start_dynamic = time.time()
        if process.stdin:
            process.stdin.write(dynamic_prompt)
            dynamic_write_done = time.time()
            timings['dynamic_write'] = (dynamic_write_done - start_dynamic) * 1000
            
            print(f"✓ Message dynamique écrit en {timings['dynamic_write']:.2f}ms (SANS flush)")
            
            # 5. Fermeture stdin (comme dans use()) - C'est ici que EOF est envoyé
            start_close = time.time()
            process.stdin.close()
            stdin_closed = time.time()
            timings['stdin_close'] = (stdin_closed - start_close) * 1000
            
            print(f"✓ Stdin fermé en {timings['stdin_close']:.2f}ms")
            print(f"  → C'est à ce moment que Node.js devrait recevoir EOF et commencer le traitement")
        else:
            raise Exception("stdin n'est pas disponible")
        
        # 6. Attente première ligne stdout
        print("\n⏳ Attente première ligne stdout...")
        first_line_time = None
        stdout_lines = []
        timeout_seconds = 30
        
        stdout_queue = Queue()
        stdout_finished = [False]
        stdout_error = [None]
        
        def read_stdout():
            try:
                for line in process.stdout:
                    stdout_queue.put(line)
                stdout_finished[0] = True
            except Exception as e:
                stdout_error[0] = e
                stdout_finished[0] = True
        
        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stdout_thread.start()
        
        stdout_start = time.time()
        timeout_reached = False
        
        while first_line_time is None and not stdout_finished[0]:
            try:
                line = stdout_queue.get(timeout=0.5)
                if first_line_time is None:
                    first_line_time = time.time()
                    timings['time_to_first_line'] = (first_line_time - stdin_closed) * 1000
                    print(f"✓ Première ligne reçue après {timings['time_to_first_line']:.2f}ms")
                    print(f"  Contenu: {line[:100] if len(line) > 100 else line.strip()}...")
                
                stdout_lines.append(line)
                if len(stdout_lines) >= 3:
                    break
            except Empty:
                elapsed = time.time() - stdout_start
                if elapsed > timeout_seconds:
                    timeout_reached = True
                    break
                continue
        
        if first_line_time is None:
            if timeout_reached:
                print(f"⚠️ Timeout après {timeout_seconds}s, aucune ligne reçue")
                timings['time_to_first_line'] = timeout_seconds * 1000
                timings['error'] = f"Timeout: aucune ligne reçue dans les {timeout_seconds}s"
            else:
                print("⚠️ Processus terminé sans sortie stdout")
                timings['time_to_first_line'] = (time.time() - stdin_closed) * 1000
                timings['error'] = "Processus terminé sans sortie"
            
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        else:
            stdout_thread.join(timeout=5)
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        
        timings['total_time'] = (time.time() - start_process) * 1000
        timings['process_exit_code'] = process.returncode
        
        print(f"\n📊 Résumé:")
        print(f"  - Temps total: {timings['total_time']:.2f}ms")
        print(f"  - Temps création processus: {timings['process_creation']:.2f}ms")
        print(f"  - Temps écriture statique: {timings.get('static_write', 0):.2f}ms")
        print(f"  - Temps flush statique: {timings.get('static_flush', 0):.2f}ms ⚠️")
        print(f"  - Temps écriture dynamique: {timings.get('dynamic_write', 0):.2f}ms")
        print(f"  - Temps fermeture stdin: {timings['stdin_close']:.2f}ms")
        print(f"  - ⏱️  TEMPS CRITIQUE - stdin.close() → première ligne: {timings['time_to_first_line']:.2f}ms")
        
        if 'error' in timings:
            print(f"  - ❌ Erreur: {timings['error']}")
        
    except Exception as e:
        timings['error'] = str(e)
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        if 'process' in locals() and process.poll() is None:
            process.kill()
    
    return timings


def test_shell_equivalent(cmd_base: list, payload: str, workdir: str, env: dict) -> Dict[str, float]:
    """
    Test équivalent shell PowerShell pour comparaison
    Note: Ce test sert de référence pour comparer avec une exécution manuelle
    """
    print("\n" + "="*80)
    print("TEST SHELL: PowerShell Get-Content | gemini (référence)")
    print("="*80)
    print("⚠️  Ce test sert uniquement de référence. Pour un test réel,")
    print("    exécutez manuellement dans PowerShell:")
    print(f"    Get-Content payload.txt | gemini --model <model> --output-format text")
    print("="*80)
    
    timings = {}
    temp_file = None
    temp_path = None
    
    try:
        # Créer fichier temporaire dans le workdir
        temp_path = os.path.join(workdir, "payload_test.txt")
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(payload)
        
        print(f"✓ Fichier temporaire créé: {temp_path}")
        
        # Construire commande PowerShell
        # Note: On utilise simplement subprocess.run pour mesurer le temps
        # mais avec redirection de fichier comme dans Variante B
        model_arg = None
        for i, arg in enumerate(cmd_base):
            if arg == "--model" and i + 1 < len(cmd_base):
                model_arg = cmd_base[i + 1]
                break
        
        if not model_arg:
            raise Exception("--model non trouvé dans la commande")
        
        # Simuler avec subprocess + fichier ouvert (comme Variante B)
        # C'est plus proche de ce que PowerShell fait réellement
        print(f"\n⏳ Exécution équivalente shell (fichier + subprocess)...")
        
        start_shell = time.time()
        with open(temp_path, 'r', encoding='utf-8') as stdin_file:
            process = subprocess.Popen(
                cmd_base,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=stdin_file,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=workdir,
                env=env
            )
            
            # Mesurer temps jusqu'à première ligne
            first_line_time = None
            stdout_lines = []
            process_start = time.time()
            
            for line in process.stdout:
                if first_line_time is None:
                    first_line_time = time.time()
                    timings['shell_time_to_first_line'] = (first_line_time - process_start) * 1000
                    print(f"✓ Première ligne reçue après {timings['shell_time_to_first_line']:.2f}ms")
                
                stdout_lines.append(line)
                if len(stdout_lines) >= 3:
                    break
            
            process.wait()
            shell_total = time.time() - start_shell
            timings['shell_total_time'] = shell_total * 1000
            timings['process_exit_code'] = process.returncode
        
        print(f"\n📊 Résumé Shell:")
        print(f"  - Temps total: {timings['shell_total_time']:.2f}ms")
        if 'shell_time_to_first_line' in timings:
            print(f"  - Temps jusqu'à première ligne: {timings['shell_time_to_first_line']:.2f}ms")
        
    except Exception as e:
        timings['error'] = str(e)
        print(f"❌ Erreur: {e}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
    
    return timings


def main():
    """Point d'entrée principal."""
    print("="*80)
    print("DIAGNOSTIC DE LATENCE - Bridge Gemini CLI via Python")
    print("="*80)
    
    # Configuration
    cli_path = find_gemini_cli()
    if not cli_path:
        print("❌ Erreur: gemini-cli non trouvé dans le PATH")
        print("   Installez-le avec: npm install -g @google/gemini-cli")
        return 1
    
    print(f"✓ CLI trouvé: {cli_path}")
    
    # Demander le modèle (avec défaut)
    model_name = input("\nNom du modèle à utiliser (défaut: gemini-2.0-flash-exp): ").strip()
    if not model_name:
        model_name = "gemini-2.0-flash-exp"
    
    # Configuration de base
    cmd_base = [cli_path, "--model", model_name, "--output-format", "text"]
    workdir = tempfile.mkdtemp(prefix="gemini_cli_latency_test_")
    env = dict(os.environ)
    env["GEMINI_SYSTEM_MD"] = "1"  # Comme dans GeminiCliSession
    
    # Créer un répertoire .gemini minimal si nécessaire (comme GeminiCliSession)
    gemini_dir = os.path.join(workdir, ".gemini")
    os.makedirs(gemini_dir, exist_ok=True)
    
    # Créer un fichier system.md minimal pour éviter les erreurs
    system_md_path = os.path.join(gemini_dir, "system.md")
    with open(system_md_path, 'w', encoding='utf-8') as f:
        f.write("# System Instructions\n\nTest de latence.\n")
    
    # Générer payload de test
    payload_choice = input("\nTaille du payload de test? (1=simple ~100 chars, 2=moyen ~2000 chars, 3=gros ~20000 chars) [défaut: 3]: ").strip()
    if payload_choice == '1':
        payload_size = 100
        payload = "Répondez simplement: Test de latence. Dites juste 'OK'."
        static_prompt = ""  # Pas de contexte statique pour test simple
        dynamic_prompt = payload
    elif payload_choice == '2':
        payload_size = 2000
        payload = generate_test_payload(payload_size)
        # Diviser approximativement : 70% statique, 30% dynamique (comme en réel)
        split_point = int(len(payload) * 0.7)
        static_prompt = payload[:split_point]
        dynamic_prompt = payload[split_point:]
    else:
        payload_size = 20000
        payload = generate_test_payload(payload_size)
        # Diviser approximativement : 70% statique, 30% dynamique (comme en réel)
        split_point = int(len(payload) * 0.7)
        static_prompt = payload[:split_point]
        dynamic_prompt = payload[split_point:]
    
    print(f"\n📦 Payload de test: {len(payload)} chars")
    if static_prompt:
        print(f"  - Contexte statique: {len(static_prompt)} chars")
        print(f"  - Message dynamique: {len(dynamic_prompt)} chars")
    
    # Exécuter les tests
    results = {}
    
    print("\n" + "="*80)
    print("LANCEMENT DES TESTS")
    print("="*80)
    
    # Variante A: Pipe stdin (actuelle)
    results['variant_a_pipe'] = test_variant_a_pipe_stdin(cmd_base, workdir, env, payload)
    time.sleep(2)  # Pause entre tests
    
    # Variante B: Fichier + redirection
    results['variant_b_file'] = test_variant_b_file_redirection(cmd_base, workdir, env, payload)
    time.sleep(2)
    
    # Variante C: Argument --prompt
    results['variant_c_prompt'] = test_variant_c_prompt_arg(cmd_base, workdir, env, payload)
    time.sleep(2)
    
    # Variante A2: Reproduction EXACTE du pool (static + dynamic)
    if static_prompt:
        results['variant_a2_pool_exact'] = test_variant_a2_pool_exact_reproduction(
            cmd_base, workdir, env, static_prompt, dynamic_prompt
        )
        time.sleep(2)
    
    # Test Shell (optionnel, peut être long)
    shell_test = input("\n❓ Exécuter le test équivalent shell pour comparaison? (o/N): ").strip().lower()
    if shell_test == 'o':
        results['shell_equivalent'] = test_shell_equivalent(cmd_base, payload, workdir, env)
    
    # Rapport final
    print("\n" + "="*80)
    print("RAPPORT FINAL - COMPARAISON DES MÉTHODES")
    print("="*80)
    
    print("\n⏱️  TEMPS CRITIQUE: stdin.close() → première ligne stdout")
    print("-" * 80)
    
    if 'time_to_first_line' in results['variant_a_pipe']:
        time_a = results['variant_a_pipe']['time_to_first_line']
        print(f"  Variante A (Pipe stdin):      {time_a:>10.2f}ms  {'⚠️ LATENCE ÉLEVÉE' if time_a > 2000 else '✓'}")
    
    if 'time_to_first_line' in results['variant_b_file']:
        time_b = results['variant_b_file']['time_to_first_line']
        print(f"  Variante B (Fichier):         {time_b:>10.2f}ms  {'⚠️ LATENCE ÉLEVÉE' if time_b > 2000 else '✓'}")
    
    if 'time_to_first_line' in results['variant_c_prompt']:
        time_c = results['variant_c_prompt']['time_to_first_line']
        print(f"  Variante C (--prompt arg):    {time_c:>10.2f}ms  {'⚠️ LATENCE ÉLEVÉE' if time_c > 2000 else '✓'}")
    
    if 'variant_a2_pool_exact' in results:
        if 'time_to_first_line' in results['variant_a2_pool_exact']:
            time_a2 = results['variant_a2_pool_exact']['time_to_first_line']
            print(f"  Variante A2 (Pool exact):     {time_a2:>10.2f}ms  {'⚠️ LATENCE ÉLEVÉE' if time_a2 > 2000 else '✓'}")
    
    if 'shell_equivalent' in results:
        if 'shell_time_to_first_line' in results['shell_equivalent']:
            time_shell = results['shell_equivalent']['shell_time_to_first_line']
            print(f"  Shell équivalent (référence):   {time_shell:>10.2f}ms  (référence)")
        elif 'shell_total_time' in results['shell_equivalent']:
            time_shell = results['shell_equivalent']['shell_total_time']
            print(f"  Shell équivalent (référence):   {time_shell:>10.2f}ms  (référence - total)")
    
    print("\n📊 RECOMMANDATIONS:")
    print("-" * 80)
    
    times = {}
    if 'time_to_first_line' in results['variant_a_pipe']:
        times['A'] = results['variant_a_pipe']['time_to_first_line']
    if 'time_to_first_line' in results['variant_b_file']:
        times['B'] = results['variant_b_file']['time_to_first_line']
    if 'time_to_first_line' in results['variant_c_prompt']:
        times['C'] = results['variant_c_prompt']['time_to_first_line']
    if 'variant_a2_pool_exact' in results:
        if 'time_to_first_line' in results['variant_a2_pool_exact']:
            times['A2'] = results['variant_a2_pool_exact']['time_to_first_line']
    
    if times:
        fastest = min(times.items(), key=lambda x: x[1])
        print(f"  → Méthode la plus rapide: Variante {fastest[0]} ({fastest[1]:.2f}ms)")
        
        if fastest[0] == 'B':
            print(f"  → RECOMMANDATION: Utiliser fichier temporaire + redirection stdin")
            print(f"     (Modifier gemini_cli_process_pool.py pour écrire dans un fichier au lieu d'un pipe)")
        elif fastest[0] == 'C':
            print(f"  → RECOMMANDATION: Utiliser argument --prompt (si taille permet)")
            print(f"     (Attention: limite Windows ~8191 chars pour les arguments)")
        elif fastest[0] == 'A2':
            print(f"  → Variante A2 reproduit le comportement du pool (static + dynamic)")
            print(f"     Si A2 est plus lent que A, le problème vient de l'écriture en deux temps")
            print(f"     ou du flush() de la partie statique")
        else:
            print(f"  → La méthode actuelle (Pipe stdin) est déjà la plus rapide")
            print(f"     Le problème de latence pourrait venir d'ailleurs (cache, réseau, etc.)")
    
    # Nettoyage
    try:
        shutil.rmtree(workdir, ignore_errors=True)
    except:
        pass
    
    print("\n✓ Test terminé")
    return 0


if __name__ == "__main__":
    sys.exit(main())


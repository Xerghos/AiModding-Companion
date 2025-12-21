# Documentation Technique du Module `features.audio`

## En-tête

*   **Titre**: Module de Gestion Audio (ASR & TTS)
*   **Description concise**: Ce module gère les fonctionnalités audio de l'application, incluant la reconnaissance vocale (ASR) et la synthèse vocale (TTS). Il implémente un mécanisme de chargement différé (lazy loading) pour les bibliothèques audio lourdes afin d'optimiser le temps de démarrage. Il interagit avec l'API Google Gemini pour la synthèse vocale.
*   **Dépendances**:
    *   **Internes**:
        *   `config`: Pour la configuration globale (`get_path`, `get_logger`, `APP_SETTINGS`).
        *   `features.Decorators`: Pour le décorateur de traçage (`trace_action`).
    *   **Externes (Chargées directement)**:
        *   `logging`: Pour la journalisation.
        *   `os`: Pour les opérations sur le système de fichiers.
        *   `threading`: Pour la gestion des threads.
        *   `base64`: Pour l'encodage/décodage de données Base64.
        *   `requests`: Pour les requêtes HTTP aux API externes.
        *   `json`: Pour la manipulation de données JSON.
        *   `traceback`: Pour l'affichage des traces d'erreurs détaillées.
    *   **Externes (Chargement différé)**:
        *   `speech_recognition`: Pour la reconnaissance vocale.
        *   `sounddevice`: Pour l'enregistrement et la lecture audio.
        *   `numpy`: Pour la manipulation de données numériques (tableaux audio).
        *   `scipy.io.wavfile.write`: Pour l'écriture de fichiers WAV.

---

## Classes & Fonctions

Ce module ne contient pas de classes, seulement des constantes, des variables globales et des fonctions.

### Constantes Globales

*   `AUDIO_CACHE_DIR`: Chemin d'accès au répertoire de cache audio.
    *   **Type**: `str`
    *   **Description**: Défini via `get_path("audio_cache")`. Utilisé pour stocker des fichiers audio temporaires ou mis en cache.
*   `TEMP_RECORDING_FILE`: Chemin d'accès au fichier temporaire pour les enregistrements audio.
    *   **Type**: `str`
    *   **Description**: Défini via `get_path("temp_audio.wav")`. Utilisé par la fonction `listen_and_recognize_thread`.
*   `SAMPLE_RATE_INPUT`: Fréquence d'échantillonnage pour l'entrée audio (enregistrement).
    *   **Type**: `int`
    *   **Valeur**: `44100` Hz.
*   `SAMPLE_RATE_OUTPUT`: Fréquence d'échantillonnage pour la sortie audio (lecture TTS).
    *   **Type**: `int`
    *   **Valeur**: `24000` Hz.

### Variables Globales (Lazy Loading)

Ces variables sont initialisées à `None` et chargées dynamiquement lors du premier appel à `_ensure_audio_libs()`.

*   `sr`: Module `speech_recognition`.
*   `sd`: Module `sounddevice`.
*   `np`: Module `numpy`.
*   `write_wav`: Fonction `write` du module `scipy.io.wavfile`.
*   `AUDIO_LIBS_LOADED`: Indique si les bibliothèques audio lourdes ont été tentées de charger.
    *   **Type**: `bool`
    *   **Valeur initiale**: `False`.
*   `AUDIO_AVAILABLE`: Indique si les bibliothèques audio lourdes ont été chargées avec succès et sont utilisables.
    *   **Type**: `bool`
    *   **Valeur initiale**: `False`.

### Fonctions

#### `_ensure_audio_libs()`

Charge les bibliothèques audio lourdes (sounddevice, numpy, speech_recognition, scipy) de manière différée. Cette fonction est bloquante (quelques secondes) lors du PREMIER appel uniquement.

*   **Signature**: `_ensure_audio_libs() -> bool`
*   **Arguments**: Aucun.
*   **Retours**:
    *   `bool`: `True` si toutes les bibliothèques nécessaires sont chargées et disponibles, `False` sinon (en cas d'`ImportError` ou autre exception).
*   **Logique interne**:
    1.  Vérifie si les bibliothèques ont déjà été chargées (`AUDIO_LIBS_LOADED`). Si oui, retourne l'état de `AUDIO_AVAILABLE`.
    2.  Tente d'importer `speech_recognition` (as `_sr`), `sounddevice` (as `_sd`), `numpy` (as `_np`), et `scipy.io.wavfile.write` (as `_write_wav`).
    3.  Si l'importation réussit, assigne ces modules aux variables globales `sr`, `sd`, `np`, `write_wav`.
    4.  Met à jour `AUDIO_LIBS_LOADED` à `True` et `AUDIO_AVAILABLE` à `True`.
    5.  En cas d'`ImportError`, journalise un avertissement et met `AUDIO_AVAILABLE` à `False`.
    6.  En cas d'autre exception, journalise une erreur critique et met `AUDIO_AVAILABLE` à `False`.
    7.  Retourne la valeur finale de `AUDIO_AVAILABLE`.

#### `init_audio()`

Initialise le répertoire de cache audio. Cette opération est légère.

*   **Signature**: `init_audio() -> None`
*   **Arguments**: Aucun.
*   **Retours**: Aucun.
*   **Logique interne**:
    1.  Vérifie si le répertoire spécifié par `AUDIO_CACHE_DIR` existe.
    2.  Si le répertoire n'existe pas, il est créé à l'aide de `os.makedirs()`.

#### `is_audio_enabled()`

Retourne l'état de disponibilité des fonctionnalités audio.

*   **Signature**: `is_audio_enabled() -> tuple[bool, bool]`
*   **Arguments**: Aucun.
*   **Retours**:
    *   `tuple[bool, bool]`:
        *   Le premier élément indique si l'interface utilisateur peut afficher l'audio comme "potentiellement" disponible (optimiste).
        *   Le second élément indique l'état réel de disponibilité de l'audio si les bibliothèques ont déjà été chargées.
*   **Logique interne**:
    1.  Si `AUDIO_LIBS_LOADED` est `True`, retourne `(AUDIO_AVAILABLE, AUDIO_AVAILABLE)`.
    2.  Sinon (si le chargement différé n'a pas encore eu lieu), retourne `(True, True)` pour indiquer un état optimiste à l'UI, évitant un ralentissement au démarrage. L'erreur surviendra lors de la première utilisation.

#### `listen_and_recognize_thread()`

Fonction exécutée dans un thread pour effectuer la reconnaissance vocale (ASR).

*   **Signature**: `listen_and_recognize_thread(result_queue: queue.Queue, record_duration: int = 5) -> None`
*   **Arguments**:
    *   `result_queue` (`queue.Queue`): Une file d'attente utilisée pour communiquer les événements (résultats ASR, erreurs, mises à jour UI) au thread principal ou à l'interface utilisateur.
    *   `record_duration` (`int`, optionnel): La durée de l'enregistrement audio en secondes. Par défaut à `5`.
*   **Retours**: Aucun.
*   **Logique interne**:
    1.  Appelle `_ensure_audio_libs()` pour s'assurer que les bibliothèques audio sont chargées. Si elles ne sont pas disponibles, envoie une erreur via `result_queue` et se termine.
    2.  Crée une instance de `speech_recognition.Recognizer`.
    3.  Envoie une mise à jour UI via `result_queue` pour indiquer que l'écoute commence.
    4.  Utilise `sounddevice.rec()` pour enregistrer l'audio pendant `record_duration` secondes au `SAMPLE_RATE_INPUT`.
    5.  Utilise `sounddevice.wait()` pour attendre la fin de l'enregistrement.
    6.  Sauvegarde les données audio enregistrées dans `TEMP_RECORDING_FILE` au format WAV en utilisant `write_wav`.
    7.  Envoie une mise à jour UI pour indiquer la transcription.
    8.  Ouvre le fichier WAV temporaire avec `sr.AudioFile` et utilise `r.record()` pour en extraire les données audio.
    9.  Transcrit l'audio en texte en utilisant `r.recognize_google()` avec la langue 'fr-FR'.
    10. Envoie le texte reconnu via `result_queue` sous le type `asr_done`.
    11. Gère les exceptions spécifiques de `speech_recognition` (`UnknownValueError`, `RequestError`) et d'autres exceptions génériques, en envoyant des erreurs via `result_queue`.
    12. Dans le bloc `finally`, tente de supprimer le fichier `TEMP_RECORDING_FILE`.

#### `_gemini_tts_request()`

Fonction utilitaire interne pour appeler l'API Gemini TTS et récupérer l'audio.

*   **Signature**: `_gemini_tts_request(text: str, api_key: str) -> numpy.ndarray`
*   **Arguments**:
    *   `text` (`str`): Le texte à convertir en parole.
    *   `api_key` (`str`): La clé API pour authentifier la requête auprès de l'API Gemini.
*   **Retours**:
    *   `numpy.ndarray`: Un tableau NumPy contenant les données audio PCM (Pulse-code modulation) au format `int16`.
*   **Logique interne**:
    1.  Construit l'URL de l'API Gemini TTS.
    2.  Crée le corps de la requête JSON, spécifiant le texte à convertir, la modalité de réponse `AUDIO` et le modèle `gemini-2.5-flash-preview-tts`.
    3.  Envoie une requête POST à l'API Gemini avec `requests.post()`.
    4.  Lève une `requests.exceptions.HTTPError` si la requête échoue.
    5.  Parse la réponse JSON et extrait les données audio encodées en Base64.
    6.  Décode les données Base64 en octets bruts.
    7.  Convertit les octets audio en un tableau NumPy (`np.frombuffer`) avec un type de données `int16`.
    8.  Lève une `ValueError` si la réponse de l'API ne contient pas les données audio attendues.

#### `speak_text_thread()`

Fonction exécutée dans un thread pour effectuer la synthèse vocale (TTS).

*   **Signature**: `speak_text_thread(text: str, api_key: str, result_queue: queue.Queue) -> None`
*   **Arguments**:
    *   `text` (`str`): Le texte que l'on souhaite faire prononcer.
    *   `api_key` (`str`): La clé API nécessaire pour l'authentification auprès du service Gemini TTS.
    *   `result_queue` (`queue.Queue`): Une file d'attente pour communiquer l'état et les résultats (succès TTS, erreurs, mises à jour UI) au thread principal.
*   **Retours**: Aucun.
*   **Logique interne**:
    1.  Appelle `_ensure_audio_libs()` pour s'assurer que les bibliothèques audio sont chargées. Si elles ne sont pas disponibles, envoie une erreur via `result_queue` et se termine.
    2.  Envoie une mise à jour UI pour indiquer le début de la génération vocale.
    3.  Appelle `_gemini_tts_request()` pour obtenir les données audio PCM à partir du texte.
    4.  Envoie une mise à jour UI pour indiquer la lecture audio.
    5.  Utilise `sounddevice.play()` pour lire les données audio (`pcm_data`) au `SAMPLE_RATE_OUTPUT`.
    6.  Utilise `sd.wait()` pour attendre la fin de la lecture.
    7.  Envoie un message `tts_done` via `result_queue` une fois la lecture terminée.
    8.  Gère les exceptions, journalise les erreurs et envoie un message `tts_error` via `result_queue`.

---

## Exemple d'usage

Voici un exemple simplifié montrant comment utiliser les fonctions `listen_and_recognize_thread` et `speak_text_thread` avec une file d'attente pour la communication inter-threads.

```python
import threading
import queue
import time
from unittest.mock import MagicMock # Pour simuler APP_SETTINGS si besoin pour un test unitaire

# --- Simuler les dépendances externes minimales pour l'exemple ---
# (Dans une application réelle, ces imports seraient gérés par le module parent)
class MockAppSettings:
    GEMINI_API_KEY = "YOUR_GEMINI_API_KEY" # Remplacez par une vraie clé ou une mock
APP_SETTINGS = MockAppSettings()

# Pour l'exemple, nous allons mocker les fonctions de logging et get_path pour éviter les erreurs
# lors de l'exécution en dehors de l'écosystème de l'application.
# Dans un usage réel, vous n'auriez pas besoin de ces mocks.
class MockLogger:
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): print(f"ERROR: {msg}") # Afficher les erreurs pour le debug de l'exemple

log = MockLogger()
def get_path(name):
    if name == "audio_cache":
        return "temp_audio_cache"
    if name == "temp_audio.wav":
        return "temp_audio.wav"
    return name

# Si vous exécutez ce code, vous aurez besoin de `import speech_recognition as sr`, etc.
# Pour l'exemple, on peut même les mocker si on ne veut pas les installer.
# Ici on va appeler les vraies fonctions du module `features.audio`
# assurez-vous que les bibliothèques (speech_recognition, sounddevice, numpy, scipy) sont installées.

# --- Code du module features.audio importé ou copié ici pour l'exemple ---
# (Dans un vrai projet, vous feriez : from features import audio)

# Copier/coller ici le contenu de features/audio.py, en s'assurant que les mocks
# de log, get_path, et APP_SETTINGS sont bien pris en compte par le code.

# --- Début de l'exemple ---

# Assurez-vous d'avoir exécuté init_audio() au démarrage de votre application
# features.audio.init_audio()

def main_application_thread():
    """Simule le thread principal de l'application."""
    print("Application démarrée.")
    
    # Initialisation du cache audio
    # audio.init_audio() # Si le module était importé
    # Ici, nous appelons directement la fonction (comme si c'était dans le même fichier)
    if not os.path.exists(AUDIO_CACHE_DIR):
        os.makedirs(AUDIO_CACHE_DIR)
        print(f"Cache audio créé: {AUDIO_CACHE_DIR}")

    # Vérifier si l'audio est activé (et forcer le lazy loading pour l'exemple)
    print("Vérification de l'état audio...")
    audio_ui_status, audio_real_status = is_audio_enabled()
    print(f"Statut UI audio: {audio_ui_status}, Statut réel audio: {audio_real_status}")
    
    # S'assurer que les libs sont chargées pour le test (normalement fait par les threads eux-mêmes)
    if not AUDIO_LIBS_LOADED:
        _ensure_audio_libs()
        print(f"Lazy loading manuel effectué. Audio disponible: {AUDIO_AVAILABLE}")
    
    # Création d'une file d'attente pour les résultats
    result_queue = queue.Queue()

    # --- Exemple ASR ---
    print("\n--- Démonstration ASR ---")
    print("Démarrage du thread d'écoute pour 5 secondes...")
    asr_thread = threading.Thread(target=listen_and_recognize_thread, args=(result_queue, 5))
    asr_thread.start()

    # Attente des résultats ASR
    asr_result = None
    while asr_thread.is_alive() or not result_queue.empty():
        try:
            message = result_queue.get(timeout=1)
            print(f"[Main App] Message de l'ASR: {message}")
            if message['type'] == 'asr_done':
                asr_result = message['text']
                break
            elif message['type'] == 'asr_error':
                print(f"[Main App] Erreur ASR: {message['error']}")
                break
        except queue.Empty:
            pass
    asr_thread.join() # S'assurer que le thread est terminé

    if asr_result:
        print(f"\n[Main App] Texte reconnu: '{asr_result}'")
        text_to_speak = f"J'ai compris : {asr_result}. Maintenant je vais le répéter."
    else:
        text_to_speak = "Je n'ai rien compris ou il y a eu une erreur."
    
    # --- Exemple TTS ---
    print("\n--- Démonstration TTS ---")
    print(f"Démarrage du thread de parole pour: '{text_to_speak}'")
    tts_thread = threading.Thread(target=speak_text_thread, args=(text_to_speak, APP_SETTINGS.GEMINI_API_KEY, result_queue))
    tts_thread.start()

    # Attente des résultats TTS
    while tts_thread.is_alive() or not result_queue.empty():
        try:
            message = result_queue.get(timeout=1)
            print(f"[Main App] Message du TTS: {message}")
            if message['type'] == 'tts_done':
                print("[Main App] Lecture TTS terminée.")
                break
            elif message['type'] == 'tts_error':
                print(f"[Main App] Erreur TTS: {message['error']}")
                break
        except queue.Empty:
            pass
    tts_thread.join()

    print("\nApplication terminée.")
    
    # Nettoyage
    if os.path.exists(AUDIO_CACHE_DIR):
        try:
            os.rmdir(AUDIO_CACHE_DIR) # Seulement si vide, sinon un rmtree est nécessaire
            print(f"Cache audio nettoyé: {AUDIO_CACHE_DIR}")
        except OSError:
            pass # Si le répertoire n'est pas vide (ex: fichier temp.wav non supprimé)


if __name__ == "__main__":
    # Pour exécuter cet exemple, assurez-vous que les bibliothèques sont installées :
    # pip install speechrecognition sounddevice numpy scipy requests
    # Et que vous avez une clé API Gemini valide dans APP_SETTINGS.GEMINI_API_KEY
    
    # Créer un répertoire pour temp_audio_cache si ce n'est pas fait (par init_audio)
    if not os.path.exists("temp_audio_cache"):
        os.makedirs("temp_audio_cache")

    main_application_thread()

    # Nettoyage après l'exécution si le dossier n'a pas été supprimé par l'exemple
    if os.path.exists("temp_audio_cache"):
        # Utiliser shutil.rmtree si le dossier peut contenir d'autres fichiers
        import shutil
        shutil.rmtree("temp_audio_cache", ignore_errors=True)
        print("Dossier temp_audio_cache supprimé.")
    if os.path.exists("temp_audio.wav"):
        os.remove("temp_audio.wav")
        print("Fichier temp_audio.wav supprimé.")
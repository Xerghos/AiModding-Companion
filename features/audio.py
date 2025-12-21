import logging
import os
import threading
import base64
import requests
import json
import traceback

from config import get_path, get_logger, APP_SETTINGS
from features.Decorators import trace_action

log = get_logger(__name__)

# --- Constantes Audio ---
AUDIO_CACHE_DIR = get_path("audio_cache")
TEMP_RECORDING_FILE = get_path("temp_audio.wav")
SAMPLE_RATE_INPUT = 44100
SAMPLE_RATE_OUTPUT = 24000

# --- Variables Globales pour le Lazy Loading ---
# Ces variables stockeront les modules une fois chargés
sr = None
sd = None
np = None
write_wav = None

# État du chargement
AUDIO_LIBS_LOADED = False
AUDIO_AVAILABLE = False

@trace_action(source="audio")
def _ensure_audio_libs():
    """
    Charge les bibliothèques audio lourdes (Lazy Loading).
    Cette fonction est bloquante (quelques secondes) lors du PREMIER appel uniquement.
    """
    global sr, sd, np, write_wav, AUDIO_LIBS_LOADED, AUDIO_AVAILABLE

    if AUDIO_LIBS_LOADED:
        return AUDIO_AVAILABLE

    log.info("Chargement différé des bibliothèques audio (sounddevice, numpy, speech_recognition)...")
    try:
        import speech_recognition as _sr
        import sounddevice as _sd
        import numpy as _np
        from scipy.io.wavfile import write as _write_wav
        
        # Assignation aux globales
        sr = _sr
        sd = _sd
        np = _np
        write_wav = _write_wav
        
        AUDIO_LIBS_LOADED = True
        AUDIO_AVAILABLE = True
        log.info("Bibliothèques audio chargées avec succès.")
        return True
        
    except ImportError as e:
        log.warning(f"Bibliothèques audio manquantes : {e}. L'audio sera désactivé.")
        AUDIO_LIBS_LOADED = True
        AUDIO_AVAILABLE = False
        return False
    except Exception as e:
        log.error(f"Erreur critique lors du chargement audio : {traceback.format_exc()}")
        AUDIO_LIBS_LOADED = True
        AUDIO_AVAILABLE = False
        return False

@trace_action(source="audio")
def init_audio():
    """Initialise le cache audio (opération légère)."""
    if not os.path.exists(AUDIO_CACHE_DIR):
        os.makedirs(AUDIO_CACHE_DIR)

@trace_action(source="audio")
def is_audio_enabled():
    """
    Retourne l'état de disponibilité de l'audio.
    Pour ne pas ralentir le démarrage, on est 'optimiste' : on retourne True par défaut
    si les libs ne sont pas encore chargées. L'erreur surviendra à l'utilisation.
    """
    if AUDIO_LIBS_LOADED:
        return AUDIO_AVAILABLE, AUDIO_AVAILABLE
    return True, True # Optimiste pour l'UI

# --- TÂCHES DE THREAD (ASR / TTS) ---

@trace_action(source="audio")
def listen_and_recognize_thread(result_queue, record_duration=5):
    """
    Effectue l'ASR (Reconnaissance Vocale).
    Déclenche le chargement des libs si nécessaire.
    """
    # 1. Lazy Loading
    if not _ensure_audio_libs():
        result_queue.put({'type': 'asr_error', 'error': "Bibliothèques audio non disponibles."})
        return

    r = sr.Recognizer()
    try:
        # [LOG_CLEANED] log.info(f"Démarrage de l'enregistrement ({record_duration}s)...")
        result_queue.put({'type': 'ui_update', 'widget': 'message', 'text': "--- Écoute en cours... ---"})
        
        # 2. Enregistrement avec sounddevice
        recording = sd.rec(int(record_duration * SAMPLE_RATE_INPUT), samplerate=SAMPLE_RATE_INPUT, channels=1, dtype='int16')
        sd.wait()  # Attend la fin
        
        log.info("Enregistrement terminé. Sauvegarde en WAV...")

        # 3. Sauvegarde WAV
        write_wav(TEMP_RECORDING_FILE, SAMPLE_RATE_INPUT, recording)

        log.info("Fichier WAV sauvegardé. Transcription...")
        result_queue.put({'type': 'ui_update', 'widget': 'message', 'text': "--- Transcription... ---"})

        # 4. Transcrire
        with sr.AudioFile(TEMP_RECORDING_FILE) as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data, language='fr-FR')
        
        log.info(f"Texte reconnu: {text}")
        result_queue.put({'type': 'asr_done', 'text': text})

    except sr.UnknownValueError:
        log.warning("ASR: Audio non compris")
        result_queue.put({'type': 'asr_error', 'error': "Audio non compris."})
    except sr.RequestError as e:
        log.error(f"ASR: Erreur Google: {e}")
        result_queue.put({'type': 'asr_error', 'error': "Erreur service Google."})
    except Exception as e:
        log.error(f"Erreur ASR: {traceback.format_exc()}")
        result_queue.put({'type': 'asr_error', 'error': str(e)})
    finally:
        try:
            if os.path.exists(TEMP_RECORDING_FILE):
                os.remove(TEMP_RECORDING_FILE)
        except Exception:
            pass

@trace_action(source="audio")
def _gemini_tts_request(text, api_key):
    """Appelle l'API Gemini TTS (Nécessite requests, déjà chargé)."""
    # ... (Code identique, pas de libs lourdes ici sauf numpy qui est géré dans speak_text_thread)
    log.info("TTS: Appel de l'API Gemini TTS...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": f"Parle en français: {text}"}] 
        }],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {}
            }
        },
        "model": "gemini-2.5-flash-preview-tts"
    }

    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, data=json.dumps(payload, ensure_ascii=False), headers=headers)
    response.raise_for_status()

    res_json = response.json()
    part = res_json['candidates'][0]['content']['parts'][0]
    
    if 'inlineData' not in part:
        raise ValueError("Audio manquant dans la réponse API.")
        
    base64_data = part['inlineData']['data']
    audio_bytes = base64.b64decode(base64_data)
    
    # On a besoin de numpy ici, on suppose qu'il est chargé par l'appelant
    return np.frombuffer(audio_bytes, dtype=np.int16)

@trace_action(source="audio")
def speak_text_thread(text, api_key, result_queue):
    """Effectue le TTS. Déclenche le chargement des libs."""
    # 1. Lazy Loading
    if not _ensure_audio_libs():
        result_queue.put({'type': 'tts_error', 'error': "Bibliothèques audio non disponibles."})
        return

    try:
        log.info("TTS: Génération de l'audio...")
        result_queue.put({'type': 'ui_update', 'widget': 'message', 'text': "--- Génération de la parole... ---"})
        
        # 2. Appel API (utilise numpy chargé dynamiquement)
        pcm_data = _gemini_tts_request(text, api_key)
        
        log.info("TTS: Lecture audio...")
        result_queue.put({'type': 'ui_update', 'widget': 'message', 'text': "--- Lecture audio... ---"})
        
        # 3. Lecture sounddevice
        sd.play(pcm_data, samplerate=SAMPLE_RATE_OUTPUT)
        sd.wait()
            
        log.info("TTS: Lecture terminée.")
        result_queue.put({'type': 'tts_done'})

    except Exception as e:
        log.error(f"Erreur TTS: {traceback.format_exc()}")
        result_queue.put({'type': 'tts_error', 'error': str(e)})
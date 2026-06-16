"""Audio recording and Whisper transcription."""
import threading
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000

# ── audio backend ─────────────────────────────────────────────────────────────
try:
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print('[voice] sounddevice not available — pip install sounddevice')

# ── whisper backend (prefer faster-whisper) ───────────────────────────────────
_model        = None
WHISPER_BACKEND = None

try:
    from faster_whisper import WhisperModel
    _model          = WhisperModel('tiny', device='cpu', compute_type='float32')
    WHISPER_BACKEND = 'faster'
    print('[voice] faster-whisper tiny/int8 loaded')
except ImportError:
    try:
        import whisper as _ws
        _model          = _ws.load_model('tiny')
        WHISPER_BACKEND = 'openai'
        print('[voice] openai-whisper tiny loaded')
    except ImportError:
        print('[voice] no whisper backend — pip install faster-whisper')

AVAILABLE = AUDIO_AVAILABLE and WHISPER_BACKEND is not None

# ── internal state ─────────────────────────────────────────────────────────────
_frames: list  = []
_stream        = None
_lock          = threading.Lock()


# ── public API ────────────────────────────────────────────────────────────────

def start_recording() -> bool:
    """Begin capturing audio from the default microphone. Returns True on success."""
    global _stream
    if not AUDIO_AVAILABLE:
        return False

    with _lock:
        _frames.clear()

    def _cb(indata, n, t, status):
        with _lock:
            _frames.append(indata.copy())

    try:
        _stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype='int16',
            callback=_cb, blocksize=1024,
        )
        _stream.start()
        print('[voice] recording started')
        return True
    except Exception as e:
        print(f'[voice] start error: {e}')
        return False


def stop_and_transcribe() -> str:
    """Stop recording and return Whisper transcription (blocking, ~2-5 s on Pi 5)."""
    global _stream
    _stop_stream()

    with _lock:
        frames = list(_frames)

    if not frames or _model is None:
        return ''

    audio = np.concatenate(frames, axis=0).flatten().astype(np.float32) / 32768.0
    print(f'[voice] transcribing {len(audio) / SAMPLE_RATE:.1f}s…')

    try:
        if WHISPER_BACKEND == 'faster':
            segs, _ = _model.transcribe(audio, language='en', vad_filter=True)
            text = ' '.join(s.text for s in segs).strip()
        else:
            result = _model.transcribe(audio, fp16=False, language='en')
            text = result['text'].strip()
        print(f'[voice] → {text!r}')
        return text
    except Exception as e:
        print(f'[voice] transcription error: {e}')
        return ''


def stop_and_save(path: str) -> float:
    """Stop recording and save raw audio as WAV. Returns duration in seconds."""
    _stop_stream()

    with _lock:
        frames = list(_frames)

    if not frames:
        return 0.0

    audio    = np.concatenate(frames, axis=0)
    duration = len(audio) / SAMPLE_RATE

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

    print(f'[voice] saved {duration:.1f}s → {path}')
    return duration


def recording_duration() -> float:
    """Approximate seconds recorded so far (without stopping)."""
    with _lock:
        if not _frames:
            return 0.0
        return sum(len(f) for f in _frames) / SAMPLE_RATE


# ── internal ──────────────────────────────────────────────────────────────────

def _stop_stream():
    global _stream
    if _stream is not None:
        try:
            _stream.stop()
            _stream.close()
        except Exception:
            pass
        _stream = None

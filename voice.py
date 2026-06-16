"""Audio recording and Whisper transcription."""
import threading
import wave
from pathlib import Path

import numpy as np

WHISPER_RATE = 16000   # Whisper always needs 16 kHz

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
    print('[voice] faster-whisper tiny loaded')
except ImportError:
    try:
        import whisper as _ws
        _model          = _ws.load_model('tiny')
        WHISPER_BACKEND = 'openai'
        print('[voice] openai-whisper tiny loaded')
    except ImportError:
        print('[voice] no whisper backend — pip install faster-whisper')

AVAILABLE = AUDIO_AVAILABLE and WHISPER_BACKEND is not None

# ── device sample rate (resolved once at startup) ─────────────────────────────
_device_rate: int = WHISPER_RATE   # updated below if 16 kHz isn't supported

if AUDIO_AVAILABLE:
    def _probe_rate() -> int:
        """Return the best recording rate for the default input device."""
        try:
            native = int(sd.query_devices(kind='input')['default_samplerate'])
        except Exception:
            native = 44100

        for rate in (WHISPER_RATE, native, 48000, 44100, 22050):
            try:
                with sd.InputStream(samplerate=rate, channels=1, dtype='int16'):
                    pass
                print(f'[voice] device sample rate: {rate} Hz')
                return rate
            except Exception:
                continue

        print(f'[voice] falling back to native rate {native} Hz')
        return native

    _device_rate = _probe_rate()

# ── internal state ─────────────────────────────────────────────────────────────
_frames: list = []
_stream       = None
_lock         = threading.Lock()


# ── helpers ───────────────────────────────────────────────────────────────────

def _resample(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Linear resample — fast and good enough for speech."""
    if from_rate == to_rate:
        return audio
    new_len = int(round(len(audio) * to_rate / from_rate))
    return np.interp(
        np.linspace(0, len(audio) - 1, new_len),
        np.arange(len(audio)),
        audio,
    ).astype(np.float32)


# ── public API ────────────────────────────────────────────────────────────────

def start_recording() -> bool:
    """Begin capturing audio from the default microphone."""
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
            samplerate=_device_rate, channels=1, dtype='int16',
            callback=_cb, blocksize=1024,
        )
        _stream.start()
        print(f'[voice] recording at {_device_rate} Hz…')
        return True
    except Exception as e:
        print(f'[voice] start error: {e}')
        return False


def stop_and_transcribe() -> str:
    """Stop recording and return Whisper transcription (~2-5 s on Pi 5)."""
    _stop_stream()

    with _lock:
        frames = list(_frames)

    if not frames or _model is None:
        return ''

    raw   = np.concatenate(frames, axis=0).flatten().astype(np.float32) / 32768.0
    audio = _resample(raw, _device_rate, WHISPER_RATE)
    print(f'[voice] transcribing {len(audio) / WHISPER_RATE:.1f}s…')

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
    """Stop recording and save WAV at the device's native rate."""
    _stop_stream()

    with _lock:
        frames = list(_frames)

    if not frames:
        return 0.0

    audio    = np.concatenate(frames, axis=0)
    duration = len(audio) / _device_rate

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(_device_rate)
        wf.writeframes(audio.tobytes())

    print(f'[voice] saved {duration:.1f}s → {path}')
    return duration


def recording_duration() -> float:
    """Approximate seconds recorded so far."""
    with _lock:
        if not _frames:
            return 0.0
        return sum(len(f) for f in _frames) / _device_rate


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

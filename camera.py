"""
Persistent Picamera2 wrapper for the camera screen.

start()  → spawns a daemon thread that inits the camera and loops preview captures
stop()   → signals the thread to exit and closes the camera
capture_still() → saves last_photo.jpg and a timestamped copy to static/photos/
"""
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

PREVIEW_PATH     = str(Path(__file__).parent / 'static' / 'camera_preview.jpg')
STILL_PATH       = str(Path(__file__).parent / 'static' / 'last_photo.jpg')
PHOTOS_DIR       = Path(__file__).parent / 'static' / 'photos'
PREVIEW_INTERVAL = 0.5   # seconds between preview frames
WARMUP_S         = 1.5   # let the sensor stabilise before first capture

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    PICAMERA_AVAILABLE = False
    print('[camera] picamera2 not available')

_cam      = None
_running  = False
_lock     = threading.Lock()
_on_frame = None


# ── public API ─────────────────────────────────────────────────────────────────

def start(on_frame=None):
    """Start the preview thread (non-blocking)."""
    global _running, _on_frame
    if _running:
        return
    if not PICAMERA_AVAILABLE:
        print('[camera] picamera2 unavailable — no preview')
        return
    _on_frame = on_frame
    _running  = True
    t = threading.Thread(target=_run, daemon=True, name='cam_preview')
    t.start()
    print('[camera] thread started')


def stop():
    """Signal the preview thread to exit and release the camera."""
    global _running
    _running = False
    # _cam is closed by the thread itself once _running becomes False


def capture_still() -> bool:
    """Capture a still photo to STILL_PATH and a timestamped copy in PHOTOS_DIR."""
    with _lock:
        if _cam is None:
            print('[camera] capture_still: camera not ready')
            return False
        try:
            _cam.capture_file(STILL_PATH)
            PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
            ts   = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            dest = PHOTOS_DIR / f'photo_{ts}.jpg'
            shutil.copy2(STILL_PATH, dest)
            print(f'[camera] still saved → {dest}')
            return True
        except Exception as e:
            print(f'[camera] capture_still error: {e}')
            return False


def is_running() -> bool:
    return _running


# ── internal ──────────────────────────────────────────────────────────────────

def _run():
    """Camera thread: init → warm-up → loop."""
    global _cam, _running

    try:
        cam = Picamera2()
        # Simple configuration — no exotic pixel formats
        cfg = cam.create_preview_configuration(
            main={'size': (480, 360)},
        )
        cam.configure(cfg)
        cam.start()
        print(f'[camera] warming up ({WARMUP_S}s)…')
        time.sleep(WARMUP_S)
        with _lock:
            _cam = cam
        print('[camera] preview active')
    except Exception as e:
        print(f'[camera] init error: {e}')
        _running = False
        return

    # Capture loop
    while _running:
        with _lock:
            if _cam is None:
                break
            try:
                _cam.capture_file(PREVIEW_PATH)
            except Exception as e:
                print(f'[camera] frame error: {e}')

        if _on_frame:
            _on_frame()

        time.sleep(PREVIEW_INTERVAL)

    # Clean up
    with _lock:
        if _cam is not None:
            try:
                _cam.stop()
                _cam.close()
            except Exception:
                pass
            _cam = None
    print('[camera] stopped')

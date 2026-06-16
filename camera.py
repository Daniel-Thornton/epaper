"""
Persistent Picamera2 wrapper.

One instance is kept alive while the camera screen is open.
Every PREVIEW_INTERVAL seconds it captures a frame to PREVIEW_PATH
and calls on_frame() so the render loop can redraw.

SELECT → capture_still() saves a full-quality JPEG to STILL_PATH.
"""
import threading
import time
from pathlib import Path

PREVIEW_PATH     = str(Path(__file__).parent / 'static' / 'camera_preview.jpg')
STILL_PATH       = str(Path(__file__).parent / 'static' / 'last_photo.jpg')
PREVIEW_INTERVAL = 0.5   # seconds between preview frames

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


def start(on_frame=None):
    """Open the camera and begin periodic preview captures."""
    global _cam, _running, _on_frame
    if _running:
        return
    if not PICAMERA_AVAILABLE:
        print('[camera] picamera2 unavailable — no preview')
        return

    _on_frame = on_frame
    try:
        _cam = Picamera2()
        cfg  = _cam.create_preview_configuration(
            main={'size': (480, 360), 'format': 'RGB888'},
        )
        _cam.configure(cfg)
        _cam.start()
        time.sleep(0.5)   # sensor warm-up
        _running = True

        t = threading.Thread(target=_loop, daemon=True, name='cam_preview')
        t.start()
        print('[camera] preview started')
    except Exception as e:
        print(f'[camera] start error: {e}')


def stop():
    """Stop preview and close the camera."""
    global _cam, _running
    _running = False
    with _lock:
        if _cam is not None:
            try:
                _cam.stop()
                _cam.close()
            except Exception:
                pass
            _cam = None
    print('[camera] stopped')


def capture_still() -> bool:
    """Save a still to STILL_PATH using the running camera."""
    with _lock:
        if _cam is None:
            return False
        try:
            _cam.capture_file(STILL_PATH)
            print(f'[camera] still saved → {STILL_PATH}')
            return True
        except Exception as e:
            print(f'[camera] capture error: {e}')
            return False


def is_running() -> bool:
    return _running


def _loop():
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

import json
import time
from pathlib import Path
from PIL import Image

def _refresh_rate() -> int:
    """Read refresh_rate from config.json; fall back to 60 s."""
    try:
        cfg = json.loads((Path(__file__).parent / 'data' / 'config.json').read_text())
        return int(cfg.get('refresh_rate', 60))
    except Exception:
        return 60

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print('[render] Playwright not installed — rendering disabled')

from state import state
from display import Display

FRAME_PATH = '/tmp/epaper_frame.png'
FLASK_URL  = 'http://127.0.0.1:5000/'

WEBAPP_URLS = {
    'webapp_chat':     'https://daniel-thornton.github.io/chat/',
    'webapp_calories': 'https://daniel-thornton.github.io/calorie-logger/',
}


class Renderer:
    def __init__(self):
        self._pw      = None
        self._browser = None
        self._page    = None

    def _start(self):
        self._pw      = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._page    = self._browser.new_page(viewport={'width': 480, 'height': 800})
        print('[render] Chromium launched')

    def screenshot(self, path: str) -> bool:
        if not PLAYWRIGHT_AVAILABLE:
            return False
        if self._page is None:
            self._start()
        screen  = state.screen
        url     = WEBAPP_URLS.get(screen, FLASK_URL)
        timeout = 15000 if screen in WEBAPP_URLS else 5000
        try:
            self._page.goto(url, wait_until='networkidle', timeout=timeout)
            self._page.screenshot(path=path)
            return True
        except Exception as e:
            print(f'[render] screenshot error: {e}')
            return False

    def close(self):
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass


def _to_1bit(path: str) -> Image.Image:
    return Image.open(path).convert('L').convert(
        '1', dither=Image.Dither.FLOYDSTEINBERG
    )


def run_loop(display: Display):
    renderer = Renderer()
    state.mark_dirty()  # trigger initial render

    while True:
        # Re-render on input OR after refresh_rate seconds (keeps clock up to date)
        state.dirty.wait(timeout=_refresh_rate())
        state.dirty.clear()
        time.sleep(0.05)   # debounce: let state settle after rapid inputs

        force = state.force_full_refresh
        if force:
            state.force_full_refresh = False

        if renderer.screenshot(FRAME_PATH):
            try:
                img = _to_1bit(FRAME_PATH)
                display.show(img, force_full=force)
            except Exception as e:
                print(f'[render] display error: {e}')

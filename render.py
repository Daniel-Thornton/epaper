import time
from PIL import Image

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
        try:
            self._page.goto(FLASK_URL, wait_until='networkidle', timeout=8000)
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
        # Re-render on input OR every 60 s (keeps clock up to date)
        state.dirty.wait(timeout=60)
        state.dirty.clear()
        time.sleep(0.15)   # debounce: let state settle after rapid inputs

        force = state.force_full_refresh
        if force:
            state.force_full_refresh = False

        if renderer.screenshot(FRAME_PATH):
            try:
                img = _to_1bit(FRAME_PATH)
                display.show(img, force_full=force)
            except Exception as e:
                print(f'[render] display error: {e}')

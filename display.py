import sys
from pathlib import Path
from PIL import Image

try:
    sys.path.insert(0, str(Path(__file__).parent / 'lib'))
    from waveshare_epd import epd4in26
    HW_AVAILABLE = True
except Exception as e:
    print(f'[display] EPD driver not available ({e}) — saving frames to /tmp/epaper_preview.png')
    HW_AVAILABLE = False

PREVIEW_PATH = '/tmp/epaper_preview.png'


class Display:
    PARTIAL_LIMIT = 20

    def __init__(self):
        self._epd = None
        self._partial_count = 0
        if HW_AVAILABLE:
            self._epd = epd4in26.EPD()
            self._epd.init()
            self._epd.Clear()
            print('[display] EPD initialised')

    def show(self, img: Image.Image, force_full: bool = False):
        """Push a 480×800 1-bit PIL Image to the display."""
        if not HW_AVAILABLE:
            # On non-Pi: save preview PNG so the design can be inspected
            img.save(PREVIEW_PATH)
            print(f'[display] preview saved to {PREVIEW_PATH}')
            return

        do_full = force_full or (self._partial_count >= self.PARTIAL_LIMIT)
        if do_full:
            self._epd.init()
            self._epd.display_Base(self._epd.getbuffer(img))
            self._partial_count = 0
        else:
            self._epd.display_Partial(self._epd.getbuffer(img))
            self._partial_count += 1

    def sleep(self):
        if self._epd:
            self._epd.sleep()

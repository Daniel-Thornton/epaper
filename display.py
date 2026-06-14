#!/usr/bin/python3
# -*- coding:utf-8 -*-
import logging
import time
from PIL import Image

logger = logging.getLogger(__name__)

W = 480   # portrait width  (== epd.height == 480)
H = 800   # portrait height (== epd.width  == 800)

PARTIAL_LIMIT = 20
FULL_REFRESH_SECS = 600


class DisplayManager:
    def __init__(self):
        from waveshare_epd import epd4in26
        self.epd = epd4in26.EPD()
        self.epd.init()
        self.epd.Clear()
        self._partial_count = 0
        self._last_full = time.time()
        logger.info("DisplayManager ready (%dx%d portrait)", W, H)

    def _buf(self, image):
        return self.epd.getbuffer(image)

    def full_refresh(self, image):
        logger.debug("full refresh")
        self.epd.init()
        self.epd.display_Base(self._buf(image))
        self._partial_count = 0
        self._last_full = time.time()

    def fast_refresh(self, image):
        """Full-frame fast refresh. Resets base so partial can follow."""
        logger.debug("fast refresh")
        self.epd.init()
        self.epd.display_Base(self._buf(image))
        self._partial_count = 0
        self._last_full = time.time()

    def partial_refresh(self, image):
        if (self._partial_count >= PARTIAL_LIMIT or
                time.time() - self._last_full >= FULL_REFRESH_SECS):
            logger.debug("partial→full (limit reached)")
            self.full_refresh(image)
            return
        logger.debug("partial refresh #%d", self._partial_count)
        self.epd.display_Partial(self._buf(image))
        self._partial_count += 1

    def sleep(self):
        self.epd.sleep()

    @staticmethod
    def new_image():
        """Return a blank white portrait canvas."""
        return Image.new('1', (W, H), 255)

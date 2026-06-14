#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Alarm notification screen — displayed when an alarm fires."""
import time
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

W, H = 480, 800


class AlarmScreen(BaseScreen):
    def __init__(self, app, alarm):
        super().__init__(app)
        self._alarm = alarm
        self._fired_at = time.strftime('%H:%M:%S')
        self._blink = True
        self._last_blink = time.time()

    def tick(self):
        if time.time() - self._last_blink > 0.8:
            self._blink = not self._blink
            self._last_blink = time.time()
            self.request_partial()

    def handle_input(self, action):
        from input_handler import SELECT, BACK
        if action in (SELECT, BACK):
            self.app.pop_screen()
            return True
        return False

    def render(self):
        img = self.new_image()
        draw = ImageDraw.Draw(img)
        f = self.app.fonts

        # Flashing full-screen border
        if self._blink:
            draw.rectangle([0, 0, W - 1, H - 1], outline=0, width=12)
        else:
            draw.rectangle([0, 0, W - 1, H - 1], fill=0)

        bg = 0 if not self._blink else 255
        fg = 255 if not self._blink else 0

        win95.text_centered(draw, W // 2, 220, 'ALARM', f.huge, fill=fg)
        win95.text_centered(draw, W // 2, 320,
                            f"{self._alarm.get('hour', 0):02d}:{self._alarm.get('minute', 0):02d}",
                            f.huge, fill=fg)
        label = self._alarm.get('label', '')
        if label:
            win95.text_centered(draw, W // 2, 420, label, f.xlarge, fill=fg)
        win95.text_centered(draw, W // 2, 560, f'Fired at {self._fired_at}', f.medium, fill=fg)
        win95.text_centered(draw, W // 2, 660, 'Press SELECT or BACK to dismiss', f.body, fill=fg)

        self._dirty = False
        return img

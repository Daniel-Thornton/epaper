#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Home screen — Windows 95 style desktop with app icons and clock widget."""
import time
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

# Icon grid: 3 columns × 3 rows
_COLS = [80, 240, 400]
_ROWS = [210, 380, 550]

# (key, label, icon_key)
_APPS = [
    ('notes',     'Notes',    'notes'),
    ('todo',      'To-Do',    'todo'),
    ('camera',    'Camera',   'camera'),
    ('clock',     'Clock',    'clock'),
    ('calculator','Calc',     'calc'),
    ('settings',  'Settings', 'settings'),
    ('info',      'Info',     'info'),
    ('calorie',   'Calories', 'calorie'),
    ('chat',      'Chat',     'chat'),
]


class HomeScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self._sel = 0          # selected icon index
        self._last_min = -1    # track minute changes for partial ticks

    def on_enter(self):
        super().on_enter()
        self._last_min = -1   # force full re-render

    def tick(self):
        now = time.localtime()
        if now.tm_min != self._last_min:
            self._last_min = now.tm_min
            # Minute changed — partial refresh to update clock widget
            if not self._dirty:
                self.request_partial()

    def handle_input(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        n = len(_APPS)
        if action == UP:
            if self._sel >= 3:
                self._sel -= 3
                self.request_partial()
            return True
        if action == DOWN:
            if self._sel + 3 < n:
                self._sel += 3
                self.request_partial()
            return True
        if action == LEFT:
            row, col = divmod(self._sel, 3)
            if col > 0:
                self._sel -= 1
                self.request_partial()
            return True
        if action == RIGHT:
            row, col = divmod(self._sel, 3)
            if col < 2 and self._sel + 1 < n:
                self._sel += 1
                self.request_partial()
            return True
        if action == ACCEPT:
            self._launch()
            return True
        if action == BACK:
            return True  # home is root — consume silently
        return False

    def _launch(self):
        key = _APPS[self._sel][0]
        self.app.open_app(key)

    def render(self):
        img = self.new_image()
        draw = ImageDraw.Draw(img)
        f = self.app.fonts

        win95.draw_desktop(img, draw)

        # ── Clock widget ──────────────────────────────────────────────────────
        now = time.localtime()
        cx_w, cy_w = 240, 80
        win95.draw_raised_box(draw, 20, 15, 460, 125, fill=255)
        time_str = time.strftime('%H:%M', now)
        win95.text_centered(draw, cx_w, 52, time_str, f.huge, fill=0)
        date_str = time.strftime('%A  %d %B %Y', now)
        win95.text_centered(draw, cx_w, 103, date_str, f.body, fill=0)

        # ── App icons ─────────────────────────────────────────────────────────
        for idx, (key, label, icon_key) in enumerate(_APPS):
            row, col = divmod(idx, 3)
            cx = _COLS[col]
            cy = _ROWS[row]
            painter = win95.ICON_PAINTERS.get(icon_key)
            win95.draw_icon(draw, cx, cy, label, f.small,
                            icon_draw_fn=painter, selected=(idx == self._sel))

        # ── Taskbar ───────────────────────────────────────────────────────────
        clock_str = time.strftime('%H:%M', now)
        win95.draw_taskbar(draw, f.small, clock_str)

        self._dirty = False
        return img

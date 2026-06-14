#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Settings screen — configure app behaviour."""
import os
import json
import time
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

W, H = 480, 800
TB = win95.TITLEBAR_H
TK = win95.TASKBAR_H

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'config.json')

DEFAULTS = {
    'clock_format': '24h',
    'full_refresh_interval': 600,
    'partial_refresh_limit': 20,
    'auto_sleep_mins': 0,
    'gcal_enabled': False,
}


def _load():
    if os.path.exists(DATA):
        try:
            cfg = json.load(open(DATA))
            return {**DEFAULTS, **cfg}
        except Exception:
            pass
    return dict(DEFAULTS)


def _save(cfg):
    json.dump(cfg, open(DATA, 'w'), indent=2)


ITEM_H = 64
VISIBLE = 9

# (label, key, type, options/min/max)
_SETTINGS = [
    ('Clock Format',         'clock_format',         'choice', ['12h', '24h']),
    ('Full Refresh Interval','full_refresh_interval', 'int',    (60, 3600, 60)),
    ('Partial Refresh Limit','partial_refresh_limit', 'int',    (5, 50, 5)),
    ('Auto Sleep (mins)',    'auto_sleep_mins',       'int',    (0, 60, 5)),
    ('Google Cal Enabled',   'gcal_enabled',          'bool',   None),
    ('Google Cal Setup',     '_gcal_setup',           'action', None),
    ('About',                '_about',                'action', None),
]


class SettingsApp(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self._cfg = _load()
        self._sel = 0
        self._scroll = 0
        self._editing = False
        self._sub_mode = None   # None | 'about' | 'gcal_setup'

    def on_enter(self):
        super().on_enter()
        self._cfg = _load()

    # ── Input ─────────────────────────────────────────────────────────────────

    def handle_input(self, action):
        from input_handler import UP, DOWN, BACK, SELECT
        if self._sub_mode:
            if action in (BACK, SELECT):
                self._sub_mode = None
                self.request_full()
            return True

        if action == BACK:
            if self._editing:
                self._editing = False
                _save(self._cfg)
                self.request_partial()
                return True
            self.app.pop_screen()
            return True

        if action == UP:
            if self._editing:
                self._adjust(-1)
            else:
                self._sel = max(0, self._sel - 1)
                if self._sel < self._scroll:
                    self._scroll = self._sel
                self.request_partial()
            return True

        if action == DOWN:
            if self._editing:
                self._adjust(+1)
            else:
                self._sel = min(len(_SETTINGS) - 1, self._sel + 1)
                if self._sel >= self._scroll + VISIBLE:
                    self._scroll = self._sel - VISIBLE + 1
                self.request_partial()
            return True

        if action == SELECT:
            return self._activate()

        return False

    def _activate(self):
        label, key, typ, opts = _SETTINGS[self._sel]
        if key == '_about':
            self._sub_mode = 'about'
            self.request_full()
            return True
        if key == '_gcal_setup':
            self._sub_mode = 'gcal_setup'
            self.request_full()
            return True
        if typ == 'bool':
            self._cfg[key] = not self._cfg[key]
            _save(self._cfg)
            self.request_partial()
            return True
        if typ in ('int', 'choice'):
            self._editing = not self._editing
            if not self._editing:
                _save(self._cfg)
            self.request_partial()
            return True
        return False

    def _adjust(self, delta):
        label, key, typ, opts = _SETTINGS[self._sel]
        if typ == 'choice':
            idx = opts.index(self._cfg[key]) if self._cfg[key] in opts else 0
            self._cfg[key] = opts[(idx + delta) % len(opts)]
        elif typ == 'int':
            mn, mx, step = opts
            self._cfg[key] = max(mn, min(mx, self._cfg[key] + delta * step))
        _save(self._cfg)
        self.request_partial()

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self):
        img = self.new_image()
        draw = ImageDraw.Draw(img)
        f = self.app.fonts

        draw.rectangle([0, 0, W, TB], fill=0)
        draw.text((8, 4), 'Settings', font=f.title, fill=255)

        if self._sub_mode == 'about':
            self._render_about(draw, f)
        elif self._sub_mode == 'gcal_setup':
            self._render_gcal(draw, f)
        else:
            self._render_list(draw, f)

        win95.draw_taskbar(draw, f.small, time.strftime('%H:%M'), 'Settings')
        self._dirty = False
        return img

    def _render_list(self, draw, f):
        y0 = TB + 6
        visible = _SETTINGS[self._scroll:self._scroll + VISIBLE]
        for i, (label, key, typ, opts) in enumerate(visible):
            idx = i + self._scroll
            by = y0 + i * ITEM_H
            sel = (idx == self._sel)
            editing = sel and self._editing

            bg = 0 if sel and not editing else 255
            fg = 255 if sel and not editing else 0

            win95.draw_raised_box(draw, 6, by, W - 6, by + ITEM_H - 4, fill=bg)
            draw.text((14, by + 6), label, font=f.body, fill=fg)

            # Value display
            if key.startswith('_'):
                val_str = '→'
            elif typ == 'bool':
                val_str = 'Yes' if self._cfg.get(key) else 'No'
            else:
                val_str = str(self._cfg.get(key, ''))

            vfont = f.bold_md if editing else f.body
            tw, _ = win95.text_wh(draw, val_str, vfont)
            draw.text((W - 14 - tw, by + 30), val_str, font=vfont,
                      fill=(0 if editing else fg))
            if editing:
                draw.rectangle([W - 16 - tw, by + 28, W - 8, by + ITEM_H - 10],
                               outline=0, width=2)

        if not self._editing:
            draw.text((8, H - TK - 26),
                      'UP/DOWN: navigate  SELECT: edit  BACK: save & exit',
                      font=f.small, fill=0)
        else:
            draw.text((8, H - TK - 26),
                      'UP/DOWN: change value  SELECT/BACK: confirm',
                      font=f.small, fill=0)

    def _render_about(self, draw, f):
        lines = [
            'EpaperUI v1.0',
            '4.26" B&W e-Paper HAT',
            '800×480 (portrait 480×800)',
            '',
            'Built with Python + Pillow',
            'Waveshare epd4in26 driver',
            '',
            'Apps: Clock, Notes, Camera,',
            'ToDo, Calculator, Settings,',
            'Info, Calorie Log, Chat',
            '',
            'Google Calendar integration',
            'requires credentials.json',
            'in the data/ directory.',
            '',
            'Press SELECT or BACK to close',
        ]
        for i, line in enumerate(lines):
            draw.text((20, TB + 16 + i * 28), line, font=f.body, fill=0)

    def _render_gcal(self, draw, f):
        lines = [
            'Google Calendar Setup',
            '',
            '1. Go to Google Cloud Console',
            '2. Create OAuth2 credentials',
            '3. Download credentials.json',
            '4. Copy to: data/credentials.json',
            '5. Enable Google Calendar API',
            '',
            'On first sync, a URL will be',
            'printed to the console. Open',
            'it on a device with a browser,',
            'then paste the auth code back.',
            '',
            'Required packages:',
            'pip install google-api-python',
            '-client google-auth-oauthlib',
            '',
            'Press SELECT or BACK to close',
        ]
        for i, line in enumerate(lines):
            draw.text((14, TB + 10 + i * 26), line, font=f.small, fill=0)

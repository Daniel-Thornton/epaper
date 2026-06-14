#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Web app launcher.
Displays a QR code for the URL so the user can scan it with a phone.
Optionally renders a screenshot via Playwright if installed.
"""
import os
import time
import io
import threading
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

W, H = 480, 800
TB = win95.TITLEBAR_H
TK = win95.TASKBAR_H

QR_SIZE = 300   # pixels for the QR code image


def _make_qr(url):
    try:
        import qrcode
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=5, border=3)
        qr.add_data(url)
        qr.make(fit=True)
        return qr.make_image(fill_color='black', back_color='white').convert('1')
    except ImportError:
        return None


class WebApp(BaseScreen):
    """
    Params:
        name (str): Display name for the app
        url  (str): URL to open
    """
    def __init__(self, app, name, url):
        super().__init__(app)
        self._name = name
        self._url = url
        self._qr = None
        self._screenshot = None
        self._mode = 'qr'    # 'qr' | 'screenshot' | 'loading'
        self._status = 'Press SELECT to load screenshot'
        self._menu_sel = 0
        self._menu = ['Show QR Code', 'Load Screenshot', 'Open in Browser', 'Back']

    def on_enter(self):
        super().on_enter()
        if self._qr is None:
            t = threading.Thread(target=self._gen_qr, daemon=True)
            t.start()

    def _gen_qr(self):
        self._qr = _make_qr(self._url)
        if self._qr is None:
            self._status = 'Install qrcode: pip install qrcode[pil]'
        else:
            self._status = 'Scan QR with your phone'
        self.request_partial()

    def _load_screenshot(self):
        self._mode = 'loading'
        self._status = 'Capturing screenshot...'
        self.request_partial()
        t = threading.Thread(target=self._screenshot_thread, daemon=True)
        t.start()

    def _screenshot_thread(self):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={'width': W, 'height': H - TB - TK})
                page.goto(self._url, timeout=30000)
                page.wait_for_load_state('networkidle', timeout=15000)
                data = page.screenshot()
                browser.close()
            img = Image.open(io.BytesIO(data)).convert('L').convert('1')
            self._screenshot = img
            self._mode = 'screenshot'
            self._status = 'Screenshot loaded'
        except ImportError:
            self._status = 'Playwright not installed. Run: pip install playwright && playwright install chromium'
            self._mode = 'qr'
        except Exception as e:
            self._status = f'Error: {str(e)[:60]}'
            self._mode = 'qr'
        self.request_full()

    def _open_browser(self):
        try:
            import subprocess
            subprocess.Popen(['chromium-browser', '--kiosk', self._url])
            self._status = 'Opened in Chromium'
        except Exception:
            try:
                import subprocess
                subprocess.Popen(['xdg-open', self._url])
                self._status = 'Opened in default browser'
            except Exception as e:
                self._status = f'Cannot open: {e}'
        self.request_partial()

    # ── Input ─────────────────────────────────────────────────────────────────

    def handle_input(self, action):
        from input_handler import UP, DOWN, BACK, SELECT
        if action == BACK:
            self.app.pop_screen()
            return True
        if action == UP:
            self._menu_sel = (self._menu_sel - 1) % len(self._menu)
            self.request_partial()
            return True
        if action == DOWN:
            self._menu_sel = (self._menu_sel + 1) % len(self._menu)
            self.request_partial()
            return True
        if action == SELECT:
            choice = self._menu[self._menu_sel]
            if choice == 'Back':
                self.app.pop_screen()
            elif choice == 'Show QR Code':
                self._mode = 'qr'
                self.request_full()
            elif choice == 'Load Screenshot':
                self._load_screenshot()
            elif choice == 'Open in Browser':
                self._open_browser()
            return True
        return False

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self):
        img = self.new_image()
        draw = ImageDraw.Draw(img)
        f = self.app.fonts

        draw.rectangle([0, 0, W, TB], fill=0)
        draw.text((8, 4), self._name, font=f.title, fill=255)

        if self._mode == 'screenshot' and self._screenshot:
            self._render_screenshot(img, draw, f)
        elif self._mode == 'loading':
            self._render_loading(draw, f)
        else:
            self._render_qr(img, draw, f)

        win95.draw_taskbar(draw, f.small, time.strftime('%H:%M'), self._name[:18])
        self._dirty = False
        return img

    def _render_qr(self, img, draw, f):
        # URL text (truncated)
        url_disp = self._url[:42]
        draw.text((8, TB + 8), url_disp, font=f.small, fill=0)

        # QR code
        qr = self._qr
        if qr:
            qr_scaled = qr.resize((QR_SIZE, QR_SIZE), Image.NEAREST)
            px = (W - QR_SIZE) // 2
            py = TB + 32
            img.paste(qr_scaled, (px, py))
            draw.text((8, py + QR_SIZE + 8), self._status, font=f.small, fill=0)
        else:
            win95.text_centered(draw, W // 2, TB + 180, 'Generating QR...', f.large, fill=0)
            draw.text((8, TB + 220), self._status, font=f.small, fill=0)

        # Menu
        my = TB + 32 + QR_SIZE + 40
        for i, item in enumerate(self._menu):
            by = my + i * 52
            if by + 48 > H - TK - 4:
                break
            win95.draw_button(draw, 8, by, W - 8, by + 48, item, f.medium,
                              selected=(i == self._menu_sel))

    def _render_screenshot(self, img, draw, f):
        sh = H - TB - TK - 80
        thumb = self._screenshot.resize((W, sh), Image.LANCZOS)
        img.paste(thumb, (0, TB + 4))
        y_info = TB + sh + 10
        draw.text((8, y_info), self._status, font=f.small, fill=0)
        y_info += 22
        for i, item in enumerate(self._menu[:3]):
            bx = i * (W // 3) + 4
            win95.draw_button(draw, bx, y_info, bx + W // 3 - 8, y_info + 44,
                              item, f.small, selected=(i == self._menu_sel))

    def _render_loading(self, draw, f):
        win95.text_centered(draw, W // 2, H // 2 - 30, 'Loading...', f.xlarge, fill=0)
        draw.text((8, H // 2 + 20), self._status, font=f.small, fill=0)

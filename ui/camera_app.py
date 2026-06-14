#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Camera app — photo capture, video recording, and live e-paper preview."""
import os
import time
import threading
import logging
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

logger = logging.getLogger(__name__)

W, H = 480, 800
TB = win95.TITLEBAR_H
TK = win95.TASKBAR_H

PHOTOS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'photos')

PREVIEW_W, PREVIEW_H = 480, 360   # live preview area
PREVIEW_Y = TB + 4


class CameraApp(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self._cam = None
        self._preview_frame = None
        self._recording = False
        self._rec_start = 0
        self._status = 'Initialising camera...'
        self._mode = 'preview'    # 'preview' | 'gallery'
        self._menu_sel = 0
        self._menu = ['Photo', 'Video', 'Preview ON/OFF', 'Gallery', 'Back']
        self._preview_active = True
        self._frame_lock = threading.Lock()
        self._last_preview = 0

    def on_enter(self):
        super().on_enter()
        os.makedirs(PHOTOS_DIR, exist_ok=True)
        self._start_camera()

    def on_exit(self):
        self._stop_camera()

    def _start_camera(self):
        try:
            from picamera2 import Picamera2
            self._cam = Picamera2()
            cfg = self._cam.create_still_configuration(
                main={'size': (PREVIEW_W * 2, PREVIEW_H * 2)},
                lores={'size': (PREVIEW_W, PREVIEW_H)},
                display='lores',
            )
            self._cam.configure(cfg)
            self._cam.start()
            self._status = 'Camera ready'
            if self._preview_active:
                self._start_preview_thread()
        except Exception as e:
            self._cam = None
            self._status = f'Camera unavailable: {e}'
            logger.warning("Camera init failed: %s", e)
        self.request_partial()

    def _stop_camera(self):
        if self._cam:
            try:
                self._cam.stop()
                self._cam.close()
            except Exception:
                pass
            self._cam = None

    def _start_preview_thread(self):
        t = threading.Thread(target=self._preview_loop, daemon=True)
        t.start()

    def _preview_loop(self):
        import numpy as np
        while self._cam and self._preview_active:
            try:
                frame = self._cam.capture_array('lores')
                pil_img = Image.fromarray(frame).convert('L').convert('1')
                with self._frame_lock:
                    self._preview_frame = pil_img
                self._dirty = True
                self._refresh_type = self.REFRESH_PARTIAL
            except Exception:
                pass
            time.sleep(0.5)

    def tick(self):
        if self._preview_active and self._preview_frame is not None:
            if time.time() - self._last_preview > 0.5:
                self._last_preview = time.time()
                self.request_partial()

    # ── Input ─────────────────────────────────────────────────────────────────

    def handle_input(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if self._mode == 'gallery':
            if action == BACK:
                self._mode = 'preview'
                self.request_full()
                return True
            if action in (UP, LEFT):
                if self._gallery_files:
                    self._gallery_sel = (self._gallery_sel - 1) % len(self._gallery_files)
                    self.request_full()
                return True
            if action in (DOWN, RIGHT):
                if self._gallery_files:
                    self._gallery_sel = (self._gallery_sel + 1) % len(self._gallery_files)
                    self.request_full()
                return True
            return False

        if action == UP:
            self._menu_sel = (self._menu_sel - 1) % len(self._menu)
            self.request_partial()
            return True
        if action == DOWN:
            self._menu_sel = (self._menu_sel + 1) % len(self._menu)
            self.request_partial()
            return True
        if action == BACK:
            self.app.pop_screen()
            return True
        if action == ACCEPT:
            return self._select()
        return False

    def _select(self):
        choice = self._menu[self._menu_sel]
        if choice == 'Back':
            self.app.pop_screen()
            return True
        if choice == 'Photo':
            self._capture_photo()
            return True
        if choice == 'Video':
            self._toggle_video()
            return True
        if choice == 'Preview ON/OFF':
            self._preview_active = not self._preview_active
            if self._preview_active and self._cam:
                self._start_preview_thread()
            self._status = f"Preview {'ON' if self._preview_active else 'OFF'}"
            self.request_partial()
            return True
        if choice == 'Gallery':
            self._mode = 'gallery'
            self._gallery_sel = 0
            self._load_gallery()
            self.request_full()
            return True
        return False

    def _capture_photo(self):
        if not self._cam:
            self._status = 'No camera'
            self.request_partial()
            return
        try:
            ts = time.strftime('%Y%m%d_%H%M%S')
            path = os.path.join(PHOTOS_DIR, f'photo_{ts}.jpg')
            self._cam.capture_file(path)
            self._status = f'Saved: photo_{ts}.jpg'
            logger.info("Photo saved: %s", path)
        except Exception as e:
            self._status = f'Error: {e}'
        self.request_partial()

    def _toggle_video(self):
        if not self._cam:
            self._status = 'No camera'
            self.request_partial()
            return
        if not self._recording:
            try:
                ts = time.strftime('%Y%m%d_%H%M%S')
                path = os.path.join(PHOTOS_DIR, f'video_{ts}.h264')
                from picamera2.encoders import H264Encoder
                self._cam.start_recording(H264Encoder(), path)
                self._recording = True
                self._rec_start = time.time()
                self._status = 'Recording...'
                self._menu[1] = 'Stop Video'
            except Exception as e:
                self._status = f'Rec error: {e}'
        else:
            try:
                self._cam.stop_recording()
                dur = int(time.time() - self._rec_start)
                self._status = f'Video saved ({dur}s)'
                self._menu[1] = 'Video'
            except Exception as e:
                self._status = f'Stop error: {e}'
            self._recording = False
        self.request_partial()

    def _load_gallery(self):
        self._gallery_files = sorted(
            [f for f in os.listdir(PHOTOS_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))],
            reverse=True
        ) if os.path.isdir(PHOTOS_DIR) else []

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self):
        img = self.new_image()
        draw = ImageDraw.Draw(img)
        f = self.app.fonts

        draw.rectangle([0, 0, W, TB], fill=0)
        draw.text((8, 4), 'Camera', font=f.title, fill=255)

        if self._mode == 'gallery':
            self._render_gallery(img, draw, f)
        else:
            self._render_preview(img, draw, f)

        win95.draw_taskbar(draw, f.small, time.strftime('%H:%M'), 'Camera')
        self._dirty = False
        return img

    def _render_preview(self, img, draw, f):
        # Live preview area
        win95.draw_sunken_box(draw, 0, PREVIEW_Y, W, PREVIEW_Y + PREVIEW_H, fill=255)
        with self._frame_lock:
            frame = self._preview_frame
        if frame and self._preview_active:
            img.paste(frame.resize((PREVIEW_W, PREVIEW_H)), (0, PREVIEW_Y))
        else:
            win95.text_centered(draw, W // 2, PREVIEW_Y + PREVIEW_H // 2,
                                'No Preview', f.large, fill=0)

        # Status bar
        sy = PREVIEW_Y + PREVIEW_H + 4
        draw.rectangle([0, sy, W, sy + 22], fill=0)
        draw.text((6, sy + 3), self._status[:50], font=f.small, fill=255)
        if self._recording:
            dur = int(time.time() - self._rec_start)
            draw.text((W - 70, sy + 3), f'REC {dur}s', font=f.small, fill=255)

        # Menu buttons (vertical)
        my = sy + 28
        for i, item in enumerate(self._menu):
            by = my + i * 52
            if by + 48 > H - TK - 4:
                break
            win95.draw_button(draw, 8, by, W - 8, by + 48, item, f.medium,
                              selected=(i == self._menu_sel))

    def _render_gallery(self, img, draw, f):
        if not self._gallery_files:
            win95.text_centered(draw, W // 2, H // 2, 'No photos', f.large, fill=0)
            draw.text((8, H - TK - 26), 'BACK = return to camera', font=f.small, fill=0)
            return

        fn = self._gallery_files[self._gallery_sel]
        path = os.path.join(PHOTOS_DIR, fn)
        try:
            photo = Image.open(path).convert('L').convert('1')
            max_h = H - TB - TK - 80
            photo.thumbnail((W, max_h))
            px = (W - photo.width) // 2
            py = TB + 10
            img.paste(photo, (px, py))
        except Exception as e:
            win95.text_centered(draw, W // 2, H // 2, f'Error: {e}', f.small, fill=0)

        draw.text((8, H - TK - 46), fn[:38], font=f.small, fill=0)
        draw.text((8, H - TK - 28),
                  f'{self._gallery_sel+1}/{len(self._gallery_files)}  UP/DOWN=nav  BACK=close',
                  font=f.small, fill=0)

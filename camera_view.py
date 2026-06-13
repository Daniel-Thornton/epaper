#!/usr/bin/env python3
"""
Display live camera feed on the Pi desktop (tkinter) and periodically
update the Waveshare 4.26" e-paper (800x480) with a dithered snapshot.

Desktop: real-time preview
E-paper: refreshes every EPAPER_INTERVAL seconds
"""

import sys
import os
import time
import threading
import logging

libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np
from picamera2 import Picamera2

from waveshare_epd import epd4in26

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# How often (seconds) to push a new frame to the e-paper
EPAPER_INTERVAL = 5

# Desktop preview size
PREVIEW_WIDTH  = 800
PREVIEW_HEIGHT = 480

EPD_WIDTH  = 800
EPD_HEIGHT = 480


class CameraViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Camera View")
        self.root.resizable(False, False)

        self._latest_frame: np.ndarray | None = None
        self._frame_lock = threading.Lock()
        self._running = True

        # --- Desktop UI ---
        self.canvas = tk.Canvas(root, width=PREVIEW_WIDTH, height=PREVIEW_HEIGHT, bg='black', highlightthickness=0)
        self.canvas.pack()

        status_frame = tk.Frame(root, bg='#222')
        status_frame.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Starting camera...")
        tk.Label(status_frame, textvariable=self.status_var, fg='white', bg='#222', font=('monospace', 10)).pack(side=tk.LEFT, padx=8, pady=4)

        self.epaper_var = tk.StringVar(value="E-paper: initialising...")
        tk.Label(status_frame, textvariable=self.epaper_var, fg='#aaffaa', bg='#222', font=('monospace', 10)).pack(side=tk.RIGHT, padx=8, pady=4)

        tk.Button(status_frame, text="Update E-paper Now", command=self._force_epaper_update,
                  bg='#444', fg='white', relief='flat', padx=8).pack(side=tk.RIGHT, padx=4, pady=2)

        self._tk_image = None  # keep reference to avoid GC

        # --- Camera ---
        self.picam = Picamera2()
        config = self.picam.create_preview_configuration(
            main={"format": "RGB888", "size": (PREVIEW_WIDTH, PREVIEW_HEIGHT)}
        )
        self.picam.configure(config)
        self.picam.start()
        self.status_var.set("Camera running")

        # --- E-paper ---
        self._epd = None
        self._epaper_ready = False
        self._epaper_update_requested = False
        threading.Thread(target=self._init_epaper, daemon=True).start()

        # --- Start loops ---
        self.root.after(30, self._update_preview)
        self.root.after(EPAPER_INTERVAL * 1000, self._scheduled_epaper_update)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ camera

    def _capture_frame(self) -> np.ndarray:
        """Capture one frame as an HxWx3 uint8 RGB array."""
        return self.picam.capture_array()

    def _update_preview(self):
        if not self._running:
            return
        try:
            frame = self._capture_frame()
            with self._frame_lock:
                self._latest_frame = frame

            img = Image.fromarray(frame)
            self._tk_image = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self._tk_image)
        except Exception as e:
            self.status_var.set(f"Camera error: {e}")

        self.root.after(30, self._update_preview)  # ~33 fps target

    # ------------------------------------------------------------------ e-paper

    def _init_epaper(self):
        try:
            self._epd = epd4in26.EPD()
            self._epd.init_Fast()
            self._epd.Clear()
            self._epaper_ready = True
            self.epaper_var.set(f"E-paper: ready (updates every {EPAPER_INTERVAL}s)")
            logger.info("E-paper initialised")
        except Exception as e:
            logger.error(f"E-paper init failed: {e}")
            self.epaper_var.set(f"E-paper: INIT FAILED – {e}")

    def _frame_to_epaper_image(self, frame: np.ndarray) -> Image.Image:
        """Convert RGB numpy frame to 1-bit dithered PIL image sized for the e-paper."""
        img = Image.fromarray(frame).resize((EPD_WIDTH, EPD_HEIGHT), Image.LANCZOS)
        # Floyd-Steinberg dither via mode conversion
        img = img.convert('L').convert('1')
        return img

    def _push_to_epaper(self):
        if not self._epaper_ready or self._epd is None:
            return
        with self._frame_lock:
            frame = self._latest_frame
        if frame is None:
            return
        try:
            self.epaper_var.set("E-paper: updating...")
            img = self._frame_to_epaper_image(frame)
            self._epd.display_Fast(self._epd.getbuffer(img))
            ts = time.strftime('%H:%M:%S')
            self.epaper_var.set(f"E-paper: last updated {ts}")
            logger.info("E-paper updated")
        except Exception as e:
            logger.error(f"E-paper update failed: {e}")
            self.epaper_var.set(f"E-paper: update error – {e}")

    def _scheduled_epaper_update(self):
        if not self._running:
            return
        threading.Thread(target=self._push_to_epaper, daemon=True).start()
        self.root.after(EPAPER_INTERVAL * 1000, self._scheduled_epaper_update)

    def _force_epaper_update(self):
        threading.Thread(target=self._push_to_epaper, daemon=True).start()

    # ------------------------------------------------------------------ close

    def _on_close(self):
        self._running = False
        self.status_var.set("Shutting down...")
        self.picam.stop()
        if self._epd is not None:
            try:
                self._epd.sleep()
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    app = CameraViewer(root)
    root.mainloop()


if __name__ == '__main__':
    main()

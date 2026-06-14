#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""System information screen."""
import os
import time
import platform
import subprocess
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

W, H = 480, 800
TB = win95.TITLEBAR_H
TK = win95.TASKBAR_H


def _run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return 'N/A'


def _cpu_temp():
    paths = [
        '/sys/class/thermal/thermal_zone0/temp',
        '/sys/devices/virtual/thermal/thermal_zone0/temp',
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return f"{int(open(p).read().strip()) / 1000:.1f}°C"
            except Exception:
                pass
    return _run("vcgencmd measure_temp 2>/dev/null | cut -d= -f2")


def _mem_info():
    try:
        with open('/proc/meminfo') as f:
            lines = {l.split(':')[0]: l.split(':')[1].strip() for l in f}
        total = int(lines['MemTotal'].split()[0]) // 1024
        avail = int(lines['MemAvailable'].split()[0]) // 1024
        return f'{avail} MB free / {total} MB total'
    except Exception:
        return 'N/A'


def _disk_info():
    try:
        s = os.statvfs('/')
        total = s.f_blocks * s.f_frsize // (1024 ** 3)
        free  = s.f_bavail * s.f_frsize // (1024 ** 3)
        return f'{free} GB free / {total} GB total'
    except Exception:
        return 'N/A'


def _ip():
    return _run("hostname -I 2>/dev/null | awk '{print $1}'") or 'N/A'


def _uptime():
    try:
        with open('/proc/uptime') as f:
            secs = int(float(f.read().split()[0]))
        h, r = divmod(secs, 3600)
        m, s = divmod(r, 60)
        return f'{h}h {m}m {s}s'
    except Exception:
        return 'N/A'


class InfoApp(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self._last_update = 0
        self._info = {}

    def on_enter(self):
        super().on_enter()
        self._refresh_info()

    def _refresh_info(self):
        self._info = {
            'Hostname':   platform.node() or _run('hostname'),
            'IP Address': _ip(),
            'Platform':   platform.machine(),
            'OS':         platform.system() + ' ' + platform.release(),
            'Python':     platform.python_version(),
            'CPU Temp':   _cpu_temp(),
            'Memory':     _mem_info(),
            'Disk':       _disk_info(),
            'Uptime':     _uptime(),
            'Time':       time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        self._last_update = time.time()

    def tick(self):
        if time.time() - self._last_update > 10:
            self._refresh_info()
            self.request_partial()

    def handle_input(self, action):
        from input_handler import BACK, ACCEPT
        if action == ACCEPT:
            self._refresh_info()
            self.request_full()
            return True
        if action == BACK:
            self.app.pop_screen()
            return True
        return False

    def render(self):
        img = self.new_image()
        draw = ImageDraw.Draw(img)
        f = self.app.fonts

        draw.rectangle([0, 0, W, TB], fill=0)
        draw.text((8, 4), 'System Info', font=f.title, fill=255)

        y = TB + 10
        for label, val in self._info.items():
            win95.draw_raised_box(draw, 6, y, W - 6, y + 58, fill=255)
            draw.text((14, y + 6), label, font=f.bold_sm, fill=0)
            draw.text((14, y + 30), str(val)[:42], font=f.small, fill=0)
            y += 62
            if y > H - TK - 40:
                break

        draw.text((8, H - TK - 26),
                  f'Updated {int(time.time()-self._last_update)}s ago  SELECT: refresh  BACK: home',
                  font=f.small, fill=0)

        win95.draw_taskbar(draw, f.small, time.strftime('%H:%M'), 'Info')
        self._dirty = False
        return img

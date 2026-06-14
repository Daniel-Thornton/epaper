#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Button abstraction.  Supports Waveshare HAT GPIO buttons (4-button layout)
and falls back to keyboard input on non-Pi platforms for development.

GPIO pins (BCM numbering):
  KEY1 = 21  → UP
  KEY2 = 20  → DOWN
  KEY3 = 16  → BACK
  KEY4 = 26  → SELECT
"""
import queue
import threading
import logging
import time

logger = logging.getLogger(__name__)

UP     = 'UP'
DOWN   = 'DOWN'
BACK   = 'BACK'
SELECT = 'SELECT'

_GPIO_MAP = {
    21: UP,
    20: DOWN,
    16: BACK,
    26: SELECT,
}

_KEY_MAP = {
    'w': UP,    'k': UP,
    's': DOWN,  'j': DOWN,
    'a': BACK,  'h': BACK,
    'd': SELECT,'l': SELECT,
    '\x1b[A': UP,    # arrow up
    '\x1b[B': DOWN,  # arrow down
    '\x1b[D': BACK,  # arrow left
    '\x1b[C': SELECT,# arrow right
}


class InputHandler:
    def __init__(self):
        self._q = queue.Queue()
        self._setup()

    def _setup(self):
        try:
            from gpiozero import Button
            self._buttons = {}
            for pin, action in _GPIO_MAP.items():
                btn = Button(pin, pull_up=True, bounce_time=0.05)
                btn.when_pressed = lambda a=action: self._q.put(a)
                self._buttons[pin] = btn
            logger.info("GPIO input ready")
        except Exception as e:
            logger.warning("GPIO unavailable (%s), using keyboard input", e)
            self._buttons = {}
            t = threading.Thread(target=self._keyboard_thread, daemon=True)
            t.start()

    def _keyboard_thread(self):
        """Read single keystrokes from stdin."""
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch == '\x1b':
                    ch += sys.stdin.read(2)
                action = _KEY_MAP.get(ch)
                if action:
                    self._q.put(action)
                elif ch == 'q':
                    self._q.put('QUIT')
        except Exception:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def get_event(self, timeout=0.05):
        """Non-blocking poll; returns action string or None."""
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def flush(self):
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

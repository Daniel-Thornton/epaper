#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Button abstraction.  Supports Waveshare HAT GPIO buttons (4-button layout)
AND keyboard input simultaneously (useful when SSH'd into the Pi for testing).

GPIO pins (BCM numbering):
  KEY1 = 21  → UP
  KEY2 = 20  → DOWN
  KEY3 = 16  → BACK
  KEY4 = 26  → SELECT

Keyboard bindings (always active when stdin is a TTY):
  w / k / arrow-up    → UP
  s / j / arrow-down  → DOWN
  a / h / arrow-left  → BACK
  d / l / arrow-right → SELECT
  q                   → QUIT
"""
import sys
import queue
import threading
import logging

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
    '\x1b[A': UP,     # arrow up
    '\x1b[B': DOWN,   # arrow down
    '\x1b[D': BACK,   # arrow left
    '\x1b[C': SELECT, # arrow right
    '\n': SELECT,     # Enter
    '\r': SELECT,
}


class InputHandler:
    def __init__(self):
        self._q = queue.Queue()
        self._gpio_ok = False
        self._setup_gpio()
        self._setup_keyboard()

    # ── GPIO ──────────────────────────────────────────────────────────────────

    def _setup_gpio(self):
        try:
            from gpiozero import Button
            self._buttons = {}
            for pin, action in _GPIO_MAP.items():
                btn = Button(pin, pull_up=True, bounce_time=0.05)
                btn.when_pressed = lambda a=action: self._q.put(a)
                self._buttons[pin] = btn
            self._gpio_ok = True
            logger.info("GPIO buttons ready (pins %s)", list(_GPIO_MAP.keys()))
        except Exception as e:
            self._buttons = {}
            logger.info("GPIO not available (%s)", e)

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def _setup_keyboard(self):
        """Always start keyboard listener when stdin is a real terminal."""
        if not sys.stdin.isatty():
            logger.info("stdin is not a TTY — keyboard input disabled")
            return
        t = threading.Thread(target=self._keyboard_thread, daemon=True)
        t.start()
        logger.info("Keyboard input ready (wasd / hjkl / arrows / Enter)")

    def _keyboard_thread(self):
        try:
            import tty
            import termios
        except ImportError:
            logger.warning("tty/termios not available — keyboard input disabled")
            return

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if not ch:
                    break
                if ch == '\x1b':
                    # Escape sequence — read up to 2 more bytes with a short window
                    try:
                        tty.setcbreak(fd)
                        rest = ''
                        for _ in range(2):
                            import select as sel
                            r, _, _ = sel.select([sys.stdin], [], [], 0.05)
                            if r:
                                rest += sys.stdin.read(1)
                        tty.setraw(fd)
                        ch = ch + rest
                    except Exception:
                        pass
                action = _KEY_MAP.get(ch)
                if action:
                    self._q.put(action)
                elif ch in ('q', 'Q', '\x03'):   # q or Ctrl-C
                    self._q.put('QUIT')
                    break
        except Exception as e:
            logger.debug("Keyboard thread exit: %s", e)
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass

    # ── Public API ────────────────────────────────────────────────────────────

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

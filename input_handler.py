#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
6-button input abstraction.

GPIO pins (BCM, adjust to match your HAT wiring):
  UP     = 6
  DOWN   = 19
  LEFT   = 5
  RIGHT  = 26
  BACK   = 21
  ACCEPT = 13

Keyboard equivalents (always active when stdin is a TTY):
  Arrow keys          → UP / DOWN / LEFT / RIGHT
  w/a/s/d             → UP / LEFT / DOWN / RIGHT
  Enter / Space       → ACCEPT
  Escape / Backspace  → BACK
  q / Ctrl-C          → QUIT
"""
import sys
import queue
import threading
import logging
import select as _select

logger = logging.getLogger(__name__)

UP     = 'UP'
DOWN   = 'DOWN'
LEFT   = 'LEFT'
RIGHT  = 'RIGHT'
BACK   = 'BACK'
ACCEPT = 'ACCEPT'

# ── GPIO pin → action mapping ─────────────────────────────────────────────────
# Adjust these to match your HAT's wiring
_GPIO_MAP = {
    6:  UP,
    19: DOWN,
    5:  LEFT,
    26: RIGHT,
    21: BACK,
    13: ACCEPT,
}

# ── Keyboard → action mapping ─────────────────────────────────────────────────
_KEY_MAP = {
    # WASD
    'w': UP,
    's': DOWN,
    'a': LEFT,
    'd': RIGHT,
    # Arrow keys (ANSI escape sequences)
    '\x1b[A': UP,
    '\x1b[B': DOWN,
    '\x1b[D': LEFT,
    '\x1b[C': RIGHT,
    # Accept
    '\n':  ACCEPT,
    '\r':  ACCEPT,
    ' ':   ACCEPT,
    # Back
    '\x1b': BACK,       # Escape
    '\x7f': BACK,       # Backspace (DEL)
    '\x08': BACK,       # Backspace (BS)
}


class InputHandler:
    def __init__(self):
        self._q = queue.Queue()
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
            logger.info("GPIO buttons ready — pins %s", list(_GPIO_MAP.keys()))
        except Exception as e:
            self._buttons = {}
            logger.info("GPIO not available (%s)", e)

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def _setup_keyboard(self):
        if not sys.stdin.isatty():
            logger.info("stdin is not a TTY — keyboard input disabled")
            return
        t = threading.Thread(target=self._keyboard_thread, daemon=True)
        t.start()
        logger.info("Keyboard ready  (wasd / arrows / Enter=ACCEPT / Esc=BACK / q=quit)")

    def _keyboard_thread(self):
        try:
            import tty, termios
        except ImportError:
            logger.warning("tty/termios unavailable — keyboard input disabled")
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
                    # Peek for up to 2 more bytes within 50 ms (arrow keys)
                    rest = ''
                    for _ in range(2):
                        r, _, _ = _select.select([sys.stdin], [], [], 0.05)
                        if r:
                            rest += sys.stdin.read(1)
                        else:
                            break
                    ch = ch + rest

                action = _KEY_MAP.get(ch)
                if action:
                    self._q.put(action)
                elif ch in ('q', 'Q', '\x03'):
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

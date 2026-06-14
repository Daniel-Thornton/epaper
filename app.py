#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Application controller — manages screen stack, event loop, and display refresh.
"""
import sys
import os
import time
import logging
import signal

import fonts
from display import DisplayManager
from input_handler import InputHandler, UP, DOWN, BACK, SELECT

logger = logging.getLogger(__name__)

LOOP_INTERVAL = 0.08   # seconds between event-loop ticks (~12 Hz)


class App:
    def __init__(self):
        self.fonts = fonts.get()
        self.display = DisplayManager()
        self.input = InputHandler()
        self._stack = []
        self._alarm_pending = None
        self._running = True

        # Ensure data dirs exist
        data_root = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(os.path.join(data_root, 'notes'), exist_ok=True)
        os.makedirs(os.path.join(data_root, 'photos'), exist_ok=True)

        # Push home screen first
        from ui.home import HomeScreen
        self.push_screen(HomeScreen(self))

        # Handle Ctrl+C / SIGTERM gracefully
        signal.signal(signal.SIGINT,  self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    # ── Screen management ─────────────────────────────────────────────────────

    def push_screen(self, screen):
        if self._stack:
            self._stack[-1].on_exit()
        self._stack.append(screen)
        screen.on_enter()
        logger.info("Push screen: %s", type(screen).__name__)

    def pop_screen(self):
        if len(self._stack) <= 1:
            return   # never pop home
        self._stack[-1].on_exit()
        self._stack.pop()
        self._stack[-1].on_enter()
        logger.info("Pop → %s", type(self._stack[-1]).__name__)

    @property
    def current(self):
        return self._stack[-1] if self._stack else None

    def open_app(self, key):
        """Push the named app screen."""
        screen = self._build_app(key)
        if screen:
            self.push_screen(screen)

    def _build_app(self, key):
        from ui.clock_app      import ClockApp
        from ui.notes_app      import NotesApp
        from ui.camera_app     import CameraApp
        from ui.todo_app       import TodoApp
        from ui.calculator_app import CalculatorApp
        from ui.settings_app   import SettingsApp
        from ui.info_app       import InfoApp
        from ui.webapp         import WebApp

        mapping = {
            'clock':      lambda: ClockApp(self),
            'notes':      lambda: NotesApp(self),
            'camera':     lambda: CameraApp(self),
            'todo':       lambda: TodoApp(self),
            'calculator': lambda: CalculatorApp(self),
            'settings':   lambda: SettingsApp(self),
            'info':       lambda: InfoApp(self),
            'calorie':    lambda: WebApp(self, 'Calorie Logger',
                                         'https://daniel-thornton.github.io/calorie-logger/'),
            'chat':       lambda: WebApp(self, 'Chat',
                                         'https://daniel-thornton.github.io/chat/'),
        }
        builder = mapping.get(key)
        if builder:
            return builder()
        logger.warning("Unknown app key: %s", key)
        return None

    # ── Alarm ─────────────────────────────────────────────────────────────────

    def trigger_alarm(self, alarm):
        """Called from ClockApp when an alarm fires."""
        from ui.alarm_screen import AlarmScreen
        self.push_screen(AlarmScreen(self, alarm))

    # ── Event loop ────────────────────────────────────────────────────────────

    def run(self):
        logger.info("EpaperUI starting")
        try:
            while self._running:
                self._tick()
        except Exception as e:
            logger.exception("Fatal error in event loop: %s", e)
        finally:
            self._cleanup()

    def _tick(self):
        # Process input
        action = self.input.get_event(timeout=LOOP_INTERVAL)
        if action == 'QUIT':
            self._running = False
            return
        if action:
            screen = self.current
            if screen and not screen.handle_input(action):
                # Default BACK handling
                if action == BACK and len(self._stack) > 1:
                    self.pop_screen()

        # Let current screen update its state
        if self.current:
            self.current.tick()

        # Refresh display if needed
        if self.current and self.current.needs_refresh():
            rt = self.current.get_refresh_type()
            image = self.current.render()
            if rt == 'full':
                self.display.full_refresh(image)
            elif rt == 'fast':
                self.display.fast_refresh(image)
            else:
                self.display.partial_refresh(image)
            self.current.mark_clean()

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def _shutdown(self, sig, frame):
        logger.info("Shutdown signal received")
        self._running = False

    def _cleanup(self):
        logger.info("Cleaning up")
        try:
            self.display.sleep()
        except Exception:
            pass
        try:
            from waveshare_epd import epd4in26
            epd4in26.epdconfig.module_exit(cleanup=True)
        except Exception:
            pass
        logger.info("Done")

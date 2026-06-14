#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Base class for all application screens."""
from PIL import Image, ImageDraw
from display import DisplayManager


class BaseScreen:
    REFRESH_FULL    = 'full'
    REFRESH_FAST    = 'fast'
    REFRESH_PARTIAL = 'partial'

    def __init__(self, app):
        self.app = app          # reference to App instance
        self._dirty = True
        self._refresh_type = self.REFRESH_FULL

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self):
        """Called when this screen becomes active."""
        self._dirty = True
        self._refresh_type = self.REFRESH_FULL

    def on_exit(self):
        """Called when this screen is covered or popped."""
        pass

    # ── Called each event-loop tick (≈10 Hz) ─────────────────────────────────

    def tick(self):
        """Update internal state. Set _dirty=True when a redraw is needed."""
        pass

    # ── Rendering ─────────────────────────────────────────────────────────────

    def render(self):
        """Return a PIL Image (480×800, mode '1') ready for display."""
        raise NotImplementedError

    def needs_refresh(self):
        return self._dirty

    def get_refresh_type(self):
        t = self._refresh_type
        self._refresh_type = self.REFRESH_PARTIAL  # next update is partial by default
        return t

    def mark_clean(self):
        self._dirty = False

    def request_full(self):
        self._dirty = True
        self._refresh_type = self.REFRESH_FULL

    def request_partial(self):
        self._dirty = True
        self._refresh_type = self.REFRESH_PARTIAL

    # ── Input ─────────────────────────────────────────────────────────────────

    def handle_input(self, action):
        """
        Handle a button action string (UP / DOWN / BACK / SELECT).
        Return True if handled, False to let App handle it (e.g., BACK → pop).
        """
        return False

    # ── Convenience ───────────────────────────────────────────────────────────

    def new_image(self):
        return Image.new('1', (480, 800), 255)

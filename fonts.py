#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Font loading — Win95 aesthetic: bold sans-serif throughout.
Falls back to PIL built-in if no TrueType fonts are installed.
"""
from PIL import ImageFont
import os

_BOLD_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
    '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
]

_REGULAR_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
]

_MONO_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf',
]


def _find(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def load(size, bold=True, mono=False):
    """Load a font at the given pixel size. Bold by default for Win95 look."""
    if mono:
        path = _find(_MONO_PATHS)
    else:
        path = _find(_BOLD_PATHS if bold else _REGULAR_PATHS)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


class FontSet:
    """Pre-loaded fonts — all bold for the Win95 aesthetic."""
    def __init__(self):
        # UI text (bold throughout — Win95 used MS Sans Serif Bold)
        self.small   = load(12)
        self.body    = load(15)
        self.medium  = load(18)
        self.large   = load(24)
        self.xlarge  = load(34)
        self.huge    = load(52)

        # Title bars and emphasis
        self.title   = load(17)
        self.bold_sm = load(13)
        self.bold_md = load(17)
        self.bold_lg = load(24)

        # Monospace (keyboard input display)
        self.mono    = load(14, mono=True)


_instance = None


def get():
    global _instance
    if _instance is None:
        _instance = FontSet()
    return _instance

#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Font loading with graceful fallback to PIL default font."""
from PIL import ImageFont
import os

_SEARCH_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
]

_BOLD_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
]

_MONO_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf',
]


def _find(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def load(size, bold=False, mono=False):
    path = _find(_BOLD_PATHS if bold else (_MONO_PATHS if mono else _SEARCH_PATHS))
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


class FontSet:
    """Pre-loaded fonts at common sizes."""
    def __init__(self):
        self.small   = load(12)
        self.body    = load(16)
        self.medium  = load(20)
        self.large   = load(26)
        self.xlarge  = load(36)
        self.huge    = load(56)
        self.title   = load(20, bold=True)
        self.bold_sm = load(14, bold=True)
        self.bold_md = load(20, bold=True)
        self.bold_lg = load(28, bold=True)
        self.mono    = load(16, mono=True)


_instance = None

def get():
    global _instance
    if _instance is None:
        _instance = FontSet()
    return _instance

#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
PNG icon loader for the e-paper UI.
Loads authentic Win95-style icons from pic/All pngs/, converts to 1-bit B&W,
and caches results so disk I/O only happens once per session.
"""
import os
import logging

_PIC_DIR = os.path.join(os.path.dirname(__file__), 'pic', 'All pngs')
_CACHE   = {}
_log     = logging.getLogger(__name__)

# Map app / screen key → filename inside pic/All pngs/
FILENAMES = {
    'notes':      'Notepad.png',
    'todo':       'Task Manager.png',
    'camera':     'Movie.png',
    'clock':      'Stopwatch.png',
    'calc':       'Calculator.png',
    'calculator': 'Calculator.png',
    'settings':   'Settings.png',
    'info':       'INFO.png',
    'calorie':    'Writing on list with figures.png',
    'chat':       'Chat.png',
    'keyboard':   'Keyboard.png',
    'alarm':      'Alarm (1 of 8).png',
}


def get(key: str, size: int = 56):
    """
    Return a 1-bit PIL Image at ``size × size`` for the given key,
    or None if the key is unknown or the file is missing / unreadable.
    """
    cache_key = (key, size)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    filename = FILENAMES.get(key)
    if not filename:
        _CACHE[cache_key] = None
        return None

    path = os.path.join(_PIC_DIR, filename)
    if not os.path.exists(path):
        _log.warning("Icon file not found: %s", path)
        _CACHE[cache_key] = None
        return None

    try:
        from PIL import Image
        src = Image.open(path)

        # Flatten any transparency onto a white background
        if src.mode in ('RGBA', 'LA'):
            from PIL import Image as _I
            bg = _I.new('RGB', src.size, (255, 255, 255))
            bg.paste(src, mask=src.split()[-1])
            src = bg
        elif src.mode == 'P':
            src = src.convert('RGBA')
            from PIL import Image as _I
            bg = _I.new('RGB', src.size, (255, 255, 255))
            bg.paste(src, mask=src.split()[-1])
            src = bg
        else:
            src = src.convert('RGB')

        src = src.resize((size, size), Image.LANCZOS)
        src = src.convert('L')
        src = src.convert('1', dither=Image.Dither.FLOYDSTEINBERG)

        _CACHE[cache_key] = src
        return src

    except Exception as exc:
        _log.warning("Failed to load icon '%s': %s", filename, exc)
        _CACHE[cache_key] = None
        return None

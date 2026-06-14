#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Virtual keyboard screen.
Navigate with UP/DOWN/LEFT/RIGHT, press SELECT to type the highlighted key.
Push this screen onto the stack; when done it calls on_done(text).
"""
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

W, H = 480, 800
TB = win95.TITLEBAR_H
TK = win95.TASKBAR_H

_ROWS = [
    list('abcdefg'),
    list('hijklmn'),
    list('opqrstu'),
    list('vwxyz.,'),
    list('ABCDEFG'),
    list('HIJKLMN'),
    list('OPQRSTU'),
    list('VWXYZ!?'),
    ['0','1','2','3','4','5','6'],
    ['7','8','9',' ','@','#','_'],
    ['DEL', 'SPACE', 'DONE'],
]

KEY_W = 480 // 7
KEY_H = 48
GRID_Y0 = TB + 110   # below input field


class VirtualKeyboard(BaseScreen):
    def __init__(self, app, prompt, initial='', on_done=None):
        super().__init__(app)
        self._prompt = prompt
        self._text = initial
        self._on_done = on_done
        self._row = 0
        self._col = 0

    def handle_input(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if action == UP:
            self._row = (self._row - 1) % len(_ROWS)
            self._col = min(self._col, len(_ROWS[self._row]) - 1)
            self.request_partial()
            return True
        if action == DOWN:
            self._row = (self._row + 1) % len(_ROWS)
            self._col = min(self._col, len(_ROWS[self._row]) - 1)
            self.request_partial()
            return True
        if action == LEFT:
            self._col = (self._col - 1) % len(_ROWS[self._row])
            self.request_partial()
            return True
        if action == RIGHT:
            self._col = (self._col + 1) % len(_ROWS[self._row])
            self.request_partial()
            return True
        if action == BACK:
            # Backspace — delete last character
            self._text = self._text[:-1]
            self.request_partial()
            return True
        if action == ACCEPT:
            key = _ROWS[self._row][self._col]
            if key == 'DEL':
                self._text = self._text[:-1]
            elif key == 'SPACE':
                self._text += ' '
            elif key == 'DONE':
                if self._on_done:
                    self._on_done(self._text)
                self.app.pop_screen()
            else:
                self._text += key
            self.request_partial()
            return True
        return False

    def render(self):
        img = self.new_image()
        draw = ImageDraw.Draw(img)
        f = self.app.fonts

        draw.rectangle([0, 0, W, TB], fill=0)
        draw.text((8, 4), self._prompt, font=f.title, fill=255)

        # Text field
        win95.draw_sunken_box(draw, 10, TB + 8, W - 10, TB + 98, fill=255)
        # Word-wrap display of current text (last ~3 lines)
        chars_per_line = 26
        lines = []
        for i in range(0, len(self._text) + 1, chars_per_line):
            lines.append(self._text[i:i + chars_per_line])
        lines = lines[-3:] if lines else ['']
        for li, line in enumerate(lines):
            draw.text((16, TB + 14 + li * 26), line + ('|' if li == len(lines) - 1 else ''),
                      font=f.mono, fill=0)

        # Keyboard grid
        for ri, row in enumerate(_ROWS):
            ky = GRID_Y0 + ri * KEY_H
            if ky + KEY_H > H - TK - 4:
                break
            for ci, key in enumerate(row):
                is_wide = (key in ('DEL', 'SPACE', 'DONE'))
                if is_wide:
                    kx = ci * KEY_W * 2 if key != 'DONE' else (W - KEY_W * 3)
                    kw = KEY_W * 2 - 2
                else:
                    kx = ci * KEY_W + 1
                    kw = KEY_W - 2
                sel = (ri == self._row and ci == self._col)
                win95.draw_button(draw, kx, ky + 1, kx + kw, ky + KEY_H - 2,
                                  key, f.small, selected=sel)

        win95.draw_taskbar(draw, f.small, '', 'Keyboard')
        self._dirty = False
        return img

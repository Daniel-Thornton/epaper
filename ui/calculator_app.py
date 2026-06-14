#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Simple calculator with expression display."""
import time
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

W, H = 480, 800
TB = win95.TITLEBAR_H
TK = win95.TASKBAR_H

# Calculator button layout (display_label, action_string)
_LAYOUT = [
    [('C', 'clear'), ('+/-', 'negate'), ('%', 'percent'), ('/', '/')],
    [('7', '7'),     ('8', '8'),        ('9', '9'),       ('*', '*')],
    [('4', '4'),     ('5', '5'),        ('6', '6'),       ('-', '-')],
    [('1', '1'),     ('2', '2'),        ('3', '3'),       ('+', '+')],
    [('0', '0'),     ('.', '.'),        ('DEL', 'del'),   ('=', '=')],
]

COLS = 4
ROWS = len(_LAYOUT)
KEY_W = W // COLS
KEY_H = 80


class CalculatorApp(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self._expr = ''
        self._result = ''
        self._cursor_row = 4
        self._cursor_col = 3   # Start on '='
        self._error = False

    def handle_input(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if action == UP:
            self._cursor_row = (self._cursor_row - 1) % ROWS
            self.request_partial()
            return True
        if action == DOWN:
            self._cursor_row = (self._cursor_row + 1) % ROWS
            self.request_partial()
            return True
        if action == LEFT:
            self._cursor_col = (self._cursor_col - 1) % COLS
            self.request_partial()
            return True
        if action == RIGHT:
            self._cursor_col = (self._cursor_col + 1) % COLS
            self.request_partial()
            return True
        if action == BACK:
            # Dedicated backspace / exit
            if self._expr or self._result:
                self._press('del')
                self.request_partial()
            else:
                self.app.pop_screen()
            return True
        if action == ACCEPT:
            _, op = _LAYOUT[self._cursor_row][self._cursor_col]
            self._press(op)
            self.request_partial()
            return True
        return False

    def _press(self, op):
        self._error = False
        if op == 'clear':
            self._expr = ''
            self._result = ''
        elif op == 'del':
            if self._result:
                self._result = ''
            else:
                self._expr = self._expr[:-1]
        elif op == 'negate':
            try:
                val = -eval(self._expr or '0')
                self._expr = str(int(val) if val == int(val) else val)
            except Exception:
                self._error = True
        elif op == 'percent':
            try:
                val = eval(self._expr or '0') / 100
                self._expr = str(int(val) if val == int(val) else val)
            except Exception:
                self._error = True
        elif op == '=':
            try:
                result = eval(self._expr or '0')
                if isinstance(result, float) and result == int(result):
                    result = int(result)
                self._result = str(result)
            except Exception:
                self._result = 'Error'
                self._error = True
        else:
            if self._result and op not in '+-*/':
                self._expr = self._result
                self._result = ''
            self._expr += op

    def render(self):
        img = self.new_image()
        draw = ImageDraw.Draw(img)
        f = self.app.fonts

        draw.rectangle([0, 0, W, TB], fill=0)
        draw.text((8, 4), 'Calculator', font=f.title, fill=255)

        # Display panel
        disp_y = TB + 4
        disp_h = 130
        win95.draw_sunken_box(draw, 4, disp_y, W - 4, disp_y + disp_h, fill=255)

        # Expression (top-right, smaller)
        expr_disp = self._expr[-24:]
        if expr_disp:
            tw, _ = win95.text_wh(draw, expr_disp, f.medium)
            draw.text((W - 14 - tw, disp_y + 8), expr_disp, font=f.medium, fill=0)

        # Result or current number (bottom-right, large)
        result_disp = self._result if self._result else (self._expr[-12:] if self._expr else '0')
        font_r = f.huge if len(result_disp) < 10 else f.xlarge
        tw, th = win95.text_wh(draw, result_disp, font_r)
        draw.text((W - 14 - tw, disp_y + disp_h - th - 8),
                  result_disp, font=font_r, fill=0)

        # Key grid
        grid_y = disp_y + disp_h + 6
        for ri, row in enumerate(_LAYOUT):
            for ci, (label, _) in enumerate(row):
                kx = ci * KEY_W + 2
                ky = grid_y + ri * KEY_H + 2
                sel = (ri == self._cursor_row and ci == self._cursor_col)
                pressed = (label == '=' and bool(self._result) and not self._error)
                win95.draw_button(draw, kx, ky, kx + KEY_W - 4, ky + KEY_H - 4,
                                  label, f.xlarge, selected=sel, pressed=pressed)

        draw.text((8, H - TK - 24),
                  'Arrows: move  ACCEPT: press key  BACK: delete/exit',
                  font=f.small, fill=0)

        win95.draw_taskbar(draw, f.small, time.strftime('%H:%M'), 'Calculator')
        self._dirty = False
        return img

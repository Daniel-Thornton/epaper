#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Notes app — create, view, edit, delete notes saved as JSON files."""
import os
import json
import uuid
import time
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

W, H = 480, 800
TB = win95.TITLEBAR_H
TK = win95.TASKBAR_H

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'notes')

ITEM_H = 60
VISIBLE = 9

_ACTION_OPTS = ['Edit Title', 'Delete Note', 'Back']


def _list_notes():
    os.makedirs(DATA_DIR, exist_ok=True)
    notes = []
    for fn in sorted(os.listdir(DATA_DIR), reverse=True):
        if fn.endswith('.json'):
            try:
                n = json.load(open(os.path.join(DATA_DIR, fn)))
                n['_file'] = fn
                notes.append(n)
            except Exception:
                pass
    return notes


def _save_note(note):
    os.makedirs(DATA_DIR, exist_ok=True)
    fn = note.get('_file') or f"{uuid.uuid4().hex}.json"
    note['_file'] = fn
    data = {k: v for k, v in note.items() if not k.startswith('_')}
    json.dump(data, open(os.path.join(DATA_DIR, fn), 'w'), indent=2)


def _delete_note(note):
    fn = note.get('_file')
    if fn:
        path = os.path.join(DATA_DIR, fn)
        if os.path.exists(path):
            os.remove(path)


class NotesApp(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self._mode = 'list'   # list | view | action_menu | confirm_delete
        self._notes = []
        self._sel = 0
        self._scroll = 0
        self._view_scroll = 0
        self._action_sel = 0

    def on_enter(self):
        super().on_enter()
        self._reload()

    def _reload(self):
        self._notes = _list_notes()
        self._sel = min(self._sel, max(0, len(self._notes) - 1))

    # ── Input dispatch ────────────────────────────────────────────────────────

    def handle_input(self, action):
        if self._mode == 'list':
            return self._input_list(action)
        if self._mode == 'view':
            return self._input_view(action)
        if self._mode == 'action_menu':
            return self._input_action(action)
        if self._mode == 'confirm_delete':
            return self._input_delete(action)
        return False

    def _input_list(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if action == BACK:
            self.app.pop_screen()
            return True
        if action == UP:
            self._sel = max(0, self._sel - 1)
            if self._sel < self._scroll:
                self._scroll = self._sel
            self.request_partial()
            return True
        if action == DOWN:
            limit = len(self._notes)
            self._sel = min(limit, self._sel + 1)
            if self._sel >= self._scroll + VISIBLE:
                self._scroll = self._sel - VISIBLE + 1
            self.request_partial()
            return True
        if action == ACCEPT:
            if self._sel == len(self._notes):
                self._open_keyboard('', is_new=True)
            else:
                self._mode = 'view'
                self._view_scroll = 0
                self.request_full()
            return True
        return False

    def _input_view(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if action == BACK:
            self._mode = 'list'
            self.request_full()
            return True
        if action == UP:
            self._view_scroll = max(0, self._view_scroll - 1)
            self.request_partial()
            return True
        if action == DOWN:
            self._view_scroll += 1
            self.request_partial()
            return True
        if action == ACCEPT:
            self._action_sel = 0
            self._mode = 'action_menu'
            self.request_partial()
            return True
        return False

    def _input_action(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if action == BACK:
            self._mode = 'view'
            self.request_partial()
            return True
        if action == UP:
            self._action_sel = (self._action_sel - 1) % len(_ACTION_OPTS)
            self.request_partial()
            return True
        if action == DOWN:
            self._action_sel = (self._action_sel + 1) % len(_ACTION_OPTS)
            self.request_partial()
            return True
        if action == ACCEPT:
            choice = _ACTION_OPTS[self._action_sel]
            if choice == 'Edit Title' and self._sel < len(self._notes):
                self._open_keyboard(self._notes[self._sel].get('title', ''))
            elif choice == 'Delete Note':
                self._mode = 'confirm_delete'
                self.request_partial()
            else:
                self._mode = 'view'
                self.request_partial()
            return True
        return False

    def _input_delete(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if action in (BACK, DOWN):
            self._mode = 'view'
            self.request_partial()
            return True
        if action in (ACCEPT, UP):
            if self._sel < len(self._notes):
                _delete_note(self._notes[self._sel])
            self._reload()
            self._mode = 'list'
            self.request_full()
            return True
        return False

    def _open_keyboard(self, initial_title, is_new=False):
        from ui.keyboard import VirtualKeyboard
        if is_new:
            note = {'title': '', 'body': '', 'created': time.strftime('%Y-%m-%dT%H:%M:%S')}
        else:
            note = self._notes[self._sel] if self._sel < len(self._notes) else {}

        def on_title_done(title):
            note['title'] = title or 'Untitled'
            note['modified'] = time.strftime('%Y-%m-%dT%H:%M:%S')
            _save_note(note)
            self._reload()
            self._mode = 'list'
            self.request_full()

        self.app.push_screen(
            VirtualKeyboard(self.app, 'Note Title', note.get('title', ''), on_done=on_title_done)
        )

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self):
        img = self.new_image()
        draw = ImageDraw.Draw(img)
        f = self.app.fonts

        draw.rectangle([0, 0, W, TB], fill=0)
        draw.text((8, 4), 'Notes', font=f.title, fill=255)

        if self._mode == 'list':
            self._render_list(draw, f)
        elif self._mode == 'view':
            self._render_view(draw, f)
        elif self._mode == 'action_menu':
            self._render_action_menu(draw, f)
        elif self._mode == 'confirm_delete':
            self._render_delete(draw, f)

        win95.draw_taskbar(draw, f.small, time.strftime('%H:%M'), 'Notes')
        self._dirty = False
        return img

    def _render_list(self, draw, f):
        y0 = TB + 4
        draw.text((10, y0),
                  f'{len(self._notes)} note(s)  |  UP/DOWN: scroll  SELECT: open/new',
                  font=f.small, fill=0)
        y0 += 20
        visible = self._notes[self._scroll:self._scroll + VISIBLE]
        for i, note in enumerate(visible):
            idx = i + self._scroll
            by = y0 + i * ITEM_H
            sel = (idx == self._sel)
            title = note.get('title', 'Untitled')[:28]
            date = note.get('modified', note.get('created', ''))[:10]
            bg = 0 if sel else 255
            fg = 255 if sel else 0
            win95.draw_raised_box(draw, 8, by, W - 8, by + ITEM_H - 4, fill=bg)
            draw.text((16, by + 6),  title, font=f.body,  fill=fg)
            draw.text((16, by + 32), date,  font=f.small, fill=fg)

        ny = y0 + len(visible) * ITEM_H
        if ny < H - TK - 54:
            sel = (self._sel == len(self._notes))
            win95.draw_button(draw, 8, ny, W - 8, ny + ITEM_H - 4,
                              '+ New Note', f.body, selected=sel)

    def _render_view(self, draw, f):
        if self._sel >= len(self._notes):
            return
        note = self._notes[self._sel]
        y0 = TB + 4

        win95.draw_raised_box(draw, 8, y0, W - 8, y0 + 46, fill=255)
        draw.text((14, y0 + 10), note.get('title', 'Untitled')[:28], font=f.bold_md, fill=0)
        y0 += 54

        draw.text((10, y0), note.get('modified', note.get('created', ''))[:19], font=f.small, fill=0)
        y0 += 22

        body = note.get('body', '(empty — press SELECT → Edit Title to rename)')
        lines = []
        for para in body.split('\n'):
            while len(para) > 38:
                lines.append(para[:38])
                para = para[38:]
            lines.append(para)

        vis_lines = lines[self._view_scroll:self._view_scroll + 22]
        for li, line in enumerate(vis_lines):
            draw.text((10, y0 + li * 22), line, font=f.body, fill=0)

        if len(lines) > 22:
            draw.text((W - 56, y0), f'{self._view_scroll+1}/{len(lines)}', font=f.small, fill=0)

        draw.text((8, H - TK - 26),
                  'UP/DOWN: scroll  SELECT: options  BACK: list',
                  font=f.small, fill=0)

    def _render_action_menu(self, draw, f):
        if self._sel >= len(self._notes):
            return
        note = self._notes[self._sel]
        draw.text((10, TB + 10), f"  {note.get('title', '')[:24]}", font=f.body, fill=0)
        for i, opt in enumerate(_ACTION_OPTS):
            by = TB + 60 + i * 70
            win95.draw_button(draw, 20, by, W - 20, by + 58, opt, f.large,
                              selected=(i == self._action_sel))

    def _render_delete(self, draw, f):
        win95.draw_raised_box(draw, 40, 280, W - 40, 500, fill=255)
        win95.text_centered(draw, W // 2, 330, 'Delete this note?', f.bold_md, fill=0)
        win95.text_centered(draw, W // 2, 380, 'This cannot be undone.', f.small, fill=0)
        win95.draw_button(draw, 60,  420, 200, 478, 'DELETE',  f.medium, selected=True)
        win95.draw_button(draw, 220, 420, 400, 478, 'Cancel',  f.medium)
        draw.text((8, H - TK - 26), 'SELECT/UP: delete  BACK/DOWN: cancel', font=f.small, fill=0)

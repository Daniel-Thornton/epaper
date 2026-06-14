#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
To-Do list app with optional Google Calendar integration.
Local todos stored in data/todos.json.
Google Calendar sync can be enabled in Settings.
"""
import os
import json
import time
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

W, H = 480, 800
TB = win95.TITLEBAR_H
TK = win95.TASKBAR_H

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'todos.json')
GCAL_CREDS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'credentials.json')
GCAL_TOKEN = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'token.json')

ITEM_H = 60
VISIBLE = 9


def _load():
    if os.path.exists(DATA):
        try:
            return json.load(open(DATA))
        except Exception:
            pass
    return []


def _save(todos):
    json.dump(todos, open(DATA, 'w'), indent=2)


class TodoApp(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self._todos = []
        self._sel = 0
        self._scroll = 0
        self._status = ''
        self._gcal_status = 'Not connected'
        self._mode = 'list'   # 'list' | 'confirm_delete'
        self._sync_pending = False

    def on_enter(self):
        super().on_enter()
        self._todos = _load()
        self._try_gcal_sync()

    def _try_gcal_sync(self):
        if not os.path.exists(GCAL_CREDS):
            self._gcal_status = 'No credentials.json'
            return
        import threading
        threading.Thread(target=self._gcal_sync_thread, daemon=True).start()

    def _gcal_sync_thread(self):
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request

            SCOPES = ['https://www.googleapis.com/auth/tasks.readonly',
                      'https://www.googleapis.com/auth/calendar.readonly']
            creds = None
            if os.path.exists(GCAL_TOKEN):
                creds = Credentials.from_authorized_user_file(GCAL_TOKEN, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(GCAL_CREDS, SCOPES)
                    creds = flow.run_console()
                with open(GCAL_TOKEN, 'w') as tf:
                    tf.write(creds.to_json())

            cal = build('calendar', 'v3', credentials=creds)
            now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            events = cal.events().list(
                calendarId='primary', timeMin=now_iso,
                maxResults=20, singleEvents=True, orderBy='startTime'
            ).execute().get('items', [])

            for ev in events:
                title = ev.get('summary', 'Untitled')
                start = ev.get('start', {}).get('dateTime', ev.get('start', {}).get('date', ''))
                existing = [t['title'] for t in self._todos]
                if title not in existing:
                    self._todos.append({
                        'title': title,
                        'done': False,
                        'due': start[:10],
                        'source': 'gcal'
                    })
            _save(self._todos)
            self._gcal_status = f'Synced {len(events)} events'
        except ImportError:
            self._gcal_status = 'google-api-python-client not installed'
        except Exception as e:
            self._gcal_status = f'Sync error: {e}'
        finally:
            self.request_partial()

    # ── Input ─────────────────────────────────────────────────────────────────

    def handle_input(self, action):
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
            limit = len(self._todos)   # +1 for New
            self._sel = min(limit, self._sel + 1)
            if self._sel >= self._scroll + VISIBLE:
                self._scroll = self._sel - VISIBLE + 1
            self.request_partial()
            return True
        if action == ACCEPT:
            if self._sel == len(self._todos):
                self._add_todo()
            else:
                self._toggle_done()
            return True
        return False

    def _add_todo(self):
        from ui.keyboard import VirtualKeyboard
        def on_done(text):
            if text.strip():
                self._todos.append({'title': text.strip(), 'done': False,
                                    'due': '', 'source': 'local'})
                _save(self._todos)
            self.request_full()
        self.app.push_screen(VirtualKeyboard(self.app, 'New To-Do', '', on_done=on_done))

    def _toggle_done(self):
        if 0 <= self._sel < len(self._todos):
            self._todos[self._sel]['done'] = not self._todos[self._sel]['done']
            _save(self._todos)
            self.request_partial()

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self):
        img = self.new_image()
        draw = ImageDraw.Draw(img)
        f = self.app.fonts

        draw.rectangle([0, 0, W, TB], fill=0)
        draw.text((8, 4), 'To-Do List', font=f.title, fill=255)

        y0 = TB + 4
        # Status line
        done_c = sum(1 for t in self._todos if t.get('done'))
        draw.text((8, y0), f'{done_c}/{len(self._todos)} done  |  {self._gcal_status}',
                  font=f.small, fill=0)
        y0 += 20

        visible = self._todos[self._scroll:self._scroll + VISIBLE]
        for i, todo in enumerate(visible):
            idx = i + self._scroll
            by = y0 + i * ITEM_H
            sel = (idx == self._sel)
            done = todo.get('done', False)
            source_mark = '☁' if todo.get('source') == 'gcal' else '◉'

            fg = 255 if sel else 0
            bg = 0 if sel else 255
            win95.draw_raised_box(draw, 8, by, W - 8, by + ITEM_H - 4, fill=bg)

            # Checkbox
            draw.rectangle([16, by + 14, 36, by + 34], fill=bg, outline=fg)
            if done:
                draw.line([(18, by + 24), (24, by + 32)], fill=fg, width=2)
                draw.line([(24, by + 32), (34, by + 16)], fill=fg, width=2)

            title = todo.get('title', '')[:28]
            draw.text((44, by + 8), title, font=f.body, fill=fg)
            due = todo.get('due', '')
            draw.text((44, by + 30), f'{source_mark} {due}', font=f.small, fill=fg)

        # New To-Do button
        ny = y0 + len(visible) * ITEM_H
        if ny < H - TK - 60:
            sel = (self._sel == len(self._todos))
            win95.draw_button(draw, 8, ny, W - 8, ny + ITEM_H - 4, '+ New To-Do',
                              f.body, selected=sel)

        # Instructions
        draw.text((8, H - TK - 26),
                  'SELECT: toggle done  DOWN past end: add  BACK: home',
                  font=f.small, fill=0)

        win95.draw_taskbar(draw, f.small, time.strftime('%H:%M'), 'To-Do')
        self._dirty = False
        return img

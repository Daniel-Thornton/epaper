#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Native chat client (DanGPT) for e-paper.
Calls the same Ollama backend as the web chat app via Cloudflare Tunnel URL.
Conversations are saved locally in data/chats.json.
"""
import os
import json
import time
import threading
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

W, H = 480, 800
TB = win95.TITLEBAR_H
TK = win95.TASKBAR_H

DATA     = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'chats.json')
CFG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'config.json')

SYSTEM_PROMPT = (
    "You are DanGPT, a helpful, concise AI assistant. "
    "Favour short answers unless the user asks for detail. "
    "You are running on a Raspberry Pi e-paper device with a tiny screen, "
    "so keep responses brief and avoid markdown formatting."
)

LINE_H   = 20
PAD      = 8
MSG_GAP  = 6
CHAT_Y0  = TB + 4
STATUS_H = 24


def _cfg():
    if os.path.exists(CFG_FILE):
        try:
            return json.load(open(CFG_FILE))
        except Exception:
            pass
    return {}


def _load_chats():
    if os.path.exists(DATA):
        try:
            return json.load(open(DATA))
        except Exception:
            pass
    return []


def _save_chats(chats):
    json.dump(chats, open(DATA, 'w'), indent=2)


def _wrap_text(draw, text, font, max_w):
    """Word-wrap text to fit max_w pixels. Returns list of strings."""
    words = text.split()
    if not words:
        return ['']
    lines = []
    current = []
    for word in words:
        test = ' '.join(current + [word])
        w, _ = win95.text_wh(draw, test, font)
        if w > max_w and current:
            lines.append(' '.join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(' '.join(current))
    return lines


class ChatApp(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self._messages  = []       # [{role, content}]
        self._busy      = False
        self._status    = 'ACCEPT to type a message'
        self._scroll    = 0        # pixels scrolled up from bottom
        self._mode      = 'chat'   # 'chat' | 'history'
        self._chats     = []
        self._chat_sel  = 0
        self._chat_id   = None

    def on_enter(self):
        super().on_enter()
        self._chats = _load_chats()

    # ── Input ─────────────────────────────────────────────────────────────────

    def handle_input(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if self._mode == 'history':
            return self._input_history(action)
        return self._input_chat(action)

    def _input_chat(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if action == BACK:
            self._save_current()
            self.app.pop_screen()
            return True
        if action == UP:
            self._scroll += 60
            self.request_partial()
            return True
        if action == DOWN:
            self._scroll = max(0, self._scroll - 60)
            self.request_partial()
            return True
        if action == LEFT:
            self._new_chat()
            return True
        if action == RIGHT:
            self._mode = 'history'
            self._chat_sel = 0
            self.request_full()
            return True
        if action == ACCEPT:
            if not self._busy:
                self._open_keyboard()
            return True
        return False

    def _input_history(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if action == BACK:
            self._mode = 'chat'
            self.request_full()
            return True
        if action == UP:
            self._chat_sel = max(0, self._chat_sel - 1)
            self.request_partial()
            return True
        if action == DOWN:
            self._chat_sel = min(len(self._chats) - 1, self._chat_sel + 1)
            self.request_partial()
            return True
        if action == ACCEPT:
            if 0 <= self._chat_sel < len(self._chats):
                self._load_chat(self._chats[self._chat_sel])
            return True
        return False

    # ── Chat logic ────────────────────────────────────────────────────────────

    def _open_keyboard(self):
        from ui.keyboard import VirtualKeyboard
        def on_done(text):
            if text.strip():
                self._send(text.strip())
        self.app.push_screen(VirtualKeyboard(self.app, 'Your message:', '', on_done=on_done))

    def _send(self, text):
        self._messages.append({'role': 'user', 'content': text})
        self._busy   = True
        self._scroll = 0
        self._status = 'Thinking...'
        self.request_full()
        threading.Thread(target=self._ollama_thread, daemon=True).start()

    def _ollama_thread(self):
        cfg    = _cfg()
        tunnel = (cfg.get('chat_url') or cfg.get('tunnel_url', '')).rstrip('/')
        model  = cfg.get('ollama_model', 'llama3.2')
        if not tunnel:
            self._messages.append({
                'role': 'assistant',
                'content': 'No chat URL set. Add chat_url or tunnel_url in Settings.',
            })
            self._busy = False
            self._status = 'Set chat URL in Settings'
            self.request_full()
            return
        try:
            import urllib.request
            msgs = [{'role': 'system', 'content': SYSTEM_PROMPT}] + self._messages
            payload = json.dumps({
                'model':    model,
                'messages': msgs,
                'stream':   False,
            }).encode()
            req = urllib.request.Request(
                tunnel + '/api/chat',
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = json.loads(resp.read())
            content = raw['message']['content'].strip()
            self._messages.append({'role': 'assistant', 'content': content})
            word_count = len(content.split())
            self._status = f'Response: {word_count} words'
            self._save_current()
        except Exception as e:
            self._messages.append({
                'role': 'assistant',
                'content': f'Error: {str(e)[:120]}',
            })
            self._status = 'Error — check tunnel URL'
        self._busy   = False
        self._scroll = 0
        self.request_full()

    def _new_chat(self):
        self._save_current()
        self._messages = []
        self._chat_id  = None
        self._scroll   = 0
        self._status   = 'New chat — ACCEPT to type'
        self.request_full()

    def _save_current(self):
        if not self._messages:
            return
        title = self._messages[0]['content'][:40]
        if self._chat_id:
            for ch in self._chats:
                if ch['id'] == self._chat_id:
                    ch['messages'] = list(self._messages)
                    ch['title']    = title
                    break
        else:
            self._chat_id = str(int(time.time()))
            self._chats.insert(0, {
                'id':       self._chat_id,
                'title':    title,
                'messages': list(self._messages),
                'created':  time.strftime('%Y-%m-%dT%H:%M:%S'),
            })
            self._chats = self._chats[:50]   # keep last 50 conversations
        _save_chats(self._chats)

    def _load_chat(self, chat):
        self._messages = list(chat.get('messages', []))
        self._chat_id  = chat.get('id')
        self._scroll   = 0
        self._mode     = 'chat'
        self._status   = f"Loaded: {chat.get('title', '')[:30]}"
        self.request_full()

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self):
        img  = self.new_image()
        draw = ImageDraw.Draw(img)
        f    = self.app.fonts

        draw.rectangle([0, 0, W, TB], fill=0)
        draw.text((8, 4), 'DanGPT', font=f.title, fill=255)
        if self._busy:
            draw.text((W - 90, 6), '● thinking', font=f.small, fill=255)

        if self._mode == 'history':
            self._render_history(draw, f)
        else:
            self._render_chat(draw, img, f)

        win95.draw_taskbar(draw, f.small, time.strftime('%H:%M'), 'Chat')
        self._dirty = False
        return img

    def _render_chat(self, draw, img, f):
        chat_y1 = H - TK - STATUS_H - 2

        # Status bar above taskbar
        sy = H - TK - STATUS_H
        draw.rectangle([0, sy, W, H - TK], fill=0)
        draw.text((6, sy + 4), self._status[:54], font=f.small, fill=255)

        # Hint line
        hint_parts = ['UP/DOWN:scroll', 'ACCEPT:type', 'LEFT:new', 'RIGHT:history']
        draw.text((6, chat_y1 - 14), '  '.join(hint_parts), font=f.small, fill=0)
        chat_y1 -= 16

        if not self._messages:
            win95.text_centered(draw, W // 2, (CHAT_Y0 + chat_y1) // 2,
                                'No messages yet', f.large, fill=0)
            win95.text_centered(draw, W // 2, (CHAT_Y0 + chat_y1) // 2 + 40,
                                'Press ACCEPT to start chatting', f.body, fill=0)
            return

        # Build all message blocks with line-wrapped content
        CONTENT_W = W - 20
        blocks = []
        for msg in self._messages:
            role  = msg['role']
            text  = msg['content'].strip()
            lines = _wrap_text(draw, text, f.body, CONTENT_W - PAD * 2)
            h     = max(len(lines) * LINE_H + PAD * 2, LINE_H + PAD * 2)
            blocks.append((role, lines, h))

        total_h = sum(h for _, _, h in blocks) + len(blocks) * MSG_GAP
        avail   = chat_y1 - CHAT_Y0

        # Clamp scroll
        max_scroll = max(0, total_h - avail)
        self._scroll = min(self._scroll, max_scroll)

        # Starting y position (may be above visible area for scroll)
        cy = chat_y1 - total_h + self._scroll

        for role, lines, h in blocks:
            block_end = cy + h
            if block_end > CHAT_Y0 and cy < chat_y1:
                if role == 'user':
                    # Right-aligned inverted bubble
                    max_line_w = max(win95.text_wh(draw, ln, f.body)[0] for ln in lines)
                    box_w = min(max_line_w + PAD * 2 + 4, CONTENT_W)
                    bx0   = W - 8 - box_w
                    bx1   = W - 8
                    draw.rectangle([bx0, cy, bx1, cy + h], fill=0)
                    for li, line in enumerate(lines):
                        ty = cy + PAD + li * LINE_H
                        if CHAT_Y0 <= ty < chat_y1:
                            tw, _ = win95.text_wh(draw, line, f.body)
                            draw.text((bx1 - PAD - tw, ty), line, font=f.body, fill=255)
                else:
                    # Left-aligned bordered box
                    draw.rectangle([8, cy, W - 8, cy + h], fill=255, outline=0)
                    for li, line in enumerate(lines):
                        ty = cy + PAD + li * LINE_H
                        if CHAT_Y0 <= ty < chat_y1:
                            draw.text((8 + PAD, ty), line, font=f.body, fill=0)
            cy += h + MSG_GAP

    def _render_history(self, draw, f):
        draw.text((8, TB + 6), f'Conversations ({len(self._chats)} saved):', font=f.bold_sm, fill=0)
        y0 = TB + 30
        ITEM_H = 52
        for i, ch in enumerate(self._chats):
            if y0 + ITEM_H > H - TK - 4:
                break
            sel = (i == self._chat_sel)
            win95.draw_button(draw, 8, y0, W - 8, y0 + ITEM_H - 4,
                              '', f.body, selected=sel)
            title_col = 255 if sel else 0
            draw.text((16, y0 + 6),  ch.get('title', 'Untitled')[:38], font=f.bold_sm, fill=title_col)
            date_str  = ch.get('created', '')[:16]
            n_msgs    = len(ch.get('messages', []))
            draw.text((16, y0 + 28), f'{date_str}   {n_msgs} messages', font=f.small, fill=title_col)
            y0 += ITEM_H

        if not self._chats:
            win95.text_centered(draw, W // 2, H // 2, 'No saved conversations', f.medium, fill=0)

        draw.text((8, H - TK - 24), 'UP/DOWN: navigate  ACCEPT: load  BACK: close', font=f.small, fill=0)

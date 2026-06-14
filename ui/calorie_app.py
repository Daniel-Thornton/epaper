#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Native Calorie Logger for e-paper.
Talks directly to the same Cloudflare Tunnel / Ollama backend as the web app.
Local data stored in data/calorie_log.json (same schema as web app localStorage).
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

DATA      = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'calorie_log.json')
CFG_FILE  = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'config.json')

SYSTEM_PROMPT = (
    "You are a calorie and carbohydrate estimation assistant. "
    "The user will describe food they have eaten. "
    "Respond ONLY with valid JSON in exactly this format:\n"
    '{"items":[{"name":"food item","calories":150,"carbs":20}],'
    '"total_calories":150,"total_carbs":20,"notes":"brief note or empty string"}'
)

TABS = ['Today', 'Add', 'Stats']


def _load_log():
    if os.path.exists(DATA):
        try:
            return json.load(open(DATA))
        except Exception:
            pass
    return {}


def _save_log(log):
    json.dump(log, open(DATA, 'w'), indent=2)


def _today():
    return time.strftime('%Y-%m-%d')


def _cfg():
    if os.path.exists(CFG_FILE):
        try:
            return json.load(open(CFG_FILE))
        except Exception:
            pass
    return {}


def _streak(log):
    streak = 0
    d = time.time()
    while True:
        key = time.strftime('%Y-%m-%d', time.localtime(d))
        if key in log and log[key]:
            streak += 1
            d -= 86400
        else:
            break
    return streak


def _bar(draw, x, y, w, h, filled_frac, font, label, value_str):
    """Draw a vertical bar with label below."""
    draw.rectangle([x, y, x + w, y + h], fill=255, outline=0)
    filled_h = int(h * min(1.0, filled_frac))
    if filled_h > 0:
        draw.rectangle([x, y + h - filled_h, x + w, y + h], fill=0)
    tw, th = win95.text_wh(draw, label, font)
    draw.text((x + (w - tw) // 2, y + h + 3), label, font=font, fill=0)


class CalorieApp(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self._tab      = 0
        self._log      = {}
        self._scroll   = 0
        self._status   = ''
        self._busy     = False
        self._pending  = None   # dict from Ollama response, awaiting confirm
        self._pending_desc = ''

    def on_enter(self):
        super().on_enter()
        self._log = _load_log()

    # ── Input ─────────────────────────────────────────────────────────────────

    def handle_input(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if action == BACK:
            if self._pending:
                self._pending = None
                self.request_partial()
                return True
            self.app.pop_screen()
            return True
        if action == LEFT:
            self._tab = (self._tab - 1) % len(TABS)
            self._scroll = 0
            self.request_full()
            return True
        if action == RIGHT:
            self._tab = (self._tab + 1) % len(TABS)
            self._scroll = 0
            self.request_full()
            return True
        if action == UP:
            self._scroll = max(0, self._scroll - 1)
            self.request_partial()
            return True
        if action == DOWN:
            self._scroll += 1
            self.request_partial()
            return True
        if action == ACCEPT:
            if self._pending:
                self._confirm_entry()
                return True
            if self._tab == 1:
                self._open_input()
                return True
        return False

    def _open_input(self):
        if self._busy:
            return
        from ui.keyboard import VirtualKeyboard
        def on_done(text):
            if text.strip():
                self._estimate(text.strip())
        self.app.push_screen(VirtualKeyboard(self.app, 'What did you eat?', '', on_done=on_done))

    def _estimate(self, description):
        self._busy = True
        self._pending_desc = description
        self._status = 'Asking AI...'
        self.request_partial()
        threading.Thread(target=self._ollama_thread, args=(description,), daemon=True).start()

    def _ollama_thread(self, description):
        cfg = _cfg()
        tunnel = (cfg.get('calorie_url') or cfg.get('tunnel_url', '')).rstrip('/')
        model  = cfg.get('ollama_model', 'llama3.2')
        if not tunnel:
            self._status = 'No tunnel URL — set it in Settings'
            self._busy = False
            self.request_partial()
            return
        try:
            import urllib.request
            payload = json.dumps({
                'model': model,
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user',   'content': description},
                ],
                'stream': False,
            }).encode()
            req = urllib.request.Request(
                tunnel + '/api/chat',
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = json.loads(resp.read())
            content = raw['message']['content']
            # Strip markdown fences if present
            if '```' in content:
                content = content.split('```')[1].lstrip('json').strip()
            result = json.loads(content)
            self._pending = result
            self._status = f"{result.get('total_calories', '?')} kcal  {result.get('total_carbs', '?')}g carbs"
        except Exception as e:
            self._status = f'Error: {str(e)[:60]}'
            self._pending = None
        self._busy = False
        self._tab = 1   # switch to Add tab to show result
        self.request_full()

    def _confirm_entry(self):
        p = self._pending
        if not p:
            return
        today = _today()
        if today not in self._log:
            self._log[today] = []
        entry = {
            'id':         int(time.time() * 1000),
            'time':       time.strftime('%H:%M'),
            'items':      p.get('items', []),
            'total':      p.get('total_calories', 0),
            'total_carbs':p.get('total_carbs', 0),
            'notes':      p.get('notes', ''),
            'desc':       self._pending_desc,
        }
        self._log[today].append(entry)
        _save_log(self._log)
        self._pending = None
        self._status  = 'Saved!'
        self._tab = 0   # jump to Today view
        self.request_full()

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self):
        img  = self.new_image()
        draw = ImageDraw.Draw(img)
        f    = self.app.fonts

        win95.draw_title_bar(draw, 'Calorie Logger', f.title, 'calorie', img)

        # Tab bar
        tab_h = 28
        tw_ea = W // len(TABS)
        for i, t in enumerate(TABS):
            x0 = i * tw_ea
            if i == self._tab:
                draw.rectangle([x0, TB, x0 + tw_ea - 1, TB + tab_h], fill=0)
                win95.text_centered(draw, x0 + tw_ea // 2, TB + tab_h // 2, t, f.bold_sm, fill=255)
            else:
                draw.rectangle([x0, TB, x0 + tw_ea - 1, TB + tab_h], fill=255, outline=0)
                win95.text_centered(draw, x0 + tw_ea // 2, TB + tab_h // 2, t, f.bold_sm, fill=0)

        cy = TB + tab_h + 4

        if self._tab == 0:
            self._render_today(draw, f, cy)
        elif self._tab == 1:
            self._render_add(draw, f, cy)
        elif self._tab == 2:
            self._render_stats(draw, f, cy)

        win95.draw_taskbar(draw, f.small, time.strftime('%H:%M'), 'Calories')
        self._dirty = False
        return img

    def _render_today(self, draw, f, y0):
        cfg     = _cfg()
        target  = cfg.get('target_kcal', 2000)
        today   = _today()
        entries = self._log.get(today, [])
        total   = sum(e.get('total', 0) for e in entries)
        carbs   = sum(e.get('total_carbs', 0) for e in entries)

        # Summary bar
        win95.draw_raised_box(draw, 8, y0, W - 8, y0 + 64, fill=255)
        pct = min(1.0, total / target) if target else 0
        bar_w = int((W - 24) * pct)
        draw.rectangle([12, y0 + 40, W - 12, y0 + 56], fill=255, outline=0)
        if bar_w > 0:
            draw.rectangle([12, y0 + 40, 12 + bar_w, y0 + 56], fill=0)
        draw.text((12, y0 + 6),
                  f'{total} / {target} kcal   {carbs}g carbs   streak: {_streak(self._log)} days',
                  font=f.small, fill=0)
        y0 += 70

        if not entries:
            win95.text_centered(draw, W // 2, y0 + 60, 'No entries today', f.medium, fill=0)
            win95.text_centered(draw, W // 2, y0 + 90, 'Go to Add tab to log a meal', f.small, fill=0)
            return

        visible = entries[self._scroll:]
        for entry in visible:
            if y0 + 52 > H - TK - 4:
                break
            win95.draw_sunken_box(draw, 8, y0, W - 8, y0 + 52, fill=255)
            t_str  = entry.get('time', '')
            desc   = entry.get('desc', '') or ', '.join(i['name'] for i in entry.get('items', []))
            kcal   = entry.get('total', 0)
            draw.text((14, y0 + 4),  f"{t_str}  {kcal} kcal", font=f.bold_sm, fill=0)
            draw.text((14, y0 + 26), desc[:46], font=f.small, fill=0)
            y0 += 56

    def _render_add(self, draw, f, y0):
        if self._busy:
            win95.text_centered(draw, W // 2, y0 + 80, 'Asking AI...', f.xlarge, fill=0)
            win95.text_centered(draw, W // 2, y0 + 130, 'Please wait', f.body, fill=0)
            return

        if self._pending:
            p = self._pending
            draw.text((10, y0 + 6), 'Estimated — press ACCEPT to save, BACK to cancel', font=f.small, fill=0)
            y0 += 28
            win95.draw_raised_box(draw, 8, y0, W - 8, y0 + 52, fill=255)
            draw.text((14, y0 + 6),  f"Total: {p.get('total_calories','?')} kcal  {p.get('total_carbs','?')}g carbs",
                      font=f.bold_md, fill=0)
            draw.text((14, y0 + 32), p.get('notes', '')[:46], font=f.small, fill=0)
            y0 += 60
            for item in p.get('items', [])[:6]:
                draw.text((14, y0), f"• {item.get('name','')[:32]}  {item.get('calories','?')} kcal", font=f.small, fill=0)
                y0 += 22
            return

        win95.text_centered(draw, W // 2, y0 + 60, 'Press ACCEPT to describe a meal', f.medium, fill=0)
        if self._status:
            win95.text_centered(draw, W // 2, y0 + 100, self._status, f.small, fill=0)
        win95.draw_button(draw, 60, y0 + 140, W - 60, y0 + 200, 'Log a meal', f.large, selected=True)
        draw.text((10, y0 + 220), 'Set tunnel URL and model in Settings first', font=f.small, fill=0)

    def _render_stats(self, draw, f, y0):
        BAR_AREA_H = 260
        BAR_W      = 42
        N_DAYS     = 7
        cfg        = _cfg()
        target     = cfg.get('target_kcal', 2000)

        days   = []
        totals = []
        for i in range(N_DAYS - 1, -1, -1):
            key = time.strftime('%Y-%m-%d', time.localtime(time.time() - i * 86400))
            entries = self._log.get(key, [])
            kcal    = sum(e.get('total', 0) for e in entries)
            days.append(key[8:])   # DD
            totals.append(kcal)

        max_kcal = max(max(totals), target, 1)

        draw.text((10, y0 + 4), f'Last {N_DAYS} days  (target: {target} kcal)', font=f.small, fill=0)
        y0 += 24

        bar_y = y0
        for i, (day, kcal) in enumerate(zip(days, totals)):
            bx = 10 + i * (BAR_W + 8)
            frac = kcal / max_kcal
            _bar(draw, bx, bar_y, BAR_W, BAR_AREA_H, frac, f.small, day, str(kcal))
            # Value label inside bar if space
            if kcal > 0:
                label = str(kcal)
                tw, th = win95.text_wh(draw, label, f.small)
                lx = bx + (BAR_W - tw) // 2
                filled_h = int(BAR_AREA_H * frac)
                ly = bar_y + BAR_AREA_H - filled_h + 3
                if filled_h > th + 4:
                    draw.text((lx, ly), label, font=f.small, fill=255)

        # Target line
        tgt_y = bar_y + BAR_AREA_H - int(BAR_AREA_H * target / max_kcal)
        draw.line([(8, tgt_y), (W - 10, tgt_y)], fill=0, width=1)
        draw.text((W - 50, tgt_y - 14), 'target', font=f.small, fill=0)

        y0 += BAR_AREA_H + 30
        avg = int(sum(totals) / N_DAYS) if N_DAYS else 0
        draw.text((10, y0), f'7-day avg: {avg} kcal   streak: {_streak(self._log)} days', font=f.body, fill=0)

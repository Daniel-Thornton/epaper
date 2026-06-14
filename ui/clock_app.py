#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Clock / Timer / Alarm app with tab navigation."""
import time
import math
import json
import os
from PIL import Image, ImageDraw
from ui.base_screen import BaseScreen
from ui import win95

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'alarms.json')
W, H = 480, 800
TB = win95.TITLEBAR_H
TK = win95.TASKBAR_H
CONTENT_Y = TB
CONTENT_H = H - TB - TK

TABS = ['Clock', 'Timer', 'Alarm']


def load_alarms():
    if os.path.exists(DATA):
        try:
            return json.load(open(DATA))
        except Exception:
            pass
    return []


def save_alarms(alarms):
    json.dump(alarms, open(DATA, 'w'), indent=2)


class ClockApp(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self._tab = 0              # 0=Clock, 1=Timer, 2=Alarm
        self._last_sec = -1

        # Timer state
        self._timer_running = False
        self._timer_end = 0
        self._timer_elapsed = 0
        self._timer_hms = [0, 1, 0]   # [h, m, s] set value
        self._timer_cursor = 1         # which field is selected

        # Countdown/stopwatch state
        self._stopwatch_running = False
        self._stopwatch_start = 0
        self._stopwatch_offset = 0

        # Alarm
        self._alarms = load_alarms()
        self._alarm_sel = 0
        self._alarm_mode = 'list'   # 'list' | 'edit'
        self._edit_field = 0        # 0=hour,1=min,2=enabled
        self._edit_alarm = None

    def on_enter(self):
        super().on_enter()
        self._alarms = load_alarms()

    def tick(self):
        now = time.localtime()
        if now.tm_sec != self._last_sec:
            self._last_sec = now.tm_sec
            self._check_alarms(now)
            self.request_partial()

    def _check_alarms(self, now):
        for alarm in self._alarms:
            if alarm.get('enabled') and \
               alarm['hour'] == now.tm_hour and \
               alarm['minute'] == now.tm_min and \
               now.tm_sec == 0:
                self.app.trigger_alarm(alarm)

    # ── Input ─────────────────────────────────────────────────────────────────

    def handle_input(self, action):
        from input_handler import UP, DOWN, LEFT, RIGHT, BACK, ACCEPT
        if action == BACK:
            if self._tab == 2 and self._alarm_mode == 'edit':
                self._alarm_mode = 'list'
                self.request_partial()
                return True
            self.app.pop_screen()
            return True

        # LEFT / RIGHT switch tabs
        if action == LEFT:
            self._tab = (self._tab - 1) % len(TABS)
            self.request_full()
            return True
        if action == RIGHT:
            self._tab = (self._tab + 1) % len(TABS)
            self.request_full()
            return True

        # UP / DOWN: adjust value or scroll
        if action == UP:
            if self._tab == 1:
                return self._timer_adj(+1)
            if self._tab == 2:
                return self._alarm_adj(-1)
            return True
        if action == DOWN:
            if self._tab == 1:
                return self._timer_adj(-1)
            if self._tab == 2:
                return self._alarm_adj(+1)
            return True

        # ACCEPT: confirm / start / stop / next field
        if action == ACCEPT:
            if self._tab == 1:
                return self._timer_accept()
            if self._tab == 2:
                return self._alarm_accept()
            return True

        return False

    # ── Timer ─────────────────────────────────────────────────────────────────

    def _timer_accept(self):
        if self._timer_running:
            self._timer_running = False
            self._timer_end = 0
        else:
            if self._timer_cursor < 2:
                self._timer_cursor += 1   # advance H→M→S
            else:
                # Start the timer
                secs = (self._timer_hms[0] * 3600 +
                        self._timer_hms[1] * 60 +
                        self._timer_hms[2])
                if secs > 0:
                    self._timer_end = time.time() + secs
                    self._timer_running = True
                    self._timer_cursor = 0
        self.request_partial()
        return True

    def _timer_adj(self, delta):
        if self._timer_running:
            return False
        i = self._timer_cursor   # 0=H, 1=M, 2=S
        limits = [23, 59, 59]
        self._timer_hms[i] = max(0, min(limits[i], self._timer_hms[i] + delta))
        self.request_partial()
        return True

    # ── Alarm ─────────────────────────────────────────────────────────────────

    def _alarm_accept(self):
        if self._alarm_mode == 'list':
            if self._alarm_sel < len(self._alarms):
                self._edit_alarm = dict(self._alarms[self._alarm_sel])
                self._alarm_mode = 'edit'
                self._edit_field = 0
            else:
                self._alarms.append({'hour': 7, 'minute': 0, 'label': 'Alarm', 'enabled': True})
                save_alarms(self._alarms)
                self._alarm_sel = len(self._alarms) - 1
                self._edit_alarm = dict(self._alarms[-1])
                self._alarm_mode = 'edit'
                self._edit_field = 0
        else:
            # Advance through fields; on last field save
            self._edit_field += 1
            if self._edit_field >= 3:
                self._alarms[self._alarm_sel] = self._edit_alarm
                save_alarms(self._alarms)
                self._alarm_mode = 'list'
                self._edit_field = 0
        self.request_partial()
        return True

    def _alarm_adj(self, delta):
        if self._alarm_mode == 'list':
            self._alarm_sel = max(0, min(len(self._alarms), self._alarm_sel + delta))
        else:
            if self._edit_field == 0:
                self._edit_alarm['hour'] = (self._edit_alarm['hour'] - delta) % 24
            elif self._edit_field == 1:
                self._edit_alarm['minute'] = (self._edit_alarm['minute'] - delta) % 60
            elif self._edit_field == 2:
                self._edit_alarm['enabled'] = not self._edit_alarm['enabled']
        self.request_partial()
        return True

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self):
        img = self.new_image()
        draw = ImageDraw.Draw(img)
        f = self.app.fonts

        win95.draw_title_bar(draw, 'Clock', f.title, 'clock', img)

        # Tab bar
        tab_y0 = TB
        tab_h = 30
        tab_w = W // len(TABS)
        for i, t in enumerate(TABS):
            x0 = i * tab_w
            if i == self._tab:
                draw.rectangle([x0, tab_y0, x0 + tab_w - 1, tab_y0 + tab_h], fill=0)
                win95.text_centered(draw, x0 + tab_w // 2, tab_y0 + tab_h // 2, t, f.bold_sm, fill=255)
            else:
                draw.rectangle([x0, tab_y0, x0 + tab_w - 1, tab_y0 + tab_h], fill=255, outline=0)
                win95.text_centered(draw, x0 + tab_w // 2, tab_y0 + tab_h // 2, t, f.bold_sm, fill=0)

        cy_start = tab_y0 + tab_h + 4
        cx = W // 2

        if self._tab == 0:
            self._render_clock(draw, f, cx, cy_start)
        elif self._tab == 1:
            self._render_timer(draw, f, cx, cy_start)
        elif self._tab == 2:
            self._render_alarm(draw, f, cy_start)

        win95.draw_taskbar(draw, f.small, time.strftime('%H:%M'), 'Clock')
        self._dirty = False
        return img

    def _render_clock(self, draw, f, cx, y0):
        now = time.localtime()
        # Digital time
        win95.draw_raised_box(draw, 20, y0 + 10, W - 20, y0 + 80, fill=255)
        win95.text_centered(draw, cx, y0 + 44, time.strftime('%H:%M:%S', now), f.huge, fill=0)

        # Date
        win95.draw_raised_box(draw, 20, y0 + 88, W - 20, y0 + 128, fill=255)
        win95.text_centered(draw, cx, y0 + 108, time.strftime('%A, %d %B %Y', now), f.medium, fill=0)

        # Analogue clock face
        self._draw_analogue(draw, cx, y0 + 280, 180, now)

    def _draw_analogue(self, draw, cx, cy, r, now):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255, outline=0, width=3)
        for i in range(60):
            a = math.radians(i * 6 - 90)
            if i % 5 == 0:
                r1, w = r - 18, 3
            else:
                r1, w = r - 8, 1
            x1 = cx + int(r * math.cos(a))
            y1 = cy + int(r * math.sin(a))
            x2 = cx + int(r1 * math.cos(a))
            y2 = cy + int(r1 * math.sin(a))
            draw.line([(x1, y1), (x2, y2)], fill=0, width=w)

        h = now.tm_hour % 12
        m, s = now.tm_min, now.tm_sec
        for angle, length, width in [
            ((h + m / 60) * 30 - 90, r * 0.55, 6),
            ((m + s / 60) * 6 - 90,  r * 0.80, 4),
            (s * 6 - 90,              r * 0.88, 2),
        ]:
            a = math.radians(angle)
            draw.line([(cx, cy), (cx + int(length * math.cos(a)),
                                  cy + int(length * math.sin(a)))],
                      fill=0, width=width)
        draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=0)

    def _render_timer(self, draw, f, cx, y0):
        h, m, s = self._timer_hms
        remaining = ''
        if self._timer_running:
            rem = max(0, int(self._timer_end - time.time()))
            rh, rm = divmod(rem, 3600)
            rm, rs = divmod(rm, 60)
            remaining = f'{rh:02d}:{rm:02d}:{rs:02d}'
            if rem == 0:
                self._timer_running = False

        win95.draw_raised_box(draw, 20, y0 + 10, W - 20, y0 + 80, fill=255)
        disp = remaining if self._timer_running else f'{h:02d}:{m:02d}:{s:02d}'
        win95.text_centered(draw, cx, y0 + 44, disp, f.huge, fill=0)

        if not self._timer_running:
            labels = [f'H:{h:02d}', f'M:{m:02d}', f'S:{s:02d}']
            for i, lbl in enumerate(labels):
                bx = 20 + i * 148
                sel = (self._timer_cursor == i)
                win95.draw_button(draw, bx, y0 + 100, bx + 130, y0 + 140, lbl, f.large, selected=sel)

            win95.draw_button(draw, 100, y0 + 160, 380, y0 + 210,
                              'START', f.large, selected=(self._timer_cursor == 3))
        else:
            win95.draw_button(draw, 100, y0 + 100, 380, y0 + 150, 'STOP', f.large, selected=True)

        draw.text((8, y0 + 230), 'UP/DOWN: adjust field  ACCEPT: next field / start', font=f.small, fill=0)

    def _render_alarm(self, draw, f, y0):
        if self._alarm_mode == 'list':
            draw.text((10, y0 + 6), 'Alarms  (ACCEPT=edit  UP/DOWN=scroll)', font=f.small, fill=0)
            for i, alarm in enumerate(self._alarms):
                by = y0 + 30 + i * 52
                sel = (i == self._alarm_sel)
                status = 'ON ' if alarm['enabled'] else 'OFF'
                lbl = f"{alarm['hour']:02d}:{alarm['minute']:02d}  {status}  {alarm.get('label', '')}"
                win95.draw_button(draw, 10, by, W - 10, by + 44, lbl, f.medium, selected=sel)
            # New alarm button
            ny = y0 + 30 + len(self._alarms) * 52
            sel = (self._alarm_sel == len(self._alarms))
            win95.draw_button(draw, 10, ny, W - 10, ny + 44, '+ New Alarm', f.medium, selected=sel)
        else:
            ea = self._edit_alarm
            draw.text((10, y0 + 6), 'Edit Alarm  (UP/DOWN: change  ACCEPT: next/save)', font=f.small, fill=0)
            for fi, (label, val) in enumerate([
                ('Hour',    f"{ea['hour']:02d}"),
                ('Minute',  f"{ea['minute']:02d}"),
                ('Enabled', 'Yes' if ea['enabled'] else 'No'),
            ]):
                by = y0 + 30 + fi * 70
                sel = (fi == self._edit_field)
                win95.draw_raised_box(draw, 20, by, W - 20, by + 60, fill=255)
                draw.text((30, by + 6), label, font=f.small, fill=0)
                win95.text_centered(draw, W // 2, by + 38, val,
                                    f.bold_lg if sel else f.large, fill=0)
                if sel:
                    draw.rectangle([20, by, W - 20, by + 60], outline=0, width=3)
            draw.text((10, y0 + 250), 'ACCEPT on Enabled = save', font=f.small, fill=0)

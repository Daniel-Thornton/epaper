import json
import os
import threading
import time
import wave
from datetime import datetime
from pathlib import Path

os.environ.setdefault('GPIOZERO_PIN_FACTORY', 'lgpio')
try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False

import battery
import camera
import voice
from state import state, APPS, CALC_FLAT, SYMBOL_FLAT

DATA_DIR   = Path(__file__).parent / 'data'
REC_DIR    = DATA_DIR / 'recordings'
PHOTOS_DIR = Path(__file__).parent / 'static' / 'photos'

# ── GPIO pins ─────────────────────────────────────────────────────────────────
PIN_UP      = 20
PIN_DOWN    = 13
PIN_LEFT    = 12
PIN_RIGHT   = 21
PIN_BACK    = 26
PIN_ACCEPT  = 19
PIN_REFRESH = 5
PIN_MIC     = 0

COLS_HOME = 3
COLS_SYM  = 6
ROWS_SYM  = 6


# ── data helpers ──────────────────────────────────────────────────────────────

def _load(fname, default):
    p = DATA_DIR / fname
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return default


def _save(fname, data):
    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_DIR / fname, 'w') as f:
        json.dump(data, f, indent=2)


def _list_recs():
    REC_DIR.mkdir(parents=True, exist_ok=True)
    recs = []
    for p in sorted(REC_DIR.glob('*.wav'), reverse=True):
        try:
            with wave.open(str(p), 'rb') as wf:
                dur = wf.getnframes() / wf.getframerate()
        except Exception:
            dur = 0
        recs.append({'name': p.stem, 'path': str(p), 'duration': dur})
    return recs


# ── screen handlers ───────────────────────────────────────────────────────────

def _home(btn):
    s = state
    n = len(APPS)
    if btn == 'UP':
        s.selected = (s.selected - COLS_HOME) % n
        s.mark_dirty()
    elif btn == 'DOWN':
        s.selected = (s.selected + COLS_HOME) % n
        s.mark_dirty()
    elif btn == 'LEFT':
        s.selected = (s.selected - 1) % n
        s.mark_dirty()
    elif btn == 'RIGHT':
        s.selected = (s.selected + 1) % n
        s.mark_dirty()
    elif btn == 'ACCEPT':
        dest = APPS[s.selected][1]
        s.home_selected = s.selected   # remember position before leaving
        if dest == 'camera':
            camera.start(on_frame=state.mark_dirty)
        if dest == 'images':
            s.images_view = 'list'
            s.images_idx  = 0
        s.go(dest)


def _notes(btn):
    s = state
    notes = _load('notes.json', [])
    n = len(notes)
    # Index 0 = "+ New Note", indices 1..n = notes[0..n-1]

    if s.notes_view == 'list':
        if btn in ('UP', 'LEFT'):
            s.notes_idx = max(0, s.notes_idx - 1)
            s.mark_dirty()
        elif btn in ('DOWN', 'RIGHT'):
            s.notes_idx = min(n, s.notes_idx + 1)
            s.mark_dirty()
        elif btn == 'ACCEPT':
            if s.notes_idx == 0:
                s.go('text_input',
                     ti_prompt='New Note — speak or type',
                     ti_purpose='add_note',
                     ti_return='notes',
                     ti_value='',
                     ti_kb_cursor=0)
            else:
                s.notes_view = 'view'
                s.mark_dirty()
        elif btn == 'BACK':
            s.go('home')

    elif s.notes_view == 'view':
        if btn == 'BACK':
            s.notes_view = 'list'
            s.mark_dirty()
        elif btn == 'ACCEPT':
            s.notes_view = 'confirm'
            s.notes_confirm_sel = 0
            s.mark_dirty()

    elif s.notes_view == 'confirm':
        if btn in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
            s.notes_confirm_sel = 1 - s.notes_confirm_sel
            s.mark_dirty()
        elif btn == 'ACCEPT':
            if s.notes_confirm_sel == 1:
                notes = _load('notes.json', [])
                idx = s.notes_idx - 1
                if 0 <= idx < len(notes):
                    notes.pop(idx)
                    _save('notes.json', notes)
                s.notes_idx = max(0, s.notes_idx - 1)
            s.notes_view = 'list'
            s.mark_dirty()
        elif btn == 'BACK':
            s.notes_view = 'view'
            s.mark_dirty()


def _todo(btn):
    s = state
    todos = _load('todos.json', [])
    n = len(todos)
    # Index 0 = "+ New Task", indices 1..n = todos[0..n-1]

    if s.todo_view == 'list':
        if btn == 'UP':
            s.todo_idx = max(0, s.todo_idx - 1)
            s.mark_dirty()
        elif btn in ('DOWN', 'RIGHT'):
            s.todo_idx = min(n, s.todo_idx + 1)
            s.mark_dirty()
        elif btn == 'LEFT':
            if s.todo_idx > 0:
                s.todo_view = 'confirm'
                s.todo_confirm_sel = 0
                s.mark_dirty()
            else:
                s.todo_idx = max(0, s.todo_idx - 1)
                s.mark_dirty()
        elif btn == 'ACCEPT':
            if s.todo_idx == 0:
                s.go('text_input',
                     ti_prompt='New Task — speak or type',
                     ti_purpose='add_todo',
                     ti_return='todo',
                     ti_value='',
                     ti_kb_cursor=0)
            else:
                todos[s.todo_idx - 1]['done'] = not todos[s.todo_idx - 1]['done']
                _save('todos.json', todos)
                s.mark_dirty()
        elif btn == 'BACK':
            s.go('home')

    elif s.todo_view == 'confirm':
        if btn in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
            s.todo_confirm_sel = 1 - s.todo_confirm_sel
            s.mark_dirty()
        elif btn == 'ACCEPT':
            if s.todo_confirm_sel == 1:
                todos = _load('todos.json', [])
                idx = s.todo_idx - 1
                if 0 <= idx < len(todos):
                    todos.pop(idx)
                    _save('todos.json', todos)
                s.todo_idx = max(0, s.todo_idx - 1)
            s.todo_view = 'list'
            s.mark_dirty()
        elif btn == 'BACK':
            s.todo_view = 'list'
            s.mark_dirty()


def _clock(btn):
    s = state
    if btn == 'LEFT':
        s.clock_tab = (s.clock_tab - 1) % 3
        s.mark_dirty()
    elif btn == 'RIGHT':
        s.clock_tab = (s.clock_tab + 1) % 3
        s.mark_dirty()
    elif btn == 'ACCEPT' and s.clock_tab == 1:
        if s.timer_end is None:
            s.timer_end = time.monotonic() + s.timer_total
        else:
            s.timer_end = None
        s.mark_dirty()
    elif btn == 'BACK':
        s.go('home')


def _calc(btn):
    s = state
    n    = len(CALC_FLAT)
    cols = 4
    if btn == 'UP':
        s.calc_cursor = (s.calc_cursor - cols) % n
        s.mark_dirty()
    elif btn == 'DOWN':
        s.calc_cursor = (s.calc_cursor + cols) % n
        s.mark_dirty()
    elif btn == 'LEFT':
        s.calc_cursor = (s.calc_cursor - 1) % n
        s.mark_dirty()
    elif btn == 'RIGHT':
        s.calc_cursor = (s.calc_cursor + 1) % n
        s.mark_dirty()
    elif btn == 'ACCEPT':
        _press_calc(CALC_FLAT[s.calc_cursor])
    elif btn == 'BACK':
        if s.calc_expr:
            s.calc_expr    = s.calc_expr[:-1]
            s.calc_display = s.calc_expr or '0'
            s.mark_dirty()
        else:
            s.go('home')


def _press_calc(key):
    s = state
    if key == 'C':
        s.calc_expr = ''; s.calc_display = '0'
    elif key == '⌫':
        s.calc_expr    = s.calc_expr[:-1]
        s.calc_display = s.calc_expr or '0'
    elif key == '=':
        try:
            expr   = s.calc_expr.replace('×', '*').replace('÷', '/')
            result = eval(expr)
            if isinstance(result, float) and result == int(result):
                result = int(result)
            s.calc_display = str(result)
            s.calc_expr    = str(result)
        except Exception:
            s.calc_display = 'Error'; s.calc_expr = ''
    elif key == '±':
        try:
            val = eval(s.calc_expr or '0') * -1
            s.calc_expr = str(int(val) if float(val) == int(val) else val)
            s.calc_display = s.calc_expr
        except Exception:
            pass
    elif key == '%':
        try:
            val = eval(s.calc_expr or '0') / 100
            s.calc_expr    = str(val)
            s.calc_display = s.calc_expr
        except Exception:
            pass
    else:
        if s.calc_display == '0' and key.isdigit():
            s.calc_expr = key
        else:
            s.calc_expr += key
        s.calc_display = s.calc_expr
    s.mark_dirty()


def _settings(btn):
    s = state
    if btn in ('UP', 'LEFT'):
        s.settings_idx = max(0, s.settings_idx - 1)
        s.mark_dirty()
    elif btn in ('DOWN', 'RIGHT'):
        s.settings_idx = min(4, s.settings_idx + 1)  # 5 items: 0-4
        s.mark_dirty()
    elif btn == 'ACCEPT' and s.settings_idx == 4:
        battery.toggle_charging()
    elif btn == 'BACK':
        s.go('home')


def _camera(btn):
    if btn == 'ACCEPT':
        camera.capture_still()
        state.mark_dirty()
    elif btn == 'BACK':
        camera.stop()
        state.go('home')


# ── text input screen ─────────────────────────────────────────────────────────

def _text_input(btn):
    s    = state
    cols = COLS_SYM
    rows = ROWS_SYM
    row  = s.ti_kb_cursor // cols
    col  = s.ti_kb_cursor  % cols

    if btn == 'UP':
        row = (row - 1) % rows
        s.ti_kb_cursor = row * cols + col
        s.mark_dirty()
    elif btn == 'DOWN':
        row = (row + 1) % rows
        s.ti_kb_cursor = row * cols + col
        s.mark_dirty()
    elif btn == 'LEFT':
        col = (col - 1) % cols
        s.ti_kb_cursor = row * cols + col
        s.mark_dirty()
    elif btn == 'RIGHT':
        col = (col + 1) % cols
        s.ti_kb_cursor = row * cols + col
        s.mark_dirty()
    elif btn == 'ACCEPT':
        _type_symbol(SYMBOL_FLAT[s.ti_kb_cursor])
    elif btn == 'BACK':
        if s.ti_value:
            s.ti_value = s.ti_value[:-1]
            s.mark_dirty()
        else:
            _cancel_ti()


def _type_symbol(key):
    s = state
    if key == '':
        return
    if key == '⎵':
        s.ti_value += ' '
    elif key == '⌫':
        s.ti_value = s.ti_value[:-1]
    elif key == '↵':
        s.ti_value += '\n'
    elif key == '✓':
        _confirm_ti()
        return
    elif key == '✗':
        _cancel_ti()
        return
    else:
        s.ti_value += key
    s.mark_dirty()


def _confirm_ti():
    s    = state
    text = s.ti_value.strip()

    if s.ti_purpose == 'add_note' and text:
        notes  = _load('notes.json', [])
        lines  = text.split('\n', 1)
        title  = lines[0][:80]
        body   = lines[1].strip() if len(lines) > 1 else text
        new_id = max((n['id'] for n in notes), default=0) + 1
        notes.append({
            'id':      new_id,
            'title':   title,
            'content': body,
            'created': datetime.now().isoformat()[:19],
        })
        _save('notes.json', notes)

    elif s.ti_purpose == 'add_todo' and text:
        todos  = _load('todos.json', [])
        new_id = max((t['id'] for t in todos), default=0) + 1
        todos.append({'id': new_id, 'text': text, 'done': False})
        _save('todos.json', todos)

    s.go(s.ti_return)


def _cancel_ti():
    state.go(state.ti_return)


# ── external keyboard → text input ───────────────────────────────────────────

def handle_external_key(char: str):
    """Called from keyboard_ext for every USB keystroke."""
    s = state
    if s.screen == 'text_input':
        if char == '⌫':
            if s.ti_value:
                s.ti_value = s.ti_value[:-1]
                s.mark_dirty()
        elif char in ('↵', '\r'):
            _confirm_ti()
        elif char == '\x1b':
            _cancel_ti()
        elif char == '\t':
            s.ti_value += '    '
            s.mark_dirty()
        elif char in ('↑', '↓', '←', '→'):
            pass  # arrow keys ignored in text input
        else:
            s.ti_value += char
            s.mark_dirty()
    else:
        NAV = {
            'w': 'UP',    '↑': 'UP',
            's': 'DOWN',  '↓': 'DOWN',
            'a': 'LEFT',  '←': 'LEFT',
            'd': 'RIGHT', '→': 'RIGHT',
            '\x1b': 'BACK', '⌫': 'BACK',
            '\r': 'ACCEPT', '↵': 'ACCEPT', ' ': 'ACCEPT',
        }
        btn = NAV.get(char.lower())
        if btn:
            handle(btn)


# ── audio recorder ────────────────────────────────────────────────────────────

def _audio_recorder(btn):
    s    = state
    recs = _list_recs()
    n    = len(recs)

    if btn in ('UP', 'LEFT'):
        s.audio_rec_idx = max(0, s.audio_rec_idx - 1)
        s.mark_dirty()
    elif btn in ('DOWN', 'RIGHT'):
        s.audio_rec_idx = min(max(0, n - 1), s.audio_rec_idx + 1)
        s.mark_dirty()
    elif btn == 'ACCEPT':
        if not s.audio_recording:
            if voice.start_recording():
                s.audio_recording = True
                s.audio_rec_start = time.monotonic()
                s.mark_dirty()
        else:
            _stop_and_save_rec()
    elif btn == 'BACK':
        if s.audio_recording:
            _stop_and_save_rec()
        else:
            s.go('home')


def _stop_and_save_rec():
    s     = state
    fname = f"rec_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.wav"
    path  = str(REC_DIR / fname)
    voice.stop_and_save(path)
    s.audio_recording = False
    s.audio_rec_start = None
    s.audio_rec_idx   = 0
    s.mark_dirty()


def _list_photos():
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
    return sorted(
        [p for p in PHOTOS_DIR.iterdir() if p.suffix.lower() in exts],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _images(btn):
    s      = state
    photos = _list_photos()
    n      = len(photos)

    if s.images_view == 'list':
        if btn in ('UP', 'LEFT'):
            s.images_idx = max(0, s.images_idx - 1)
            s.mark_dirty()
        elif btn in ('DOWN', 'RIGHT'):
            s.images_idx = min(max(0, n - 1), s.images_idx + 1)
            s.mark_dirty()
        elif btn == 'ACCEPT' and n > 0:
            s.images_view = 'view'
            s.mark_dirty()
        elif btn == 'BACK':
            s.go('home')

    elif s.images_view == 'view':
        if btn in ('UP', 'LEFT'):
            s.images_idx = max(0, s.images_idx - 1)
            s.mark_dirty()
        elif btn in ('DOWN', 'RIGHT'):
            s.images_idx = min(max(0, n - 1), s.images_idx + 1)
            s.mark_dirty()
        elif btn == 'ACCEPT':
            s.images_view        = 'confirm'
            s.images_confirm_sel = 0
            s.mark_dirty()
        elif btn == 'BACK':
            s.images_view = 'list'
            s.mark_dirty()

    elif s.images_view == 'confirm':
        if btn in ('LEFT', 'RIGHT', 'UP', 'DOWN'):
            s.images_confirm_sel = 1 - s.images_confirm_sel
            s.mark_dirty()
        elif btn == 'ACCEPT':
            if s.images_confirm_sel == 1 and 0 <= s.images_idx < n:
                try:
                    photos[s.images_idx].unlink()
                except Exception as e:
                    print(f'[images] delete error: {e}')
                s.images_idx = 0
            s.images_view = 'list'
            s.mark_dirty()
        elif btn == 'BACK':
            s.images_view = 'view'
            s.mark_dirty()


def _back_only(btn):
    if btn == 'BACK':
        state.go('home')


def _webapp(btn):
    s = state
    if btn == 'BACK':
        s.browser_cmd = None
        s.go('home')
        return
    cmd = {
        'UP':     {'action': 'scroll', 'x': 0,  'y': -250},
        'DOWN':   {'action': 'scroll', 'x': 0,  'y':  250},
        'LEFT':   {'action': 'key', 'key': 'Shift+Tab'},
        'RIGHT':  {'action': 'key', 'key': 'Tab'},
        'ACCEPT': {'action': 'key', 'key': 'Enter'},
    }.get(btn)
    if cmd:
        s.browser_cmd = cmd
        s.mark_dirty()


# ── main dispatch ─────────────────────────────────────────────────────────────

_HANDLERS = {
    'home':              _home,
    'notes':             _notes,
    'todo':              _todo,
    'clock':             _clock,
    'calculator':        _calc,
    'settings':          _settings,
    'camera':            _camera,
    'images':            _images,
    'text_input':        _text_input,
    'audio_recorder':    _audio_recorder,
    'webapp_chat':       _webapp,
    'webapp_calories':   _webapp,
    'info':              _back_only,
}


def handle(btn: str):
    h = _HANDLERS.get(state.screen)
    if h:
        h(btn)


# ── GPIO 6: mic button (push-to-hold) ────────────────────────────────────────

def _on_mic_press():
    s = state
    if s.screen == 'text_input':
        if voice.start_recording():
            s.recording_voice = True
            s.mark_dirty()
    elif s.screen == 'audio_recorder' and not s.audio_recording:
        if voice.start_recording():
            s.audio_recording = True
            s.audio_rec_start = time.monotonic()
            s.mark_dirty()


def _on_mic_release():
    s = state
    if s.screen == 'text_input' and s.recording_voice:
        s.recording_voice = False
        s.transcribing    = True
        s.mark_dirty()
        threading.Thread(target=_transcribe_bg, daemon=True, name='transcribe').start()
    elif s.screen == 'audio_recorder' and s.audio_recording:
        _stop_and_save_rec()


def _transcribe_bg():
    text = voice.stop_and_transcribe()
    s    = state
    s.transcribing = False
    if text and s.screen == 'text_input':
        if s.ti_value and not s.ti_value.endswith(' '):
            s.ti_value += ' '
        s.ti_value += text
    s.mark_dirty()


# ── GPIO setup ────────────────────────────────────────────────────────────────

def start():
    if not GPIO_AVAILABLE:
        print('[input] GPIO not available — use --keyboard flag')
        return ()

    def cb(name):
        return lambda: handle(name)

    nav_btns = (
        Button(PIN_UP,     pull_up=True, bounce_time=0.08),
        Button(PIN_DOWN,   pull_up=True, bounce_time=0.08),
        Button(PIN_LEFT,   pull_up=True, bounce_time=0.08),
        Button(PIN_RIGHT,  pull_up=True, bounce_time=0.08),
        Button(PIN_BACK,   pull_up=True, bounce_time=0.08),
        Button(PIN_ACCEPT, pull_up=True, bounce_time=0.08),
    )
    nav_btns[0].when_pressed = cb('UP')
    nav_btns[1].when_pressed = cb('DOWN')
    nav_btns[2].when_pressed = cb('LEFT')
    nav_btns[3].when_pressed = cb('RIGHT')
    nav_btns[4].when_pressed = cb('BACK')
    nav_btns[5].when_pressed = cb('ACCEPT')

    refresh_btn = Button(PIN_REFRESH, pull_up=True, bounce_time=0.05)
    refresh_btn.when_pressed = lambda: _set_full_refresh()

    mic_btn = Button(PIN_MIC, pull_up=True, bounce_time=0.05)
    mic_btn.when_pressed  = _on_mic_press
    mic_btn.when_released = _on_mic_release

    print('[input] 8 GPIO buttons registered (6 nav + refresh + mic)')
    return nav_btns + (refresh_btn, mic_btn)


def _set_full_refresh():
    state.force_full_refresh = True
    state.mark_dirty()

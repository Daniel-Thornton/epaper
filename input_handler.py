import json
import os
import time
from pathlib import Path

# Pi 5 / Bookworm: only lgpio backend works
os.environ.setdefault('GPIOZERO_PIN_FACTORY', 'lgpio')

try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False

from state import state, APPS, CALC_FLAT

DATA_DIR = Path(__file__).parent / 'data'

PIN_UP     = 20
PIN_DOWN   = 13
PIN_LEFT   = 16
PIN_RIGHT  = 21
PIN_BACK   = 26
PIN_ACCEPT = 19


# ── helpers ──────────────────────────────────────────────────────────────────

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


# ── per-screen handlers ───────────────────────────────────────────────────────

COLS = 3  # home grid columns

def _home(btn):
    s = state
    n = len(APPS)
    if btn == 'UP':
        s.selected = (s.selected - COLS) % n
        s.mark_dirty()
    elif btn == 'DOWN':
        s.selected = (s.selected + COLS) % n
        s.mark_dirty()
    elif btn == 'LEFT':
        s.selected = (s.selected - 1) % n
        s.mark_dirty()
    elif btn == 'RIGHT':
        s.selected = (s.selected + 1) % n
        s.mark_dirty()
    elif btn == 'ACCEPT':
        s.go(APPS[s.selected][1])


def _notes(btn):
    s = state
    notes = _load('notes.json', [])
    if s.notes_view == 'list':
        if btn in ('UP', 'LEFT'):
            s.notes_idx = max(0, s.notes_idx - 1)
            s.mark_dirty()
        elif btn in ('DOWN', 'RIGHT'):
            s.notes_idx = min(len(notes) - 1, max(0, s.notes_idx + 1))
            s.mark_dirty()
        elif btn == 'ACCEPT' and notes:
            s.notes_view = 'view'
            s.mark_dirty()
        elif btn == 'BACK':
            s.go('home')
    else:
        if btn == 'BACK':
            s.notes_view = 'list'
            s.mark_dirty()


def _todo(btn):
    s = state
    todos = _load('todos.json', [])
    if btn in ('UP', 'LEFT'):
        s.todo_idx = max(0, s.todo_idx - 1)
        s.mark_dirty()
    elif btn in ('DOWN', 'RIGHT'):
        s.todo_idx = min(len(todos) - 1, max(0, s.todo_idx + 1))
        s.mark_dirty()
    elif btn == 'ACCEPT' and todos:
        todos[s.todo_idx]['done'] = not todos[s.todo_idx]['done']
        _save('todos.json', todos)
        s.mark_dirty()
    elif btn == 'BACK':
        s.go('home')


def _clock(btn):
    s = state
    if btn in ('LEFT',):
        s.clock_tab = (s.clock_tab - 1) % 3
        s.mark_dirty()
    elif btn in ('RIGHT',):
        s.clock_tab = (s.clock_tab + 1) % 3
        s.mark_dirty()
    elif btn == 'ACCEPT' and s.clock_tab == 1:
        import time as _t
        if s.timer_end is None:
            s.timer_end = _t.monotonic() + s.timer_total
        else:
            s.timer_end = None
        s.mark_dirty()
    elif btn == 'BACK':
        s.go('home')


def _calc(btn):
    s = state
    n = len(CALC_FLAT)
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
        _press(CALC_FLAT[s.calc_cursor])
    elif btn == 'BACK':
        if s.calc_expr:
            s.calc_expr = s.calc_expr[:-1]
            s.calc_display = s.calc_expr or '0'
            s.mark_dirty()
        else:
            s.go('home')


def _press(key):
    s = state
    if key == 'C':
        s.calc_expr = ''
        s.calc_display = '0'
    elif key == '⌫':
        s.calc_expr = s.calc_expr[:-1]
        s.calc_display = s.calc_expr or '0'
    elif key == '=':
        try:
            expr = s.calc_expr.replace('×', '*').replace('÷', '/')
            result = eval(expr)  # local device, acceptable
            # Format: remove trailing .0 for clean integers
            if isinstance(result, float) and result == int(result):
                result = int(result)
            s.calc_display = str(result)
            s.calc_expr = str(result)
        except Exception:
            s.calc_display = 'Error'
            s.calc_expr = ''
    elif key == '±':
        try:
            val = eval(s.calc_expr or '0') * -1
            s.calc_expr = str(val)
            s.calc_display = s.calc_expr
        except Exception:
            pass
    elif key == '%':
        try:
            val = eval(s.calc_expr or '0') / 100
            s.calc_expr = str(val)
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
    n = 4
    if btn in ('UP', 'LEFT'):
        s.settings_idx = max(0, s.settings_idx - 1)
        s.mark_dirty()
    elif btn in ('DOWN', 'RIGHT'):
        s.settings_idx = min(n - 1, s.settings_idx + 1)
        s.mark_dirty()
    elif btn == 'BACK':
        s.go('home')


def _camera(btn):
    s = state
    if btn == 'SELECT':
        _capture()
    elif btn == 'BACK':
        s.go('home')


def _capture():
    try:
        from picamera2 import Picamera2
        cam = Picamera2()
        cam.configure(cam.create_still_configuration())
        cam.start()
        time.sleep(1.5)
        save_path = str(Path(__file__).parent / 'static' / 'last_photo.jpg')
        cam.capture_file(save_path)
        cam.stop()
        cam.close()
        print(f'[camera] captured to {save_path}')
    except Exception as e:
        print(f'[camera] error: {e}')
    state.mark_dirty()


# ── public dispatch ───────────────────────────────────────────────────────────

def _back_only(btn):
    if btn == 'BACK':
        state.go('home')

_HANDLERS = {
    'home':              _home,
    'notes':             _notes,
    'todo':              _todo,
    'clock':             _clock,
    'calculator':        _calc,
    'settings':          _settings,
    'camera':            _camera,
    'webapp_chat':       _back_only,
    'webapp_calories':   _back_only,
    'info':              _back_only,
}


def handle(btn: str):
    h = _HANDLERS.get(state.screen)
    if h:
        h(btn)


def start():
    """Wire up GPIO buttons. Returns button objects (keep alive)."""
    if not GPIO_AVAILABLE:
        print('[input] GPIO not available — use keyboard fallback (--keyboard flag)')
        return ()

    def cb(name):
        return lambda: handle(name)

    btns = (
        Button(PIN_UP,     pull_up=True, bounce_time=0.08),
        Button(PIN_DOWN,   pull_up=True, bounce_time=0.08),
        Button(PIN_LEFT,   pull_up=True, bounce_time=0.08),
        Button(PIN_RIGHT,  pull_up=True, bounce_time=0.08),
        Button(PIN_BACK,   pull_up=True, bounce_time=0.08),
        Button(PIN_ACCEPT, pull_up=True, bounce_time=0.08),
    )
    btns[0].when_pressed = cb('UP')
    btns[1].when_pressed = cb('DOWN')
    btns[2].when_pressed = cb('LEFT')
    btns[3].when_pressed = cb('RIGHT')
    btns[4].when_pressed = cb('BACK')
    btns[5].when_pressed = cb('ACCEPT')
    print('[input] 6 GPIO buttons registered')
    return btns

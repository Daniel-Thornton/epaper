import threading

APPS = [
    ('Notes',       'notes'),
    ('To-Do',       'todo'),
    ('Camera',      'camera'),
    ('Clock',       'clock'),
    ('Calc',        'calculator'),
    ('Settings',    'settings'),
    ('Pi Info',     'info'),
    ('Voice Notes', 'audio_recorder'),
    ('Chat',        'webapp_chat'),
    ('Calories',    'webapp_calories'),
]

APP_ICONS = ['✎', '✔', '◉', '◷', '#', '⚙', 'π', '♪', '✉', '⊕']

APP_ICON_FILES = [
    'notes.png',
    'todo.png',
    'camera.png',
    'clock.png',
    'calculator.png',
    'settings.png',
    'info.png',
    'voice.png',
    'chat.png',
    'calories.png',
]

CALC_BUTTONS = [
    ['C',  '±', '%', '÷'],
    ['7',  '8', '9', '×'],
    ['4',  '5', '6', '-'],
    ['1',  '2', '3', '+'],
    ['0',  '.', '⌫', '='],
]
CALC_FLAT = [b for row in CALC_BUTTONS for b in row]

# Symbol keyboard for text input — 6 cols × 6 rows = 36 keys
SYMBOL_KB = [
    ['1',  '2',  '3',  '4',  '5',  '6'],
    ['7',  '8',  '9',  '0',  '.',  ','],
    ['!',  '?',  ':',  ';',  "'",  '"'],
    ['-',  '_',  '(',  ')',  '@',  '&'],
    ['/',  '+',  '=',  '#',  '*',  '~'],
    ['⎵',  '⌫',  '↵',  '✓',  '✗',  ''],
]
SYMBOL_FLAT = [k for row in SYMBOL_KB for k in row]


class AppState:
    def __init__(self):
        self._lock  = threading.Lock()
        self.dirty  = threading.Event()

        # ── navigation ────────────────────────────────────────────
        self.screen   = 'home'
        self.selected = 0

        # ── notes ─────────────────────────────────────────────────
        self.notes_view = 'list'   # 'list' | 'view'
        self.notes_idx  = 0

        # ── todo ──────────────────────────────────────────────────
        self.todo_idx = 0

        # ── clock ─────────────────────────────────────────────────
        self.clock_tab  = 0        # 0=clock 1=timer 2=alarms
        self.alarm_idx  = 0
        self.timer_total = 60
        self.timer_end   = None    # monotonic finish time

        # ── calculator ────────────────────────────────────────────
        self.calc_expr    = ''
        self.calc_display = '0'
        self.calc_cursor  = 0

        # ── settings ──────────────────────────────────────────────
        self.settings_idx = 0

        # ── text input screen ─────────────────────────────────────
        self.ti_value     = ''     # text being composed
        self.ti_prompt    = ''     # label shown in title bar
        self.ti_purpose   = ''     # 'add_note' | 'add_todo'
        self.ti_return    = 'home' # screen to go back to on confirm/cancel
        self.ti_kb_cursor = 0      # flat index into SYMBOL_FLAT

        # ── voice / mic state ─────────────────────────────────────
        self.recording_voice = False   # GPIO 6 held, recording
        self.transcribing    = False   # transcription in progress

        # ── audio recorder app ────────────────────────────────────
        self.audio_rec_idx      = 0
        self.audio_recording    = False
        self.audio_rec_start    = None  # monotonic start time

        # ── display ───────────────────────────────────────────────
        self.force_full_refresh = False

        # ── webapp browser commands ────────────────────────────────
        self.browser_cmd = None  # dict set by input_handler, consumed by render

    def mark_dirty(self):
        self.dirty.set()

    def go(self, screen, **kwargs):
        with self._lock:
            self.screen   = screen
            self.selected = 0
            for k, v in kwargs.items():
                setattr(self, k, v)
        self.dirty.set()


state = AppState()

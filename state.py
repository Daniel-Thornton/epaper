import threading

APPS = [
    ('Notes',    'notes'),
    ('To-Do',    'todo'),
    ('Camera',   'camera'),
    ('Clock',    'clock'),
    ('Calc',     'calculator'),
    ('Settings', 'settings'),
    ('Pi Info',  'info'),
    ('Chat',     'webapp_chat'),
    ('Calories', 'webapp_calories'),
]

CALC_BUTTONS = [
    ['C',  '±', '%', '÷'],
    ['7',  '8', '9', '×'],
    ['4',  '5', '6', '-'],
    ['1',  '2', '3', '+'],
    ['0',  '.', '⌫', '='],
]
CALC_FLAT = [b for row in CALC_BUTTONS for b in row]


class AppState:
    def __init__(self):
        self._lock = threading.Lock()
        self.dirty = threading.Event()

        self.screen = 'home'
        self.selected = 0

        # Notes
        self.notes_view = 'list'
        self.notes_idx = 0

        # Todo
        self.todo_idx = 0

        # Clock
        self.clock_tab = 0      # 0=clock 1=timer 2=alarms
        self.alarm_idx = 0

        # Timer (seconds remaining, or None if stopped)
        self.timer_total = 60
        self.timer_end = None   # monotonic time when timer finishes

        # Calculator
        self.calc_expr = ''
        self.calc_display = '0'
        self.calc_cursor = 0

        # Settings
        self.settings_idx = 0

    def mark_dirty(self):
        self.dirty.set()

    def go(self, screen, **kwargs):
        with self._lock:
            self.screen = screen
            self.selected = 0
            for k, v in kwargs.items():
                setattr(self, k, v)
        self.dirty.set()


state = AppState()

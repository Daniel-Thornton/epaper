"""
USB keyboard input via evdev for headless Pi operation.

Setup:
  sudo apt install python3-evdev   OR   pip install evdev
  sudo usermod -aG input $USER     (then log out and back in)
"""
import threading

try:
    from evdev import InputDevice, categorize, ecodes, list_devices
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False
    print('[keyboard_ext] evdev not available — sudo apt install python3-evdev')

# ── key → character map ───────────────────────────────────────────────────────
# Tuples are (normal, shifted); strings are invariant.
_KEYMAP = {
    'KEY_A':'a','KEY_B':'b','KEY_C':'c','KEY_D':'d','KEY_E':'e',
    'KEY_F':'f','KEY_G':'g','KEY_H':'h','KEY_I':'i','KEY_J':'j',
    'KEY_K':'k','KEY_L':'l','KEY_M':'m','KEY_N':'n','KEY_O':'o',
    'KEY_P':'p','KEY_Q':'q','KEY_R':'r','KEY_S':'s','KEY_T':'t',
    'KEY_U':'u','KEY_V':'v','KEY_W':'w','KEY_X':'x','KEY_Y':'y',
    'KEY_Z':'z',
    'KEY_1':('1','!'), 'KEY_2':('2','@'), 'KEY_3':('3','#'),
    'KEY_4':('4','$'), 'KEY_5':('5','%'), 'KEY_6':('6','^'),
    'KEY_7':('7','&'), 'KEY_8':('8','*'), 'KEY_9':('9','('),
    'KEY_0':('0',')'),
    'KEY_MINUS':     ('-','_'),  'KEY_EQUAL':    ('=','+'),
    'KEY_LEFTBRACE': ('[','{'),  'KEY_RIGHTBRACE':(']','}'),
    'KEY_SEMICOLON': (';',':'),  'KEY_APOSTROPHE':("'",'"'),
    'KEY_COMMA':     (',','<'),  'KEY_DOT':       ('.','>'),
    'KEY_SLASH':     ('/','?'),  'KEY_BACKSLASH': ('\\','|'),
    'KEY_GRAVE':     ('`','~'),
    'KEY_SPACE':     ' ',
    'KEY_BACKSPACE': '⌫',
    'KEY_ENTER':     '↵',
    'KEY_KP_ENTER':  '↵',
    'KEY_TAB':       '\t',
    'KEY_ESC':       '\x1b',
    'KEY_UP':        '↑',
    'KEY_DOWN':      '↓',
    'KEY_LEFT':      '←',
    'KEY_RIGHT':     '→',
}

_SHIFT_KEYS = {'KEY_LEFTSHIFT', 'KEY_RIGHTSHIFT'}
_CAPS_KEYS  = {'KEY_CAPSLOCK'}


def _find_keyboard():
    for path in list_devices():
        try:
            dev  = InputDevice(path)
            caps = dev.capabilities()
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                if ecodes.KEY_A in keys and ecodes.KEY_SPACE in keys:
                    return dev
        except Exception:
            pass
    return None


def start(on_char) -> object:
    """
    Locate a USB keyboard and call on_char(str) for each keystroke.
    Letters are lowercase unless Shift/CapsLock held.
    Special chars: '⌫' backspace, '↵' enter, '\\x1b' escape.
    Returns the InputDevice (keep reference) or None.
    """
    if not EVDEV_AVAILABLE:
        return None

    dev = _find_keyboard()
    if not dev:
        print('[keyboard_ext] no USB keyboard found')
        return None

    print(f'[keyboard_ext] using {dev.name!r} at {dev.path}')

    def _loop():
        shift = False
        caps  = False
        try:
            for event in dev.read_loop():
                if event.type != ecodes.EV_KEY:
                    continue
                ke   = categorize(event)
                name = ke.keycode if isinstance(ke.keycode, str) else ke.keycode[0]

                if name in _SHIFT_KEYS:
                    shift = (ke.keystate != ke.key_up)
                    continue
                if name in _CAPS_KEYS and ke.keystate == ke.key_down:
                    caps = not caps
                    continue
                if ke.keystate != ke.key_down:
                    continue

                entry = _KEYMAP.get(name)
                if entry is None:
                    continue

                if isinstance(entry, tuple):
                    char = entry[1] if shift else entry[0]
                elif entry in (' ', '⌫', '↵', '\t', '\x1b', '↑', '↓', '←', '→'):
                    char = entry
                else:
                    char = entry.upper() if (shift ^ caps) else entry

                on_char(char)
        except Exception as e:
            print(f'[keyboard_ext] stopped: {e}')

    t = threading.Thread(target=_loop, daemon=True, name='keyboard_ext')
    t.start()
    return dev

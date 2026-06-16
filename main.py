"""
EpaperUI — entry point
  python main.py            # Pi with GPIO
  python main.py --keyboard # WASD+QE keyboard fallback for dev/debug
"""
import sys
import threading
import time

import server
import input_handler
import keyboard_ext
import render
from display import Display
from state import state


def _keyboard_thread():
    """WASD = UP/DOWN/LEFT/RIGHT  Q = BACK  E = ACCEPT"""
    MAP = {
        'w': 'UP',  's': 'DOWN', 'a': 'LEFT', 'd': 'RIGHT',
        'q': 'BACK', 'e': 'ACCEPT',
        'W': 'UP',  'S': 'DOWN', 'A': 'LEFT', 'D': 'RIGHT',
        'Q': 'BACK', 'E': 'ACCEPT',
    }
    print('[keyboard] WASD=navigate  Q=BACK  E=ACCEPT  Ctrl+C=quit')
    try:
        import tty, termios
        fd  = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch == '\x03':
                    raise KeyboardInterrupt
                btn = MAP.get(ch)
                if btn:
                    input_handler.handle(btn)
                else:
                    input_handler.handle_external_key(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except ImportError:
        try:
            import msvcrt
            while True:
                ch = msvcrt.getwch()
                if ch == '\x03':
                    raise KeyboardInterrupt
                btn = MAP.get(ch)
                if btn:
                    input_handler.handle(btn)
                else:
                    input_handler.handle_external_key(ch)
        except Exception as e:
            print(f'[keyboard] not available: {e}')


if __name__ == '__main__':
    use_keyboard = '--keyboard' in sys.argv

    display = Display()

    # Flask in background thread
    flask_thread = threading.Thread(
        target=lambda: server.app.run(
            host='127.0.0.1', port=5000,
            debug=False, use_reloader=False, threaded=True,
        ),
        daemon=True,
        name='flask',
    )
    flask_thread.start()
    time.sleep(1.2)
    print('[main] Flask on http://127.0.0.1:5000/')

    # GPIO buttons (returns tuple to keep references alive)
    _buttons = input_handler.start()

    # USB keyboard via evdev — feeds into text input when active
    _kbd_dev = keyboard_ext.start(input_handler.handle_external_key)

    # Optional WASD keyboard fallback (dev/debug)
    if use_keyboard:
        kb = threading.Thread(target=_keyboard_thread, daemon=True, name='keyboard')
        kb.start()

    # Render loop in main thread
    try:
        render.run_loop(display)
    except KeyboardInterrupt:
        print('\n[main] shutting down…')
        display.sleep()

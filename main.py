"""
EpaperUI — entry point
  python main.py            # Pi with GPIO + headless rendering
  python main.py --keyboard # adds W/S/Q/E keyboard fallback (dev/debug)
  python main.py --preview  # keyboard only, saves PNG preview (no Pi needed)
"""
import sys
import threading
import time

import server
import input_handler
import render
from display import Display
from state import state


def _keyboard_thread():
    """W=UP  S=DOWN  Q=BACK  E=SELECT  Ctrl+C=quit"""
    MAP = {'w': 'UP', 's': 'DOWN', 'a': 'LEFT', 'd': 'RIGHT',
           'q': 'BACK', 'e': 'ACCEPT',
           'W': 'UP', 'S': 'DOWN', 'A': 'LEFT', 'D': 'RIGHT',
           'Q': 'BACK', 'E': 'ACCEPT'}
    print('[keyboard] W=UP S=DOWN A=LEFT D=RIGHT Q=BACK E=ACCEPT')
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
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except ImportError:
        # Windows fallback
        try:
            import msvcrt
            while True:
                ch = msvcrt.getwch()
                if ch == '\x03':
                    raise KeyboardInterrupt
                btn = MAP.get(ch)
                if btn:
                    input_handler.handle(btn)
        except Exception as e:
            print(f'[keyboard] not available: {e}')


if __name__ == '__main__':
    use_keyboard = '--keyboard' in sys.argv or '--preview' in sys.argv

    display = Display()

    # Flask in background thread
    flask_thread = threading.Thread(
        target=lambda: server.app.run(
            host='127.0.0.1', port=5000,
            debug=False, use_reloader=False, threaded=True
        ),
        daemon=True,
        name='flask',
    )
    flask_thread.start()
    time.sleep(1.2)  # wait for Flask to be ready
    print('[main] Flask started on http://127.0.0.1:5000/')

    # GPIO buttons
    _buttons = input_handler.start()  # kept alive via reference

    # Optional keyboard fallback
    if use_keyboard:
        kb = threading.Thread(target=_keyboard_thread, daemon=True, name='keyboard')
        kb.start()

    # Render loop runs in main thread
    try:
        render.run_loop(display)
    except KeyboardInterrupt:
        print('\n[main] shutting down…')
        display.sleep()

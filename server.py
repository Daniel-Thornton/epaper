import base64
import io
import json
import platform
import subprocess
import time
import wave
from datetime import datetime
from pathlib import Path

import psutil
import qrcode
from flask import Flask, render_template

from state import state, APPS, APP_ICONS, CALC_BUTTONS, SYMBOL_KB

app      = Flask(__name__)
DATA_DIR = Path(__file__).parent / 'data'
REC_DIR  = DATA_DIR / 'recordings'


# ── data helpers ──────────────────────────────────────────────────────────────

def _load(fname, default):
    p = DATA_DIR / fname
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return default


def _qr_b64(url: str) -> str:
    qr = qrcode.QRCode(version=2, box_size=6, border=2,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


def _list_recs():
    REC_DIR.mkdir(parents=True, exist_ok=True)
    recs = []
    for p in sorted(REC_DIR.glob('*.wav'), reverse=True):
        try:
            with wave.open(str(p), 'rb') as wf:
                dur = wf.getnframes() / wf.getframerate()
        except Exception:
            dur = 0
        recs.append({
            'name':     p.stem,
            'duration': f"{int(dur // 60)}:{int(dur % 60):02d}",
        })
    return recs


# ── routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    s  = state
    sc = s.screen

    if sc == 'home':
        return render_template('home.html', apps=APPS, icons=APP_ICONS,
                               selected=s.selected,
                               clock=datetime.now().strftime('%H:%M'))

    if sc == 'notes':
        notes = _load('notes.json', [])
        if s.notes_view == 'list':
            return render_template('notes.html', view='list', notes=notes,
                                   selected=s.notes_idx)
        note = notes[s.notes_idx] if 0 <= s.notes_idx < len(notes) else {}
        return render_template('notes.html', view='view', note=note)

    if sc == 'todo':
        todos = _load('todos.json', [])
        done  = sum(1 for t in todos if t.get('done'))
        return render_template('todo.html', todos=todos,
                               selected=s.todo_idx, done=done)

    if sc == 'clock':
        now       = datetime.now()
        alarms    = _load('alarms.json', [])
        remaining = None
        if s.timer_end is not None:
            remaining = max(0, int(s.timer_end - time.monotonic()))
        return render_template('clock.html', tab=s.clock_tab, now=now,
                               alarms=alarms, alarm_idx=s.alarm_idx,
                               timer_total=s.timer_total, remaining=remaining,
                               timer_running=s.timer_end is not None)

    if sc == 'calculator':
        return render_template('calculator.html', buttons=CALC_BUTTONS,
                               display=s.calc_display, cursor=s.calc_cursor)

    if sc == 'settings':
        cfg   = _load('config.json', {'timezone': 'UTC', 'refresh_rate': 60})
        items = [
            ('Timezone',     cfg.get('timezone', 'UTC')),
            ('Refresh Rate', f"{cfg.get('refresh_rate', 60)}s"),
            ('Display',      'Black & White'),
            ('Version',      'EpaperUI v2.0'),
        ]
        return render_template('settings.html', items=items,
                               selected=s.settings_idx)

    if sc == 'info':
        return render_template('info.html', info=_pi_info())

    if sc == 'camera':
        has_photo = (Path(__file__).parent / 'static' / 'last_photo.jpg').exists()
        return render_template('camera.html', has_photo=has_photo)

    if sc == 'text_input':
        return render_template('text_input.html',
                               prompt=s.ti_prompt,
                               value=s.ti_value,
                               ti_kb_cursor=s.ti_kb_cursor,
                               symbol_kb=SYMBOL_KB,
                               recording=s.recording_voice,
                               transcribing=s.transcribing)

    if sc == 'audio_recorder':
        elapsed = 0
        if s.audio_recording and s.audio_rec_start:
            elapsed = int(time.monotonic() - s.audio_rec_start)
        return render_template('audio_recorder.html',
                               recordings=_list_recs(),
                               selected=s.audio_rec_idx,
                               recording=s.audio_recording,
                               elapsed=elapsed)

    if sc == 'webapp_chat':
        url = 'https://daniel-thornton.github.io/chat/'
        return render_template('webapp.html', title='Chat App', url=url,
                               qr=_qr_b64(url), desc='AI chat interface')

    if sc == 'webapp_calories':
        url = 'https://daniel-thornton.github.io/calorie-logger/'
        return render_template('webapp.html', title='Calorie Logger', url=url,
                               qr=_qr_b64(url), desc='Track daily calories')

    return render_template('home.html', apps=APPS, icons=APP_ICONS,
                           selected=0, clock=datetime.now().strftime('%H:%M'))


# ── system info ───────────────────────────────────────────────────────────────

def _pi_info():
    info = {}
    try:
        out = subprocess.run(['vcgencmd', 'measure_temp'],
                             capture_output=True, text=True, timeout=2).stdout
        info['CPU Temp'] = out.strip().replace('temp=', '')
    except Exception:
        info['CPU Temp'] = 'N/A'

    info['CPU Usage'] = f"{psutil.cpu_percent(interval=0.1):.0f}%"

    mem = psutil.virtual_memory()
    info['RAM'] = f"{mem.used // (1024**2)} / {mem.total // (1024**2)} MB"

    disk = psutil.disk_usage('/')
    info['Disk'] = f"{disk.used / (1024**3):.1f} / {disk.total / (1024**3):.1f} GB"

    secs = int(time.time() - psutil.boot_time())
    h, r = divmod(secs, 3600)
    info['Uptime'] = f"{h}h {r // 60}m"

    try:
        import socket
        info['IP'] = socket.gethostbyname(socket.gethostname())
    except Exception:
        info['IP'] = 'N/A'

    try:
        with open('/etc/os-release') as f:
            for line in f:
                if line.startswith('PRETTY_NAME='):
                    info['OS'] = line.split('=', 1)[1].strip().strip('"')
                    break
    except Exception:
        info['OS'] = platform.system()

    try:
        out = subprocess.run(['cat', '/proc/device-tree/model'],
                             capture_output=True, text=True, timeout=2).stdout
        info['Model'] = out.strip().rstrip('\x00')
    except Exception:
        info['Model'] = 'Raspberry Pi'

    try:
        out = subprocess.run(['uname', '-r'],
                             capture_output=True, text=True, timeout=2).stdout
        info['Kernel'] = out.strip()
    except Exception:
        info['Kernel'] = 'N/A'

    return info

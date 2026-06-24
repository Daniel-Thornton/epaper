"""
Battery management module.

GPIO6  — DigitalInputDevice  : AC power status (HIGH=OK, LOW=failed)
GPIO16 — OutputDevice        : Charge control  (LOW=enabled, HIGH=disabled)
I2C1   — smbus2 (GPIO2/GPIO3): Fuel gauge read (tries MAX17043 @ 0x36, then IP5306 @ 0x75)
"""

import os
import threading
import time

os.environ.setdefault('GPIOZERO_PIN_FACTORY', 'lgpio')

try:
    import smbus2
    _SMBUS_OK = True
except ImportError:
    _SMBUS_OK = False
    print('[battery] smbus2 not available — I2C reading disabled')

try:
    from gpiozero import DigitalInputDevice, OutputDevice
    _GPIO_OK = True
except Exception:
    _GPIO_OK = False

from state import state

_PIN_AC_OK  = 6   # HIGH = power supply OK, LOW = failed
_PIN_CHARGE = 16  # LOW  = charging enabled, HIGH = disabled

_I2C_BUS  = 1
_MAX17043  = 0x36  # MAX17040/MAX17043 Li-Po fuel gauge
_IP5306    = 0x75  # IP5306 power management IC

POLL_INTERVAL = 30  # seconds

_ac_sensor  = None
_charge_out = None


# ── I2C fuel gauge readers ─────────────────────────────────────────────────────

def _read_max17043():
    """Returns (pct: int, mv: int) or (None, None). MAX17043 @ 0x36."""
    try:
        bus  = smbus2.SMBus(_I2C_BUS)
        raw  = bus.read_i2c_block_data(_MAX17043, 0x02, 2)
        mv   = ((raw[0] << 4) | (raw[1] >> 4)) * 125 // 100  # 1.25 mV per LSB
        raw  = bus.read_i2c_block_data(_MAX17043, 0x04, 2)
        pct  = min(100, raw[0])
        bus.close()
        print(f'[battery] MAX17043: {pct}% {mv}mV')
        return pct, mv
    except Exception as e:
        print(f'[battery] MAX17043 not found at 0x36: {e}')
        return None, None


def _read_ip5306():
    """Returns (pct: int, None) or (None, None). IP5306 @ 0x75, 25% steps."""
    try:
        bus  = smbus2.SMBus(_I2C_BUS)
        val  = bus.read_byte_data(_IP5306, 0x78)
        bus.close()
        n    = bin((val >> 4) & 0x0F).count('1')
        pct  = [0, 25, 50, 75, 100][min(n, 4)]
        print(f'[battery] IP5306: {pct}%')
        return pct, None
    except Exception as e:
        print(f'[battery] IP5306 not found at 0x75: {e}')
        return None, None


# ── background poller ──────────────────────────────────────────────────────────

def _poll():
    while True:
        pct, mv = None, None
        if _SMBUS_OK:
            pct, mv = _read_max17043()
            if pct is None:
                pct, mv = _read_ip5306()

        ac_ok = True
        if _ac_sensor is not None:
            try:
                ac_ok = _ac_sensor.is_active
            except Exception:
                pass

        charging = False
        if _charge_out is not None:
            try:
                # LOW (value=0) = enabled
                charging = (not bool(_charge_out.value)) and ac_ok
            except Exception:
                pass
        else:
            # No control pin — assume charging when AC is present
            charging = ac_ok

        state.battery_pct      = pct if pct is not None else -1
        state.battery_mv       = mv or 0
        state.battery_charging = charging
        state.battery_ac_ok    = ac_ok
        state.mark_dirty()

        time.sleep(POLL_INTERVAL)


# ── charging control ───────────────────────────────────────────────────────────

def set_charging(enabled: bool):
    """Enable (pin LOW) or disable (pin HIGH) battery charging."""
    if _charge_out is None:
        return
    if enabled:
        _charge_out.off()   # LOW = charging enabled
    else:
        _charge_out.on()    # HIGH = charging disabled
    state.battery_charging = enabled and state.battery_ac_ok
    state.mark_dirty()


def toggle_charging():
    """Toggle charging on/off; returns new enabled state."""
    if _charge_out is None:
        return state.battery_charging
    currently_enabled = not bool(_charge_out.value)  # LOW=0=enabled
    set_charging(not currently_enabled)
    return not currently_enabled


# ── startup ────────────────────────────────────────────────────────────────────

def start():
    global _ac_sensor, _charge_out

    if _GPIO_OK:
        try:
            # pull_up=None: external circuit drives this pin; active_state=True: HIGH=active
            _ac_sensor = DigitalInputDevice(_PIN_AC_OK, pull_up=None, active_state=True)
            print(f'[battery] AC sensor on GPIO{_PIN_AC_OK}')
        except Exception as e:
            print(f'[battery] AC sensor init failed: {e}')

        try:
            # initial_value=False → pin starts LOW → charging enabled on boot
            _charge_out = OutputDevice(_PIN_CHARGE, initial_value=False)
            print(f'[battery] charge control on GPIO{_PIN_CHARGE}')
        except Exception as e:
            print(f'[battery] charge control init failed: {e}')

    t = threading.Thread(target=_poll, daemon=True, name='battery')
    t.start()
    print('[battery] polling started (30s interval)')

#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Windows 95 drawing primitives for a 480×800 B&W e-paper display.

Coordinate convention: (0,0) = top-left, x right, y down.
Black = 0 (ink), White = 255 (paper).

Win95 3D border scheme (authentic 2-pixel):
  Raised: top+left = white (highlight), bottom+right = black (shadow, 2px each)
  Sunken: top+left = black (shadow, 2px each), bottom+right = white (highlight)

Because the display is B&W (no gray), white highlight lines on a white face
are invisible but are still drawn so the scheme works correctly when fill=0
(inverted/selected elements show visible white highlights on the dark face).
"""
from PIL import ImageDraw

W = 480
H = 800

TASKBAR_H  = 40
TITLEBAR_H = 30
STATUSBAR_H = 28

_BK = 0    # shadow / dark
_WH = 255  # highlight / bright


# ── Helpers ──────────────────────────────────────────────────────────────────

def text_wh(draw, text, font):
    """Return (width, height) of rendered text, Pillow-version agnostic."""
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0], bb[3] - bb[1]
    except AttributeError:
        return font.getsize(text)


def text_centered(draw, cx, cy, text, font, fill=0):
    tw, th = text_wh(draw, text, font)
    draw.text((cx - tw // 2, cy - th // 2), text, font=font, fill=fill)


def text_right(draw, rx, cy, text, font, fill=0):
    tw, th = text_wh(draw, text, font)
    draw.text((rx - tw, cy - th // 2), text, font=font, fill=fill)


def _vtext_y(draw, font, container_h, offset=0):
    """Top-y so text is vertically centred in a container of container_h px."""
    _, th = text_wh(draw, 'Ag', font)
    return max(0, (container_h - th) // 2) + offset


# ── Desktop ──────────────────────────────────────────────────────────────────

def draw_desktop(image, draw):
    """Win95-style stipple desktop (alternating dot pattern ≈ 50% gray)."""
    for y in range(0, H - TASKBAR_H, 2):
        for x in range(y % 2, W, 2):
            draw.point((x, y), fill=_BK)


# ── Core Win95 3D border primitives ──────────────────────────────────────────

def _border_raised(draw, x0, y0, x1, y1):
    """
    Draw the Win95 raised 3D border lines only (no fill).
    2px highlight on top+left, 2px shadow on bottom+right.
    """
    # Outer highlight: top, left
    draw.line([(x0,   y0),   (x1,   y0)  ], fill=_WH)
    draw.line([(x0,   y0),   (x0,   y1)  ], fill=_WH)
    # Inner highlight: top, left
    draw.line([(x0+1, y0+1), (x1-1, y0+1)], fill=_WH)
    draw.line([(x0+1, y0+1), (x0+1, y1-1)], fill=_WH)
    # Inner shadow: bottom, right
    draw.line([(x0+1, y1-1), (x1-1, y1-1)], fill=_BK)
    draw.line([(x1-1, y0+1), (x1-1, y1-1)], fill=_BK)
    # Outer shadow: bottom, right
    draw.line([(x0,   y1),   (x1,   y1)  ], fill=_BK)
    draw.line([(x1,   y0),   (x1,   y1)  ], fill=_BK)


def _border_sunken(draw, x0, y0, x1, y1):
    """Win95 sunken 3D border (inset look) — inverse of raised."""
    # Outer shadow: top, left
    draw.line([(x0,   y0),   (x1,   y0)  ], fill=_BK)
    draw.line([(x0,   y0),   (x0,   y1)  ], fill=_BK)
    # Inner shadow: top, left
    draw.line([(x0+1, y0+1), (x1-1, y0+1)], fill=_BK)
    draw.line([(x0+1, y0+1), (x0+1, y1-1)], fill=_BK)
    # Inner highlight: bottom, right
    draw.line([(x0+1, y1-1), (x1-1, y1-1)], fill=_WH)
    draw.line([(x1-1, y0+1), (x1-1, y1-1)], fill=_WH)
    # Outer highlight: bottom, right
    draw.line([(x0,   y1),   (x1,   y1)  ], fill=_WH)
    draw.line([(x1,   y0),   (x1,   y1)  ], fill=_WH)


def draw_raised_box(draw, x0, y0, x1, y1, fill=_WH):
    """Win95 raised 3D box with proper 2-pixel embossed border."""
    draw.rectangle([x0, y0, x1, y1], fill=fill)
    _border_raised(draw, x0, y0, x1, y1)


def draw_sunken_box(draw, x0, y0, x1, y1, fill=_WH):
    """Win95 sunken / inset box with proper 2-pixel border."""
    draw.rectangle([x0, y0, x1, y1], fill=fill)
    _border_sunken(draw, x0, y0, x1, y1)


def draw_flat_box(draw, x0, y0, x1, y1, fill=_WH):
    draw.rectangle([x0, y0, x1, y1], fill=fill, outline=_BK, width=1)


# ── Button ───────────────────────────────────────────────────────────────────

def draw_button(draw, x0, y0, x1, y1, label, font, selected=False, pressed=False):
    """
    Win95-style button.
    selected → black face (current navigation item).
    pressed  → sunken/active.
    """
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    if pressed:
        draw_sunken_box(draw, x0, y0, x1, y1, fill=_BK)
        text_centered(draw, cx, cy, label, font, fill=_WH)
    elif selected:
        draw_raised_box(draw, x0, y0, x1, y1, fill=_BK)
        text_centered(draw, cx, cy, label, font, fill=_WH)
    else:
        draw_raised_box(draw, x0, y0, x1, y1, fill=_WH)
        text_centered(draw, cx, cy, label, font, fill=_BK)


# ── Title bar window controls ─────────────────────────────────────────────────

def _draw_win_button(draw, bx, by, sz, symbol):
    """Draw a single Win95-style white control button at (bx,by) size sz×sz."""
    draw.rectangle([bx, by, bx + sz, by + sz], fill=_WH)
    # Raised border for the button itself (within the dark title bar)
    draw.line([(bx, by),   (bx+sz-1, by)  ], fill=_WH)   # top highlight
    draw.line([(bx, by),   (bx,   by+sz-1)], fill=_WH)   # left highlight
    draw.line([(bx, by+sz), (bx+sz, by+sz)], fill=_BK)   # bottom shadow
    draw.line([(bx+sz, by), (bx+sz, by+sz)], fill=_BK)   # right shadow
    draw.line([(bx+1, by+sz-1),(bx+sz-1, by+sz-1)], fill=_BK)
    draw.line([(bx+sz-1, by+1),(bx+sz-1, by+sz-1)], fill=_BK)
    cx, cy = bx + sz // 2, by + sz // 2
    pad = sz // 4
    if symbol == 'X':
        draw.line([(bx+pad, by+pad), (bx+sz-pad, by+sz-pad)], fill=_BK, width=2)
        draw.line([(bx+sz-pad, by+pad), (bx+pad, by+sz-pad)], fill=_BK, width=2)
    elif symbol == '_':
        bar_y = by + sz - pad - 2
        draw.rectangle([bx+pad, bar_y, bx+sz-pad, bar_y+2], fill=_BK)


# ── App title bar ─────────────────────────────────────────────────────────────

def draw_title_bar(draw, title, font, icon_key=None, base_img=None):
    """
    Full-width Win95 title bar (black gradient → solid black in B&W).
    Includes PNG icon on left (if provided), window controls on right.
    """
    draw.rectangle([0, 0, W, TITLEBAR_H], fill=_BK)

    btn_sz = TITLEBAR_H - 8   # e.g. 22 for TITLEBAR_H=30
    btn_y  = 4

    # Close button (rightmost)
    close_x = W - btn_sz - 4
    _draw_win_button(draw, close_x, btn_y, btn_sz, 'X')

    # Minimize button (left of close)
    min_x = close_x - btn_sz - 3
    _draw_win_button(draw, min_x, btn_y, btn_sz, '_')

    # Left: icon (if any)
    x = 4
    if icon_key and base_img:
        import icons as _icons
        icon = _icons.get(icon_key, size=TITLEBAR_H - 6)
        if icon:
            base_img.paste(icon, (x, 3))
            x += TITLEBAR_H - 2

    # Title text (vertically centred, clipped before the control buttons)
    max_w = min_x - x - 6
    _, th = text_wh(draw, title, font)
    ty    = max(2, (TITLEBAR_H - th) // 2)
    draw.text((x, ty), title, font=font, fill=_WH)


# ── Taskbar ───────────────────────────────────────────────────────────────────

def _win_flag(draw, fx, fy, sz=14):
    """Draw a 4-quadrant Windows flag icon centred at (fx, fy)."""
    h = sz // 2 - 1
    draw.rectangle([fx,   fy,   fx+h,   fy+h  ], fill=_BK)  # top-left
    draw.rectangle([fx+h+2, fy, fx+sz,  fy+h  ], fill=_BK)  # top-right
    draw.rectangle([fx,   fy+h+2, fx+h, fy+sz ], fill=_BK)  # bottom-left
    draw.rectangle([fx+h+2, fy+h+2, fx+sz, fy+sz], fill=_BK) # bottom-right


def draw_taskbar(draw, font, clock_str, app_name=''):
    """Win95-style taskbar: white face, raised top, Start + app + tray."""
    y0 = H - TASKBAR_H

    # White face
    draw.rectangle([0, y0, W, H], fill=_WH)

    # Raised top edge (2px)
    draw.line([(0, y0),   (W, y0)  ], fill=_WH)   # outer highlight (paper)
    draw.line([(0, y0+1), (W, y0+1)], fill=_BK)   # visible dark line

    btn_h  = TASKBAR_H - 8          # button height
    btn_y0 = y0 + 4
    btn_y1 = btn_y0 + btn_h

    # ── Start button ──────────────────────────────────────────────────────
    start_w = 90
    draw_raised_box(draw, 4, btn_y0, 4 + start_w, btn_y1, fill=_WH)

    flag_x = 10
    flag_y = btn_y0 + (btn_h - 14) // 2
    _win_flag(draw, flag_x, flag_y, sz=14)

    _, th = text_wh(draw, 'Start', font)
    draw.text((flag_x + 16, btn_y0 + (btn_h - th) // 2), 'Start', font=font, fill=_BK)

    # ── Separator after Start ─────────────────────────────────────────────
    sep = 4 + start_w + 5
    draw.line([(sep,   btn_y0), (sep,   btn_y1)], fill=_BK)
    draw.line([(sep+1, btn_y0), (sep+1, btn_y1)], fill=_WH)

    # ── System tray (sunken, right side) ──────────────────────────────────
    tray_w  = 84
    tray_x0 = W - tray_w - 4
    draw_sunken_box(draw, tray_x0, btn_y0, W - 4, btn_y1, fill=_WH)
    text_centered(draw, tray_x0 + tray_w // 2, btn_y0 + btn_h // 2,
                  clock_str, font, fill=_BK)

    # ── Active app button (sunken/pressed to show it's active) ────────────
    if app_name:
        app_x0 = sep + 3
        app_x1 = tray_x0 - 5
        if app_x1 > app_x0 + 20:
            draw_sunken_box(draw, app_x0, btn_y0, app_x1, btn_y1, fill=_WH)
            _, th = text_wh(draw, app_name[:22], font)
            draw.text((app_x0 + 6, btn_y0 + (btn_h - th) // 2),
                      app_name[:22], font=font, fill=_BK)


# ── Window frame (floating dialog — rarely used) ──────────────────────────────

def draw_window(draw, x0, y0, x1, y1, title, font, close=True, minimize=True):
    draw_raised_box(draw, x0, y0, x1, y1, fill=_WH)
    draw.rectangle([x0+2, y0+2, x1-2, y0+2+TITLEBAR_H], fill=_BK)
    draw.text((x0 + 6, y0 + 6), title, font=font, fill=_WH)
    bx = x1 - 4
    for sym in (['X'] if close else []) + (['_'] if minimize else []):
        bx -= 22
        _draw_win_button(draw, bx, y0 + 3, 18, sym)


def draw_app_frame(draw, title, font):
    draw.rectangle([0, 0, W, TITLEBAR_H], fill=_BK)
    draw.text((8, 6), title, font=font, fill=_WH)
    draw.rectangle([0, TITLEBAR_H, W-1, H-TASKBAR_H-1], outline=_BK, width=1)


# ── Desktop icon ──────────────────────────────────────────────────────────────

ICON_SIZE = 56

def draw_icon(draw, cx, cy, label, font, icon_draw_fn=None, selected=False,
              *, icon_img=None, base_img=None):
    """
    Desktop icon centred at (cx, cy).
    PNG path:     pass icon_img + base_img.
    Painter path: pass icon_draw_fn callable.
    """
    from PIL import ImageOps
    ix = cx - ICON_SIZE // 2
    iy = cy - ICON_SIZE // 2
    iw = ih = ICON_SIZE

    if selected:
        draw.rectangle([ix - 2, iy - 2, ix + iw + 2, iy + ih + 2], fill=_BK)
    else:
        # Sunken icon box (icons sit in a slight inset on the desktop)
        draw.rectangle([ix, iy, ix + iw, iy + ih], fill=_WH)
        _border_sunken(draw, ix, iy, ix + iw, iy + ih)

    if icon_img is not None and base_img is not None:
        sized = icon_img.resize((iw, ih)) if icon_img.size != (iw, ih) else icon_img
        if selected:
            sized = ImageOps.invert(sized.convert('L')).convert('1')
        base_img.paste(sized, (ix, iy))
    elif callable(icon_draw_fn):
        icon_draw_fn(draw, ix, iy, iw, ih, selected)

    # Label below icon
    lbl_y = iy + ih + 4
    tw, th = text_wh(draw, label, font)
    lx = cx - tw // 2
    if selected:
        draw.rectangle([lx - 2, lbl_y, lx + tw + 2, lbl_y + th + 2], fill=_BK)
        draw.text((lx, lbl_y + 1), label, font=font, fill=_WH)
    else:
        draw.text((lx, lbl_y + 1), label, font=font, fill=_BK)


# ── Pre-built icon painters (fallback when PNG not found) ────────────────────

def icon_notes(draw, ix, iy, iw, ih, sel):
    f = _WH if sel else _BK
    b = ix+8; t = iy+6; r = ix+iw-8; bm = iy+ih-6
    draw.rectangle([b, t, r, bm], fill=(_BK if sel else _WH), outline=f, width=1)
    for ln in range(4):
        draw.line([(b+5, t+10+ln*9), (r-5, t+10+ln*9)], fill=f, width=1)

def icon_todo(draw, ix, iy, iw, ih, sel):
    f = _WH if sel else _BK
    for i, checked in enumerate([True, False, True]):
        ly = iy+10+i*14
        draw.rectangle([ix+8, ly, ix+19, ly+10], fill=(_BK if sel else _WH), outline=f)
        if checked:
            draw.line([(ix+10, ly+5),(ix+13, ly+8)], fill=f, width=2)
            draw.line([(ix+13, ly+8),(ix+18, ly+2)], fill=f, width=2)
        draw.line([(ix+23, ly+5),(ix+iw-8, ly+5)], fill=f, width=1)

def icon_camera(draw, ix, iy, iw, ih, sel):
    f = _WH if sel else _BK
    cx, cy = ix+iw//2, iy+ih//2+2
    draw.rectangle([ix+6, iy+14, ix+iw-6, iy+ih-10], fill=(_BK if sel else _WH), outline=f, width=2)
    draw.ellipse([cx-10, cy-10, cx+10, cy+10], fill=(_BK if sel else _WH), outline=f, width=2)
    draw.ellipse([cx-5, cy-5, cx+5, cy+5], fill=f)
    draw.rectangle([ix+iw-18, iy+10, ix+iw-8, iy+16], fill=f)

def icon_clock(draw, ix, iy, iw, ih, sel):
    import math
    f = _WH if sel else _BK
    cx, cy = ix+iw//2, iy+ih//2
    r = min(iw, ih)//2-5
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(_BK if sel else _WH), outline=f, width=2)
    for h in [0, 3, 6, 9]:
        a = math.radians(h*30-90)
        draw.point((cx+int((r-4)*math.cos(a)), cy+int((r-4)*math.sin(a))), fill=f)
    draw.line([(cx, cy),(cx, cy-r+8)], fill=f, width=2)
    draw.line([(cx, cy),(cx+r-12, cy)], fill=f, width=2)

def icon_calc(draw, ix, iy, iw, ih, sel):
    f = _WH if sel else _BK
    b=ix+6; t=iy+6; r=ix+iw-6; bm=iy+ih-6
    draw.rectangle([b, t, r, bm], fill=(_BK if sel else _WH), outline=f, width=1)
    draw.rectangle([b+3, t+3, r-3, t+12], fill=f)
    for row in range(3):
        for col in range(3):
            kx = b+4+col*14; ky = t+17+row*11
            draw.rectangle([kx, ky, kx+10, ky+8],
                           fill=f if (row==2 and col==2) else (_BK if sel else _WH), outline=f)

def icon_settings(draw, ix, iy, iw, ih, sel):
    import math
    f = _WH if sel else _BK
    cx, cy = ix+iw//2, iy+ih//2
    draw.ellipse([cx-18, cy-18, cx+18, cy+18], fill=(_BK if sel else _WH), outline=f, width=2)
    draw.ellipse([cx-10, cy-10, cx+10, cy+10], fill=(_BK if sel else _WH), outline=f, width=2)
    for i in range(8):
        a = math.radians(i*45)
        tx, ty = cx+int(18*math.cos(a)), cy+int(18*math.sin(a))
        draw.ellipse([tx-3, ty-3, tx+3, ty+3], fill=f)

def icon_info(draw, ix, iy, iw, ih, sel):
    f = _WH if sel else _BK
    cx, cy = ix+iw//2, iy+ih//2
    r = min(iw, ih)//2-5
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(_BK if sel else _WH), outline=f, width=2)
    draw.rectangle([cx-3, cy-r+12, cx+3, cy-r+18], fill=f)
    draw.rectangle([cx-3, cy-4, cx+3, cy+r-10], fill=f)

def icon_calorie(draw, ix, iy, iw, ih, sel):
    f = _WH if sel else _BK
    cx = ix+iw//2
    draw.ellipse([cx-14, iy+14, cx+14, iy+ih-6], fill=(_BK if sel else _WH), outline=f, width=2)
    draw.ellipse([cx-5, iy+8, cx+5, iy+16], fill=(_BK if sel else _WH), outline=f, width=2)
    draw.line([(cx+3, iy+12),(cx+10, iy+6)], fill=f, width=2)

def icon_chat(draw, ix, iy, iw, ih, sel):
    f = _WH if sel else _BK
    b=ix+6; t=iy+8; r=ix+iw-6; bm=iy+ih-14
    draw.rounded_rectangle([b, t, r, bm], radius=6, fill=(_BK if sel else _WH), outline=f, width=2)
    draw.polygon([(b+8, bm),(b+3, bm+8),(b+18, bm)], fill=f)
    for ln in range(3):
        draw.line([(b+6, t+8+ln*9),(r-6, t+8+ln*9)], fill=f, width=1)


ICON_PAINTERS = {
    'notes':    icon_notes,
    'todo':     icon_todo,
    'camera':   icon_camera,
    'clock':    icon_clock,
    'calc':     icon_calc,
    'settings': icon_settings,
    'info':     icon_info,
    'calorie':  icon_calorie,
    'chat':     icon_chat,
}

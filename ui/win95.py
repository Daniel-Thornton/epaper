#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""
Windows 95 style drawing primitives for a 480×800 B&W e-paper display.

Coordinate convention: (0,0) = top-left, x right, y down.
Black = 0, White = 255.

3D border trick (B&W):
  Raised: white 1px top+left, black 1px bottom+right, then black 1px inner top+left
  Sunken: reverse
We approximate this by drawing a shadow rect then the face rect on top.
"""
from PIL import ImageDraw

# Portrait canvas dimensions
W = 480
H = 800

# Common geometry constants
TASKBAR_H = 36
TITLEBAR_H = 26
STATUSBAR_H = 28


# ── Helpers ──────────────────────────────────────────────────────────────────

def text_wh(draw, text, font):
    """Return (width, height) of rendered text, Pillow-version agnostic."""
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0], bb[3] - bb[1]
    except AttributeError:
        return font.getsize(text)


def text_centered(draw, cx, cy, text, font, fill=0):
    """Draw text centered on (cx, cy)."""
    tw, th = text_wh(draw, text, font)
    draw.text((cx - tw // 2, cy - th // 2), text, font=font, fill=fill)


def text_right(draw, rx, cy, text, font, fill=0):
    """Draw text right-aligned at x=rx, vertically centered at cy."""
    tw, th = text_wh(draw, text, font)
    draw.text((rx - tw, cy - th // 2), text, font=font, fill=fill)


# ── Desktop ──────────────────────────────────────────────────────────────────

def draw_desktop(image, draw):
    """Fill desktop with a Win95-style stipple (25% black density)."""
    for y in range(0, H - TASKBAR_H, 4):
        for x in range(y // 4 % 4, W, 4):
            draw.point((x, y), fill=0)


# ── Borders / boxes ──────────────────────────────────────────────────────────

def draw_raised_box(draw, x0, y0, x1, y1, fill=255):
    """Raised 3D effect: shadow offset + white face."""
    draw.rectangle([x0 + 3, y0 + 3, x1 + 3, y1 + 3], fill=0)   # shadow
    draw.rectangle([x0, y0, x1, y1], fill=fill, outline=0, width=2)
    # inner highlight on top/left
    draw.line([(x0 + 2, y0 + 2), (x1 - 2, y0 + 2)], fill=255, width=1)
    draw.line([(x0 + 2, y0 + 2), (x0 + 2, y1 - 2)], fill=255, width=1)


def draw_sunken_box(draw, x0, y0, x1, y1, fill=255):
    """Sunken / inset box."""
    draw.rectangle([x0, y0, x1, y1], fill=fill, outline=0, width=1)
    # dark inner top/left, lighter bottom/right
    draw.line([(x0 + 1, y0 + 1), (x1 - 1, y0 + 1)], fill=0, width=1)
    draw.line([(x0 + 1, y0 + 1), (x0 + 1, y1 - 1)], fill=0, width=1)


def draw_flat_box(draw, x0, y0, x1, y1, fill=255):
    draw.rectangle([x0, y0, x1, y1], fill=fill, outline=0, width=1)


# ── Button ───────────────────────────────────────────────────────────────────

def draw_button(draw, x0, y0, x1, y1, label, font, selected=False, pressed=False):
    if pressed:
        draw_sunken_box(draw, x0, y0, x1, y1, fill=0)
        text_centered(draw, (x0 + x1) // 2, (y0 + y1) // 2, label, font, fill=255)
    elif selected:
        draw_raised_box(draw, x0, y0, x1, y1, fill=0)
        text_centered(draw, (x0 + x1) // 2, (y0 + y1) // 2, label, font, fill=255)
    else:
        draw_raised_box(draw, x0, y0, x1, y1, fill=255)
        text_centered(draw, (x0 + x1) // 2, (y0 + y1) // 2, label, font, fill=0)


# ── Window / app frame ───────────────────────────────────────────────────────

def draw_window(draw, x0, y0, x1, y1, title, font, close=True, minimize=True):
    """Draw a complete Win95 window frame with title bar."""
    draw.rectangle([x0, y0, x1, y1], fill=255, outline=0, width=2)
    # Title bar
    draw.rectangle([x0, y0, x1, y0 + TITLEBAR_H], fill=0)
    draw.text((x0 + 6, y0 + 4), title, font=font, fill=255)
    btn_y0, btn_y1 = y0 + 3, y0 + TITLEBAR_H - 3
    bx = x1 - 4
    if close:
        bx -= 22
        draw.rectangle([bx, btn_y0, bx + 20, btn_y1], fill=255, outline=0)
        text_centered(draw, bx + 10, (btn_y0 + btn_y1) // 2, 'X', font, fill=0)
    if minimize:
        bx -= 24
        draw.rectangle([bx, btn_y0, bx + 20, btn_y1], fill=255, outline=0)
        text_centered(draw, bx + 10, (btn_y0 + btn_y1) // 2, '_', font, fill=0)


def draw_app_frame(draw, title, font):
    """Draw full-screen app frame (title bar + status bar area)."""
    # Title bar
    draw.rectangle([0, 0, W, TITLEBAR_H], fill=0)
    draw.text((8, 4), title, font=font, fill=255)
    # Content border
    draw.rectangle([0, TITLEBAR_H, W - 1, H - TASKBAR_H - 1], outline=0, width=1)


# ── Taskbar ───────────────────────────────────────────────────────────────────

def draw_taskbar(draw, font, clock_str, app_name=''):
    y0 = H - TASKBAR_H
    draw.rectangle([0, y0, W, H], fill=0)
    # Start button
    draw.rectangle([2, y0 + 2, 72, H - 2], fill=255, outline=0)
    text_centered(draw, 37, y0 + TASKBAR_H // 2, 'START', font, fill=0)
    # Separator
    draw.line([(76, y0 + 4), (76, H - 4)], fill=255, width=1)
    # Active app name (middle)
    if app_name:
        draw.rectangle([80, y0 + 4, W - 84, H - 4], fill=255, outline=0)
        tw, th = text_wh(draw, app_name, font)
        draw.text((84, y0 + (TASKBAR_H - th) // 2), app_name[:30], font=font, fill=0)
    # System clock (right)
    draw.rectangle([W - 82, y0 + 4, W - 2, H - 4], fill=255, outline=0)
    text_centered(draw, W - 42, y0 + TASKBAR_H // 2, clock_str, font, fill=0)


# ── Desktop icon ──────────────────────────────────────────────────────────────

ICON_SIZE = 56

def draw_icon(draw, cx, cy, label, font, icon_draw_fn=None, selected=False):
    """
    Draw a desktop icon centred at (cx, cy).
    icon_draw_fn(draw, ix, iy, iw, ih, selected) paints the icon graphic.
    """
    ix = cx - ICON_SIZE // 2
    iy = cy - ICON_SIZE // 2
    iw = ih = ICON_SIZE

    if selected:
        draw.rectangle([ix - 2, iy - 2, ix + iw + 2, iy + ih + 2], fill=0)
    else:
        draw.rectangle([ix, iy, ix + iw, iy + ih], fill=255, outline=0, width=1)

    if icon_draw_fn:
        icon_draw_fn(draw, ix, iy, iw, ih, selected)

    # Label
    lbl_y = iy + ih + 4
    tw, th = text_wh(draw, label, font)
    lx = cx - tw // 2
    if selected:
        draw.rectangle([lx - 2, lbl_y, lx + tw + 2, lbl_y + th + 2], fill=0)
        draw.text((lx, lbl_y + 1), label, font=font, fill=255)
    else:
        draw.text((lx, lbl_y + 1), label, font=font, fill=0)


# ── Pre-built icon painters ───────────────────────────────────────────────────

def icon_notes(draw, ix, iy, iw, ih, sel):
    f = 255 if sel else 0
    b = ix + 8; t = iy + 6; r = ix + iw - 8; h2 = iy + ih - 6
    draw.rectangle([b, t, r, h2], fill=(0 if sel else 255), outline=f, width=1)
    for ln in range(4):
        ly = t + 10 + ln * 9
        draw.line([(b + 5, ly), (r - 5, ly)], fill=f, width=1)

def icon_todo(draw, ix, iy, iw, ih, sel):
    f = 255 if sel else 0
    for i, checked in enumerate([True, False, True]):
        ly = iy + 10 + i * 14
        draw.rectangle([ix + 8, ly, ix + 19, ly + 10], fill=(0 if sel else 255), outline=f)
        if checked:
            draw.line([(ix + 10, ly + 5), (ix + 13, ly + 8)], fill=f, width=2)
            draw.line([(ix + 13, ly + 8), (ix + 18, ly + 2)], fill=f, width=2)
        draw.line([(ix + 23, ly + 5), (ix + iw - 8, ly + 5)], fill=f, width=1)

def icon_camera(draw, ix, iy, iw, ih, sel):
    f = 255 if sel else 0
    cx, cy = ix + iw // 2, iy + ih // 2 + 2
    draw.rectangle([ix + 6, iy + 14, ix + iw - 6, iy + ih - 10], fill=(0 if sel else 255), outline=f, width=2)
    draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=(0 if sel else 255), outline=f, width=2)
    draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=f)
    draw.rectangle([ix + iw - 18, iy + 10, ix + iw - 8, iy + 16], fill=f)

def icon_clock(draw, ix, iy, iw, ih, sel):
    f = 255 if sel else 0
    cx, cy = ix + iw // 2, iy + ih // 2
    r = min(iw, ih) // 2 - 5
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0 if sel else 255), outline=f, width=2)
    import math
    for h, m in [(0, 0), (3, 0), (6, 0), (9, 0)]:
        a = math.radians(h * 30 - 90)
        tx = cx + int((r - 4) * math.cos(a))
        ty = cy + int((r - 4) * math.sin(a))
        draw.point((tx, ty), fill=f)
    draw.line([(cx, cy), (cx, cy - r + 8)], fill=f, width=2)
    draw.line([(cx, cy), (cx + r - 12, cy)], fill=f, width=2)

def icon_calc(draw, ix, iy, iw, ih, sel):
    f = 255 if sel else 0
    b = ix + 6; t = iy + 6; r = ix + iw - 6; bm = iy + ih - 6
    draw.rectangle([b, t, r, bm], fill=(0 if sel else 255), outline=f, width=1)
    draw.rectangle([b + 3, t + 3, r - 3, t + 12], fill=f)
    for row in range(3):
        for col in range(3):
            kx = b + 4 + col * 14
            ky = t + 17 + row * 11
            draw.rectangle([kx, ky, kx + 10, ky + 8], fill=f if (row == 2 and col == 2) else (0 if sel else 255), outline=f)

def icon_settings(draw, ix, iy, iw, ih, sel):
    f = 255 if sel else 0
    cx, cy = ix + iw // 2, iy + ih // 2
    import math
    r_out = 18; r_in = 10
    draw.ellipse([cx - r_out, cy - r_out, cx + r_out, cy + r_out], fill=(0 if sel else 255), outline=f, width=2)
    draw.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], fill=(0 if sel else 255), outline=f, width=2)
    for i in range(8):
        a = math.radians(i * 45)
        tx = cx + int(r_out * math.cos(a))
        ty = cy + int(r_out * math.sin(a))
        draw.ellipse([tx - 3, ty - 3, tx + 3, ty + 3], fill=f)

def icon_info(draw, ix, iy, iw, ih, sel):
    f = 255 if sel else 0
    cx, cy = ix + iw // 2, iy + ih // 2
    r = min(iw, ih) // 2 - 5
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0 if sel else 255), outline=f, width=2)
    tw = 3
    draw.rectangle([cx - tw, cy - r + 12, cx + tw, cy - r + 18], fill=f)
    draw.rectangle([cx - tw, cy - 4, cx + tw, cy + r - 10], fill=f)

def icon_calorie(draw, ix, iy, iw, ih, sel):
    f = 255 if sel else 0
    cx = ix + iw // 2
    draw.ellipse([cx - 14, iy + 14, cx + 14, iy + ih - 6], fill=(0 if sel else 255), outline=f, width=2)
    draw.ellipse([cx - 5, iy + 8, cx + 5, iy + 16], fill=(0 if sel else 255), outline=f, width=2)
    draw.line([(cx + 3, iy + 12), (cx + 10, iy + 6)], fill=f, width=2)

def icon_chat(draw, ix, iy, iw, ih, sel):
    f = 255 if sel else 0
    b = ix + 6; t = iy + 8; r = ix + iw - 6; bm = iy + ih - 14
    draw.rounded_rectangle([b, t, r, bm], radius=6, fill=(0 if sel else 255), outline=f, width=2)
    draw.polygon([(b + 8, bm), (b + 3, bm + 8), (b + 18, bm)], fill=f)
    for ln in range(3):
        ly = t + 8 + ln * 9
        draw.line([(b + 6, ly), (r - 6, ly)], fill=f, width=1)


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

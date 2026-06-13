#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import math
import time
import logging

picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd4in26

logging.basicConfig(level=logging.DEBUG)

CENTER_X = 400
CENTER_Y = 240
FACE_HALF_W = 360   # leaves 40 px margin on each side of 800 px display
FACE_HALF_H = 200   # leaves 40 px margin top/bottom on 480 px display
FULL_REFRESH_INTERVAL = 600


def rect_edge_point(cx, cy, half_w, half_h, degrees):
    """Intersection of a ray from (cx, cy) at clock-angle degrees with a rectangle."""
    rad = math.radians(degrees - 90)
    dx, dy = math.cos(rad), math.sin(rad)
    tx = half_w / abs(dx) if abs(dx) > 1e-9 else float('inf')
    ty = half_h / abs(dy) if abs(dy) > 1e-9 else float('inf')
    t = min(tx, ty)
    return (cx + dx * t, cy + dy * t)


def hand_endpoint(cx, cy, length, degrees):
    rad = math.radians(degrees - 90)
    return (cx + length * math.cos(rad), cy + length * math.sin(rad))


def draw_tapered_hand(draw, cx, cy, length, degrees, base_width, tip_width=3):
    """Filled tapering polygon: wide at the pivot, pointed at the tip, with a short tail."""
    rad  = math.radians(degrees - 90)
    perp = rad + math.pi / 2
    tail = length * 0.18

    tip  = (cx + length * math.cos(rad), cy + length * math.sin(rad))
    back = (cx - tail   * math.cos(rad), cy - tail   * math.sin(rad))

    bw      = base_width / 2
    tw      = tip_width  / 2
    bw_back = base_width * 0.35 / 2

    pts = [
        (back[0] + bw_back * math.cos(perp), back[1] + bw_back * math.sin(perp)),
        (cx      + bw      * math.cos(perp), cy      + bw      * math.sin(perp)),
        (tip[0]  + tw      * math.cos(perp), tip[1]  + tw      * math.sin(perp)),
        (tip[0]  - tw      * math.cos(perp), tip[1]  - tw      * math.sin(perp)),
        (cx      - bw      * math.cos(perp), cy      - bw      * math.sin(perp)),
        (back[0] - bw_back * math.cos(perp), back[1] - bw_back * math.sin(perp)),
    ]
    draw.polygon(pts, fill=0)


def draw_clock(draw, now, font_num):
    cx, cy = CENTER_X, CENTER_Y
    hw, hh = FACE_HALF_W, FACE_HALF_H
    gap    = 10    # spacing between outer and inner border

    # Outer border – thick frame
    draw.rectangle((cx - hw, cy - hh, cx + hw, cy + hh), outline=0, width=5)

    # Inner border – single-pixel inset rule
    ibw, ibh = hw - gap, hh - gap
    draw.rectangle((cx - ibw, cy - ibh, cx + ibw, cy + ibh), outline=0, width=1)

    # Filled-square corner accents on the inner border
    cs = 8
    for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
        x, y = cx + sx * ibw, cy + sy * ibh
        draw.rectangle((x - cs, y - cs, x + cs, y + cs), fill=0)

    # Tick marks radiating inward from the inner border
    for i in range(60):
        deg   = i * 6
        start = rect_edge_point(cx, cy, ibw - 1, ibh - 1, deg)
        rad   = math.radians(deg - 90)
        ix, iy = -math.cos(rad), -math.sin(rad)   # inward unit vector

        if i % 5 == 0:
            if (i // 5) % 3 == 0:      # major: 12 / 3 / 6 / 9
                tlen, twidth = 30, 4
            else:                       # minor hours
                tlen, twidth = 18, 2
        else:                           # minute marks
            tlen, twidth = 7, 1

        end = (start[0] + ix * tlen, start[1] + iy * tlen)
        draw.line((start, end), fill=0, width=twidth)

    # Numerals at 12, 3, 6, 9
    inset = 62
    for hour, deg in [(12, 0), (3, 90), (6, 180), (9, 270)]:
        pt  = rect_edge_point(cx, cy, ibw - 1, ibh - 1, deg)
        rad = math.radians(deg - 90)
        tx  = pt[0] - math.cos(rad) * inset
        ty  = pt[1] - math.sin(rad) * inset
        txt = str(hour)
        bb  = font_num.getbbox(txt)
        tw_t, th_t = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((tx - bb[0] - tw_t / 2, ty - bb[1] - th_t / 2),
                  txt, font=font_num, fill=0)

    # ── Hands ──────────────────────────────────────────────────────────────
    h = now.tm_hour % 12
    m = now.tm_min
    s = now.tm_sec

    h_deg = (h + m / 60 + s / 3600) * 30
    m_deg = (m + s / 60) * 6
    s_deg = s * 6

    arm = min(hw, hh)   # scale hand lengths to the shorter face dimension

    draw_tapered_hand(draw, cx, cy, arm * 0.55, h_deg, base_width=18, tip_width=5)
    draw_tapered_hand(draw, cx, cy, arm * 0.80, m_deg, base_width=12, tip_width=4)

    # Second hand: slim needle with counterbalance tail
    rad_s = math.radians(s_deg - 90)
    sx,  sy  = cx + arm * 0.85 * math.cos(rad_s),  cy + arm * 0.85 * math.sin(rad_s)
    sbx, sby = cx - arm * 0.22 * math.cos(rad_s),  cy - arm * 0.22 * math.sin(rad_s)
    draw.line([(sbx, sby), (sx, sy)], fill=0, width=2)

    # Centre cap: filled disc with white pip
    cr = 12
    draw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=0)
    draw.ellipse((cx - 5,  cy - 5,  cx + 5,  cy + 5),  fill=255)


def make_image(epd, now):
    font_num = ImageFont.load_default()
    for path in (
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    ):
        try:
            font_num = ImageFont.truetype(path, 38)
            break
        except OSError:
            pass

    image = Image.new('1', (epd.width, epd.height), 255)
    draw_clock(ImageDraw.Draw(image), now, font_num)
    return image


try:
    epd = epd4in26.EPD()

    logging.info("init and Clear")
    epd.init()
    epd.Clear()

    last_full_refresh = time.time()
    now = time.localtime()
    epd.display_Base(epd.getbuffer(make_image(epd, now)))

    while True:
        time.sleep(1)
        now = time.localtime()
        elapsed = time.time() - last_full_refresh

        if elapsed >= FULL_REFRESH_INTERVAL:
            epd.init()
            epd.display_Base(epd.getbuffer(make_image(epd, now)))
            last_full_refresh = time.time()
        else:
            epd.display_Partial(epd.getbuffer(make_image(epd, now)))

except IOError as e:
    logging.info(e)

except KeyboardInterrupt:
    logging.info("ctrl + c:")
    epd4in26.epdconfig.module_exit(cleanup=True)
    exit()

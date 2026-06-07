#!/usr/bin/env python3
"""
render_ket_qua_frame.py
Render 1 frame test Ket qua tran dau theo dung spec.
"""
import sys, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

BASE        = Path(__file__).parent
TEMPLATE    = BASE / "assets/templates/ket-qua-tran-dau-clean.png"
CONFIG      = BASE / "assets/templates/ket-qua-tran-dau-config.json"
FONT_PATH   = BASE / "assets/fonts/Inter-Variable.ttf"
ARTICLE_IMG = BASE / "output/2026-06-06_113005_soc-thang-doi-thu-hon-39-bac/images/scene_01.jpg"
OUT         = BASE / "output/frames/test-ket-qua-tran-dau.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

DATA = {
    "category": "KẾT QUẢ",
    "badge":    "KẾT THÚC",
    "home_team": "Real Madrid",
    "away_team": "Barcelona",
    "score":     "1 - 1",
    "headline":  "El Clasico chia điểm kịch tính",
    "subtitle":  "Trận đấu căng thẳng đến những phút cuối",
}

cfg  = json.loads(CONFIG.read_text(encoding="utf-8"))
CW   = cfg["canvas"]["width"]
CH   = cfg["canvas"]["height"]
SL   = cfg["image_slot"]
CAT  = cfg["category_box"]
BAD  = cfg["badge_box"]
TEA  = cfg["teams_area"]
SCO  = cfg["score_area"]
HL   = cfg["headline_area"]
SUB  = cfg["subtitle_area"]

_RED   = (196, 14, 42)
_GOLD  = (208, 162, 38)
_DARK  = (4, 6, 18)
_WHITE = (255, 255, 255)
_GRAY  = (216, 216, 216)

def font(size, bold=False):
    try:
        f = ImageFont.truetype(str(FONT_PATH), size)
        if bold:
            try: f.set_variation_by_name("Bold")
            except: pass
        return f
    except:
        return ImageFont.load_default()

def cover_crop(img, w, h):
    iw, ih = img.size
    scale  = max(w/iw, h/ih)
    nw, nh = max(int(iw*scale), w), max(int(ih*scale), h)
    img    = img.resize((nw, nh), Image.LANCZOS)
    l, t   = (nw-w)//2, (nh-h)//2
    return img.crop((l, t, l+w, t+h))

def draw_center(draw, text, x, y, w, h, size, color, bold=True):
    f  = font(size, bold)
    tw = f.getlength(text)
    bb = f.getbbox(text)
    th = bb[3] - bb[1]
    tx = int(x + (w - tw) / 2)
    ty = int(y + (h - th) / 2) - bb[1]
    draw.text((tx, ty), text, font=f, fill=color)

def wrap_text(draw, text, f, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if f.getlength(test) <= max_w:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def draw_block_center(draw, text, x, y, w, h, fmax, fmin, color, bold, max_lines, spacing):
    if not text:
        return
    for size in range(fmax, fmin-1, -1):
        f     = font(size, bold)
        lines = wrap_text(draw, text, f, w)[:max_lines]
        lh    = int(size * spacing)
        total = lh * (len(lines)-1) + size
        if total <= h:
            ty = y
            for line in lines:
                tw  = f.getlength(line)
                tx  = x + int((w - tw) / 2)
                draw.text((tx, ty), line, font=f, fill=color)
                ty += lh
            return
    f     = font(fmin, bold)
    lines = wrap_text(draw, text, f, w)[:max_lines]
    ty    = y
    for line in lines:
        tw  = f.getlength(line)
        tx  = x + int((w - tw) / 2)
        draw.text((tx, ty), line, font=f, fill=color)
        ty += int(fmin * spacing)

def add_bottom_gradient(canvas, ix, iy, iw, ih, grad_h=200):
    """Gradient toi o day anh de blend vao panel."""
    arr = np.array(canvas)
    dark = np.array(_DARK, dtype=np.uint8)
    grad_start = iy + ih - grad_h
    for row in range(grad_start, iy + ih):
        alpha = (row - grad_start) / grad_h          # 0.0 → 1.0
        # blend: pixel = pixel*(1-alpha) + dark*alpha
        arr[row, ix:ix+iw, :3] = (
            arr[row, ix:ix+iw, :3] * (1 - alpha) + dark * alpha
        ).astype(np.uint8)
    return Image.fromarray(arr)


# ══════════════════════════════════════
# RENDER
# ══════════════════════════════════════

canvas = Image.open(TEMPLATE).convert("RGBA")
canvas = canvas.resize((CW, CH), Image.LANCZOS)

# Panel dark phu len tu cuoi slot tro xuong
panel_y = SL["y"] + SL["h"]   # 160+890 = 1050
ImageDraw.Draw(canvas).rectangle([0, panel_y, CW, CH], fill=(*_DARK, 255))

# Chen article image (cover crop + rounded corners)
ix, iy, iw, ih, ir = SL["x"], SL["y"], SL["w"], SL["h"], SL["radius"]
if ARTICLE_IMG.exists():
    art = cover_crop(Image.open(ARTICLE_IMG).convert("RGB"), iw, ih)
else:
    art = Image.new("RGB", (iw, ih), (30, 40, 60))
mask = Image.new("L", (iw, ih), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, iw-1, ih-1], radius=ir, fill=255)
art_rgba = art.convert("RGBA")
art_rgba.putalpha(mask)
canvas.paste(art_rgba, (ix, iy), art_rgba)

# Gradient toi o day anh
canvas = add_bottom_gradient(canvas, ix, iy, iw, ih, grad_h=220)

draw = ImageDraw.Draw(canvas)

# Vien do seam (4px)
draw.rectangle([0, panel_y, CW, panel_y + 4], fill=(*_RED, 255))

# Badge pill do centered
bx, by, bw, bh = BAD["x"], BAD["y"], BAD["w"], BAD["h"]
draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=10, fill=(*_RED, 255))

# Accent line do-vang
accent_y = HL["y"] - 22
draw.rectangle([96, accent_y, 96+168, accent_y+3], fill=(*_RED, 255))
draw.rectangle([96+174, accent_y, 96+220, accent_y+3], fill=(*_GOLD, 255))

# Category text
cat = DATA["category"].upper()
draw_center(draw, cat, CAT["x"], CAT["y"], CAT["w"], CAT["h"],
            CAT["font_size_max"], _WHITE, bold=True)

# Badge text
draw_center(draw, DATA["badge"].upper(), bx, by, bw, bh,
            BAD["font_size_max"], _WHITE, bold=True)

# Teams
if DATA.get("home_team") and DATA.get("away_team"):
    teams_txt = f"{DATA['home_team']}  vs  {DATA['away_team']}"
    tsz = TEA["font_size_max"]
    for sz in range(TEA["font_size_max"], TEA["font_size_min"]-1, -1):
        if font(sz, bold=False).getlength(teams_txt) <= TEA["w"]:
            tsz = sz; break
    draw_center(draw, teams_txt, TEA["x"], TEA["y"], TEA["w"], TEA["h"],
                tsz, tuple(TEA["color"]), bold=False)

# Score
if DATA.get("score"):
    ssz = SCO["font_size_max"]
    for sz in range(SCO["font_size_max"], SCO["font_size_min"]-1, -4):
        if font(sz, bold=True).getlength(DATA["score"]) <= SCO["w"]:
            ssz = sz; break
    draw_center(draw, DATA["score"], SCO["x"], SCO["y"], SCO["w"], SCO["h"],
                ssz, _WHITE, bold=True)

# Headline
draw_block_center(draw, DATA.get("headline", ""),
                  HL["x"], HL["y"], HL["w"], HL["h"],
                  HL["font_size_max"], HL["font_size_min"],
                  _WHITE, True, HL["max_lines"], HL["line_spacing"])

# Subtitle
draw_block_center(draw, DATA.get("subtitle", ""),
                  SUB["x"], SUB["y"], SUB["w"], SUB["h"],
                  SUB["font_size_max"], SUB["font_size_min"],
                  _GRAY, False, SUB["max_lines"], SUB["line_spacing"])

canvas.convert("RGB").save(str(OUT), "PNG")
print(f"Done → {OUT.resolve()}")

"""
scene_renderer.py — Render từng scene PNG 720×1280

LAYOUT: Dark Sports Editorial (theo template THỂ THAO 247)
  - Ảnh full-bleed, color grading tối + vignette mạnh (cinematic)
  - Branding "THỂ THAO 247" top-left, tag top-right
  - Badge đỏ centered ở giữa khung
  - Headline lớn centered, subtext nhỏ centered
  - Gradient 3 tầng: top dark (logo) + fade giữa + dark panel dưới
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
import numpy as np

# ───────────────────────────────────────────────────────────
# Frame & Ken Burns
# ───────────────────────────────────────────────────────────
FRAME_W, FRAME_H = 720, 1280
BG_SCALE = 1.3
BG_W     = int(FRAME_W * BG_SCALE)   # 936
BG_H     = int(FRAME_H * BG_SCALE)   # 1664

# ───────────────────────────────────────────────────────────
# Layout — theo template
# ───────────────────────────────────────────────────────────
BRAND_Y      = 52      # branding row (top-left logo, top-right tag)
BRAND_LEFT   = 36      # logo left margin
BRAND_RIGHT  = 684     # right margin cho tag (right-aligned)

BADGE_CY     = 700     # badge center y
HEADLINE_Y   = 760     # top của headline
SUBTEXT_GAP  = 14      # khoảng cách headline bottom → subtext top
TEXT_LEFT    = 48      # left margin (centered text dùng FRAME_W//2)
TEXT_RIGHT   = 672     # right margin
TEXT_W       = TEXT_RIGHT - TEXT_LEFT  # 624px

SAFE_BOTTOM  = 1160    # không đặt text quan trọng dưới đây

# ───────────────────────────────────────────────────────────
# Colors
# ───────────────────────────────────────────────────────────
DARK_NAVY       = (6, 8, 18)           # #060812
TEXT_PRIMARY    = (255, 255, 255)      # trắng
TEXT_SECONDARY  = (180, 185, 195)      # xám lạnh
ACCENT_RED      = (200, 16, 46)        # #C8102E
ACCENT_GOLD     = (212, 175, 55)       # #D4AF37
BADGE_RED_DARK  = (120, 8, 25)         # badge gradient dark end

_ACCENT_MAP = {
    "emerald": ACCENT_GOLD,
    "cyan":    ACCENT_GOLD,
    "amber":   ACCENT_GOLD,
    "red":     ACCENT_RED,
    "gold":    ACCENT_GOLD,
}

def _resolve_accent(s: str) -> tuple:
    return _ACCENT_MAP.get(s, ACCENT_RED)

# ───────────────────────────────────────────────────────────
# Fonts
# ───────────────────────────────────────────────────────────
FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"

FONT_HEADLINE_CANDIDATES = [
    Path("C:/Windows/Fonts/segoeuib.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    FONT_DIR / "Oswald-Bold.ttf",
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]
FONT_UI_CANDIDATES = [
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]

def _find_font(candidates):
    for p in candidates:
        if p.exists():
            return str(p)
    raise FileNotFoundError(f"Không tìm thấy font: {candidates}")

FONT_HEADLINE_PATH = _find_font(FONT_HEADLINE_CANDIDATES)
FONT_UI_PATH       = _find_font(FONT_UI_CANDIDATES)

# ───────────────────────────────────────────────────────────
# Smart word-wrap
# ───────────────────────────────────────────────────────────

@dataclass
class WrappedText:
    lines: list[str]
    font: ImageFont.FreeTypeFont
    truncated: bool


def _measure(draw, text, font):
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0], b[3] - b[1]


def _wrap_words(words, font, max_w, draw):
    lines, cur = [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if _measure(draw, cand, font)[0] <= max_w:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def smart_wrap(draw, text, max_width, max_lines, font_path,
               start_size, min_size=24, step=4):
    words = text.strip().split()
    size = start_size
    last_lines, last_font = [], None
    while size >= min_size:
        font  = ImageFont.truetype(font_path, size)
        lines = _wrap_words(words, font, max_width, draw)
        last_lines, last_font = lines, font
        if len(lines) <= max_lines:
            if all(_measure(draw, l, font)[0] <= max_width for l in lines):
                if len(lines) > 1 and len(lines[-1].split()) == 1 and size - step >= min_size:
                    size -= step; continue
                return WrappedText(lines, font, False)
        size -= step
    # truncate with "…"
    trunc = last_lines[:max_lines]
    if len(last_lines) > max_lines and trunc:
        ws = trunc[-1].split()
        while ws:
            att = " ".join(ws) + "…"
            if _measure(draw, att, last_font)[0] <= max_width:
                trunc[-1] = att; break
            ws.pop()
        else:
            trunc[-1] = "…"
    return WrappedText(trunc, last_font, True)


# ───────────────────────────────────────────────────────────
# Image helpers
# ───────────────────────────────────────────────────────────

def _fit_full_bleed(img, tw, th):
    return ImageOps.fit(img, (tw, th), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _classify_aspect(img):
    w, h = img.size
    a = w / h
    return "landscape" if a > 1.3 else ("portrait" if a < 0.7 else "square")


def _apply_color_grading(img):
    """Tối + lạnh + vignette mạnh để ảnh có cảm giác cinematic/dark editorial."""
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img = ImageEnhance.Brightness(img).enhance(0.88)
    img = ImageEnhance.Color(img).enhance(0.80)
    # Cold navy tint 10%
    tint = Image.new("RGB", img.size, (0, 6, 24))
    img  = Image.blend(img, tint, alpha=0.10)
    # Vignette numpy
    arr   = np.array(img).astype(np.float32)
    h, w  = arr.shape[:2]
    ys    = np.linspace(-1, 1, h)[:, None]
    xs    = np.linspace(-1, 1, w)[None, :]
    dist  = np.sqrt(xs**2 + ys**2) / np.sqrt(2)
    vig   = 1.0 - np.clip(dist * 0.65, 0, 0.45)
    arr   = np.clip(arr * vig[:, :, None], 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _render_bg(img):
    img = _apply_color_grading(img)
    return _fit_full_bleed(img, BG_W, BG_H)


# ───────────────────────────────────────────────────────────
# Gradient overlay (3 tầng theo template)
# ───────────────────────────────────────────────────────────

def _draw_gradient(canvas):
    """
    3-tầng gradient:
      Top  (0-160):   alpha 180→0   — nền tối cho logo
      Mid  (160-620): alpha 0→30    — rất nhẹ, ảnh thoáng
      Low  (620-900): alpha 30→160  — fade vào dark panel
      Base (900+):    alpha 160→220 — dark panel cho text
    """
    w, h   = canvas.size
    arr    = np.array(canvas).astype(np.float32)
    dn     = np.array(DARK_NAVY, dtype=np.float32)

    def blend_row(y, alpha):
        a = alpha / 255.0
        arr[y, :, :3] = arr[y, :, :3] * (1 - a) + dn * a
        arr[y, :, 3]  = alpha

    for y in range(0, 160):           # top dark (logo)
        t = 1 - y / 160
        blend_row(y, 180 * t)
    arr[:160, :, 3] = np.clip(arr[:160, :, 3], 0, 180)

    for y in range(160, 620):         # mid: nearly transparent
        t = (y - 160) / 460
        blend_row(y, 30 * t)

    for y in range(620, 900):         # low: fade to dark
        t = (y - 620) / 280
        e = t * t * (3 - 2 * t)      # smoothstep
        blend_row(y, 30 + e * 130)

    for y in range(900, h):           # base: dark panel
        t = (y - 900) / max(h - 900, 1)
        blend_row(y, 160 + t * 60)

    # Top area truly transparent (image shows through)
    arr[160:620, :, 3] = np.clip(arr[160:620, :, 3], 0, 30)

    canvas.paste(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)), (0, 0))


# ───────────────────────────────────────────────────────────
# UI elements
# ───────────────────────────────────────────────────────────

def _strip_emoji(text):
    import re
    return re.sub(r"[^\w\sÀ-ɏḀ-ỿ]", "", text).strip()


def _draw_branding(canvas, tag_text: str) -> None:
    """Logo THỂ THAO 247 top-left, tag top-right."""
    draw  = ImageDraw.Draw(canvas)
    flogo = ImageFont.truetype(FONT_HEADLINE_PATH, 20)
    ftag  = ImageFont.truetype(FONT_UI_PATH, 17)

    # Dấu chấm accent (logo icon)
    dot_r = 7
    dot_x, dot_y = BRAND_LEFT, BRAND_Y - dot_r
    draw.ellipse((dot_x, dot_y, dot_x + dot_r * 2, dot_y + dot_r * 2),
                 fill=ACCENT_RED + (240,))

    # Logo text
    logo_x = BRAND_LEFT + dot_r * 2 + 8
    lw, lh = _measure(draw, "THỂ THAO 247", flogo)
    draw.text((logo_x, BRAND_Y - lh // 2 - 1), "THỂ THAO 247",
              font=flogo, fill=TEXT_PRIMARY + (240,))

    # Thin line dưới logo
    line_y = BRAND_Y + lh // 2 + 6
    draw.rectangle([BRAND_LEFT, line_y, BRAND_LEFT + lw + dot_r * 2 + 8, line_y + 1],
                   fill=ACCENT_RED + (120,))

    # Tag top-right: "BREAKING //"
    tag_clean = _strip_emoji(tag_text).upper()
    tag_str   = f"{tag_clean}  //"
    tw, th    = _measure(draw, tag_str, ftag)
    tag_x     = FRAME_W - tw - (FRAME_W - BRAND_RIGHT)
    draw.text((tag_x, BRAND_Y - th // 2), tag_str,
              font=ftag, fill=TEXT_SECONDARY + (200,))


def _draw_badge(canvas, tag_text: str, accent: tuple) -> None:
    """Badge centered, nền gradient đỏ, text CATEGORY."""
    draw  = ImageDraw.Draw(canvas)
    fbadge = ImageFont.truetype(FONT_UI_PATH, 24)
    label  = _strip_emoji(tag_text).upper()

    tw, th = _measure(draw, label, fbadge)
    pad_x, pad_y = 28, 14
    bw = tw + pad_x * 2
    bh = th + pad_y * 2
    bx = (FRAME_W - bw) // 2
    by = BADGE_CY - bh // 2

    # Badge background: gradient horizontal (accent_dark → accent)
    badge_img  = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(badge_img)

    # Gradient: left dark → right accent color
    r1, g1, b1 = BADGE_RED_DARK
    r2, g2, b2 = accent
    for x in range(bw):
        t = x / max(bw - 1, 1)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        badge_draw.rectangle([x, 0, x, bh], fill=(r, g, b, 220))

    # Rounded mask
    mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw, bh), radius=bh // 2, fill=255)
    badge_img.putalpha(mask)
    canvas.alpha_composite(badge_img, (bx, by))

    # Border ăn với rounded
    border_layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border_layer)
    bd.rounded_rectangle((0, 0, bw - 1, bh - 1), radius=bh // 2,
                          outline=(255, 255, 255, 60), width=1)
    canvas.alpha_composite(border_layer, (bx, by))

    # Text centered in badge
    draw = ImageDraw.Draw(canvas)
    tx = bx + (bw - tw) // 2
    ty = by + (bh - th) // 2 - 1
    draw.text((tx, ty), label, font=fbadge, fill=TEXT_PRIMARY + (255,))


def _draw_centered_text(canvas, text, font_path, start_size, max_lines,
                        top_y, fill, max_width=None):
    """Vẽ text centered theo chiều ngang. Trả về y cuối cùng."""
    max_width = max_width or TEXT_W
    draw = ImageDraw.Draw(canvas)
    wrapped = smart_wrap(draw, text, max_width=max_width, max_lines=max_lines,
                         font_path=font_path, start_size=start_size)
    lh  = int(wrapped.font.size * 1.10)
    cur_y = top_y
    for line in wrapped.lines:
        lw, _ = _measure(draw, line, wrapped.font)
        x     = (FRAME_W - lw) // 2
        draw.text((x, cur_y), line, font=wrapped.font, fill=fill)
        cur_y += lh
    return cur_y


# ───────────────────────────────────────────────────────────
# Public render functions
# ───────────────────────────────────────────────────────────

def render_scene(scene, image_path, bg_output, overlay_output,
                 scene_index=0, total_scenes=4):
    img = Image.open(image_path).convert("RGB")
    aspect_class = _classify_aspect(img)

    # BG: color-graded + center-crop cho Ken Burns
    bg = _render_bg(img)
    bg_output.parent.mkdir(parents=True, exist_ok=True)
    bg.save(bg_output, "JPEG", quality=92)

    # Overlay: transparent RGBA
    canvas = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))
    _draw_gradient(canvas)

    accent = _resolve_accent(scene.get("accent", "red"))
    tag    = scene.get("tag", "⚡ BREAKING")

    _draw_branding(canvas, tag)
    _draw_badge(canvas, tag, accent)

    # Headline — centered, lớn
    headline_bottom = _draw_centered_text(
        canvas, scene["headline"],
        font_path=FONT_HEADLINE_PATH,
        start_size=72, max_lines=2,
        top_y=HEADLINE_Y,
        fill=TEXT_PRIMARY + (255,),
    )

    # Subtext — centered, nhỏ hơn
    subtext_y = headline_bottom + SUBTEXT_GAP
    _draw_centered_text(
        canvas, scene["subtext"],
        font_path=FONT_UI_PATH,
        start_size=28, max_lines=2,
        top_y=subtext_y,
        fill=TEXT_SECONDARY + (220,),
    )

    overlay_output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(overlay_output, "PNG", optimize=True)

    return {
        "aspect_class": aspect_class,
        "aspect": img.size[0] / img.size[1],
        "image_size": img.size,
        "bg_size": bg.size,
    }


def render_all_scenes(scenes, images_dir, frames_dir):
    results = []
    for idx, scene in enumerate(scenes):
        scene_id = scene.get("id", f"{idx+1:02d}")
        image_path = None
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            cand = images_dir / f"scene_{scene_id}{ext}"
            if cand.exists():
                image_path = cand; break
        if image_path is None:
            raise FileNotFoundError(f"Không tìm thấy ảnh scene {scene_id}")

        bg_out  = frames_dir / f"bg_{scene_id}.jpg"
        ov_out  = frames_dir / f"overlay_{scene_id}.png"
        meta    = render_scene(scene, image_path, bg_out, ov_out,
                               scene_index=idx, total_scenes=len(scenes))
        meta["scene_id"] = scene_id
        results.append(meta)
        print(f"  ✓ scene {scene_id} → bg {meta['bg_size']} + overlay {FRAME_W}×{FRAME_H}"
              f" (aspect {meta['aspect']:.2f} / {meta['aspect_class']})")
    return results

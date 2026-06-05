"""
scene_renderer.py — Render từng scene PNG 720×1280

LAYOUT: Dark Sports Editorial
- Ảnh full-bleed 720×1280 với color grading (contrast, vignette, cold tint)
- Gradient tối phủ từ 45% màn hình xuống đáy — không có khối nền cứng
- Text nổi trực tiếp trên gradient: tag pill → accent line → headline → subtext
- Progress dots ở safe zone (≥120px từ đáy, tránh UI TikTok/Reels)

THAY ĐỔI SO VỚI PHIÊN BẢN CŨ:
- Không còn template_bg.png (khối nền xanh cứng)
- Ảnh mở rộng toàn khung (800px → 1280px)
- Chỉ 2 accent: gold (#D4AF37) và red (#C8102E)
- Font: Bebas Neue cho headline, Arial Bold cho subtext
- Thứ bậc rõ ràng: headline 68px vs subtext 27px
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
import numpy as np

# ───────────────────────────────────────────────────────────
# Frame & layout constants
# ───────────────────────────────────────────────────────────
FRAME_W, FRAME_H = 720, 1280

# Gradient: bắt đầu tối dần từ y=480, gần đặc tại y=1000
GRADIENT_START_Y = 480
GRADIENT_DENSE_Y = 1000

# Text zone — phía dưới ảnh
DOTS_Y       = 872   # progress dots — ĐẶT TRÊN tag pill, tránh TikTok UI
TAG_Y        = 900   # top của tag pill
ACCENT_Y     = 950   # đường kẻ accent mỏng
HEADLINE_Y   = 964   # top của headline
PANEL_LEFT   = 56    # left margin
PANEL_RIGHT  = 664   # right limit (56px từ phải)
PANEL_TEXT_W = PANEL_RIGHT - PANEL_LEFT  # 608px

# Safe zone — không đặt text quan trọng dưới đây (TikTok/Reels UI ~bottom 15%)
SAFE_BOTTOM = 1160

# Ken Burns — bg image lớn hơn frame để có room pan/zoom (full frame)
BG_SCALE = 1.3
BG_W     = int(FRAME_W * BG_SCALE)   # 936
BG_H     = int(FRAME_H * BG_SCALE)   # 1664

# ───────────────────────────────────────────────────────────
# Color scheme — Dark Sports Editorial
# ───────────────────────────────────────────────────────────
DARK_NAVY        = (8, 12, 22)          # #080C16 — nền gradient
TEXT_PRIMARY     = (248, 248, 248)      # #F8F8F8 — headline trắng ngà
TEXT_SECONDARY   = (160, 165, 178)      # #A0A5B2 — subtext xám lạnh
ACCENT_GOLD      = (212, 175, 55)       # #D4AF37 — vàng kim
ACCENT_RED       = (200, 16, 46)        # #C8102E — đỏ Arsenal

# Map accent cũ → 2 màu mới
_ACCENT_MAP: dict[str, tuple] = {
    "emerald": ACCENT_GOLD,
    "cyan":    ACCENT_GOLD,
    "amber":   ACCENT_GOLD,
    "red":     ACCENT_RED,
    "gold":    ACCENT_GOLD,
}

def _resolve_accent(accent_str: str) -> tuple:
    return _ACCENT_MAP.get(accent_str, ACCENT_GOLD)

# ───────────────────────────────────────────────────────────
# Fonts
# ───────────────────────────────────────────────────────────
FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"

# Headline: Segoe UI Bold (Vietnamese OK) → fallback Noto Sans → DejaVu Bold
# Oswald-Bold.ttf trong repo thiếu Vietnamese subset — cần thay bằng full version
FONT_HEADLINE_CANDIDATES = [
    Path("C:/Windows/Fonts/segoeuib.ttf"),                                      # Windows — Vietnamese OK ✓
    Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),                   # Ubuntu fonts-noto
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
    FONT_DIR / "Oswald-Bold.ttf",                                               # nếu có full-subset version
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),       # Ubuntu fonts-liberation
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]

# Subtext: Arial Bold → Segoe UI → Liberation
FONT_SUBTEXT_CANDIDATES = [
    Path("C:/Windows/Fonts/arialbd.ttf"),                                       # Windows
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),                # Ubuntu fonts-noto
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),    # Ubuntu
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]

def _find_font(candidates: list[Path]) -> str:
    for p in candidates:
        if p.exists():
            return str(p)
    raise FileNotFoundError(f"Không tìm thấy font: {candidates}")

FONT_HEADLINE_PATH = _find_font(FONT_HEADLINE_CANDIDATES)
FONT_SUBTEXT_PATH  = _find_font(FONT_SUBTEXT_CANDIDATES)

# ───────────────────────────────────────────────────────────
# Smart word-wrap (giữ nguyên logic)
# ───────────────────────────────────────────────────────────

@dataclass
class WrappedText:
    lines: list[str]
    font: ImageFont.FreeTypeFont
    truncated: bool


def _measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap_words(words: list[str], font: ImageFont.FreeTypeFont, max_width: int,
                draw: ImageDraw.ImageDraw) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        w, _ = _measure_text(draw, candidate, font)
        if w <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def smart_wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_lines: int,
    font_path: str,
    start_size: int,
    min_size: int = 24,
    step: int = 4,
) -> WrappedText:
    words = text.strip().split()
    size = start_size
    last_lines: list[str] = []
    last_font: Optional[ImageFont.FreeTypeFont] = None

    while size >= min_size:
        font = ImageFont.truetype(font_path, size)
        lines = _wrap_words(words, font, max_width, draw)
        last_lines = lines
        last_font = font

        if len(lines) <= max_lines:
            if all(_measure_text(draw, line, font)[0] <= max_width for line in lines):
                if len(lines) > 1 and len(lines[-1].split()) == 1 and size - step >= min_size:
                    size -= step
                    continue
                return WrappedText(lines=lines, font=font, truncated=False)
        size -= step

    assert last_font is not None
    truncated_lines = last_lines[:max_lines]
    if len(last_lines) > max_lines and truncated_lines:
        last_line = truncated_lines[-1]
        last_words = last_line.split()
        while last_words:
            attempt = " ".join(last_words) + "…"
            w, _ = _measure_text(draw, attempt, last_font)
            if w <= max_width:
                truncated_lines[-1] = attempt
                break
            last_words.pop()
        else:
            truncated_lines[-1] = "…"
    return WrappedText(lines=truncated_lines, font=last_font, truncated=True)


# ───────────────────────────────────────────────────────────
# Image helpers
# ───────────────────────────────────────────────────────────

def _fit_full_bleed(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    return ImageOps.fit(img, (target_w, target_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _apply_color_grading(img: Image.Image) -> Image.Image:
    """Tăng contrast, giảm saturation, thêm cold tint và vignette."""
    # 1. Contrast +15%
    img = ImageEnhance.Contrast(img).enhance(1.15)
    # 2. Saturation -12%
    img = ImageEnhance.Color(img).enhance(0.88)
    # 3. Cold navy tint (8% blue overlay)
    w, h = img.size
    tint = Image.new("RGB", (w, h), (0, 8, 28))
    img = Image.blend(img, tint, alpha=0.08)
    # 4. Vignette (numpy radial gradient)
    arr = np.array(img).astype(np.float32)
    y_idx = np.linspace(-1, 1, h)[:, None]
    x_idx = np.linspace(-1, 1, w)[None, :]
    dist = np.sqrt(x_idx ** 2 + y_idx ** 2) / np.sqrt(2)   # 0=center, 1=corner
    vignette = 1.0 - np.clip(dist * 0.55, 0, 0.38)          # max 38% darkening at corners
    arr = arr * vignette[:, :, None]
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _draw_gradient_overlay(canvas: Image.Image) -> None:
    """
    Phủ gradient 2 tầng lên canvas RGBA:
      Tầng 1 (y=640-832): nhẹ, alpha 0→50 — ảnh vẫn thấy được
      Tầng 2 (y=832-1280): dark panel, alpha 140→220 — nền cho text

    Ảnh hiện rõ từ y=0-640 (50%), mờ nhẹ đến y=832, tối cho text từ y=832+.
    """
    w, h = canvas.size
    arr = np.array(canvas).astype(np.float32)   # RGBA (transparent initially)

    FADE_START = 640    # bắt đầu mờ nhẹ
    PANEL_START = 832   # bắt đầu dark panel cho text

    dn = np.array(DARK_NAVY, dtype=np.float32)

    # Tầng 1: light fade  y = [640, 832)
    for y in range(FADE_START, PANEL_START):
        t = (y - FADE_START) / (PANEL_START - FADE_START)   # 0→1 linear
        a = t * 50.0 / 255.0                                  # alpha 0→50
        arr[y, :, :3] = arr[y, :, :3] * (1 - a) + dn * a
        arr[y, :, 3] = t * 80.0                              # alpha channel nhẹ

    # Tầng 2: dark panel  y = [832, h)
    for y in range(PANEL_START, h):
        t = (y - PANEL_START) / max(h - PANEL_START, 1)     # 0→1
        a = (140.0 + t * 80.0) / 255.0                       # alpha 140→220
        arr[y, :, :3] = arr[y, :, :3] * (1 - a) + dn * a
        arr[y, :, 3] = 140.0 + t * 80.0

    # Vùng trên: trong suốt hoàn toàn
    arr[:FADE_START, :, 3] = 0.0

    result = np.clip(arr, 0, 255).astype(np.uint8)
    canvas.paste(Image.fromarray(result), (0, 0))


def _strip_emoji(text: str) -> str:
    import re
    return re.sub(r"[^\w\sÀ-ɏḀ-ỿ]", "", text).strip()


def _draw_tag_pill(canvas: Image.Image, tag: str, accent: tuple, x: int, y: int) -> int:
    """Vẽ tag pill nhỏ gọn. Trả về width của pill."""
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT_SUBTEXT_PATH, 22)
    label = _strip_emoji(tag).upper()
    w, h = _measure_text(draw, label, font)
    pill_w = w + 36
    pill_h = h + 18
    r = pill_h // 2

    # Vẽ pill bằng rounded rectangle mask
    mask = Image.new("L", (pill_w, pill_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, pill_w, pill_h), radius=r, fill=255)
    layer = Image.new("RGBA", (pill_w, pill_h), accent + (230,))
    canvas.paste(layer, (x, y), mask)

    draw.text((x + 18, y + (pill_h - h) // 2 - 1), label,
              font=font, fill=(255, 255, 255, 255))
    return pill_w


def _draw_accent_line(canvas: Image.Image, accent: tuple, x: int, y: int, width: int = 90) -> None:
    """Vẽ đường kẻ accent mỏng (2px) — phân tách tag và headline."""
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([x, y, x + width, y + 2], fill=accent + (210,))


def _draw_progress_dots(canvas: Image.Image, scene_index: int, total: int,
                        center_x: int, y: int, accent: tuple) -> None:
    draw = ImageDraw.Draw(canvas)
    dot_r = 5
    gap   = 14
    total_w = total * (dot_r * 2) + (total - 1) * gap
    start_x = center_x - total_w // 2
    for i in range(total):
        cx = start_x + i * (dot_r * 2 + gap) + dot_r
        fill = accent + (220,) if i == scene_index else (255, 255, 255, 70)
        draw.ellipse((cx - dot_r, y - dot_r, cx + dot_r, y + dot_r), fill=fill)


# ───────────────────────────────────────────────────────────
# BG render (ảnh gốc → 936×1664 cho Ken Burns full frame)
# ───────────────────────────────────────────────────────────

def _render_bg(img: Image.Image) -> Image.Image:
    """Color grading + center-crop fill 936×1664 cho Ken Burns."""
    img = _apply_color_grading(img)
    return _fit_full_bleed(img, BG_W, BG_H)


# ───────────────────────────────────────────────────────────
# Overlay render (gradient + text, 720×1280 RGBA trong suốt trên)
# ───────────────────────────────────────────────────────────

def _render_overlay(scene: dict, scene_index: int, total_scenes: int = 4) -> Image.Image:
    """
    Render overlay 720×1280 RGBA:
    - Phần trên (< GRADIENT_START_Y): trong suốt, ảnh Ken Burns hiện qua
    - Phần giữa-dưới: gradient tối → text nổi lên

    Layout (từ trên xuống trong vùng tối):
      TAG_Y   → tag pill (nhỏ, màu accent)
      ACCENT_Y → đường kẻ mỏng 90px
      HEADLINE_Y → headline lớn (Bebas Neue / Impact)
      [calc]  → subtext nhỏ hơn 60%
      DOTS_Y  → progress dots
    """
    accent_rgb = _resolve_accent(scene.get("accent", "gold"))

    # Canvas trong suốt
    canvas = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))

    # Phủ gradient tối
    _draw_gradient_overlay(canvas)

    draw = ImageDraw.Draw(canvas)

    # ── 1. Tag pill ──
    tag = scene.get("tag", "⚡ BREAKING")
    _draw_tag_pill(canvas, tag, accent_rgb, PANEL_LEFT, TAG_Y)

    # ── 2. Accent line ──
    _draw_accent_line(canvas, accent_rgb, PANEL_LEFT, ACCENT_Y)

    # ── 3. Headline (Bebas Neue 68px, max 2 dòng) ──
    h_wrap = smart_wrap(
        draw, scene["headline"],
        max_width=PANEL_TEXT_W, max_lines=2,
        font_path=FONT_HEADLINE_PATH, start_size=68, min_size=48, step=4,
    )
    h_line_h = int(h_wrap.font.size * 1.10)
    cur_y = HEADLINE_Y
    for line in h_wrap.lines:
        draw.text((PANEL_LEFT, cur_y), line,
                  font=h_wrap.font, fill=TEXT_PRIMARY + (255,))
        cur_y += h_line_h
    headline_bottom = cur_y

    # ── 4. Subtext (Arial Bold 27px, max 2 dòng) ──
    gap = 10
    subtext_y = headline_bottom + gap
    s_wrap = smart_wrap(
        draw, scene["subtext"],
        max_width=PANEL_TEXT_W, max_lines=2,
        font_path=FONT_SUBTEXT_PATH, start_size=27, min_size=22, step=2,
    )
    s_line_h = int(s_wrap.font.size * 1.15)

    # Nếu tràn safe zone → giới hạn 1 dòng
    estimated_bottom = subtext_y + s_line_h * len(s_wrap.lines)
    if estimated_bottom > SAFE_BOTTOM:
        s_wrap = smart_wrap(
            draw, scene["subtext"],
            max_width=PANEL_TEXT_W, max_lines=1,
            font_path=FONT_SUBTEXT_PATH, start_size=26, min_size=22, step=2,
        )
        s_line_h = int(s_wrap.font.size * 1.15)

    cur_y = subtext_y
    for line in s_wrap.lines:
        draw.text((PANEL_LEFT, cur_y), line,
                  font=s_wrap.font, fill=TEXT_SECONDARY + (230,))
        cur_y += s_line_h

    # ── 5. Progress dots ──
    _draw_progress_dots(canvas, scene_index, total_scenes,
                        center_x=FRAME_W // 2, y=DOTS_Y, accent=accent_rgb)

    return canvas


# ───────────────────────────────────────────────────────────
# Public API
# ───────────────────────────────────────────────────────────

def _classify_aspect(img: Image.Image) -> str:
    w, h = img.size
    aspect = w / h
    if aspect > 1.3:
        return "landscape"
    elif aspect < 0.7:
        return "portrait"
    return "square"


def render_scene(scene: dict, image_path: Path, bg_output: Path, overlay_output: Path,
                 scene_index: int = 0, total_scenes: int = 4) -> dict:
    """
    Render 1 scene → 2 file:
    - bg_output:      936×1664 JPEG (full-frame, color-graded, cho Ken Burns)
    - overlay_output: 720×1280 PNG RGBA (gradient + text, trong suốt phía trên)
    """
    img = Image.open(image_path).convert("RGB")
    aspect_class = _classify_aspect(img)

    bg = _render_bg(img)
    bg_output.parent.mkdir(parents=True, exist_ok=True)
    bg.save(bg_output, "JPEG", quality=92)

    overlay = _render_overlay(scene, scene_index, total_scenes=total_scenes)
    overlay_output.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(overlay_output, "PNG", optimize=True)

    return {
        "aspect_class": aspect_class,
        "aspect": img.size[0] / img.size[1],
        "image_size": img.size,
        "bg_size": bg.size,
    }


def render_all_scenes(scenes: list[dict], images_dir: Path, frames_dir: Path) -> list[dict]:
    results = []
    for idx, scene in enumerate(scenes):
        scene_id = scene.get("id", f"{idx+1:02d}")
        image_path = None
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            candidate = images_dir / f"scene_{scene_id}{ext}"
            if candidate.exists():
                image_path = candidate
                break
        if image_path is None:
            raise FileNotFoundError(f"Không tìm thấy ảnh cho scene {scene_id} trong {images_dir}")

        bg_output      = frames_dir / f"bg_{scene_id}.jpg"
        overlay_output = frames_dir / f"overlay_{scene_id}.png"
        meta = render_scene(scene, image_path, bg_output, overlay_output,
                            scene_index=idx, total_scenes=len(scenes))
        meta["scene_id"] = scene_id
        results.append(meta)
        print(f"  ✓ scene {scene_id} → bg {meta['bg_size']} + overlay {FRAME_W}×{FRAME_H}"
              f" (aspect {meta['aspect']:.2f} / {meta['aspect_class']})")
    return results

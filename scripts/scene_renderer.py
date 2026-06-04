"""
scene_renderer.py — Render từng scene PNG 720×1280

NGUYÊN LÝ ĐƠN GIẢN:
- 1 layout duy nhất, áp dụng mọi aspect ratio
- Hình LUÔN full-bleed 720×1280 (zoom + center crop)
- Text đè trên hình, có gradient đen ở vùng text để đảm bảo đọc được
- Không bao giờ có dải đen trống trên màn hình

SMART WORD-WRAP:
- Không bao giờ cắt giữa từ
- Quá dài → giảm font 4px/lần (min 28px)
- Vẫn không vừa → cắt cuối với "…" ở ranh giới từ
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ───────────────────────────────────────────────────────────
# Constants
# ───────────────────────────────────────────────────────────

FRAME_W, FRAME_H = 720, 1280

# Accent colors xoay vòng theo scene
ACCENT_COLORS = {
    "emerald": "#10B981",
    "cyan":    "#06B6D4",
    "amber":   "#F59E0B",
    "red":     "#EF4444",
}
ACCENT_ROTATION = ["emerald", "cyan", "amber", "red"]

# Template layout
TEMPLATE_PATH = Path(__file__).parent.parent / "assets" / "template_bg.png"
PANEL_TOP     = 800   # top nội thất khung tối
PHOTO_ZONE_H  = PANEL_TOP  # bg ảnh phủ đúng tới đây, không có gap đen
PANEL_BOTTOM  = 1018  # bottom nội thất khung tối
PANEL_LEFT    = 65    # padding trái (tránh chamfer góc)
PANEL_RIGHT   = 655   # padding phải
PANEL_TEXT_W  = PANEL_RIGHT - PANEL_LEFT   # = 590
PANEL_TEXT_GAP = 16   # khoảng cách headline → subtext

# Font paths (sẽ fallback nếu không có Segoe UI)
FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"
FONT_BOLD_CANDIDATES = [
    FONT_DIR / "segoeuib.ttf",
    Path("C:/Windows/Fonts/segoeuib.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/System/Library/Fonts/Helvetica.ttc"),
]
FONT_REG_CANDIDATES = [
    FONT_DIR / "segoeui.ttf",
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/System/Library/Fonts/Helvetica.ttc"),
]


def _find_font(candidates: list[Path]) -> str:
    for p in candidates:
        if p.exists():
            return str(p)
    raise FileNotFoundError(f"Không tìm thấy font nào trong: {candidates}")


FONT_BOLD_PATH = _find_font(FONT_BOLD_CANDIDATES)
FONT_REG_PATH = _find_font(FONT_REG_CANDIDATES)


# ───────────────────────────────────────────────────────────
# Smart word-wrap
# ───────────────────────────────────────────────────────────

@dataclass
class WrappedText:
    lines: list[str]
    font: ImageFont.FreeTypeFont
    truncated: bool


def _measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """Trả về (width, height) của 1 dòng text."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap_words(words: list[str], font: ImageFont.FreeTypeFont, max_width: int,
                draw: ImageDraw.ImageDraw) -> list[str]:
    """Wrap từng từ vào max_width. Không cắt giữa từ."""
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
    min_size: int = 28,
    step: int = 4,
) -> WrappedText:
    """
    Smart word-wrap:
    1. Wrap theo từ ở size hiện tại
    2. Nếu nhiều dòng hơn max_lines → giảm size, thử lại
    3. Đến min_size mà vẫn dài → cắt cuối với '…' ở ranh giới từ
    """
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
            # Vừa max_lines, kiểm tra width thực tế
            if all(_measure_text(draw, line, font)[0] <= max_width for line in lines):
                # Tránh orphan: nếu dòng cuối chỉ 1 từ và còn thể giảm size → giảm tiếp
                if len(lines) > 1 and len(lines[-1].split()) == 1 and size - step >= min_size:
                    size -= step
                    continue
                return WrappedText(lines=lines, font=font, truncated=False)

        size -= step

    # Đã đến min_size mà vẫn không vừa → cắt cuối với '…'
    assert last_font is not None
    truncated_lines = last_lines[:max_lines]
    if len(last_lines) > max_lines and truncated_lines:
        # Thêm '…' vào dòng cuối, ưu tiên cắt ở ranh giới từ
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

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))  # type: ignore


def _classify_aspect(img: Image.Image) -> str:
    """Phân loại để log thôi, không dùng để chọn layout nữa."""
    w, h = img.size
    aspect = w / h
    if aspect > 1.3:
        return "landscape"
    elif aspect < 0.7:
        return "portrait"
    else:
        return "square"


def _fit_full_bleed(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Center-crop ảnh để fill full 720×1280, không méo, không blur."""
    return ImageOps.fit(img, (target_w, target_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _draw_vertical_gradient(canvas: Image.Image, x: int, y: int, w: int, h: int,
                            top_alpha: int, bottom_alpha: int) -> None:
    """Vẽ gradient đen dọc lên canvas (RGBA), top→bottom alpha."""
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for i in range(h):
        t = i / max(h - 1, 1)
        alpha = int(top_alpha + (bottom_alpha - top_alpha) * t)
        for_row = Image.new("RGBA", (w, 1), (0, 0, 0, alpha))
        grad.paste(for_row, (0, i))
    canvas.alpha_composite(grad, (x, y))


def _rounded_rectangle(canvas: Image.Image, bbox: tuple[int, int, int, int],
                       radius: int, fill: tuple) -> None:
    """Vẽ rounded rectangle có alpha."""
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    layer = Image.new("RGBA", (w, h), fill)
    canvas.paste(layer, (x1, y1), mask)


# ───────────────────────────────────────────────────────────
# Common elements
# ───────────────────────────────────────────────────────────

def _strip_emoji(text: str) -> str:
    """Xóa emoji Unicode khỏi chuỗi, giữ lại text ASCII/Latin/Vietnamese."""
    import re
    return re.sub(r"[^\w\sÀ-ɏḀ-ỿ]", "", text).strip()


def _draw_tag_pill(canvas: Image.Image, tag: str, accent_hex: str,
                   x: int, y: int) -> int:
    """Vẽ tag pill (không emoji), trả về width của pill."""
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT_BOLD_PATH, 26)
    label = _strip_emoji(tag).upper()  # bỏ emoji, chỉ giữ text
    w, h = _measure_text(draw, label, font)
    pill_w = w + 48
    pill_h = h + 24
    accent_rgb = _hex_to_rgb(accent_hex) + (255,)
    _rounded_rectangle(canvas, (x, y, x + pill_w, y + pill_h), radius=pill_h // 2, fill=accent_rgb)
    text_x = x + 24
    text_y = y + (pill_h - h) // 2 - 2
    draw.text((text_x, text_y), label, font=font, fill=(255, 255, 255, 255))
    return pill_w


def _draw_progress_dots(canvas: Image.Image, scene_index: int, total: int,
                        center_x: int, y: int, accent_hex: str) -> None:
    """Vẽ progress dots dưới đáy."""
    draw = ImageDraw.Draw(canvas)
    accent_rgb = _hex_to_rgb(accent_hex) + (255,)
    white_dim = (255, 255, 255, 100)
    dot_r = 8
    gap = 20
    total_w = total * (dot_r * 2) + (total - 1) * gap
    start_x = center_x - total_w // 2
    for i in range(total):
        cx = start_x + i * (dot_r * 2 + gap) + dot_r
        fill = accent_rgb if i == scene_index else white_dim
        draw.ellipse((cx - dot_r, y - dot_r, cx + dot_r, y + dot_r), fill=fill)


def _draw_text_block(canvas: Image.Image, text: str, x: int, y: int,
                     max_width: int, max_lines: int, start_size: int,
                     font_path: str, fill=(255, 255, 255, 255),
                     line_spacing: float = 1.15) -> int:
    """Vẽ block text với smart word-wrap. Trả về y cuối block."""
    draw = ImageDraw.Draw(canvas)
    wrapped = smart_wrap(
        draw, text, max_width=max_width, max_lines=max_lines,
        font_path=font_path, start_size=start_size,
    )
    line_height = int(wrapped.font.size * line_spacing)
    cur_y = y
    for line in wrapped.lines:
        draw.text((x, cur_y), line, font=wrapped.font, fill=fill)
        cur_y += line_height
    return cur_y


# ───────────────────────────────────────────────────────────
# UNIFIED RENDER — tách bg (hình) + overlay (text) cho Ken Burns
# ───────────────────────────────────────────────────────────

# Khi Ken Burns zoom in/pan, hình base phải LỚN HƠN vùng ảnh để không bị viền đen.
# Với template layout: chỉ cần fill PHOTO_ZONE (738px) × BG_SCALE thay vì full frame.
# → giảm upscale từ 2.3x xuống ~1.3x cho ảnh landscape → không vỡ pixel.
BG_SCALE = 1.3
BG_W      = int(FRAME_W * BG_SCALE)         # 936
BG_H      = int(PHOTO_ZONE_H * BG_SCALE)    # 800 × 1.3 = 1040  (vùng ảnh đến panel)


def _render_bg(img: Image.Image) -> Image.Image:
    """Render bg BG_W×BG_H cho Ken Burns — center-crop fill, không méo, không viền đen."""
    return _fit_full_bleed(img, BG_W, BG_H)


def _render_overlay(scene: dict, scene_index: int, total_scenes: int = 3) -> Image.Image:
    """
    Render overlay 720×1280 dùng template cố định.
    - Vùng ảnh (y < PHOTO_ZONE_H): alpha=0 → bg Ken Burns hiện qua
    - Vùng khung tối: giữ nguyên từ template
    - Text headline + subtext căn giữa DỌC trong khung, không bao giờ tràn ra ngoài
    """
    import numpy as np

    template = Image.open(TEMPLATE_PATH).convert("RGBA")
    canvas = template.resize((FRAME_W, FRAME_H), Image.Resampling.LANCZOS)

    # Vùng ảnh → transparent
    arr = np.array(canvas)
    arr[:PHOTO_ZONE_H, :, 3] = 0
    canvas = Image.fromarray(arr)

    draw = ImageDraw.Draw(canvas)
    panel_h = PANEL_BOTTOM - PANEL_TOP  # ~218px

    # --- Pre-wrap để tính chiều cao thực tế ---
    h_wrap = smart_wrap(draw, scene["headline"],
                        max_width=PANEL_TEXT_W, max_lines=2,
                        font_path=FONT_BOLD_PATH, start_size=58)
    s_wrap = smart_wrap(draw, scene["subtext"],
                        max_width=PANEL_TEXT_W, max_lines=2,
                        font_path=FONT_REG_PATH, start_size=34)

    h_line_h = int(h_wrap.font.size * 1.15)
    s_line_h = int(s_wrap.font.size * 1.15)
    h_total  = h_line_h * len(h_wrap.lines)
    s_total  = s_line_h * len(s_wrap.lines)

    block_h = h_total + PANEL_TEXT_GAP + s_total

    # Nếu block > panel: thu nhỏ font subtext đến 1 dòng tối đa
    if block_h > panel_h:
        s_wrap = smart_wrap(draw, scene["subtext"],
                            max_width=PANEL_TEXT_W, max_lines=1,
                            font_path=FONT_REG_PATH, start_size=32)
        s_line_h = int(s_wrap.font.size * 1.15)
        s_total  = s_line_h * len(s_wrap.lines)
        block_h  = h_total + PANEL_TEXT_GAP + s_total

    # Căn giữa dọc trong khung, clamp không tràn
    start_y = PANEL_TOP + (panel_h - block_h) // 2
    start_y = max(PANEL_TOP, min(start_y, PANEL_BOTTOM - block_h))

    headline_y = start_y
    subtext_y  = start_y + h_total + PANEL_TEXT_GAP

    # --- Vẽ text đã pre-wrap ---
    cur_y = headline_y
    for line in h_wrap.lines:
        draw.text((PANEL_LEFT, cur_y), line, font=h_wrap.font, fill=(255, 255, 255, 255))
        cur_y += h_line_h

    cur_y = subtext_y
    for line in s_wrap.lines:
        draw.text((PANEL_LEFT, cur_y), line, font=s_wrap.font, fill=(220, 220, 220, 230))
        cur_y += s_line_h

    return canvas


# ───────────────────────────────────────────────────────────
# Public API
# ───────────────────────────────────────────────────────────

def render_scene(scene: dict, image_path: Path, bg_output: Path, overlay_output: Path,
                 scene_index: int = 0, total_scenes: int = 3) -> dict:
    """
    Render 1 scene → 2 file:
    - bg_output: hình 936×1664 (lớn hơn frame để composer Ken Burns)
    - overlay_output: PNG 720×1280 trong suốt chứa text + gradient + dots

    Composer sẽ ghép: Ken Burns bg + đè overlay → frame final.

    Returns:
        {aspect: float, aspect_class: str, image_size: tuple, bg_size: tuple}
    """
    img = Image.open(image_path).convert("RGB")
    aspect_class = _classify_aspect(img)  # chỉ để log

    # Render bg (hình lớn hơn frame để Ken Burns)
    bg = _render_bg(img)
    bg_output.parent.mkdir(parents=True, exist_ok=True)
    bg.save(bg_output, "JPEG", quality=92)

    # Render overlay trong suốt
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
    """
    Render toàn bộ scenes ra 2 file mỗi scene:
    - frames_dir/bg_<id>.jpg  (hình base 936×1664)
    - frames_dir/overlay_<id>.png  (text overlay 720×1280 trong suốt)

    Args:
        scenes: list scene dict
        images_dir: folder chứa hình gốc scene_01.jpg, ...
        frames_dir: folder để lưu bg + overlay
    """
    results = []
    for idx, scene in enumerate(scenes):
        scene_id = scene.get("id", f"{idx+1:02d}")
        # Tìm ảnh gốc
        image_path = None
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            candidate = images_dir / f"scene_{scene_id}{ext}"
            if candidate.exists():
                image_path = candidate
                break
        if image_path is None:
            raise FileNotFoundError(f"Không tìm thấy ảnh cho scene {scene_id} trong {images_dir}")

        bg_output = frames_dir / f"bg_{scene_id}.jpg"
        overlay_output = frames_dir / f"overlay_{scene_id}.png"
        meta = render_scene(scene, image_path, bg_output, overlay_output,
                            scene_index=idx, total_scenes=len(scenes))
        meta["scene_id"] = scene_id
        results.append(meta)
        print(f"  ✓ scene {scene_id} → bg {meta['bg_size']} + overlay 720×1280 (aspect {meta['aspect']:.2f} / {meta['aspect_class']})")

    return results


# ───────────────────────────────────────────────────────────
# Test với mock data
# ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("scene_renderer.py — chạy directly để test")
    print("Sử dụng test_renderer.py để chạy demo đầy đủ")

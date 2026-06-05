"""
scene_renderer.py — Render frame từ template PNG + article image + dynamic text.

QUY TẮC BẮT BUỘC:
  - KHÔNG bao giờ ghi đè vào assets/templates/
  - Chỉ ghi file mới vào output/frames/
  - KHÔNG thiết kế lại template, KHÔNG generate template bằng AI
  - Template là tài sản nhận diện đã chốt

FLOW mỗi scene:
  1. Mở template → resize 941×1672 → 1080×1920
  2. Chèn ảnh bài viết vào article_image_box (upper-right zone)
  3. Fill tối vùng placeholder text
  4. Vẽ category (top-right), badge (center), headline, subtitle
  5. Xuất composite PNG → output/frames/

OUTPUT: 1080×1920 (9:16, chuẩn TikTok / Shorts / Reels)
"""

from __future__ import annotations
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

# ───────────────────────────────────────────────────────────
# Constants
# ───────────────────────────────────────────────────────────
CANVAS_W, CANVAS_H = 1080, 1920        # output resolution
TEMPLATE_DIR = Path(__file__).parent.parent / "assets" / "templates"

# Vùng chèn ảnh bài viết (trong không gian 1080×1920)
ARTICLE_BOX = {"x": 540, "y": 380, "w": 440, "h": 560}

# Config vị trí text theo từng template (trong 1080×1920)
TEMPLATE_CONFIG: dict[str, dict] = {
    "tin-nhanh": {
        "category_x_right": 1036,  # right edge của category text
        "category_y": 62,
        "badge_cx": 540,           # badge center x
        "badge_cy": 1085,          # badge center y
        "fill_y": 1000,            # bắt đầu fill tối (che placeholder)
        "headline_y": 1120,
        "max_headline_lines": 2,
        "headline_size": 88,
    },
    "phan-tich": {
        "category_x_right": 1036,
        "category_y": 62,
        "badge_cx": 540,
        "badge_cy": 1085,
        "fill_y": 1000,
        "headline_y": 1120,
        "max_headline_lines": 2,
        "headline_size": 88,
    },
    "chuyen-nhuong": {
        "category_x_right": 1036,
        "category_y": 62,
        "badge_cx": 540,
        "badge_cy": 1085,
        "fill_y": 1000,
        "headline_y": 1120,
        "max_headline_lines": 2,
        "headline_size": 80,
    },
    "nhan-dinh-tran-dau": {
        "category_x_right": 1036,
        "category_y": 62,
        "badge_cx": 540,
        "badge_cy": 1085,
        "fill_y": 1000,
        "headline_y": 1120,
        "max_headline_lines": 2,
        "headline_size": 80,
    },
    "ket-qua-tran-dau": {
        "category_x_right": 1036,
        "category_y": 62,
        "badge_cx": 540,
        "badge_cy": 1085,
        "fill_y": 1000,
        "headline_y": 1120,
        "max_headline_lines": 2,
        "headline_size": 80,
    },
    "dang-ky-kenh": None,  # end card, không thay text
}

# Giới hạn text theo document
MAX_HEADLINE_1LINE = 32
MAX_HEADLINE_2LINE = 52
MAX_SUBTITLE_CHARS = 55
MAX_CATEGORY_CHARS = 22
MAX_BADGE_CHARS    = 14

# Colors
TEXT_WHITE  = (255, 255, 255, 255)
TEXT_GRAY   = (190, 192, 200, 220)
BADGE_RED1  = (160, 8, 18)      # badge gradient dark
BADGE_RED2  = (210, 20, 40)     # badge gradient light
DARK_FILL   = (5, 5, 12, 248)   # fill che text placeholder (gần đục hoàn toàn)

# ───────────────────────────────────────────────────────────
# Fonts
# ───────────────────────────────────────────────────────────
FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"

FONT_BOLD_CANDIDATES = [
    Path("C:/Windows/Fonts/segoeuib.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]
FONT_REG_CANDIDATES = [
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
    raise FileNotFoundError(f"Font not found: {candidates}")

FONT_BOLD = _find_font(FONT_BOLD_CANDIDATES)
FONT_REG  = _find_font(FONT_REG_CANDIDATES)

# ───────────────────────────────────────────────────────────
# Template protection
# ───────────────────────────────────────────────────────────

def _checksum(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()[:8]

_TEMPLATE_CHECKSUMS: dict[str, str] = {}

def _load_template(name: str) -> Image.Image:
    """
    Mở template, kiểm tra không bị ghi đè, trả về bản copy resized 1080×1920.
    KHÔNG BAO GIỜ trả về reference trực tiếp → caller không thể ghi lên gốc.
    """
    path = TEMPLATE_DIR / f"{name}.png"
    if not path.exists():
        raise FileNotFoundError(f"Template không tồn tại: {path}")

    # Lưu checksum lần đầu
    cs = _checksum(path)
    if name not in _TEMPLATE_CHECKSUMS:
        _TEMPLATE_CHECKSUMS[name] = cs
    elif _TEMPLATE_CHECKSUMS[name] != cs:
        raise RuntimeError(f"Template {name} đã bị thay đổi! Checksum mismatch.")

    img = Image.open(path).convert("RGBA")
    # Resize về 1080×1920 (9:16), KHÔNG crop
    img = img.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
    return img   # bản copy, không phải file gốc


# ───────────────────────────────────────────────────────────
# Text utilities
# ───────────────────────────────────────────────────────────

def _measure(draw, text, font):
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0], b[3] - b[1]


@dataclass
class Wrapped:
    lines: list[str]
    font: ImageFont.FreeTypeFont


def _smart_wrap(draw, text, max_w, max_lines, font_path, start_size, min_size=28, step=4):
    words = text.strip().split()
    for size in range(start_size, min_size - 1, -step):
        font  = ImageFont.truetype(font_path, size)
        lines, cur = [], ""
        for w in words:
            cand = f"{cur} {w}".strip()
            if _measure(draw, cand, font)[0] <= max_w:
                cur = cand
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        if len(lines) <= max_lines:
            return Wrapped(lines, font)
    # fallback: truncate last line
    font   = ImageFont.truetype(font_path, min_size)
    lines  = lines[:max_lines]
    if lines:
        ws = lines[-1].split()
        while ws:
            att = " ".join(ws) + "…"
            if _measure(draw, att, font)[0] <= max_w:
                lines[-1] = att; break
            ws.pop()
    return Wrapped(lines, font)


def _strip_emoji(text):
    import re
    return re.sub(r"[^\w\sÀ-ɏḀ-ỿ]", "", text).strip()

# ───────────────────────────────────────────────────────────
# Article image overlay
# ───────────────────────────────────────────────────────────

def _place_article_image(canvas: Image.Image, image_path: Path) -> None:
    """
    Chèn ảnh bài viết vào ARTICLE_BOX trên canvas.
    Không được che logo, badge, headline (nằm dưới fill_y).
    """
    box = ARTICLE_BOX
    try:
        article = Image.open(image_path).convert("RGBA")
    except Exception:
        return

    # Crop ảnh về tỉ lệ box
    target_ratio = box["w"] / box["h"]
    img_ratio    = article.width / article.height
    if img_ratio > target_ratio:
        new_w = int(article.height * target_ratio)
        left  = (article.width - new_w) // 2
        article = article.crop((left, 0, left + new_w, article.height))
    else:
        new_h = int(article.width / target_ratio)
        top   = (article.height - new_h) // 2
        article = article.crop((0, top, article.width, top + new_h))

    article = article.resize((box["w"], box["h"]), Image.Resampling.LANCZOS)

    # Bo góc 24px
    radius = 24
    mask   = Image.new("L", (box["w"], box["h"]), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, box["w"], box["h"]), radius=radius, fill=255)

    # Overlay tối nhẹ 30% lên ảnh để hòa với template
    dark = Image.new("RGBA", (box["w"], box["h"]), (0, 0, 0, 80))
    article = Image.alpha_composite(article, dark)

    # Dán lên canvas
    canvas.paste(article, (box["x"], box["y"]), mask)

    # Viền đỏ mảnh 2px
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]),
        radius=radius,
        outline=(180, 15, 22, 210),
        width=2,
    )


# ───────────────────────────────────────────────────────────
# Text layer: category, badge, headline, subtitle
# ───────────────────────────────────────────────────────────

def _draw_category(canvas, cfg, tag_text):
    """Category label top-right: 'TIN NHANH //'. Fill tối vùng này trước để che text cũ."""
    import re
    clean = re.sub(r"[^\w\sÀ-ɏḀ-ỿ]", "", tag_text).strip().upper()
    clean = clean[:MAX_CATEGORY_CHARS]
    label = f"{clean}  //"

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT_REG, 30)
    tw, th = _measure(draw, label, font)
    x = cfg["category_x_right"] - tw
    y = cfg["category_y"] - th // 2

    # Fill dark rect toàn bộ vùng top-right để che "CHUYÊN MỤC //" + đường kẻ template
    ImageDraw.Draw(canvas).rectangle(
        [400, 26, CANVAS_W, 150],
        fill=(5, 5, 12, 255),
    )

    draw.text((x + 1, y + 1), label, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), label, font=font, fill=(210, 210, 220, 220))


def _draw_badge(canvas, cfg, tag_text):
    """Badge đỏ gradient centered, phía trên headline."""
    import re
    clean = re.sub(r"[^\w\sÀ-ɏḀ-ỿ]", "", tag_text).strip().upper()
    clean = clean[:MAX_BADGE_CHARS]

    draw  = ImageDraw.Draw(canvas)
    font  = ImageFont.truetype(FONT_REG, 28)
    tw, th = _measure(draw, clean, font)
    pad_x, pad_y = 36, 16
    bw = tw + pad_x * 2
    bh = th + pad_y * 2
    bx = cfg["badge_cx"] - bw // 2
    by = cfg["badge_cy"] - bh // 2

    # Gradient đỏ horizontal
    badge = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    for ix in range(bw):
        t   = ix / max(bw - 1, 1)
        r   = int(BADGE_RED1[0] + (BADGE_RED2[0] - BADGE_RED1[0]) * t)
        g   = int(BADGE_RED1[1] + (BADGE_RED2[1] - BADGE_RED1[1]) * t)
        b   = int(BADGE_RED1[2] + (BADGE_RED2[2] - BADGE_RED1[2]) * t)
        ImageDraw.Draw(badge).rectangle([ix, 0, ix, bh], fill=(r, g, b, 225))

    # Rounded mask
    mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw, bh), radius=bh // 2, fill=255)
    badge.putalpha(mask)
    canvas.alpha_composite(badge, (bx, by))

    # Border trắng mỏng
    bd = ImageDraw.Draw(canvas)
    bd.rounded_rectangle((bx, by, bx + bw - 1, by + bh - 1),
                          radius=bh // 2, outline=(255, 255, 255, 50), width=1)

    # Text
    tx = bx + (bw - tw) // 2
    ty = by + (bh - th) // 2 - 1
    draw.text((tx, ty), clean, font=font, fill=TEXT_WHITE)


def _apply_text_fill(canvas: Image.Image, cfg: dict) -> None:
    """Fill fully-opaque dark rect từ fill_y xuống đáy để che toàn bộ placeholder text."""
    ImageDraw.Draw(canvas).rectangle(
        [0, cfg["fill_y"], CANVAS_W, CANVAS_H],
        fill=(5, 5, 12, 255),
    )


def _draw_headline_subtitle(canvas, cfg, headline, subtitle):
    """Vẽ headline + subtitle centered (gọi SAU _apply_text_fill và _draw_badge)."""
    draw = ImageDraw.Draw(canvas)

    pad_x   = 56   # left/right margin
    max_w   = CANVAS_W - pad_x * 2

    # Headline
    wrapped_h = _smart_wrap(draw, headline, max_w, cfg["max_headline_lines"],
                             FONT_BOLD, cfg["headline_size"])
    lh_h  = int(wrapped_h.font.size * 1.10)
    cur_y = cfg["headline_y"]
    for line in wrapped_h.lines:
        tw, _ = _measure(draw, line, wrapped_h.font)
        x     = (CANVAS_W - tw) // 2
        # Shadow
        draw.text((x + 2, cur_y + 2), line, font=wrapped_h.font, fill=(0, 0, 0, 180))
        draw.text((x, cur_y), line, font=wrapped_h.font, fill=TEXT_WHITE)
        cur_y += lh_h

    # Subtitle
    sub_y   = cur_y + 18
    sub     = subtitle[:MAX_SUBTITLE_CHARS]
    wrapped_s = _smart_wrap(draw, sub, max_w - 40, 2, FONT_REG, 32, min_size=26)
    lh_s  = int(wrapped_s.font.size * 1.15)
    for line in wrapped_s.lines:
        tw, _ = _measure(draw, line, wrapped_s.font)
        x     = (CANVAS_W - tw) // 2
        draw.text((x, sub_y), line, font=wrapped_s.font, fill=TEXT_GRAY)
        sub_y += lh_s


# ───────────────────────────────────────────────────────────
# Template selection
# ───────────────────────────────────────────────────────────

_TAG_TO_TEMPLATE = {
    "CHUYỂN NHƯỢNG": "chuyen-nhuong",
    "TRẬN ĐẤU":      "nhan-dinh-tran-dau",
    "KẾT QUẢ":       "ket-qua-tran-dau",
    "CHIẾN THUẬT":   "phan-tich",
    "NGÔI SAO":      "tin-nhanh",
    "GIẢI ĐẤU":      "tin-nhanh",
    "BREAKING":      "tin-nhanh",
    "BÓNG ĐÁ VN":   "tin-nhanh",
}

def select_template(tag: str) -> str:
    """Chọn template phù hợp theo tag của scene."""
    import re
    clean = re.sub(r"[^\w\sÀ-ɏḀ-ỿ]", "", tag).strip().upper()
    for key, tmpl in _TAG_TO_TEMPLATE.items():
        if key in clean:
            return tmpl
    return "tin-nhanh"  # default


# ───────────────────────────────────────────────────────────
# Public API (giữ nguyên interface cũ cho main.py)
# ───────────────────────────────────────────────────────────

def render_scene(scene: dict, image_path: Path, bg_output: Path,
                 overlay_output: Path, scene_index: int = 0,
                 total_scenes: int = 4) -> dict:
    """
    Render 1 scene theo template.

    bg_output   : không dùng (ảnh tĩnh, không cần Ken Burns bg)
    overlay_output: file frame composite cuối cùng (1080×1920)
    """
    tag      = scene.get("tag", "⚡ BREAKING")
    tmpl_name = select_template(tag)
    cfg      = TEMPLATE_CONFIG.get(tmpl_name) or TEMPLATE_CONFIG["tin-nhanh"]

    # 1. Load template (bản copy, không ghi đè gốc)
    canvas = _load_template(tmpl_name)

    # 2. Chèn ảnh bài viết
    if image_path and image_path.exists():
        _place_article_image(canvas, image_path)

    # 3. Thứ tự bắt buộc: fill tối → badge (nằm trên fill) → headline/subtitle
    _draw_category(canvas, cfg, tag)      # top-right, không bị fill che
    _apply_text_fill(canvas, cfg)         # fill tối từ fill_y xuống đáy
    _draw_badge(canvas, cfg, tag)         # badge vẽ SAU fill (không bị che)
    _draw_headline_subtitle(canvas, cfg, scene["headline"], scene["subtext"])

    # 4. Xuất ra output/frames/ (KHÔNG ghi vào assets/templates/)
    overlay_output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(overlay_output, "PNG", optimize=True)

    # bg_output không cần cho approach này, tạo symlink/copy nhỏ
    bg_output.parent.mkdir(parents=True, exist_ok=True)
    if not bg_output.exists():
        canvas.convert("RGB").save(bg_output, "JPEG", quality=85)

    img_orig = Image.open(image_path) if image_path and image_path.exists() else None
    aspect   = (img_orig.size[0] / img_orig.size[1]) if img_orig else 1.0
    return {
        "aspect_class": "landscape" if aspect > 1.3 else "portrait",
        "aspect": aspect,
        "image_size": img_orig.size if img_orig else (0, 0),
        "bg_size": (CANVAS_W, CANVAS_H),
        "template": tmpl_name,
    }


def render_all_scenes(scenes: list[dict], images_dir: Path, frames_dir: Path) -> list[dict]:
    results = []
    for idx, scene in enumerate(scenes):
        scene_id   = scene.get("id", f"{idx+1:02d}")
        image_path = None
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            cand = images_dir / f"scene_{scene_id}{ext}"
            if cand.exists():
                image_path = cand; break

        bg_out = frames_dir / f"bg_{scene_id}.jpg"
        ov_out = frames_dir / f"overlay_{scene_id}.png"
        meta   = render_scene(scene, image_path, bg_out, ov_out,
                               scene_index=idx, total_scenes=len(scenes))
        meta["scene_id"] = scene_id
        results.append(meta)
        print(f"  ✓ scene {scene_id} → {CANVAS_W}×{CANVAS_H}"
              f" template={meta['template']} (aspect {meta['aspect']:.2f})")
    return results

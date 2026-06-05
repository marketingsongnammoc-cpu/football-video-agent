"""
scene_renderer.py — Template compositing. KHÔNG thiết kế lại template.

QUY TẮC CỨNG:
  - Template PNG là nền bất biến. Không vẽ lại, không tạo panel mới.
  - Chỉ được PASTE article image vào đúng vùng quy định.
  - Chỉ được FILL vùng text nhỏ để che placeholder, rồi draw text.
  - Không được touch logo, badge, category, panel gốc.

FLOW:
  template = Image.open(...).resize(1080x1920)    # bản copy
  paste(article_image, box)                        # chèn ảnh bài viết
  fill(headline_zone, bg_color)                    # che placeholder cũ
  draw_text(headline)                              # vẽ tiêu đề mới
  fill(subtitle_zone, bg_color)                   # che placeholder cũ
  draw_text(subtitle)                             # vẽ mô tả mới
  save("output/frames/...")                        # KHÔNG ghi vào assets/templates/
"""

from __future__ import annotations
import hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ───────────────────────────────────────────────────────────
# Constants
# ───────────────────────────────────────────────────────────
CANVAS_W, CANVAS_H = 1080, 1920
TEMPLATE_DIR = Path(__file__).parent.parent / "assets" / "templates"

# Cấu hình mỗi template: vùng ảnh bài viết + vùng text (trong 1080×1920)
# Đo từ template gốc, KHÔNG được thay đổi.
TEMPLATE_CONFIG = {
    # Vị trí đo thực tế từ pixel-scan trên template 1080×1920
    "chuyen-nhuong": {
        "article": {"x": 610, "y": 390, "w": 360, "h": 430},
        # Headline placeholder thực: y=1330-1445 → fill từ y=1310, cao 155px
        # Draw tại y=1320 (theo document)
        "headline": {"x": 90, "fill_y": 1310, "fill_h": 155,
                     "draw_y": 1320, "w": 900,
                     "bg": (12, 14, 17), "size": 72, "lines": 2},
        # Subtitle placeholder thực: y=1485-1575 → fill từ y=1480, cao 100px
        "subtitle": {"x": 150, "fill_y": 1480, "fill_h": 100,
                     "draw_y": 1495, "w": 780,
                     "bg": (0, 2, 6), "size": 34, "lines": 2},
    },
    "tin-nhanh": {
        "article": {"x": 610, "y": 390, "w": 360, "h": 430},
        # Headline placeholder thực: y=1385-1485 → fill từ y=1260 (gộp cả badge text)
        "headline": {"x": 90, "fill_y": 1260, "fill_h": 230,
                     "draw_y": 1340, "w": 900,
                     "bg": (1, 3, 12), "size": 72, "lines": 2},
        # Subtitle: bên dưới headline, ước tính y=1495-1560
        "subtitle": {"x": 150, "fill_y": 1490, "fill_h": 200,
                     "draw_y": 1500, "w": 780,
                     "bg": (3, 3, 7), "size": 34, "lines": 2},
    },
    "phan-tich": {
        "article": {"x": 610, "y": 390, "w": 360, "h": 430},
        "headline": {"x": 90, "fill_y": 1260, "fill_h": 230,
                     "draw_y": 1340, "w": 900,
                     "bg": (1, 3, 12), "size": 72, "lines": 2},
        "subtitle": {"x": 150, "fill_y": 1490, "fill_h": 200,
                     "draw_y": 1500, "w": 780,
                     "bg": (3, 3, 7), "size": 34, "lines": 2},
    },
    "nhan-dinh-tran-dau": {
        "article": {"x": 610, "y": 320, "w": 360, "h": 380},
        "headline": {"x": 90, "fill_y": 1260, "fill_h": 230,
                     "draw_y": 1340, "w": 900,
                     "bg": (12, 4, 7), "size": 68, "lines": 2},
        "subtitle": {"x": 150, "fill_y": 1490, "fill_h": 200,
                     "draw_y": 1500, "w": 780,
                     "bg": (8, 5, 8), "size": 32, "lines": 2},
    },
    "ket-qua-tran-dau": {
        "article": {"x": 610, "y": 320, "w": 360, "h": 380},
        "headline": {"x": 90, "fill_y": 1260, "fill_h": 230,
                     "draw_y": 1340, "w": 900,
                     "bg": (12, 13, 16), "size": 68, "lines": 2},
        "subtitle": {"x": 150, "fill_y": 1490, "fill_h": 200,
                     "draw_y": 1500, "w": 780,
                     "bg": (0, 0, 4), "size": 32, "lines": 2},
    },
    "dang-ky-kenh": None,  # end card — không thay đổi gì
}

# Map tag → template
_TAG_TEMPLATE = {
    "CHUYỂN NHƯỢNG": "chuyen-nhuong",
    "TRẬN ĐẤU":      "nhan-dinh-tran-dau",
    "CHIẾN THUẬT":   "phan-tich",
}

# ───────────────────────────────────────────────────────────
# Font
# ───────────────────────────────────────────────────────────
_FONT_BOLD = next(
    str(p) for p in [
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ] if p.exists()
)
_FONT_REG = next(
    str(p) for p in [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ] if p.exists()
)

# ───────────────────────────────────────────────────────────
# Template protection
# ───────────────────────────────────────────────────────────
_CHECKSUMS: dict[str, str] = {}

def _load_template(name: str) -> Image.Image:
    """
    Mở template → resize về 1080×1920 → trả về bản COPY.
    KHÔNG BAO GIỜ ghi vào file gốc.
    """
    path = TEMPLATE_DIR / f"{name}.png"
    if not path.exists():
        raise FileNotFoundError(f"Template không có: {path}")
    cs = hashlib.md5(path.read_bytes()).hexdigest()[:8]
    if name in _CHECKSUMS and _CHECKSUMS[name] != cs:
        raise RuntimeError(f"Template {name} bị thay đổi! Restore lại file gốc.")
    _CHECKSUMS.setdefault(name, cs)
    img = Image.open(path).convert("RGBA")
    return img.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)

# ───────────────────────────────────────────────────────────
# Text helpers
# ───────────────────────────────────────────────────────────

def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0], b[3] - b[1]


def _wrap_text(draw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if _measure(draw, cand, font)[0] <= max_w:
            cur = cand
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


def _draw_text_in_zone(canvas: Image.Image, text: str, zone: dict,
                        font_path: str, color=(255, 255, 255, 255)) -> None:
    """
    Fill vùng placeholder cũ + vẽ text mới vào đúng vùng panel template.
    zone cần có: x, fill_y, fill_h, draw_y, w, bg, size, lines
    """
    x         = zone["x"]
    w         = zone["w"]
    fill_y    = zone["fill_y"]
    fill_h    = zone["fill_h"]
    draw_y    = zone["draw_y"]
    bg        = zone["bg"] + (255,)   # fully opaque
    start_size = zone["size"]
    max_lines  = zone["lines"]

    draw = ImageDraw.Draw(canvas)

    # 1. Fill vùng placeholder bằng màu nền thật của template (che text cũ)
    draw.rectangle([0, fill_y, CANVAS_W, fill_y + fill_h], fill=bg)

    # 2. Tìm font size vừa vặn với max_lines
    size = start_size
    chosen_lines, chosen_font = [], None
    while size >= 28:
        font  = ImageFont.truetype(font_path, size)
        lines = _wrap_text(draw, text, font, w)
        if len(lines) <= max_lines:
            chosen_lines = lines
            chosen_font  = font
            break
        size -= 4
    if not chosen_lines:
        font   = ImageFont.truetype(font_path, 28)
        lines  = _wrap_text(draw, text, font, w)
        chosen_lines = lines[:max_lines]
        chosen_font  = font

    # 3. Vẽ text căn giữa ngang, bắt đầu tại draw_y
    line_h = int(chosen_font.size * 1.12)
    cur_y  = draw_y
    for line in chosen_lines:
        lw, _ = _measure(draw, line, chosen_font)
        lx    = x + (w - lw) // 2   # căn giữa trong width
        draw.text((lx + 1, cur_y + 1), line, font=chosen_font, fill=(0, 0, 0, 160))
        draw.text((lx, cur_y),         line, font=chosen_font, fill=color)
        cur_y += line_h


# ───────────────────────────────────────────────────────────
# Article image compositing
# ───────────────────────────────────────────────────────────

def _paste_article_image(canvas: Image.Image, image_path: Path, zone: dict) -> None:
    """
    Chèn ảnh bài viết vào đúng vùng quy định.
    Crop theo tỉ lệ zone, bo góc 22px, overlay tối 25%, viền #B80F16 2px.
    Không đặt ảnh đè lên logo, badge, panel tiêu đề.
    """
    x, y, w, h = zone["x"], zone["y"], zone["w"], zone["h"]
    try:
        art = Image.open(image_path).convert("RGBA")
    except Exception:
        return

    # Crop theo đúng tỉ lệ zone (giống code mẫu trong document)
    target_ratio = w / h
    img_ratio    = art.width / art.height
    if img_ratio > target_ratio:
        new_w = int(art.height * target_ratio)
        left  = (art.width - new_w) // 2
        art   = art.crop((left, 0, left + new_w, art.height))
    else:
        new_h = int(art.width / target_ratio)
        top   = (art.height - new_h) // 2
        art   = art.crop((0, top, art.width, top + new_h))

    art = art.resize((w, h), Image.Resampling.LANCZOS)

    # Bo góc 22px
    from PIL import ImageDraw as _ID
    mask = Image.new("L", (w, h), 0)
    _ID.Draw(mask).rounded_rectangle((0, 0, w, h), radius=22, fill=255)

    # Overlay tối 25% (dark_overlay_opacity = 25%)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 64))   # 64/255 ≈ 25%
    art = Image.alpha_composite(art, overlay)

    # Dán vào canvas
    canvas.paste(art, (x, y), mask)

    # Viền đỏ mảnh 2px (#B80F16)
    ImageDraw.Draw(canvas).rounded_rectangle(
        (x, y, x + w, y + h),
        radius=22,
        outline=(184, 15, 22, 230),
        width=2,
    )


# ───────────────────────────────────────────────────────────
# Template selection
# ───────────────────────────────────────────────────────────

def _select_template(tag: str) -> str:
    import re
    clean = re.sub(r"[^\w\sÀ-ɏḀ-ỿ]", "", tag).strip().upper()
    for key, tmpl in _TAG_TEMPLATE.items():
        if key in clean:
            return tmpl
    return "tin-nhanh"


# ───────────────────────────────────────────────────────────
# Public API — giữ interface cũ cho main.py
# ───────────────────────────────────────────────────────────

def render_scene(scene: dict, image_path: Path | None, bg_output: Path,
                 overlay_output: Path, scene_index: int = 0,
                 total_scenes: int = 4) -> dict:
    """
    Composite 1 scene đúng quy trình:
      1. Mở template (bản copy, resize 1080×1920)
      2. Paste ảnh bài viết vào vùng quy định
      3. Fill + draw text tại headline zone
      4. Fill + draw text tại subtitle zone
      5. Save ra output — KHÔNG ghi vào assets/templates/
    """
    tag       = scene.get("tag", "⚡ BREAKING")
    tmpl_name = _select_template(tag)
    cfg       = TEMPLATE_CONFIG.get(tmpl_name)

    if cfg is None:
        # end card — giữ nguyên template, không thêm gì
        canvas = _load_template(tmpl_name)
        overlay_output.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(overlay_output, "PNG")
        bg_output.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(bg_output, "JPEG", quality=85)
        return {"template": tmpl_name, "aspect": 1.0,
                "image_size": (0, 0), "bg_size": (CANVAS_W, CANVAS_H)}

    # 1. Mở template — bản copy resized
    canvas = _load_template(tmpl_name)

    # 2. Paste ảnh bài viết vào đúng vùng (không đè logo/panel)
    if image_path and image_path.exists():
        _paste_article_image(canvas, image_path, cfg["article"])

    # 3. Fill + draw headline trong panel gốc của template
    _draw_text_in_zone(canvas, scene["headline"],
                       cfg["headline"], _FONT_BOLD)

    # 4. Fill + draw subtitle trong panel gốc của template
    _draw_text_in_zone(canvas, scene["subtext"],
                       cfg["subtitle"], _FONT_REG,
                       color=(200, 200, 205, 220))

    # 5. Lưu ra output — TUYỆT ĐỐI không ghi vào assets/templates/
    overlay_output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(overlay_output, "PNG", optimize=True)
    bg_output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(bg_output, "JPEG", quality=85)

    img_orig = Image.open(image_path) if image_path and image_path.exists() else None
    aspect   = (img_orig.size[0] / img_orig.size[1]) if img_orig else 1.0
    return {
        "template": tmpl_name,
        "aspect":   aspect,
        "image_size": img_orig.size if img_orig else (0, 0),
        "bg_size":  (CANVAS_W, CANVAS_H),
    }


def render_all_scenes(scenes: list[dict], images_dir: Path, frames_dir: Path) -> list[dict]:
    results = []
    for idx, scene in enumerate(scenes):
        scene_id = scene.get("id", f"{idx+1:02d}")
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

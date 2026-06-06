"""
scene_renderer.py — Render engine cho video frame THỂ THAO 247.

CÔNG THỨC DUY NHẤT:
    canvas = Image.open(background.png)        ← template gốc, đầy đủ thiết kế
    paste(article_image, image_slot)           ← ảnh bài viết lớn, phủ lên vùng ảnh chính
    fill_text_zone(zone, zone.fill_color)      ← xóa placeholder text bằng fill màu panel
    draw_text(category, badge, headline, sub)  ← đặt text mới
    save()

KHÔNG dùng foreground_overlay.png:
    - foreground_overlay có inner box viền đỏ (cái frame sai của thumbnail nhỏ)
    - foreground_overlay che panel đẹp của background.png
    → Loại bỏ hoàn toàn, chỉ dùng background.png

Fill text zone:
    - KHÔNG phải tự dựng panel/badge/layout mới
    - Chỉ fill đè lên vùng text placeholder nhỏ với màu background tương ứng
    - Các design element (badge shape, borders, lines) vẫn từ background.png
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CANVAS_W, CANVAS_H = 1080, 1920
TEMPLATE_DIR = Path(__file__).parent.parent / "assets" / "templates"
FONT_DIR     = Path(__file__).parent.parent / "assets" / "fonts"

_INTER = FONT_DIR / "Inter-Variable.ttf"

_FALLBACK_BOLD = next(
    (p for p in [
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ] if p.exists()),
    None,
)
_FALLBACK_REG = next(
    (p for p in [
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ] if p.exists()),
    None,
)


# ─── Font ─────────────────────────────────────────────────────────────────────

def _get_font(size: int, bold: bool) -> ImageFont.FreeTypeFont:
    src = _INTER if _INTER.exists() else (_FALLBACK_BOLD if bold else _FALLBACK_REG)
    if src is None:
        return ImageFont.load_default()
    try:
        font = ImageFont.truetype(str(src), size)
        if _INTER.exists():
            try:
                font.set_variation_by_name("Bold" if bold else "Regular")
            except Exception:
                pass
        return font
    except Exception:
        return ImageFont.load_default()


# ─── Text helpers ─────────────────────────────────────────────────────────────

def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0], b[3] - b[1]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
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
    return lines or [text]


def _draw_text_zone(canvas: Image.Image, text: str, zone: dict) -> None:
    """
    Xóa placeholder text bằng fill, rồi draw text mới.
    fill_color từ text_config.json — màu background panel tương ứng.
    Đây KHÔNG phải tự dựng panel mới — chỉ đè màu nhỏ lên vùng text.
    """
    if not text:
        return

    x, y, w, h = zone["x"], zone["y"], zone["w"], zone["h"]
    draw = ImageDraw.Draw(canvas)

    # Fill để xóa placeholder text (màu khớp background panel)
    raw_fill = zone.get("fill_color")
    if raw_fill:
        fill_rgba = tuple(raw_fill[:4]) if len(raw_fill) >= 4 else tuple(raw_fill[:3]) + (255,)
        draw.rectangle([x, y, x + w, y + h], fill=fill_rgba)

    uppercase = zone.get("uppercase", False)
    display   = text.upper() if uppercase else text
    bold      = zone.get("bold", True)
    max_sz    = zone.get("font_size_max", 48)
    min_sz    = zone.get("font_size_min", 20)
    max_lines = zone.get("max_lines", 2)
    align     = zone.get("align", "left")
    raw_color = zone.get("color", [255, 255, 255, 255])
    color     = tuple(raw_color[:4]) if len(raw_color) == 4 else tuple(raw_color[:3]) + (255,)

    # Auto-shrink font để vừa max_lines
    chosen_lines: list[str] = []
    chosen_font: ImageFont.FreeTypeFont | None = None
    for sz in range(max_sz, min_sz - 1, -2):
        font  = _get_font(sz, bold)
        lines = _wrap(draw, display, font, w)
        if len(lines) <= max_lines:
            chosen_lines = lines
            chosen_font  = font
            break
    if not chosen_lines:
        chosen_font  = _get_font(min_sz, bold)
        chosen_lines = _wrap(draw, display, chosen_font, w)[:max_lines]

    # Vertical center trong zone
    line_h  = int(chosen_font.size * 1.18)
    total_h = line_h * len(chosen_lines)
    cur_y   = y + max(0, (h - total_h) // 2)

    for line in chosen_lines:
        lw, _ = _measure(draw, line, chosen_font)
        if align == "center":
            lx = x + (w - lw) // 2
        elif align == "right":
            lx = x + w - lw
        else:
            lx = x
        # Shadow nhẹ
        draw.text((lx + 1, cur_y + 1), line, font=chosen_font, fill=(0, 0, 0, 160))
        draw.text((lx, cur_y),         line, font=chosen_font, fill=color)
        cur_y += line_h


# ─── Article image compositing ────────────────────────────────────────────────

def _paste_article_image(canvas: Image.Image, image_path: Path, slot: dict) -> None:
    """
    Paste ảnh bài viết lớn vào vùng ảnh chính.
    Cover crop (không méo), bo góc nhẹ, overlay tối nhẹ.
    Ảnh phải đủ lớn — là visual chính của video.
    """
    x, y, w, h = slot["x"], slot["y"], slot["w"], slot["h"]
    radius     = slot.get("border_radius", slot.get("radius", 0))
    ov_opacity = slot.get("overlay_opacity", 0)

    try:
        art = Image.open(image_path).convert("RGBA")
    except Exception as e:
        print(f"  ⚠ Không mở được ảnh: {e}")
        return

    # Cover crop — giữ center, không méo
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

    # Bo góc nhẹ
    mask = Image.new("L", (w, h), 0)
    if radius > 0:
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    else:
        mask.paste(255, [0, 0, w, h])

    # Dark overlay nhẹ nếu ảnh quá sáng
    if ov_opacity > 0:
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, ov_opacity))
        art = Image.alpha_composite(art, overlay)

    canvas.paste(art, (x, y), mask)


# ─── Template loader ──────────────────────────────────────────────────────────

def _load_template(name: str) -> tuple[Image.Image, dict | None]:
    """
    Load background.png từ assets/templates/{name}/.
    KHÔNG dùng foreground_overlay — nó có inner box sai và che panel đẹp.
    Returns: (background_canvas, config)
    """
    folder = TEMPLATE_DIR / name
    if not folder.exists():
        raise FileNotFoundError(
            f"Template folder không tìm thấy: {folder}\n"
            f"Đặt template vào: assets/templates/{name}/"
        )

    bg_path = folder / "background.png"
    if not bg_path.exists():
        raise FileNotFoundError(f"Thiếu background.png trong {folder}")

    bg = Image.open(bg_path).convert("RGBA")
    if bg.size != (CANVAS_W, CANVAS_H):
        bg = bg.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)

    cfg_path = folder / "text_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else None

    return bg, cfg


# ─── Tag → template mapping ───────────────────────────────────────────────────

_TAG_MAP: dict[str, str] = {
    "CHUYỂN NHƯỢNG": "chuyen-nhuong",
    "CHUYÊN NHƯỢNG": "chuyen-nhuong",
    "KẾT QUẢ":       "ket-qua-tran-dau",
    "NHẬN ĐỊNH":     "nhan-dinh-tran-dau",
    "TRẬN ĐẤU":      "nhan-dinh-tran-dau",
    "PHÂN TÍCH":     "phan-tich",
    "CHIẾN THUẬT":   "phan-tich",
    "TIN NHANH":     "tin-nhanh",
    "BREAKING":      "tin-nhanh",
}

_DEFAULT_BADGE: dict[str, str] = {
    "chuyen-nhuong":      "ĐÀM PHÁN",
    "tin-nhanh":          "CẬP NHẬT",
    "phan-tich":          "PHÂN TÍCH",
    "nhan-dinh-tran-dau": "TRƯỚC TRẬN",
    "ket-qua-tran-dau":   "KẾT THÚC",
    "dang-ky-kenh":       "",
}

_DEFAULT_CATEGORY: dict[str, str] = {
    "chuyen-nhuong":      "CHUYỂN NHƯỢNG",
    "tin-nhanh":          "TIN NHANH",
    "phan-tich":          "PHÂN TÍCH",
    "nhan-dinh-tran-dau": "NHẬN ĐỊNH TRẬN ĐẤU",
    "ket-qua-tran-dau":   "KẾT QUẢ TRẬN ĐẤU",
    "dang-ky-kenh":       "",
}


def _select_template(tag: str) -> str:
    clean = re.sub(r"[^\w\sÀ-ɏḀ-ỿ]", "", tag).strip().upper()
    for key, tmpl in _TAG_MAP.items():
        if key in clean:
            return tmpl
    return "tin-nhanh"


# ─── Public API ───────────────────────────────────────────────────────────────

def render_scene(
    scene: dict,
    image_path: Path | None,
    bg_output: Path,
    overlay_output: Path,
    scene_index: int = 0,
    total_scenes: int = 4,
) -> dict:
    """
    Render 1 scene:
        1. Open background.png (đầy đủ thiết kế: logo, panel, badge, borders)
        2. Paste ảnh bài viết lớn vào vùng ảnh chính
        3. Fill text zones để xóa placeholder text
        4. Draw text mới (category, badge, headline, subtitle)
        5. Save
    """
    tag       = scene.get("tag", "TIN NHANH")
    tmpl_name = _select_template(tag)

    if scene_index == total_scenes - 1:
        tmpl_name = "dang-ky-kenh"

    canvas, cfg = _load_template(tmpl_name)

    if cfg:
        # Bước 2: Paste ảnh bài viết lớn
        slot = cfg.get("article_image")
        if slot and image_path and image_path.exists():
            _paste_article_image(canvas, image_path, slot)

        # Bước 3+4: Fill text zones + draw text mới
        texts = {
            "category": scene.get("category") or _DEFAULT_CATEGORY.get(tmpl_name, ""),
            "badge":    scene.get("badge")    or _DEFAULT_BADGE.get(tmpl_name, ""),
            "headline": scene.get("headline", ""),
            "subtitle": scene.get("subtext",  ""),
        }
        for zone in cfg.get("text_zones", []):
            key = zone.get("key", "")
            val = texts.get(key, "")
            if val:
                _draw_text_zone(canvas, val, zone)

    img_orig = None
    if image_path and image_path.exists():
        try:
            img_orig = Image.open(image_path)
        except Exception:
            pass

    overlay_output.parent.mkdir(parents=True, exist_ok=True)
    bg_output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(overlay_output, "PNG", optimize=True)
    canvas.convert("RGB").save(bg_output, "JPEG", quality=85)

    return {
        "template":   tmpl_name,
        "aspect":     (img_orig.width / img_orig.height) if img_orig else 1.0,
        "image_size": img_orig.size if img_orig else (0, 0),
        "bg_size":    (CANVAS_W, CANVAS_H),
    }


def render_all_scenes(
    scenes: list[dict], images_dir: Path, frames_dir: Path
) -> list[dict]:
    results = []
    for idx, scene in enumerate(scenes):
        scene_id   = scene.get("id", f"{idx+1:02d}")
        image_path = None
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            cand = images_dir / f"scene_{scene_id}{ext}"
            if cand.exists():
                image_path = cand
                break

        bg_out = frames_dir / f"bg_{scene_id}.jpg"
        ov_out = frames_dir / f"overlay_{scene_id}.png"
        meta   = render_scene(
            scene, image_path, bg_out, ov_out,
            scene_index=idx, total_scenes=len(scenes),
        )
        meta["scene_id"] = scene_id
        results.append(meta)
        print(
            f"  ✓ scene {scene_id} → {CANVAS_W}×{CANVAS_H}"
            f"  template={meta['template']}  aspect={meta['aspect']:.2f}"
        )
    return results

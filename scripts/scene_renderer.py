"""
scene_renderer.py  —  Template-based render engine THỂ THAO 247.

Dùng tin-nhanh-clean.png làm base, overlay text + image.
End card (dang-ky-kenh) dùng background.png riêng.

Layout tin-nhanh (1080×1920):
  ┌──────────────────────────┐  y=0
  │  [LOGO]   [TIN NHANH]   │  Header từ template
  ├──────────────────────────┤  y=231
  │   Article image (frame)  │  y=231..1225  w=972 h=994  r=35
  ├──────────────────────────┤  y=1270
  │       [CẬP NHẬT]        │  Badge  y=1270..1376
  │  Headline text bold      │  y=1406  fmax=66
  │  ─────────────────       │  accent line  y≈1612
  │  Subtitle text           │  y=1650  fmax=32
  └──────────────────────────┘  y=1920
"""

from __future__ import annotations
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

CANVAS_W, CANVAS_H = 1080, 1920
TEMPLATE_DIR = Path(__file__).parent.parent / "assets" / "templates"
FONT_DIR     = Path(__file__).parent.parent / "assets" / "fonts"

_INTER = FONT_DIR / "Inter-Variable.ttf"
_FALLBACK_BOLD = next(
    (p for p in [Path("C:/Windows/Fonts/segoeuib.ttf"),
                 Path("C:/Windows/Fonts/arialbd.ttf")] if p.exists()),
    None,
)
_FALLBACK_REG = next(
    (p for p in [Path("C:/Windows/Fonts/segoeui.ttf"),
                 Path("C:/Windows/Fonts/arial.ttf")] if p.exists()),
    None,
)

# ── Palette ────────────────────────────────────────────────────────────────────
_BG    = (6,  10, 18)
_WHITE = (255, 255, 255)
_GRAY  = (216, 216, 216)

# ── Shared layout constants (1080×1920, tin-nhanh base) ──────────────────────
_RED  = (196, 14, 42)
_GOLD = (208, 162, 38)

# ── Tin-nhanh / Chuyển-nhượng coordinates ────────────────────────────────────
_IMG_SLOT  = dict(x=44,  y=231,  w=972, h=994, radius=35)
_CAT_BOX   = dict(x=735, y=84,   w=285, h=64,  size=34)
_BADGE_BOX = dict(x=324, y=1270, w=424, h=106, size=34)
_HL_AREA   = dict(x=96,  y=1406, w=888, h=165, fmax=66, fmin=42,  max_lines=2, spacing=1.08)
_SUB_AREA  = dict(x=96,  y=1650, w=888, h=110, fmax=32, fmin=26,  max_lines=2, spacing=1.18)

# Alias cho backward compat (composer.py dùng _TN_IMG)
_TN_IMG = _IMG_SLOT

# ── Ket-qua-tran-dau coordinates (approved 2026-06-07) ───────────────────────
_KQ_IMG_SLOT  = dict(x=52,  y=160,  w=976, h=890, radius=22)  # panel_y=1050
_KQ_PANEL_Y   = 1050
_KQ_BADGE_BOX = dict(x=336, y=1080, w=408, h=74,  size=34)
_KQ_TEAMS_Y   = 1200
_KQ_TEAMS_H   = 55
_KQ_SCORE_AREA = dict(x=96, y=1270, w=888, h=145, fmax=96, fmin=72)
_KQ_HL_AREA   = dict(x=96,  y=1455, w=888, h=100, fmax=44, fmin=32,  max_lines=2, spacing=1.08)
_KQ_SUB_AREA  = dict(x=96,  y=1585, w=888, h=100, fmax=30, fmin=24,  max_lines=2, spacing=1.18)
_KQ_ACCENT_Y  = 1433  # between score_area bottom and headline_area top

# ── Template registry ─────────────────────────────────────────────────────────
_TEMPLATES: dict[str, dict] = {
    "tin-nhanh": {
        "clean":    TEMPLATE_DIR / "tin-nhanh-clean.png",
        "category": "TIN NHANH",
        "badge":    "CẬP NHẬT",
    },
    "chuyen-nhuong": {
        "clean":    TEMPLATE_DIR / "chuyen-nhuong-clean.png",
        "category": "CHUYỂN NHƯỢNG",
        "badge":    "ĐÀM PHÁN",
    },
    "ket-qua-tran-dau": {
        "clean":    TEMPLATE_DIR / "ket-qua-tran-dau-clean.png",
        "category": "KẾT QUẢ",
        "badge":    "KẾT THÚC",
    },
}

# ── Tag → template routing ────────────────────────────────────────────────────
_TAG_MAP: dict[str, str] = {
    "KẾT QUẢ":       "ket-qua-tran-dau",
    "KẾT THÚC":      "ket-qua-tran-dau",
    "HẾT GIỜ":       "ket-qua-tran-dau",
    "SAU TRẬN":      "ket-qua-tran-dau",
    "CHUNG CUỘC":    "ket-qua-tran-dau",
    "CHUYỂN NHƯỢNG": "chuyen-nhuong",
    "CHUYÊN NHƯỢNG": "chuyen-nhuong",
    "KÝ HỢP ĐỒNG":  "chuyen-nhuong",
    "ĐÀM PHÁN":     "chuyen-nhuong",
    "GIA NHẬP":      "chuyen-nhuong",
    "RỜI CLB":       "chuyen-nhuong",
    "THƯƠNG VỤ":    "chuyen-nhuong",
    "BẾN ĐỖ":       "chuyen-nhuong",
    "TIN NHANH":    "tin-nhanh",
    "BREAKING":     "tin-nhanh",
}

_KEYWORD_MAP: list[tuple[list[str], str]] = [
    (["tỷ số", "kết quả", " thắng ", " thua ", " hòa ", "bàn thắng",
      "3 điểm", "bị loại", "đi tiếp", "ngược dòng", "chung cuộc"], "ket-qua-tran-dau"),
    (["chuyển nhượng", "ký hợp đồng", "đàm phán", "gia nhập",
      "rời clb", "thương vụ", "phí chuyển nhượng", "bến đỗ",
      "theo đuổi", "sắp ký"], "chuyen-nhuong"),
]


def _select_template(tag: str, headline: str = "", subtext: str = "") -> str:
    clean_tag = re.sub(r"[^\w\sÀ-ɏḀ-ỿ]", "", tag).strip().upper()
    for key, tmpl in _TAG_MAP.items():
        if key in clean_tag:
            return tmpl
    # Keyword fallback trong headline/subtext
    combined = (headline + " " + subtext).lower()
    for keywords, tmpl in _KEYWORD_MAP:
        if any(kw in combined for kw in keywords):
            return tmpl
    return "tin-nhanh"


# ── Font helpers ───────────────────────────────────────────────────────────────

def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    src = _INTER if _INTER.exists() else (_FALLBACK_BOLD if bold else _FALLBACK_REG)
    if src is None:
        return ImageFont.load_default()
    try:
        f = ImageFont.truetype(str(src), size)
        if _INTER.exists():
            try:
                f.set_variation_by_name("Bold" if bold else "Regular")
            except Exception:
                pass
        return f
    except Exception:
        return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str,
          f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if f.getlength(cand) <= max_w:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text]


def _cover_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    iw, ih = img.size
    scale  = max(w / iw, h / ih)
    nw, nh = max(int(iw * scale), w), max(int(ih * scale), h)
    img    = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


# ── Text drawing helpers ───────────────────────────────────────────────────────

def _draw_center_text(draw: ImageDraw.ImageDraw,
                      text: str, bx: int, by: int, bw: int, bh: int,
                      size: int, color: tuple, bold: bool = True) -> None:
    font = _font(size, bold)
    tw   = font.getlength(text)
    bb   = font.getbbox(text)
    th   = bb[3] - bb[1]
    tx   = int(bx + (bw - tw) / 2)
    ty   = int(by + (bh - th) / 2) - bb[1]
    draw.text((tx, ty), text, font=font, fill=color)


def _draw_block_text(draw: ImageDraw.ImageDraw,
                     text: str, x: int, y: int, w: int, h: int,
                     fmax: int, fmin: int, color: tuple,
                     bold: bool, max_lines: int, spacing: float) -> None:
    if not text:
        return
    for size in range(fmax, fmin - 1, -1):
        font  = _font(size, bold)
        lines = _wrap(draw, text, font, w)[:max_lines]
        lh    = int(size * spacing)
        total = lh * (len(lines) - 1) + size
        if total <= h:
            ty = y
            for line in lines:
                draw.text((x, ty), line, font=font, fill=color)
                ty += lh
            return
    font  = _font(fmin, bold)
    lines = _wrap(draw, text, font, w)[:max_lines]
    ty    = y
    for line in lines:
        draw.text((x, ty), line, font=font, fill=color)
        ty += int(fmin * spacing)


# ── Generic template renderer ─────────────────────────────────────────────────

def _render_tin_nhanh(scene: dict, image_path: Path | None,
                      overlay_out: Path, img_raw_out: Path) -> None:
    """Render content frame dùng template PNG.
    overlay_out  = template + text, image slot trong suốt (RGBA PNG)
    img_raw_out  = article image crop to slot size (RGB PNG)
    """
    tag      = scene.get("tag", "")
    headline = scene.get("headline", "")
    subtext  = scene.get("subtext",  "")
    tmpl_key = _select_template(tag, headline, subtext)

    # Route ket-qua to dedicated renderer
    if tmpl_key == "ket-qua-tran-dau":
        _render_ket_qua(scene, image_path, overlay_out, img_raw_out)
        return

    tmpl     = _TEMPLATES.get(tmpl_key, _TEMPLATES["tin-nhanh"])
    clean_path = tmpl["clean"]
    if not clean_path.exists():
        raise FileNotFoundError(f"Template không tìm thấy: {clean_path}")

    category = (scene.get("category") or tmpl["category"]).upper()
    badge    = (scene.get("badge")    or tmpl["badge"]).upper()

    canvas = Image.open(clean_path).convert("RGBA")
    canvas = canvas.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)

    # Clear image slot → trong suốt (rounded corners giữ nguyên từ template)
    iw, ih = _IMG_SLOT["w"], _IMG_SLOT["h"]
    ix, iy = _IMG_SLOT["x"], _IMG_SLOT["y"]
    slot_mask = Image.new("L", (iw, ih), 0)
    ImageDraw.Draw(slot_mask).rounded_rectangle(
        [0, 0, iw - 1, ih - 1], radius=_IMG_SLOT["radius"], fill=255
    )
    canvas.paste(Image.new("RGBA", (iw, ih), (0, 0, 0, 0)), (ix, iy), slot_mask)

    draw = ImageDraw.Draw(canvas)
    _draw_center_text(draw, category,
                      _CAT_BOX["x"], _CAT_BOX["y"],
                      _CAT_BOX["w"], _CAT_BOX["h"],
                      _CAT_BOX["size"], _WHITE)
    _draw_center_text(draw, badge,
                      _BADGE_BOX["x"], _BADGE_BOX["y"],
                      _BADGE_BOX["w"], _BADGE_BOX["h"],
                      _BADGE_BOX["size"], _WHITE)
    _draw_block_text(draw, headline,
                     _HL_AREA["x"], _HL_AREA["y"], _HL_AREA["w"], _HL_AREA["h"],
                     _HL_AREA["fmax"], _HL_AREA["fmin"], _WHITE, True,
                     _HL_AREA["max_lines"], _HL_AREA["spacing"])
    _draw_block_text(draw, subtext,
                     _SUB_AREA["x"], _SUB_AREA["y"], _SUB_AREA["w"], _SUB_AREA["h"],
                     _SUB_AREA["fmax"], _SUB_AREA["fmin"], _GRAY, False,
                     _SUB_AREA["max_lines"], _SUB_AREA["spacing"])

    overlay_out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(overlay_out), "PNG")

    # Lưu article image raw (cho composer zoom riêng)
    if image_path and image_path.exists():
        art = _cover_crop(Image.open(image_path).convert("RGB"), iw, ih)
        img_raw_out.parent.mkdir(parents=True, exist_ok=True)
        art.save(str(img_raw_out), "PNG")


# ── Ket-qua helpers ───────────────────────────────────────────────────────────

def _draw_centered_block(draw: ImageDraw.ImageDraw,
                          text: str, x: int, y: int, w: int, h: int,
                          fmax: int, fmin: int, color: tuple,
                          bold: bool, max_lines: int, spacing: float) -> None:
    """Auto-shrink block, center each line horizontally."""
    if not text:
        return
    for size in range(fmax, fmin - 1, -1):
        font  = _font(size, bold)
        lines = _wrap(draw, text, font, w)[:max_lines]
        lh    = int(size * spacing)
        total = lh * (len(lines) - 1) + size
        if total <= h:
            ty = y
            for line in lines:
                tw = font.getlength(line)
                tx = x + int((w - tw) / 2)
                draw.text((tx, ty), line, font=font, fill=color)
                ty += lh
            return
    font  = _font(fmin, bold)
    lines = _wrap(draw, text, font, w)[:max_lines]
    ty    = y
    for line in lines:
        tw = font.getlength(line)
        tx = x + int((w - tw) / 2)
        draw.text((tx, ty), line, font=font, fill=color)
        ty += int(fmin * spacing)


# ── Ket-qua template renderer ─────────────────────────────────────────────────

def _render_ket_qua(scene: dict, image_path: Path | None,
                    overlay_out: Path, img_raw_out: Path) -> None:
    """Render ket-qua-tran-dau (layout approved 2026-06-07).

    image_slot : x=52,  y=160,  w=976, h=890, radius=22  → panel_y=1050
    panel      : y=1050-1920, dark (4,6,18) + premium decorations
    badge_pill : x=336, y=1080, w=408, h=74   (red, centered)
    teams_area : x=96,  y=1200, w=888, h=55
    score_area : x=96,  y=1270, w=888, h=145, fmax=96
    accent_line: y=1433
    headline   : x=96,  y=1455, w=888, h=100, fmax=44
    subtitle   : x=96,  y=1585, w=888, h=100, fmax=30
    """
    import json as _json

    base_path = TEMPLATE_DIR / "ket-qua-tran-dau-clean.png"
    if not base_path.exists():
        base_path = TEMPLATE_DIR / "tin-nhanh-clean.png"
    if not base_path.exists():
        raise FileNotFoundError(f"Template: {base_path}")

    category  = (scene.get("category")  or "KẾT QUẢ").upper()
    badge     = (scene.get("badge")     or "KẾT THÚC").upper()
    home_team = scene.get("home_team", "")
    away_team = scene.get("away_team", "")
    score     = scene.get("score", "")
    headline  = scene.get("headline", "")
    subtext   = scene.get("subtext",  "")

    _KQ_IX, _KQ_IY = _KQ_IMG_SLOT["x"], _KQ_IMG_SLOT["y"]   # 52, 160
    _KQ_IW, _KQ_IH = _KQ_IMG_SLOT["w"], _KQ_IMG_SLOT["h"]   # 976, 890
    _KQ_IR          = _KQ_IMG_SLOT["radius"]                  # 22
    _PANEL_Y        = _KQ_PANEL_Y                             # 1050

    _BDX, _BDY = _KQ_BADGE_BOX["x"], _KQ_BADGE_BOX["y"]     # 336, 1080
    _BDW, _BDH = _KQ_BADGE_BOX["w"], _KQ_BADGE_BOX["h"]     # 408, 74

    canvas = Image.open(base_path).convert("RGBA")
    canvas = canvas.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
    draw   = ImageDraw.Draw(canvas)

    # 1. Panel dark phủ từ y=1050 xuống cuối
    draw.rectangle([0, _PANEL_Y, CANVAS_W, CANVAS_H], fill=(4, 6, 18, 255))

    # 2. Red seam (4px viền đỏ đỉnh panel)
    draw.rectangle([0, _PANEL_Y, CANVAS_W, _PANEL_Y + 4], fill=(*_RED, 255))

    # 3. Badge pill đỏ centered
    draw.rounded_rectangle(
        [_BDX, _BDY, _BDX + _BDW, _BDY + _BDH],
        radius=10, fill=(*_RED, 255),
    )

    # 4. Red-gold accent line
    draw.rectangle([96, _KQ_ACCENT_Y, 96 + 168, _KQ_ACCENT_Y + 3], fill=(*_RED, 255))
    draw.rectangle([96 + 174, _KQ_ACCENT_Y, 96 + 220, _KQ_ACCENT_Y + 3], fill=(*_GOLD, 255))

    # 5. Clear image slot → transparent
    slot_mask = Image.new("L", (_KQ_IW, _KQ_IH), 0)
    ImageDraw.Draw(slot_mask).rounded_rectangle(
        [0, 0, _KQ_IW - 1, _KQ_IH - 1], radius=_KQ_IR, fill=255
    )
    canvas.paste(Image.new("RGBA", (_KQ_IW, _KQ_IH), (0, 0, 0, 0)),
                 (_KQ_IX, _KQ_IY), slot_mask)

    # 6. Gradient tối ở đáy slot (blend ảnh → panel) — vẽ lên overlay transparent
    GRAD_H = 220
    grad = np.zeros((_KQ_IH, _KQ_IW, 4), dtype=np.uint8)
    for off in range(GRAD_H):
        row = _KQ_IH - GRAD_H + off
        a   = int(200 * off / GRAD_H)
        grad[row, :] = [4, 6, 18, a]
    canvas.paste(Image.fromarray(grad, "RGBA"), (_KQ_IX, _KQ_IY),
                 Image.fromarray(grad, "RGBA"))

    draw = ImageDraw.Draw(canvas)

    # 7. Category text (top-right box từ template header)
    _draw_center_text(draw, category,
                      _CAT_BOX["x"], _CAT_BOX["y"],
                      _CAT_BOX["w"], _CAT_BOX["h"],
                      _CAT_BOX["size"], _WHITE)

    # 8. Badge text
    _draw_center_text(draw, badge, _BDX, _BDY, _BDW, _BDH, 34, _WHITE)

    # 9. Teams (1 dòng, centered, gray)
    if home_team and away_team:
        teams_text = f"{home_team}  vs  {away_team}"
        tsz = _KQ_SCORE_AREA["fmax"] // 3  # start at 32
        for sz in range(32, 20, -1):
            if _font(sz, bold=False).getlength(teams_text) <= 888:
                tsz = sz; break
        _draw_center_text(draw, teams_text, 96, _KQ_TEAMS_Y, 888, _KQ_TEAMS_H,
                          tsz, _GRAY, bold=False)

    # 10. Score (trọng tâm, lớn nhất)
    if score:
        ssz = _KQ_SCORE_AREA["fmax"]
        for sz in range(_KQ_SCORE_AREA["fmax"], _KQ_SCORE_AREA["fmin"] - 1, -4):
            if _font(sz, bold=True).getlength(score) <= 888:
                ssz = sz; break
        _draw_center_text(draw, score,
                          _KQ_SCORE_AREA["x"], _KQ_SCORE_AREA["y"],
                          _KQ_SCORE_AREA["w"], _KQ_SCORE_AREA["h"],
                          ssz, _WHITE, bold=True)

    # 11. Headline (centered block)
    _draw_centered_block(draw, headline,
                          _KQ_HL_AREA["x"], _KQ_HL_AREA["y"],
                          _KQ_HL_AREA["w"], _KQ_HL_AREA["h"],
                          _KQ_HL_AREA["fmax"], _KQ_HL_AREA["fmin"],
                          _WHITE, True, _KQ_HL_AREA["max_lines"], _KQ_HL_AREA["spacing"])

    # 12. Subtitle (centered block)
    _draw_centered_block(draw, subtext,
                          _KQ_SUB_AREA["x"], _KQ_SUB_AREA["y"],
                          _KQ_SUB_AREA["w"], _KQ_SUB_AREA["h"],
                          _KQ_SUB_AREA["fmax"], _KQ_SUB_AREA["fmin"],
                          _GRAY, False, _KQ_SUB_AREA["max_lines"], _KQ_SUB_AREA["spacing"])

    overlay_out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(overlay_out), "PNG")

    # Sidecar JSON (composer cần slot coords cho ffmpeg zoompan)
    sidecar = overlay_out.parent / overlay_out.name.replace("overlay_", "img_slot_").replace(".png", ".json")
    sidecar.write_text(
        _json.dumps({"x": _KQ_IX, "y": _KQ_IY, "w": _KQ_IW, "h": _KQ_IH}),
        encoding="utf-8",
    )

    # Article image raw tại kích thước slot ket-qua
    if image_path and image_path.exists():
        art = _cover_crop(Image.open(image_path).convert("RGB"), _KQ_IW, _KQ_IH)
        img_raw_out.parent.mkdir(parents=True, exist_ok=True)
        art.save(str(img_raw_out), "PNG")


# ── End card ──────────────────────────────────────────────────────────────────

def render_end_card_frame(out: Path) -> None:
    p = TEMPLATE_DIR / "dang-ky-kenh" / "background.png"
    img = Image.open(p).convert("RGB") if p.exists() else Image.new("RGB", (CANVAS_W, CANVAS_H), _BG)
    img = img.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out), "PNG")


# ── Public API ────────────────────────────────────────────────────────────────

def render_scene(
    scene: dict,
    image_path: Path | None,
    bg_output: Path,
    overlay_output: Path,
    scene_index: int = 0,
    total_scenes: int = 4,
) -> dict:
    img_raw_out = overlay_output.parent / overlay_output.name.replace("overlay_", "img_raw_")
    _render_tin_nhanh(scene, image_path, overlay_output, img_raw_out)
    tmpl_key = _select_template(scene.get("tag", ""), scene.get("headline", ""), scene.get("subtext", ""))
    return {
        "template":   tmpl_key,
        "img_raw":    str(img_raw_out) if img_raw_out.exists() else None,
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

        ov_out      = frames_dir / f"overlay_{scene_id}.png"
        img_raw_out = frames_dir / f"img_raw_{scene_id}.png"
        _render_tin_nhanh(scene, image_path, ov_out, img_raw_out)
        meta = {
            "scene_id": scene_id,
            "template": "tin-nhanh",
            "has_img":  img_raw_out.exists(),
        }
        results.append(meta)
        print(f"  ✓ scene {scene_id}  template=tin-nhanh  img={'✓' if meta['has_img'] else '✗'}")
    return results

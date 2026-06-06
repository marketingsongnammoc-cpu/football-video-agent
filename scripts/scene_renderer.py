"""
scene_renderer.py  —  Premium render engine THỂ THAO 247.

Build frame hoàn toàn bằng PIL, không dùng template PNG (trừ end card).

Layout cố định (1080×1920):
  ┌──────────────────────────┐  y=0
  │  LOGO        [CATEGORY]  │  Header  h=106
  ├──────────────────────────┤  y=106
  │                          │
  │   Article image          │  full-width cover-crop  h=984
  │   (full-bleed, no frame) │
  │   ▓▓▓▓ gradient fade ▓▓▓ │
  ├╲────────────────────────╱┤  y=1090  chamfer 22px
  │     [  BADGE  ]          │  centered on seam
  │  Headline text           │  Panel  h=830
  │  ─────────────           │  accent line
  │  Subtitle text           │
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
_BG    = (6,  10, 18)     # deep navy — canvas background
_PANEL = (4,   7, 14)     # panel (slightly darker)
_RED   = (196, 14, 42)    # THỂ THAO 247 signature red
_GOLD  = (208, 162, 38)   # accent gold
_WHITE = (255, 255, 255)
_GRAY  = (172, 172, 186)  # subtitle text

# ── Layout constants ───────────────────────────────────────────────────────────
_HEADER_H  = 106    # header strip height
_IMG_TOP   = _HEADER_H + 4   # 110 — small gap below header
_IMG_BTM   = 1090            # image bottom = panel top
_IMG_H     = _IMG_BTM - _IMG_TOP   # 980 — article image height
_CHAMFER   = 22              # panel corner chamfer size (px)

_HEADLINE_X    = 52
_HEADLINE_W    = CANVAS_W - _HEADLINE_X * 2   # 976
_HEADLINE_Y    = _IMG_BTM + 68                # 1158
_HEADLINE_FMAX = 80
_HEADLINE_FMIN = 44
_HEADLINE_LMAX = 2

_SUB_FMAX = 33
_SUB_FMIN = 19
_SUB_LMAX = 2


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


def _measure(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont) -> tuple[int, int]:
    b = d.textbbox((0, 0), text, font=f)
    return b[2] - b[0], b[3] - b[1]


def _wrap(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if _measure(d, cand, f)[0] <= max_w:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text]


# ── Template / badge / category defaults ──────────────────────────────────────

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
    "chuyen-nhuong":      "CHUYỂN NHƯỢNG",
    "tin-nhanh":          "TIN NHANH",
    "phan-tich":          "PHÂN TÍCH",
    "nhan-dinh-tran-dau": "NHẬN ĐỊNH",
    "ket-qua-tran-dau":   "KẾT QUẢ",
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


# ── Logo (drawn programmatically) ─────────────────────────────────────────────

def _draw_logo_inline(canvas: Image.Image, draw: ImageDraw.ImageDraw) -> None:
    """Draw THỂ THAO 247 logo text at top-left of header."""
    x0, y0 = 22, 20

    # Football icon: small red circle with white inner circle
    icon_cx, icon_cy, icon_r = x0 + 18, y0 + 32, 18
    draw.ellipse(
        [icon_cx - icon_r, icon_cy - icon_r, icon_cx + icon_r, icon_cy + icon_r],
        fill=(*_RED, 255),
    )
    draw.ellipse(
        [icon_cx - 7, icon_cy - 7, icon_cx + 7, icon_cy + 7],
        fill=(*_WHITE, 200),
    )

    # "THỂ THAO" in white bold
    f_logo = _font(27, bold=True)
    tx = icon_cx + icon_r + 10
    ty = y0 + 20
    draw.text((tx, ty), "THỂ THAO", font=f_logo, fill=(*_WHITE, 255))

    # "247" in red bold — right below or same line, slightly larger
    w_tt, h_tt = _measure(draw, "THỂ THAO", f_logo)
    f247 = _font(27, bold=True)
    draw.text((tx, ty + h_tt + 2), "247", font=f247, fill=(*_RED, 255))


# ── Draw primitives ───────────────────────────────────────────────────────────

def _draw_header(canvas: Image.Image, draw: ImageDraw.ImageDraw, category: str) -> None:
    """Header strip: logo left + category box right + red borders."""
    # Thin red top stripe
    draw.rectangle([0, 0, CANVAS_W, 3], fill=(*_RED, 255))

    # Logo
    _draw_logo_inline(canvas, draw)

    # Header bottom divider
    draw.rectangle([0, _HEADER_H - 2, CANVAS_W, _HEADER_H], fill=(*_RED, 170))

    # Category box — compact, red border, right-aligned
    fc = _font(18, bold=True)
    cat = category.upper()[:22]
    tw, th = _measure(draw, cat, fc)
    px, py = 14, 9
    bw, bh = tw + px * 2, th + py * 2
    bx = CANVAS_W - bw - 28
    by = (_HEADER_H - bh) // 2
    draw.rounded_rectangle([bx, by, bx + bw, by + bh],
                           radius=4, outline=(*_RED, 220), width=2)
    draw.text((bx + px, by + py), cat, font=fc, fill=(*_WHITE, 255))


def _paste_article_image(canvas: Image.Image, image_path: Path) -> None:
    """Cover-crop image to CANVAS_W × _IMG_H, paste at _IMG_TOP. No border."""
    try:
        art = Image.open(image_path).convert("RGB")
    except Exception as e:
        print(f"  ⚠ Cannot open image: {e}")
        return

    tr = CANVAS_W / _IMG_H
    ir = art.width / art.height
    if ir > tr:
        nw = int(art.height * tr)
        left = (art.width - nw) // 2
        art = art.crop((left, 0, left + nw, art.height))
    else:
        nh = int(art.width / tr)
        top = (art.height - nh) // 2
        art = art.crop((0, top, art.width, top + nh))
    art = art.resize((CANVAS_W, _IMG_H), Image.Resampling.LANCZOS)
    canvas.paste(art, (0, _IMG_TOP))


def _apply_bottom_fade(canvas: Image.Image) -> None:
    """Fade image bottom into panel color using numpy gradient."""
    fade_h  = 380
    fade_y0 = _IMG_BTM - fade_h

    arr = np.zeros((fade_h, CANVAS_W, 4), dtype=np.uint8)
    for y in range(fade_h):
        t     = (y / fade_h) ** 1.9
        alpha = int(255 * t)
        arr[y, :] = (*_PANEL, alpha)

    overlay = Image.fromarray(arr, "RGBA")
    canvas.alpha_composite(overlay, (0, fade_y0))


def _draw_panel(canvas: Image.Image, draw: ImageDraw.ImageDraw) -> None:
    """Dark panel with chamfer corners and red border."""
    ch = _CHAMFER

    # Panel fill
    draw.rectangle([0, _IMG_BTM, CANVAS_W, CANVAS_H], fill=(*_PANEL, 255))

    # Chamfer: cut triangles at top-left and top-right using canvas bg color
    draw.polygon([(0, _IMG_BTM), (ch, _IMG_BTM), (0, _IMG_BTM + ch)],
                 fill=(*_BG, 255))
    draw.polygon([(CANVAS_W, _IMG_BTM), (CANVAS_W - ch, _IMG_BTM),
                  (CANVAS_W, _IMG_BTM + ch)],
                 fill=(*_BG, 255))

    # Red border — horizontal + two diagonal chamfer edges
    draw.line([(ch, _IMG_BTM), (CANVAS_W - ch, _IMG_BTM)],
              fill=(*_RED, 255), width=3)
    draw.line([(0, _IMG_BTM + ch), (ch, _IMG_BTM)],
              fill=(*_RED, 255), width=3)
    draw.line([(CANVAS_W - ch, _IMG_BTM), (CANVAS_W, _IMG_BTM + ch)],
              fill=(*_RED, 255), width=3)


def _draw_badge(draw: ImageDraw.ImageDraw, text: str) -> None:
    """Single red badge centered on panel seam."""
    if not text:
        return
    fb = _font(21, bold=True)
    tu = text.upper()
    tw, th = _measure(draw, tu, fb)
    px, py = 22, 10
    bw, bh = tw + px * 2, th + py * 2
    bx = (CANVAS_W - bw) // 2
    by = _IMG_BTM - bh // 2   # centered on seam

    draw.rounded_rectangle([bx, by, bx + bw, by + bh],
                           radius=6, fill=(*_RED, 255))
    # shadow + text
    draw.text((bx + px + 1, by + py + 1), tu, font=fb, fill=(0, 0, 0, 110))
    draw.text((bx + px, by + py),         tu, font=fb, fill=(*_WHITE, 255))


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str, x: int, y: int, max_w: int,
    fmax: int, fmin: int, max_lines: int,
    bold: bool, color: tuple,
) -> int:
    """Auto-shrink font to fit max_lines. Returns y after last line."""
    if not text:
        return y
    chosen_lines: list[str] = []
    chosen_font: ImageFont.FreeTypeFont | None = None
    for sz in range(fmax, fmin - 1, -2):
        f  = _font(sz, bold)
        ls = _wrap(draw, text, f, max_w)
        if len(ls) <= max_lines:
            chosen_lines = ls
            chosen_font  = f
            break
    if not chosen_lines:
        chosen_font  = _font(fmin, bold)
        chosen_lines = _wrap(draw, text, chosen_font, max_w)[:max_lines]

    lh    = int(chosen_font.size * 1.24)
    cur_y = y
    for line in chosen_lines:
        draw.text((x + 1, cur_y + 1), line, font=chosen_font, fill=(0, 0, 0, 115))
        draw.text((x,     cur_y),     line, font=chosen_font, fill=(*color, 255))
        cur_y += lh
    return cur_y


def _draw_accent_line(draw: ImageDraw.ImageDraw, y: int) -> None:
    """Short red + gold decorative line under headline."""
    draw.rectangle([_HEADLINE_X,       y, _HEADLINE_X + 168, y + 3],
                   fill=(*_RED, 255))
    draw.rectangle([_HEADLINE_X + 174, y, _HEADLINE_X + 220, y + 3],
                   fill=(*_GOLD, 255))


# ── End card (static) ─────────────────────────────────────────────────────────

def _render_end_card(overlay_out: Path, bg_out: Path) -> dict:
    p = TEMPLATE_DIR / "dang-ky-kenh" / "background.png"
    if p.exists():
        img = Image.open(p).convert("RGB")
        img = img.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
    else:
        img = Image.new("RGB", (CANVAS_W, CANVAS_H), _BG)

    for out in (overlay_out, bg_out):
        out.parent.mkdir(parents=True, exist_ok=True)
    img.save(overlay_out, "PNG")
    img.save(bg_out, "JPEG", quality=85)
    return {"template": "dang-ky-kenh", "aspect": 1.0,
            "image_size": (0, 0), "bg_size": (CANVAS_W, CANVAS_H)}


# ── Premium frame builder ──────────────────────────────────────────────────────

def _build_frame(scene: dict, image_path: Path | None) -> Image.Image:
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (*_BG, 255))
    draw   = ImageDraw.Draw(canvas)

    tag      = scene.get("tag", "TIN NHANH")
    tmpl     = _select_template(tag)
    category = scene.get("category") or _DEFAULT_CATEGORY.get(tmpl, "THỂ THAO 247")
    badge    = scene.get("badge")    or _DEFAULT_BADGE.get(tmpl, "TIN NHANH")
    headline = scene.get("headline", "")
    subtext  = scene.get("subtext",  "")

    # 1. Article image (full-width, no border, no frame)
    if image_path and image_path.exists():
        _paste_article_image(canvas, image_path)

    # 2. Fade image bottom into panel
    _apply_bottom_fade(canvas)

    # 3. Panel
    _draw_panel(canvas, draw)

    # 4. Badge — centered on panel seam
    _draw_badge(draw, badge)

    # 5. Headline
    hl_bottom = _draw_text_block(
        draw, headline,
        x=_HEADLINE_X, y=_HEADLINE_Y, max_w=_HEADLINE_W,
        fmax=_HEADLINE_FMAX, fmin=_HEADLINE_FMIN, max_lines=_HEADLINE_LMAX,
        bold=True, color=_WHITE,
    )

    # 6. Accent line
    accent_y = hl_bottom + 22
    _draw_accent_line(draw, accent_y)

    # 7. Subtitle
    _draw_text_block(
        draw, subtext,
        x=_HEADLINE_X, y=accent_y + 28, max_w=_HEADLINE_W,
        fmax=_SUB_FMAX, fmin=_SUB_FMIN, max_lines=_SUB_LMAX,
        bold=False, color=_GRAY,
    )

    # 8. Header drawn last — always on top of image
    _draw_header(canvas, draw, category)

    return canvas


# ── Public API ────────────────────────────────────────────────────────────────

def render_scene(
    scene: dict,
    image_path: Path | None,
    bg_output: Path,
    overlay_output: Path,
    scene_index: int = 0,
    total_scenes: int = 4,
) -> dict:
    if scene_index == total_scenes - 1:
        return _render_end_card(overlay_output, bg_output)

    canvas = _build_frame(scene, image_path)

    img_orig = None
    if image_path and image_path.exists():
        try:
            img_orig = Image.open(image_path)
        except Exception:
            pass

    overlay_output.parent.mkdir(parents=True, exist_ok=True)
    bg_output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(overlay_output, "PNG", optimize=True)
    canvas.convert("RGB").save(bg_output,      "JPEG", quality=85)

    return {
        "template":   tmpl_name if (tmpl_name := _select_template(scene.get("tag", ""))) else "premium",
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

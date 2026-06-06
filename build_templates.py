#!/usr/bin/env python3
"""
build_templates.py — Copy template clean + sinh config JSON.

YÊU CẦU: Template clean phải do người dùng cung cấp — file PNG hoàn chỉnh
1080×1920 đã có đầy đủ thiết kế (logo, panel, badge shape, category box,
viền, họa tiết). Code KHÔNG được tự dựng lại bất kỳ thứ gì.

Chạy sau khi đặt file template clean vào assets/templates/:
    python build_templates.py

Bước duy nhất của script này:
    1. Mở file template clean nguồn
    2. Resize về 1080×1920 nếu chưa đúng
    3. Lưu {name}-clean.png
    4. Sinh {name}-config.json với tọa độ image_slot và text zones

TUYỆT ĐỐI KHÔNG:
    - Tự vẽ panel
    - Tự vẽ badge
    - Tự vẽ category box
    - Tự vẽ nền
    - Tự thêm bất kỳ shape nào
"""

import json
import sys
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

ROOT         = Path(__file__).parent
TEMPLATE_DIR = ROOT / "assets" / "templates"
CANVAS_W, CANVAS_H = 1080, 1920


# ─── Template definitions ─────────────────────────────────────────────────────
#
# source: file template clean do người dùng cung cấp.
#         File này phải HOÀN CHỈNH — có sẵn logo, panel, badge shape,
#         category box, viền, họa tiết. Các vùng text để TRỐNG.
#
# image_slot: tọa độ ô ảnh bài viết trong template.
#         CALIBRATE: đo từ file template thực tế.
#
# text_zones: tọa độ các vùng text trong template.
#         CALIBRATE: đo từ file template thực tế.
#
# Tọa độ hiện tại là GIÁ TRỊ TẠM — PHẢI calibrate sau khi có template clean đúng.
#

def _content_zones() -> dict:
    """
    Tọa độ text zones tại canvas 1080×1920.
    CALIBRATE: Đo từ file template clean thực tế trước khi dùng.
    """
    return {
        "category": {
            "x": 648, "y": 68, "w": 385, "h": 46,
            "font_size_max": 22, "font_size_min": 14,
            "bold": True, "color": [255, 255, 255],
            "align": "right", "uppercase": True, "max_lines": 1,
        },
        "badge": {
            "x": 100, "y": 1178, "w": 268, "h": 37,
            "font_size_max": 22, "font_size_min": 14,
            "bold": True, "color": [255, 255, 255],
            "align": "center", "uppercase": True, "max_lines": 1,
        },
        "headline": {
            "x": 88, "y": 1240, "w": 904, "h": 195,
            "font_size_max": 72, "font_size_min": 36,
            "bold": True, "color": [255, 255, 255],
            "align": "left", "uppercase": False, "max_lines": 2,
        },
        "subtitle": {
            "x": 88, "y": 1455, "w": 904, "h": 120,
            "font_size_max": 34, "font_size_min": 18,
            "bold": False, "color": [200, 200, 205],
            "align": "left", "uppercase": False, "max_lines": 2,
        },
    }


TEMPLATES = {

    "chuyen-nhuong": {
        "source": "chuyen-nhuong.png",
        "image_slot": {
            "x": 553, "y": 310, "w": 450, "h": 545,
            "radius": 22, "overlay_opacity": 50,
        },
        "text_zones": _content_zones(),
    },

    "tin-nhanh": {
        "source": "tin-nhanh.png",
        "image_slot": {
            "x": 553, "y": 310, "w": 450, "h": 545,
            "radius": 22, "overlay_opacity": 50,
        },
        "text_zones": _content_zones(),
    },

    "phan-tich": {
        "source": "phan-tich.png",
        "image_slot": {
            "x": 553, "y": 310, "w": 450, "h": 545,
            "radius": 22, "overlay_opacity": 50,
        },
        "text_zones": _content_zones(),
    },

    "nhan-dinh-tran-dau": {
        "source": "nhan-dinh-tran-dau.png",
        "image_slot": None,  # Template đã có visual đội bóng — không có image slot riêng
        "text_zones": _content_zones(),
    },

    "ket-qua-tran-dau": {
        "source": "ket-qua-tran-dau.png",
        "image_slot": None,
        "text_zones": _content_zones(),
    },

    "dang-ky-kenh": {
        "source": "dang-ky-kenh.png",
        "image_slot": None,
        "text_zones": {},   # Static end card — không draw text
    },
}


# ─── Build logic ──────────────────────────────────────────────────────────────

def _build_one(name: str, defn: dict) -> None:
    src_path = TEMPLATE_DIR / defn["source"]
    if not src_path.exists():
        print(f"  ✗ THIẾU FILE: {defn['source']}")
        print(f"    → Đặt file template clean vào: {src_path}")
        return

    # Chỉ resize nếu chưa đúng kích thước — KHÔNG vẽ thêm gì
    img = Image.open(src_path).convert("RGB")
    if img.size != (CANVAS_W, CANVAS_H):
        print(f"  ⚠ {defn['source']} là {img.size} → resize về {CANVAS_W}×{CANVAS_H}")
        img = img.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
    else:
        print(f"  ✓ {defn['source']} đúng {CANVAS_W}×{CANVAS_H}")

    clean_path = TEMPLATE_DIR / f"{name}-clean.png"
    img.save(clean_path, "PNG")
    print(f"  ✓ {name}-clean.png  saved")

    cfg = {
        "canvas":     {"width": CANVAS_W, "height": CANVAS_H},
        "source":     defn["source"],
        "image_slot": defn["image_slot"],
        "text_zones": defn["text_zones"],
    }
    cfg_path = TEMPLATE_DIR / f"{name}-config.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {name}-config.json  saved")


def build_all() -> None:
    print(f"Processing templates → {TEMPLATE_DIR}\n")
    missing = []
    for name, defn in TEMPLATES.items():
        print(f"[{name}]")
        src = TEMPLATE_DIR / defn["source"]
        if not src.exists():
            missing.append(defn["source"])
        _build_one(name, defn)
        print()

    if missing:
        print("=" * 60)
        print("THIẾU CÁC FILE TEMPLATE CLEAN SAU:")
        for f in missing:
            print(f"  → assets/templates/{f}")
        print("\nĐặt file template clean hoàn chỉnh vào đúng đường dẫn")
        print("rồi chạy lại: python build_templates.py")
    else:
        print("Done. Tất cả template đã sẵn sàng.")
        print("QUAN TRỌNG: Calibrate tọa độ text_zones trong config JSON")
        print("trước khi render chính thức.")


if __name__ == "__main__":
    build_all()

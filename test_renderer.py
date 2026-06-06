#!/usr/bin/env python3
"""
test_renderer.py — Kiểm tra render engine với sample data.
Chạy: python test_renderer.py
Output: output/test_render/overlay_XX.png
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

from scene_renderer import render_scene

# Tìm ảnh test từ output cũ
test_img = next(Path("output").glob("*/images/*.jpg"), None)
if test_img is None:
    test_img = next(Path("output").glob("*/images/*.png"), None)
print(f"Test image: {test_img or '(none — render without image)'}\n")

SCENES = [
    {
        "id": "01",
        "tag": "CHUYỂN NHƯỢNG",
        "headline": "Arsenal chi 80 triệu euro đón tiền đạo người Pháp",
        "subtext": "Diễn biến mới nhất trong 24 giờ qua — kỳ chuyển nhượng hè 2026",
        "category": "CHUYỂN NHƯỢNG",
        "badge": "ĐÀM PHÁN",
    },
    {
        "id": "02",
        "tag": "TIN NHANH",
        "headline": "Mbappe ghi hat-trick, Real Madrid đại thắng 5-1",
        "subtext": "Siêu phẩm khiến sân nổ tung trong 15 phút cuối",
        "category": "TIN NHANH",
        "badge": "CẬP NHẬT",
    },
    {
        "id": "03",
        "tag": "NHẬN ĐỊNH",
        "headline": "Chelsea vs Arsenal — Trận derby London đỉnh cao",
        "subtext": "Cục diện trận đấu trước giờ bóng lăn",
        "category": "NHẬN ĐỊNH TRẬN ĐẤU",
        "badge": "TRƯỚC TRẬN",
    },
    {
        "id": "04",
        "tag": "KẾT QUẢ",
        "headline": "Real Madrid 3-1 Liverpool — Chung kết Champions League",
        "subtext": "Màn trình diễn xuất sắc của Vinicius Jr tại Munich",
        "category": "KẾT QUẢ TRẬN ĐẤU",
        "badge": "KẾT THÚC",
    },
    {
        "id": "05",
        "tag": "ĐĂNG KÝ KÊNH",
        "headline": "",
        "subtext": "",
    },
]

out_dir = Path("output/test_render")
out_dir.mkdir(parents=True, exist_ok=True)

total = len(SCENES)
for idx, scene in enumerate(SCENES):
    sid  = scene["id"]
    img  = test_img  # reuse same image for all scenes (visual test)
    bg   = out_dir / f"bg_{sid}.jpg"
    ov   = out_dir / f"overlay_{sid}.png"
    meta = render_scene(scene, img, bg, ov, scene_index=idx, total_scenes=total)
    print(f"  ✓ scene {sid}: template={meta['template']}")

print(f"\nDone. Xem kết quả: {out_dir.resolve()}")

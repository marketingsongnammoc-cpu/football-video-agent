"""Tạo video preview chung kết Champions League 2026: Arsenal vs PSG"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv("config/.env")

import requests as _requests
from urllib.parse import urlparse
from pathlib import Path as _Path
from unittest.mock import MagicMock

# Monkey-patch requests.get để hỗ trợ file:// URLs
_orig_get = _requests.get
def _patched_get(url, **kwargs):
    parsed = urlparse(url)
    if parsed.scheme == "file":
        local = _Path(parsed.path)
        if local.exists():
            mock = MagicMock()
            mock.status_code = 200
            mock.raise_for_status = lambda: None
            mock.iter_content = lambda chunk_size=8192: iter([local.read_bytes()])
            return mock
    return _orig_get(url, **kwargs)
_requests.get = _patched_get

from main import process_article
from scripts.fetcher.base import Article

TITLE = "Chung kết Champions League 2026: Arsenal vs PSG - Trận chiến của những giấc mơ tại Budapest"

BODY = """Ngày 30/5/2026, lịch sử bóng đá châu Âu sẽ được viết lại tại Puskás Aréna, Budapest khi Arsenal và PSG gặp nhau trong trận chung kết UEFA Champions League 2026.

Arsenal - Lần đầu chạm tới đỉnh cao châu Âu sau 20 năm
Kể từ lần cuối lọt vào chung kết Champions League năm 2006 (khi thua Barcelona 1-2), Arsenal cuối cùng đã trở lại sân khấu lớn nhất. Dưới tay Mikel Arteta, đội bóng thành London đã xây dựng một thế hệ cầu thủ đặc biệt — kết hợp sức trẻ, kỷ luật chiến thuật và bản lĩnh thi đấu ở mức độ mà chưa CLB nào ở Anh làm được trong nhiều năm. Đây không chỉ là chung kết, đây là thời điểm để Arsenal trả nợ lịch sử.

PSG - Khát vọng lặp lại kỳ tích
PSG đang muốn trở thành đội đầu tiên vô địch Champions League hai lần liên tiếp kể từ thời kỳ hoàng kim của Real Madrid. Sau khi loại Bayern Munich ở bán kết với màn trình diễn hủy diệt, đội bóng Paris đang trong phong độ đỉnh cao và sẵn sàng viết tiếp trang sử cho bóng đá Pháp.

Địa điểm lịch sử: Puskás Aréna, Budapest
Đây là lần đầu tiên Hungary đăng cai chung kết Champions League. Sân vận động với sức chứa 67.000 chỗ ngồi nằm ngay trung tâm thủ đô Budapest sẽ là nơi chứng kiến một trong những trận đấu lớn nhất trong lịch sử bóng đá châu Âu. Giá vé dao động từ 70 euro đến 950 euro, với Arsenal nhận 16.824 suất cho CĐV.

Trận đấu bắt đầu lúc 2h ngày 31/5/2026 (giờ Việt Nam). The Killers sẽ biểu diễn trong lễ khai mạc hoành tráng được tài trợ bởi Pepsi.

Ai sẽ nâng chiếc cúp tai voi huyền thoại? Arsenal với giấc mơ lần đầu vô địch châu Âu, hay PSG với tham vọng bá chủ lục địa già? Câu trả lời sẽ có vào đêm 30/5."""

# Lấy ảnh từ folder FA Cup sẵn có
IMG_DIR = os.path.join(os.path.dirname(__file__), "output",
                       "2026-05-17_041004_semenyo-lap-sieu-pham-fa-cup", "images")

def get_local_images(img_dir, n=8):
    p = _Path(img_dir)
    if not p.exists():
        print(f"  Không tìm thấy folder ảnh: {img_dir}")
        return []
    all_imgs = sorted(p.glob("scene_*.jpg"))
    valid = []
    for img in all_imgs:
        try:
            from PIL import Image as PILImage
            with PILImage.open(img) as im:
                if max(im.size) >= 600:
                    valid.append(img)
        except Exception:
            pass
    return ["file://" + str(img) for img in valid[:n]]

if __name__ == "__main__":
    images = get_local_images(IMG_DIR, n=8)
    print(f"  → Dùng {len(images)} ảnh từ folder FA Cup Man City")
    if not images:
        print("  LỖI: Không có ảnh nào!")
        sys.exit(1)

    article = Article(
        title=TITLE,
        body=BODY,
        images=images,
        url="manual_cl_final_" + str(int(time.time())),
        source_name="manual",
        language="vi",
    )
    result = process_article(article, is_tabloid=False, no_publish=True)
    if result:
        print(f"\n✓ Video đã tạo xong: {result}")
    else:
        print("\n✗ Tạo video thất bại")

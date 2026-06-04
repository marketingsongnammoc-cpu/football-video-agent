"""Scheduled task 22h ngay 17/5/2026 — Michael Carrick chinh thuc lam HLV Man Utd."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", ".env"))

import requests as _requests
from urllib.parse import urlparse
from pathlib import Path as _Path
from unittest.mock import MagicMock

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

TITLE = "Fabrizio Romano xac nhan: Michael Carrick chinh thuc lam HLV truong Man Utd"

BODY = (
    "Here we go! Fabrizio Romano da chinh thuc xac nhan: Manchester United va Michael Carrick "
    "da dat thoa thuan de vi cuu tien ve nguoi Anh tro thanh HLV truong chinh thuc cua Quy Do. "
    "Day la tin tuc chan dong bong da Anh trong dem 17 thang 5 nam 2026.\n\n"

    "Carrick ky hop dong 2 nam den thang 6 nam 2028, voi quyen chon gia han them 1 mua nua. "
    "Man Utd du kien cong bo chinh thuc ngay truoc tran cuoi san nha gap Nottingham Forest "
    "vao Chu Nhat 24 thang 5 — mot khoanh khac day cam xuc tai Old Trafford.\n\n"

    "Carrick tiep quan ghe tam quyen tu thang 1 sau khi Man Utd sa thai Ruben Amorim. "
    "Trong 15 tran nam quyen, nguoi con cu cua Old Trafford gianh duoc 10 chien thang, "
    "chi thua 2 tran — ket qua an tuong de dua Man Utd tra lai dau truong Champions League. "
    "Thanh tich nay da thuyet phuc ban lanh dao Ineos va ty phu Jim Ratcliffe rang Carrick "
    "xung dang co hoi dan dat doi bong lau dai hon.\n\n"

    "Truoc khi chon Carrick, Man Utd tung tiep can Andoni Iraola va Unai Emery, "
    "nhung cuoi cung quyet dinh tin tuong nguoi ben trong. "
    "Carrick — cuu tien ve huyen thoai, tung gianh 5 Premier League, 1 Champions League voi Man Utd "
    "va sau do co kinh nghiem dan dat Middlesbrough 3 mua — duoc danh gia la lua chon thanh cong "
    "nhat tu thi truong HLV ngay nay.\n\n"

    "Ke hoach chuyen nhuong mua he da san sang: Man Utd se dai tu tuyen giua voi viec biet nhom "
    "Casemiro, nhieu kha nang ban Ugarte, va tich cuc san don tien ve chi huy moi. "
    "Ngoai ra, Fabrizio Romano tiet lo Federico Valverde cua Real Madrid "
    "la cai ten nam trong tam ngam cua Man City — nhung chinh Valverde khang dinh muon o lai Bernabeu. "
    "Cuoc cach mang tai Old Trafford chinh thuc bat dau tu mua he 2026!"
)

# Dung anh tu folder Premier League title race
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output",
                       "2026-05-17_091530_arsenal-dan-2-diem-man-city-con-cua", "images")

def get_local_images(img_dir, n=6):
    p = _Path(img_dir)
    if not p.exists():
        print(f"  [warn] Khong tim thay folder {img_dir}, thu folder du phong...")
        # Fallback: dung folder FA Cup
        fallback = _Path(os.path.dirname(os.path.abspath(__file__))) / "output" / \
                   "2026-05-17_041004_semenyo-lap-sieu-pham-fa-cup" / "images"
        if fallback.exists():
            p = fallback
        else:
            return []
    all_imgs = sorted(p.glob("scene_*.jpg"))
    valid = []
    for img in all_imgs:
        try:
            from PIL import Image as _PILImage
            with _PILImage.open(img) as im:
                if max(im.size) >= 600:
                    valid.append(img)
        except Exception:
            pass
        if len(valid) >= n:
            break
    return ["file://" + str(img) for img in valid]

if __name__ == "__main__":
    images = get_local_images(IMG_DIR, n=6)
    print(f"  -> Dung {len(images)} anh tu folder Premier League")
    if not images:
        print("  [ERROR] Khong co anh hop le. Dung script.")
        sys.exit(1)

    article = Article(
        title=TITLE,
        body=BODY,
        images=images,
        url="manual_carrick_manutd_" + str(int(time.time())),
        source_name="manual",
        language="vi",
    )
    process_article(article, is_tabloid=False)

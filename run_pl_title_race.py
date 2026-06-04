import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv("config/.env")

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

TITLE = "Arsenal dan 2 diem, Man City con cua vo dich sau khi doat FA Cup"

BODY = (
    "Cuoc dua vo dich Premier League 2025/26 dang buoc vao hoi kich tinh nhat voi chi con 2 vong cuoi. "
    "Arsenal dang dan dau voi 79 diem, hon Manchester City 2 diem. Ca hai doi se phai quyet dau den tran cuoi mua.\n\n"
    "Arsenal can gi de vo dich? "
    "Doi quan cua Mikel Arteta dang nam van menh trong tay. "
    "Neu Arsenal thang ca hai tran con lai — gap Burnley tren san nha va chuyen lam khach toi Crystal Palace — "
    "ho se lan dau tien dang quang Premier League sau hon hai thap ky. "
    "Chi can mot tran hoa, Arsenal co the mat loi the neu Man City toan thang.\n\n"
    "Man City dang o dau? "
    "Guardiola vua doat FA Cup bang sieu pham cua Antoine Semenyo, tao ra hy vong an ba trong nuoc lich su. "
    "Voi 77 diem va hieu so ban thang bai +43 — cao hon Arsenal (+42) — "
    "Man City chi can Arsenal vap nga mot lan la co co hoi duoi kip va gianh chuc vo dich.\n\n"
    "Lich thi dau con lai: "
    "Arsenal: vs Burnley (san nha), vs Crystal Palace (san khach). "
    "Man City: 2 tran cuoi mua cung phai quyet dinh. "
    "Day la cuoc dua vo dich hap dan nhat Ngoai hang Anh trong nhieu nam qua — "
    "va tat ca se nga ngu trong 2 vong dau cuoi cung."
)

IMG_DIR = os.path.join(os.path.dirname(__file__), "output",
                       "2026-05-17_041004_semenyo-lap-sieu-pham-fa-cup", "images")

def get_local_images(img_dir, n=6):
    p = _Path(img_dir)
    if not p.exists():
        return []
    all_imgs = sorted(p.glob("scene_*.jpg")); imgs = [i for i in all_imgs if __import__("PIL.Image", fromlist=["Image"]).open(i).size[0] >= 600][:n]
    return ["file://" + str(img) for img in imgs]

if __name__ == "__main__":
    images = get_local_images(IMG_DIR, n=6)
    print("  -> Dung " + str(len(images)) + " anh tu folder FA Cup Man City")
    article = Article(
        title=TITLE,
        body=BODY,
        images=images,
        url="manual_pl_title_" + str(int(time.time())),
        source_name="manual",
        language="vi",
    )
    process_article(article, is_tabloid=False)

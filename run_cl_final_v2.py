"""Tao video Arsenal vs PSG CL Final."""
import sys, os, time, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", ".env"))

import requests as _req
from urllib.parse import urlparse
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime

_orig_get = _req.get
def _pg(url, **kw):
    p = urlparse(url)
    if p.scheme == "file":
        loc = Path(p.path)
        if loc.exists():
            m = MagicMock()
            m.status_code = 200
            m.raise_for_status = lambda: None
            m.iter_content = lambda chunk_size=8192: iter([loc.read_bytes()])
            return m
    return _orig_get(url, **kw)
_req.get = _pg

# Patch write_videofile to always pass temp_audiofile_path to a writable dir
import moviepy.video.VideoClip as _mvc
_orig_wvf = _mvc.VideoClip.write_videofile
def _patched_wvf(self, filename, *args, **kwargs):
    # Force temp audio to same folder as output file
    if "temp_audiofile_path" not in kwargs:
        kwargs["temp_audiofile_path"] = str(Path(filename).parent)
    return _orig_wvf(self, filename, *args, **kwargs)
_mvc.VideoClip.write_videofile = _patched_wvf

ROOT = Path(os.path.abspath(__file__)).parent
OUTPUT_DIR = ROOT / "output"
SRC = OUTPUT_DIR / "2026-05-17_041004_semenyo-lap-sieu-pham-fa-cup"

from scripts.script_gen import generate_script
from scripts.scene_renderer import render_all_scenes
from scripts.composer import compose_video

TITLE = "Chung ket Champions League 2026: Arsenal vs PSG tai Budapest"
BODY = (
    "Ngay 30 thang 5 nam 2026, lich su bong da chau Au se duoc viet lai tai Puskas Arena Budapest "
    "khi Arsenal va PSG gap nhau trong tran chung ket UEFA Champions League 2026. "
    "Arsenal lan dau cham toi dinh cao chau Au sau 20 nam. "
    "Ke tu lan cuoi lot vao chung ket nam 2006 khi thua Barcelona 1-2, Arsenal cuoi cung da tro lai. "
    "Duoi tay Mikel Arteta doi bong thanh London xay dung the he cau thu dac biet. "
    "Day la thoi diem tra no lich su cho The Gunners. "
    "PSG khat vong lap lai ky tich vo dich Champions League lan thu hai lien tiep. "
    "Sau khi loai Bayern Munich o ban ket voi man trinh dien huy diet, "
    "doi bong Paris dang trong phong do dinh cao san sang viet tiep trang su. "
    "Dia diem lich su Puskas Arena Budapest lan dau tien Hungary dang cai chung ket. "
    "San van dong 67000 cho ngoi ve tu 70 den 950 euro Arsenal nhan 16824 suat ve. "
    "Tran dau bat dau 2 gio sang ngay 31 thang 5 theo gio Viet Nam. "
    "The Killers bieu dien le khai mac hoanh trang duoc tai tro boi Pepsi. "
    "Ai se nang chiec cup tai voi huyen thoai Arsenal hay PSG?"
)

N = 8
ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
vf = OUTPUT_DIR / (ts + "_arsenal-psg-cl-final-2026")
imgs_d = vf / "images"
aud_d = vf / "audio"
frm_d = vf / "frames"
for d in (imgs_d, aud_d, frm_d):
    d.mkdir(parents=True, exist_ok=True)

src_imgs = sorted((SRC/"images").glob("scene_*.jpg"))[:N]
print("Using %d images" % len(src_imgs))
for i, img in enumerate(src_imgs, 1):
    shutil.copy2(img, imgs_d / ("scene_%02d.jpg" % i))

print("Generating script...")
scenes = generate_script(TITLE, BODY, num_scenes=N)
for i, s in enumerate(scenes):
    s["image_url"] = str(src_imgs[i]) if i < len(src_imgs) else ""

vf.joinpath("source.json").write_text(
    json.dumps({"url": "manual_cl_final_%d"%int(time.time()), "title_vi": TITLE,
                "body_vi": BODY, "source_name": "manual", "language": "vi",
                "was_translated": False, "is_tabloid": False, "num_scenes": N},
               ensure_ascii=False, indent=2), encoding="utf-8")
vf.joinpath("script.json").write_text(
    json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")

print("Rendering frames...")
render_all_scenes(scenes, imgs_d, frm_d)

print("Copying audio...")
for i, src in enumerate(sorted((SRC/"audio").glob("scene_*.mp3"))[:N], 1):
    shutil.copy2(src, aud_d / ("scene_%02d.mp3" % i))
    print("  audio %02d ok" % i)

import os as _os
_orig_rm = _os.remove
def _srm(path):
    try: _orig_rm(path)
    except PermissionError: pass
_os.remove = _srm

print("Composing video...")
out_mp4 = vf / "video.mp4"
try:
    result = compose_video(scenes, vf, out_mp4)
finally:
    _os.remove = _orig_rm

sz = out_mp4.stat().st_size / 1024 / 1024
print("DONE: %s" % out_mp4)
print("Duration: %.1fs  Size: %.1fMB" % (result["duration"], sz))

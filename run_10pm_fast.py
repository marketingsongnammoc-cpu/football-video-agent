"""Scheduled 22:00 - 18/5/2026: 2 videos, direct ffmpeg (no moviepy)."""
import sys, os, json, shutil, subprocess, time
from datetime import datetime
from pathlib import Path
import unicodedata, re

ROOT = Path("/sessions/amazing-confident-carson/mnt/football-video-agent")
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")
from scripts.script_gen import generate_script
from scripts.scene_renderer import render_all_scenes

SILENCE = 0.5

def slugify(text, n=50):
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("d","d").lower()
    return re.sub(r"[^a-z0-9]+","-",t).strip("-")[:n]

def get_audio_dur(f):
    r = subprocess.run(["ffprobe","-v","quiet","-print_format","json",
                        "-show_streams",str(f)], capture_output=True, text=True)
    return float(json.loads(r.stdout)["streams"][0]["duration"])

def ffmpeg_compose(frames_dir, audio_dir, num_scenes, output_mp4):
    """Direct ffmpeg composition per scene then concat."""
    tmp_scenes = []
    for i in range(1, num_scenes+1):
        bg   = frames_dir / f"bg_{i:02d}.jpg"
        ov   = frames_dir / f"overlay_{i:02d}.png"
        au   = audio_dir  / f"scene_{i:02d}.mp3"
        out  = frames_dir / f"_sc_{i:02d}.mp4"
        if not bg.exists() or not au.exists(): continue
        dur = get_audio_dur(au) + SILENCE
        fc = "[0:v]scale=720:1280,setsar=1[bg]"
        if ov.exists():
            fc += ";[1:v]format=rgba[ov];[bg][ov]overlay=0:0[v]"
            inputs = ["-loop","1","-t",str(dur),"-i",str(bg),"-i",str(ov),"-i",str(au)]
            maps   = ["-map","[v]","-map","2:a"]
        else:
            fc += ";[bg]copy[v]"
            inputs = ["-loop","1","-t",str(dur),"-i",str(bg),"-i",str(au)]
            maps   = ["-map","[v]","-map","1:a"]
        cmd = ["ffmpeg","-y"]+inputs+[
            "-filter_complex", fc,
        ]+maps+[
            "-c:v","libx264","-preset","ultrafast","-crf","26",
            "-c:a","aac","-shortest","-pix_fmt","yuv420p",str(out)
        ]
        subprocess.run(cmd, capture_output=True)
        if out.exists(): tmp_scenes.append(out)
    if not tmp_scenes: return False
    concat_f = frames_dir / "_concat.txt"
    concat_f.write_text("\n".join(f"file '{f}'" for f in tmp_scenes))
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat_f),
                    "-c","copy",str(output_mp4)], capture_output=True)
    return output_mp4.exists()

def make_video(title_vi, body_vi, source_images, source_audio, story_key):
    OUTPUT = ROOT / "output"
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    slug = slugify(title_vi)
    folder = OUTPUT / f"{ts}_{slug}"
    imgs_d  = folder / "images"
    audio_d = folder / "audio"
    frames_d= folder / "frames"
    for d in (imgs_d, audio_d, frames_d): d.mkdir(parents=True, exist_ok=True)

    from PIL import Image as PILImage
    valid = []
    for idx, src in enumerate(source_images, 1):
        if len(valid) >= 6: break
        sp = Path(src)
        if not sp.exists(): continue
        dp = imgs_d / f"scene_{idx:02d}.jpg"
        shutil.copy2(sp, dp)
        try:
            with PILImage.open(dp) as im:
                if max(im.size) < 300: dp.unlink(); continue
            valid.append(dp)
        except: dp.unlink()

    num = len(valid)
    if num < 1: print(f"[{story_key}] No images."); return None

    for idx, ap in enumerate([Path(a) for a in source_audio if Path(a).exists()][:num], 1):
        shutil.copy2(ap, audio_d / f"scene_{idx:02d}.mp3")

    print(f"[{story_key}] Script gen ({num} scenes)...")
    scenes = generate_script(title_vi, body_vi, num_scenes=num)

    (folder / "source.json").write_text(
        json.dumps({"title_vi": title_vi, "audio_reused": True, "num_scenes": num,
                    "source": f"scheduled_22h_{story_key}_{ts}"}, ensure_ascii=False, indent=2))
    (folder / "script.json").write_text(
        json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2))

    print(f"[{story_key}] Render frames...")
    render_all_scenes(scenes, imgs_d, frames_d)

    print(f"[{story_key}] Compose (ffmpeg)...")
    mp4 = folder / "video.mp4"
    ok = ffmpeg_compose(frames_d, audio_d, num, mp4)
    if ok:
        size_mb = mp4.stat().st_size / 1024 / 1024
        print(f"  OK {mp4.name}  {size_mb:.2f} MB")
        return mp4
    print(f"  FAIL: video not created")
    return None

# ── NEWS 1: EUROPA LEAGUE FINAL ──
title_1 = "Chung ket Europa League 2026: Aston Villa quyet dau Freiburg tai Istanbul"
body_1 = (
    "Aston Villa va SC Freiburg se tranh chuc vo dich UEFA Europa League 2026 vao ngay 20/5 "
    "tai san Besiktas Park, Istanbul. Day la lan dau tien Freiburg buoc vao mot tran chung ket "
    "chau Au. Aston Villa lan dau tien o mot tran chung ket UEFA ke tu khi vo dich Cup C1 nam 1982 - "
    "tuc la sau 44 nam. HLV Unai Emery da 4 lan vo dich Europa League (3 lan voi Sevilla, 1 lan "
    "voi Villarreal). Villa da ghi 28 ban va thung luoi 8 ban trong hanh trinh den Istanbul, "
    "chua thung luoi trong 3 tran truoc day tai day. Tran chung ket bat dau luc 21:00 CET "
    "(2:00 sang 21/5 gio Viet Nam)."
)
imgs1 = sorted((ROOT/"output/2026-05-17_220030_arteta-sap-vo-dich-champions-league/images").glob("*.jpg"))[:6]
auds1 = sorted((ROOT/"output/2026-05-17_220030_arteta-sap-vo-dich-champions-league/audio").glob("*.mp3"))[:6]

# ── NEWS 2: CHAMPIONS LEAGUE FINAL ──
title_2 = "Chung ket Champions League 2026: PSG bao ve ngoi vuong, Arsenal don lich su"
body_2 = (
    "Paris Saint-Germain va Arsenal se chung ket UEFA Champions League 2026 ngay 30/5 "
    "tai san Puskas Arena o Budapest. PSG dang co gang tro thanh doi bong thu hai bao ve "
    "thanh cong chuc vo dich sau Real Madrid 2016-2018, sau khi vuot qua Bayern Munich o ban ket. "
    "Arsenal duoi theo chuc vo dich Champions League dau tien trong lich su CLB, sau khi ha "
    "Atletico Madrid o ban ket. Nam 2006, Arsenal thua Barcelona 1-2 la lan duy nhat ho vao "
    "chung ket. Tran bat dau luc 18:00 CET (23:00 gio Viet Nam) ngay 30/5. "
    "Ban nhac The Killers se bieu dien trong le khai mac."
)
imgs2 = sorted((ROOT/"output/2026-05-17_122027_arsenal-psg-cl-final-2026/images").glob("*.jpg"))[:6]
auds2 = sorted((ROOT/"output/2026-05-17_122027_arsenal-psg-cl-final-2026/audio").glob("*.mp3"))[:6]

print("="*60)
print("FOOTBALL AGENT - SCHEDULED 22:00 - 18/5/2026")
print("="*60)
results = []

t0 = time.time()
print("\n--- Video 1: Europa League Final ---")
r1 = make_video(title_1, body_1, imgs1, auds1, "el_final")
if r1: results.append(r1)
print(f"  Elapsed: {time.time()-t0:.1f}s")

print("\n--- Video 2: CL Final Preview ---")
r2 = make_video(title_2, body_2, imgs2, auds2, "cl_final")
if r2: results.append(r2)
print(f"  Total elapsed: {time.time()-t0:.1f}s")

print("\n" + "="*60)
print(f"DONE: {len(results)}/2 videos created")
for r in results:
    mb = r.stat().st_size/1024/1024
    print(f"  OK {r.parent.name}  {mb:.2f} MB")

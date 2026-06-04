"""
voice_gen.py — TTS đa tầng fallback.

Thứ tự ưu tiên:
  1. Vbee (API polling) — giọng Việt chuyên nghiệp nhất
  2. FPT.AI — fallback
  3. Google Chirp3-HD — fallback
  4. edge-tts — fallback miễn phí

Pool giọng thể thao Vbee (quay vòng ngẫu nhiên mỗi video):
  - hn_male_manhdung_full_48k-fhg   — Mạnh Dũng, HN, Nam — giọng BLV chắc
  - hn_male_thanhlong_full_48k-fhg  — Thanh Long, HN, Nam — trầm, uy
  - hn_male_anhkhoi_full_48k-fhg    — Anh Khôi, HN, Nam — tươi, trẻ
  - hn_male_chidad_full_48k-fhg     — Chí Đạt, HN, Nam — sôi nổi
  - sg_male_trungkien_full_48k-fhg  — Trung Kiên, SG, Nam — miền Nam tự nhiên
  - sg_male_minhhoang_full_48k-fhg  — Minh Hoàng, SG, Nam — miền Nam khỏe
"""

from __future__ import annotations
import asyncio
import base64
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

# Fix Windows console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ───────────────────────────────────────────────────────────
# Vbee TTS (ưu tiên #1)
# ───────────────────────────────────────────────────────────

VBEE_TTS_URL = "https://api.vbee.vn/v1/tts"
VBEE_SPEED   = 1.1   # hơi nhanh hơn chuẩn, phong cách tin tức thể thao

# Pool giọng NAM thể thao đã xác nhận hoạt động — quay vòng ngẫu nhiên mỗi video
VBEE_SPORTS_VOICES = [
    "hn_male_manhdung_news_48k-fhg",               # Mạnh Dũng   — HN, giọng tin tức ★ best
    "sg_male_trungkien_vdts_48k-fhg",              # Trung Kiên  — SG, nam tự nhiên
    "sg_male_minhhoang_full_48k-fhg",              # Minh Hoàng  — SG, nam khỏe
    "n_hanoi_male_thangchuyennghiep_advertise_vc", # Thắng CN    — HN, sôi nổi
    "n_hanoi_male_nhabaohoangnam_news_vc",          # Hoàng Nam   — HN, nhà báo
    "n_hanoi_male_tuananhnews_news_vc",             # Tuấn Anh    — HN, tin tức
    "n_hanoi_male_bountintuc_news_vc",              # Bou Tin Tức — HN, tin tức
    "n_hanoi_male_namduatinhot_news_vc",            # Nam Đưa Tin — HN, tin nóng
]
VBEE_DEFAULT_VOICE = VBEE_SPORTS_VOICES[0]  # Mạnh Dũng news


def _vbee_headers(app_id: str, token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "App-Id": app_id,
        "Content-Type": "application/json",
    }


def _vbee_tts(text: str, output: Path, app_id: str, token: str,
              voice: str = VBEE_DEFAULT_VOICE) -> bool:
    """Vbee TTS qua async mode + webhook.site relay."""
    text = _prep_tts_text(text)
    headers = _vbee_headers(app_id, token)
    return _vbee_async_webhook(text, output, headers, voice)


def _vbee_async_webhook(text: str, output: Path, headers: dict, voice: str) -> bool:
    """Async mode — dùng webhook.site làm relay nhận callback."""
    try:
        with httpx.Client(timeout=15) as client:
            wh = client.post("https://webhook.site/token",
                             json={"default_status": 200}, timeout=10)
        wh_uuid = wh.json()["uuid"]
        wh_url  = f"https://webhook.site/{wh_uuid}"
    except Exception as e:
        print(f"  [Vbee async] Khong tao duoc webhook.site: {e}")
        return False

    try:
        with httpx.Client(timeout=20) as client:
            r = client.post(VBEE_TTS_URL, headers=headers, json={
                "text": text,
                "voiceCode": voice,
                "mode": "async",
                "webhookUrl": wh_url,
                "outputFormat": "mp3",
                "bitrate": 128,
                "speed": VBEE_SPEED,
            })
        if r.status_code not in (200, 201):
            print(f"  [Vbee async] Submit loi {r.status_code}: {r.text[:120]}")
            return False

        deadline = time.time() + 90
        while time.time() < deadline:
            time.sleep(3)
            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    f"https://webhook.site/token/{wh_uuid}/requests",
                    params={"per_page": 1}, timeout=10)
            data = resp.json().get("data", [])
            if data:
                body = json.loads(data[0]["content"])
                status = body.get("status", "")
                if status == "SUCCESS":
                    audio_link = body.get("audioLink") or body.get("audio_link")
                    with httpx.Client(timeout=60, follow_redirects=True) as client:
                        dl = client.get(audio_link)
                    if dl.status_code == 200 and len(dl.content) > 500:
                        output.write_bytes(dl.content)
                        return True
                elif status == "FAILURE":
                    print(f"  [Vbee async] FAILURE: {body}")
                    return False

        print(f"  [Vbee async] Timeout 90s")
    except Exception as e:
        print(f"  [Vbee async] Exception: {e}")
    finally:
        try:
            with httpx.Client(timeout=5) as client:
                client.delete(f"https://webhook.site/token/{wh_uuid}")
        except Exception:
            pass
    return False


# ───────────────────────────────────────────────────────────
# Kie.ai → ElevenLabs TTS
# ───────────────────────────────────────────────────────────

KIEAI_CREATE_URL   = "https://api.kie.ai/api/v1/jobs/createTask"
KIEAI_POLL_URL     = "https://api.kie.ai/api/v1/jobs/recordInfo"
KIEAI_MODEL        = "elevenlabs/text-to-speech-multilingual-v2"

KIEAI_VOICES = {
    "phil":   "LG95yZDEHg6fCZdQjLqj",
    "james":  "EkK5I93UQWFDigLMpZcX",
    "brian":  "nPczCjzI2devNBz1zQrb",
    "nathan": "x70vRnQBMBu4FAYhjJbO",
}
KIEAI_DEFAULT_VOICE = "phil"


def _kieai_elevenlabs_tts(text: str, output: Path, api_key: str,
                           voice: str = KIEAI_DEFAULT_VOICE) -> bool:
    text = _prep_tts_text(text)
    voice_id = KIEAI_VOICES.get(voice, KIEAI_VOICES[KIEAI_DEFAULT_VOICE])
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(
                KIEAI_CREATE_URL,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={
                    "model": KIEAI_MODEL,
                    "input": {
                        "text": text,
                        "voice": voice_id,
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.3,
                        "speed": 1.05,
                        "language_code": "vi",
                    },
                },
            )
        if r.status_code != 200:
            print(f"  [KieAI] Lỗi tạo task: {r.status_code}")
            return False
        task_id = r.json().get("data", {}).get("taskId")
        if not task_id:
            return False

        for attempt in range(20):
            time.sleep(3)
            with httpx.Client(timeout=30) as client:
                poll = client.get(
                    KIEAI_POLL_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"taskId": task_id},
                )
            data = poll.json().get("data", {})
            state = data.get("state", "")
            if state == "success":
                result = json.loads(data.get("resultJson", "{}"))
                urls = result.get("resultUrls", [])
                if urls:
                    with httpx.Client(timeout=60) as client:
                        dl = client.get(urls[0])
                    if dl.status_code == 200 and len(dl.content) > 500:
                        output.write_bytes(dl.content)
                        return True
            elif state == "fail":
                print(f"  [KieAI] Task thất bại: {data.get('failMsg')}")
                return False

        print(f"  [KieAI] Timeout sau 60s")
    except Exception as e:
        print(f"  [KieAI] Exception: {e}")
    return False


# ───────────────────────────────────────────────────────────
# FPT.AI TTS
# ───────────────────────────────────────────────────────────

FPT_TTS_URL = "https://api.fpt.ai/hmi/tts/v5"

FPT_VOICES = [
    "banmai",    # nữ, miền Nam
    "leminh",    # nam, miền Nam
    "thuminh",   # nữ, miền Bắc
    "minhquang", # nam, miền Bắc
    "lannhi",    # nữ
    "minhtu",    # nam
]
FPT_DEFAULT_VOICE = "minhquang"
FPT_SPEED = "2"


# Pool giọng tiếng Việt fallback (FPT + edge) — dùng khi Vbee fail
VOICE_POOL = [
    {"engine": "fpt",  "voice": "minhquang"},           # nam Bắc, FPT.AI
    {"engine": "fpt",  "voice": "banmai"},              # nữ Nam, FPT.AI
    {"engine": "edge", "voice": "vi-VN-NamMinhNeural"}, # nam, Microsoft Neural
    {"engine": "edge", "voice": "vi-VN-HoaiMyNeural"},  # nữ, Microsoft Neural
]


def _prep_tts_text(text: str) -> str:
    """
    Xóa dấu câu gây pause trong TTS (. , ; :) — chỉ giữ ! và ?
    """
    text = re.sub(r'[.,;:—–]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _fpt_tts(text: str, output: Path, api_key: str, voice: str = FPT_DEFAULT_VOICE) -> bool:
    text = _prep_tts_text(text)
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(
                FPT_TTS_URL,
                headers={"api-key": api_key, "voice": voice, "speed": FPT_SPEED},
                content=text.encode("utf-8"),
            )
        if r.status_code != 200:
            print(f"  [FPT TTS] Lỗi {r.status_code}: {r.text[:120]}")
            return False

        data = r.json()
        if data.get("error", 1) != 0:
            print(f"  [FPT TTS] API error: {data.get('message')}")
            return False

        async_url = data.get("async", "")
        if not async_url:
            return False

        for attempt in range(8):
            time.sleep(2)
            with httpx.Client(timeout=30) as client:
                dl = client.get(async_url)
            if dl.status_code == 200 and len(dl.content) > 500:
                output.write_bytes(dl.content)
                return True

        print(f"  [FPT TTS] Timeout chờ async URL")
    except Exception as e:
        print(f"  [FPT TTS] Exception: {e}")
    return False


# ───────────────────────────────────────────────────────────
# Google Cloud TTS (fallback)
# ───────────────────────────────────────────────────────────

GOOGLE_TTS_URL  = "https://texttospeech.googleapis.com/v1/text:synthesize"
GOOGLE_LANG     = "vi-VN"
SPEAKING_RATE   = 1.05

CHIRP3_HD_VOICES = [
    "vi-VN-Chirp3-HD-Alnilam",
    "vi-VN-Chirp3-HD-Achernar",
    "vi-VN-Chirp3-HD-Aoede",
    "vi-VN-Chirp3-HD-Charon",
    "vi-VN-Chirp3-HD-Fenrir",
    "vi-VN-Chirp3-HD-Kore",
    "vi-VN-Chirp3-HD-Leda",
    "vi-VN-Chirp3-HD-Puck",
    "vi-VN-Chirp3-HD-Zephyr",
]
DEFAULT_VOICE_NAME = CHIRP3_HD_VOICES[0]


def _google_tts(text: str, output: Path, api_key: str, voice: str = CHIRP3_HD_VOICES[0]) -> bool:
    text = _prep_tts_text(text)
    body = {
        "input": {"text": text},
        "voice": {"languageCode": GOOGLE_LANG, "name": voice},
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": SPEAKING_RATE,
            "pitch": 0.0,
        },
    }
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(GOOGLE_TTS_URL, params={"key": api_key}, json=body)
        if r.status_code == 200:
            audio = base64.b64decode(r.json()["audioContent"])
            output.write_bytes(audio)
            return True
        print(f"  [Google TTS] Lỗi {r.status_code} ({voice}): {r.text[:120]}")
    except Exception as e:
        print(f"  [Google TTS] Exception: {e}")
    return False


# ───────────────────────────────────────────────────────────
# edge-tts fallback
# ───────────────────────────────────────────────────────────

EDGE_VOICE_VI   = "vi-VN-NamMinhNeural"
EDGE_VOICE_VI_F = "vi-VN-HoaiMyNeural"
EDGE_RATE       = "+25%"


def _is_english(text: str) -> bool:
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / max(len(text), 1) > 0.92


def _edge_tts_voice(text: str, output: Path, voice: str) -> bool:
    import edge_tts
    text = _prep_tts_text(text)

    async def _run():
        try:
            comm = edge_tts.Communicate(text, voice, rate="+25%")
            await comm.save(str(output))
            return output.exists() and output.stat().st_size > 500
        except Exception:
            return False

    try:
        loop = asyncio.new_event_loop()
        ok = loop.run_until_complete(_run())
        loop.close()
        return ok
    except Exception:
        return False


def _edge_tts(text: str, output: Path) -> bool:
    import edge_tts
    text = _prep_tts_text(text)

    if _is_english(text):
        voices = [(EDGE_VOICE_VI, EDGE_RATE), ("en-US-GuyNeural", EDGE_RATE)]
    else:
        voices = [(EDGE_VOICE_VI, EDGE_RATE), (EDGE_VOICE_VI_F, EDGE_RATE)]

    async def _try_voice(voice: str, rate: str) -> bool:
        try:
            comm = edge_tts.Communicate(text, voice, rate=rate)
            await comm.save(str(output))
            return output.exists() and output.stat().st_size > 500
        except Exception:
            return False

    for voice, rate in voices:
        try:
            loop = asyncio.new_event_loop()
            ok = loop.run_until_complete(_try_voice(voice, rate))
            loop.close()
            if ok:
                return True
        except Exception:
            continue
    return False


# ───────────────────────────────────────────────────────────
# Public API
# ───────────────────────────────────────────────────────────

def generate_voice(text: str, output: Path,
                   voice_name: str = DEFAULT_VOICE_NAME,
                   fpt_voice: str = FPT_DEFAULT_VOICE,
                   kieai_voice: str = KIEAI_DEFAULT_VOICE,
                   vbee_voice: str = VBEE_DEFAULT_VOICE) -> str:
    """
    Sinh 1 file mp3. Trả về tên engine đã dùng.
    Ưu tiên: Vbee → FPT.AI → Google Chirp3-HD → edge-tts
    """
    # 1. Vbee — chất lượng cao nhất, giọng BLV thể thao
    vbee_app_id = os.environ.get("VBEE_APP_ID", "")
    vbee_token  = os.environ.get("VBEE_TOKEN", "")
    if vbee_app_id and vbee_token and _vbee_tts(text, output, vbee_app_id, vbee_token, voice=vbee_voice):
        return f"vbee/{vbee_voice}"

    # 2. FPT.AI — fallback
    fpt_key = os.environ.get("FPT_TTS_API_KEY", "")
    if fpt_key and _fpt_tts(text, output, fpt_key, voice=fpt_voice):
        return f"fpt/{fpt_voice}"

    # 3. Google Chirp3-HD — fallback
    google_key = os.environ.get("GOOGLE_TTS_API_KEY", "")
    if google_key and _google_tts(text, output, google_key, voice=voice_name):
        return f"google/{voice_name.split('-')[-1]}"

    # 4. edge-tts — fallback miễn phí
    if _edge_tts(text, output):
        return "edge-tts"

    raise RuntimeError(f"Không tạo được audio cho: {output.name}")


def generate_all_voices(scenes: list[dict], audio_dir: Path,
                        parallel: bool = True,
                        voice_name: str | None = None,
                        fpt_voice: str = FPT_DEFAULT_VOICE) -> list[dict]:
    """
    Sinh voice cho tất cả scenes song song.
    Vbee ưu tiên với pool 6 giọng nam thể thao quay vòng ngẫu nhiên.

    Returns: list [{id, engine, audio_path}]
    """
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Vbee: chọn ngẫu nhiên 1 giọng thể thao cho cả video
    vbee_voice = random.choice(VBEE_SPORTS_VOICES)
    print(f"  [voice_gen] Vbee voice: {vbee_voice}")

    # Fallback pool (FPT/edge) — chọn ngẫu nhiên nếu Vbee fail
    fallback = random.choice(VOICE_POOL)
    fb_engine = fallback["engine"]
    fb_voice  = fallback["voice"]

    selected_google_voice = voice_name or random.choice(CHIRP3_HD_VOICES)

    def _gen_one(scene: dict) -> dict:
        sid = scene["id"]
        out_path = audio_dir / f"scene_{sid}.mp3"
        if out_path.exists() and out_path.stat().st_size > 500:
            return {"id": sid, "engine": "cached", "audio_path": str(out_path)}

        text = scene["narration"]

        # Thử Vbee trước
        vbee_app_id = os.environ.get("VBEE_APP_ID", "")
        vbee_token  = os.environ.get("VBEE_TOKEN", "")
        if vbee_app_id and vbee_token:
            if _vbee_tts(text, out_path, vbee_app_id, vbee_token, voice=vbee_voice):
                return {"id": sid, "engine": f"vbee/{vbee_voice}", "audio_path": str(out_path)}
            print(f"  [voice_gen] Vbee fail scene {sid}, chuyển fallback")

        # Fallback engine
        if fb_engine == "fpt":
            engine = generate_voice(text, out_path,
                                    voice_name=selected_google_voice,
                                    fpt_voice=fb_voice,
                                    vbee_voice=vbee_voice)
        elif fb_engine == "edge":
            ok = _edge_tts_voice(text, out_path, fb_voice)
            if ok:
                engine = f"edge/{fb_voice.split('-')[-1]}"
            else:
                engine = generate_voice(text, out_path,
                                        voice_name=selected_google_voice,
                                        fpt_voice=fpt_voice,
                                        vbee_voice=vbee_voice)
        else:
            engine = generate_voice(text, out_path,
                                    voice_name=selected_google_voice,
                                    fpt_voice=fpt_voice,
                                    vbee_voice=vbee_voice)

        return {"id": sid, "engine": engine, "audio_path": str(out_path)}

    if parallel and len(scenes) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(scenes))) as ex:
            results = list(ex.map(_gen_one, scenes))
    else:
        results = [_gen_one(sc) for sc in scenes]

    results.sort(key=lambda r: r["id"])
    for r in results:
        print(f"  ✓ scene {r['id']} voice → {r['engine']}")
    return results

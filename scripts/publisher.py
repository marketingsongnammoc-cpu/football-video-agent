"""
scripts/publisher.py — Đăng video lên TikTok + Facebook qua WoopSocial REST API.

Flow:
  1. GET /projects          → lấy project_id đầu tiên
  2. GET /social-accounts   → tìm tài khoản TIKTOK + FACEBOOK đã kết nối
  3. POST /media/upload-sessions → tạo upload session, lấy presigned URLs
  4. PUT {presigned_url}    → upload từng chunk, thu ETag
  5. POST /media/upload-sessions/{id}/complete → finalize, lấy mediaId
  6. POST /posts            → tạo post với media + caption
"""

from __future__ import annotations
import os
import subprocess
import tempfile
import requests
from pathlib import Path

BASE_URL = "https://api.woopsocial.com/v1"
_DEFAULT_PLATFORMS = ["TIKTOK", "FACEBOOK", "YOUTUBE"]

# Chỉ đăng lên kênh thể thao — không được đăng lên kênh sức khỏe
_ALLOWED_ACCOUNT_IDS = {
    "129140003941908480",  # FACEBOOK — Tin Nhanh Thể thao
    "129136862328520704",  # TIKTOK   — thethao247vnn
    "130161624014127104",  # YOUTUBE  — Tin Nhanh Thể Thao 247
}


class WoopSocialPublisher:
    def __init__(self, api_key: str):
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _get(self, path: str, **kw):
        r = self.s.get(f"{BASE_URL}{path}", timeout=30, **kw)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, **kw):
        r = self.s.post(f"{BASE_URL}{path}", timeout=60, **kw)
        r.raise_for_status()
        return r.json()

    # ── Discovery ──────────────────────────────────────────

    def get_project_id(self) -> str:
        projects = self._get("/projects")
        if not projects:
            raise RuntimeError(
                "Chưa có project nào trên WoopSocial. Tạo tại app.woopsocial.com"
            )
        # Dùng project đầu tiên
        pid = projects[0]["id"]
        print(f"  [publish] Project: {projects[0].get('name', pid)}")
        return pid

    def get_social_accounts(self, project_id: str, platforms: list[str]) -> list[dict]:
        accounts = self._get("/social-accounts", params={"projectId": project_id})
        matched = [
            a for a in accounts
            if a.get("platform") in platforms
            and a.get("status") == "CONNECTED"
            and a.get("id") in _ALLOWED_ACCOUNT_IDS
        ]
        if not matched:
            raise RuntimeError(
                f"Không tìm thấy tài khoản thể thao {platforms} đã kết nối. "
                "Kết nối tại app.woopsocial.com"
            )
        for a in matched:
            print(f"  [publish] Account: {a.get('platform')} — {a.get('username', a['id'])}")
        return matched

    # ── Upload ─────────────────────────────────────────────

    def _reencode_30fps(self, video_path: Path) -> Path:
        """Re-encode video lên 30fps cho TikTok (duplicate frames, nhanh)."""
        out = video_path.parent / f"_tiktok_{video_path.name}"
        cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-r", "30",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  [publish] Re-encoded 30fps: {out.name} ({out.stat().st_size//1024}KB)")
        return out

    def upload_video(self, project_id: str, video_path: Path) -> str:
        """Upload video theo chunked multipart, trả về mediaId."""
        file_size = video_path.stat().st_size
        print(f"  [publish] Upload video {file_size / 1024 / 1024:.1f} MB...")

        # 1. Tạo session
        session = self._post("/media/upload-sessions", json={
            "projectId": project_id,
            "fileSizeInBytes": file_size,
        })
        session_id = session["uploadSessionId"]
        parts_info = session["parts"]       # [{partNumber, url}, ...]
        part_size = session["partSizeInBytes"]

        # 2. Upload từng part → thu ETag
        etags = []
        with open(video_path, "rb") as f:
            for part in parts_info:
                chunk = f.read(part_size)
                r = requests.put(part["uploadUrl"], data=chunk, timeout=120)
                r.raise_for_status()
                etag = r.headers.get("ETag", "").strip('"')
                etags.append({"partNumber": part["partNumber"], "etag": etag})
                print(f"    part {part['partNumber']}/{len(parts_info)} ✓")

        # 3. Complete session
        complete = self._post(
            f"/media/upload-sessions/{session_id}/complete",
            json={"parts": etags},
        )
        media_id = complete.get("mediaId") or complete.get("id") or complete.get("media_id")
        if not media_id:
            raise RuntimeError(f"Complete upload không trả về mediaId: {complete}")
        print(f"  [publish] Media ID: {media_id}")
        return media_id

    # ── Publish ────────────────────────────────────────────

    def publish(
        self,
        video_path: Path,
        caption: str,
        platforms: list[str] | None = None,
        scheduled_at: str | None = None,
    ) -> dict:
        """
        Upload video và đăng lên các platforms.

        Args:
            video_path: đường dẫn file video.mp4
            caption: nội dung bài đăng
            platforms: ["TIKTOK", "FACEBOOK"] (default)
            scheduled_at: ISO 8601 UTC string để lên lịch, None = đăng ngay

        Returns:
            dict response từ WoopSocial (chứa post id)
        """
        if platforms is None:
            platforms = _DEFAULT_PLATFORMS

        # 1. Project + accounts
        project_id = self.get_project_id()
        accs = self.get_social_accounts(project_id, platforms)

        # 2. Re-encode 30fps (TikTok yêu cầu min 23fps, Facebook/YouTube cũng tốt hơn)
        tmp_path = self._reencode_30fps(video_path)

        # 3. Upload video
        try:
            media_id = self.upload_video(project_id, tmp_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        # 4. Build platform-specific social account entries (discriminator = platform)
        social_accounts = []
        for acc in accs:
            entry: dict = {"platform": acc["platform"], "socialAccountId": acc["id"]}
            if acc["platform"] == "TIKTOK":
                entry.update({
                    "postType": "VIDEO",
                    "privacyLevel": "PUBLIC_TO_EVERYONE",
                    "allowComment": True,
                    "allowDuet": True,
                    "allowStitch": True,
                    "isYourBrand": False,
                    "isBrandedContent": False,
                    "autoAddMusic": False,
                })
            elif acc["platform"] == "FACEBOOK":
                entry["postType"] = "REEL"
            elif acc["platform"] == "YOUTUBE":
                entry.update({"postType": "VIDEO", "privacy": "public", "title": caption[:100]})
            social_accounts.append(entry)

        schedule = (
            {"type": "SCHEDULE_FOR_LATER", "scheduledFor": scheduled_at}
            if scheduled_at
            else {"type": "PUBLISH_NOW"}
        )
        if scheduled_at:
            print(f"  [publish] Lên lịch đăng lúc {scheduled_at}")

        result = self._post("/posts", json={
            "content": [{"text": caption, "media": [{"type": "MEDIA_LIBRARY", "mediaId": media_id}]}],
            "schedule": schedule,
            "socialAccounts": social_accounts,
        })
        print(f"  [publish] ✓ Đăng thành công! Post ID: {result.get('id', '?')}")
        return result


# ── Caption helper ─────────────────────────────────────────

def make_caption(title_vi: str, scenes: list[dict]) -> str:
    """
    Dùng Gemini để viết caption hay cho TikTok/Facebook/YouTube.
    Fallback về caption đơn giản nếu API lỗi.
    """
    from google import genai
    from google.genai import types as genai_types

    narrations = "\n".join(
        f"- {s.get('narration', '')}" for s in scenes if s.get("narration")
    )
    headlines = " | ".join(
        s.get("headline", "") for s in scenes if s.get("headline")
    )

    prompt = f"""Viết 1 caption duy nhất cho video bóng đá đăng lên TikTok và Facebook.
Viết bằng tiếng Việt, ngắn gọn, hấp dẫn.

Tiêu đề: {title_vi}
Nội dung chính: {headlines}
Chi tiết: {narrations[:500]}

Cấu trúc caption (3-4 dòng tổng cộng):
- Dòng 1: Hook mạnh, emoji + câu gây tò mò (không bắt đầu bằng tên cầu thủ/đội)
- Dòng 2: Điểm nhấn nội dung nóng nhất
- Dòng cuối: 4-5 hashtag

Chỉ trả về đúng 1 caption hoàn chỉnh, KHÔNG đánh số, KHÔNG giải thích, KHÔNG markdown."""

    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(max_output_tokens=300, temperature=0.7),
        )
        caption = resp.text.strip()
        print(f"  [publish] Caption AI:\n{caption}")
        return caption
    except Exception as e:
        print(f"  [publish] Caption AI lỗi ({e}), dùng caption đơn giản.")
        hashtags = "#bongda #football #tintucbongda #tiktokbongda"
        return f"{title_vi}\n\n{hashtags}"


# ── Public entry point ─────────────────────────────────────

def publish_video(video_path: Path, caption: str, delay_minutes: int = 0) -> dict | None:
    """
    Đăng video lên TikTok + Facebook.
    delay_minutes=0 → đăng ngay; >0 → lên lịch sau N phút.
    Trả về None nếu WOOPSOCIAL_API_KEY chưa cấu hình (silent skip).
    """
    from datetime import datetime, timezone, timedelta

    api_key = os.environ.get("WOOPSOCIAL_API_KEY", "").strip()
    if not api_key:
        print("\n  [publish] WOOPSOCIAL_API_KEY chưa cấu hình → bỏ qua bước đăng.")
        return None

    scheduled_at = None
    if delay_minutes > 0:
        scheduled_at = (
            datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        pub = WoopSocialPublisher(api_key)
        return pub.publish(video_path, caption, scheduled_at=scheduled_at)
    except requests.HTTPError as e:
        body = e.response.text[:300] if e.response is not None else ""
        print(f"\n  [publish] HTTP lỗi: {e} — {body}")
        return None
    except Exception as e:
        print(f"\n  [publish] Lỗi đăng video: {e}")
        return None

"""
script_gen.py — Sinh script N scenes từ bài viết bằng Claude API.

Số scenes = num_images (theo số hình lấy được từ bài).

Narration words/scene tự động co giãn theo số scenes:
- 3 scenes  → 35-50 từ/scene (~10s mỗi scene)
- 5 scenes  → 25-35 từ/scene (~7s/scene)
- 8 scenes  → 18-25 từ/scene (~5s/scene)
- 12+ scenes → 10-16 từ/scene (~3.5s/scene)
"""

from __future__ import annotations
import json
import os
import re
import time
from typing import Optional

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None


ACCENT_ROTATION = ["emerald", "cyan", "amber", "red"]
VALID_TAGS = [
    "⚽ TRẬN ĐẤU",
    "🏆 GIẢI ĐẤU",
    "🔄 CHUYỂN NHƯỢNG",
    "👤 NGÔI SAO",
    "🎯 CHIẾN THUẬT",
    "🇻🇳 BÓNG ĐÁ VN",
    "⚡ BREAKING",
]

MAX_HEADLINE_CHARS = 50
MAX_HEADLINE_WORDS = 8
MAX_SUBTEXT_CHARS = 90
MAX_SUBTEXT_WORDS = 16


def _narration_word_range(num_scenes: int) -> tuple[int, int]:
    """Khoảng từ/scene phù hợp để giữ video ~30-60s."""
    if num_scenes <= 3:
        return 30, 55
    elif num_scenes <= 5:
        return 22, 45
    elif num_scenes <= 8:
        return 16, 32
    elif num_scenes <= 12:
        return 12, 25
    else:
        return 8, 20


def _build_system_prompt(num_scenes: int) -> str:
    min_w, max_w = _narration_word_range(num_scenes)
    return f"""Bạn là biên tập viên video TikTok bóng đá — chuyên viết nội dung viral, thu hút.
Nhiệm vụ: biến 1 bài báo thành {num_scenes} cảnh video ngắn CỰC HẤP DẪN.

QUY TẮC NỘI DUNG (quan trọng nhất):
1. Headline và subtext KHÔNG cần copy từ bài gốc — hãy VIẾT LẠI thành hook giật tít,
   gây tò mò, kích thích người xem dừng lại. Dùng câu hỏi, số liệu gây sốc, đối lập.
2. Narration cũng KHÔNG cần copy nguyên văn — kể chuyện hấp dẫn hơn bài gốc,
   như đang kể cho bạn bè nghe, không phải đọc báo cáo.
3. Scene 1 PHẢI là hook mạnh nhất — câu hỏi/sự kiện gây sốc khiến người xem phải xem tiếp.
4. Scene cuối: cảm xúc/ý nghĩa lớn hơn — để lại dư âm cho người xem.

QUY TẮC FORMAT:
5. Output JSON thuần — KHÔNG markdown, KHÔNG giải thích.
6. Headline ≤ 7 từ và ≤ 45 ký tự — ngắn, đập vào mắt ngay lập tức.
7. Subtext ≤ 14 từ và ≤ 75 ký tự — bổ sung thông tin, không lặp headline.
8. Narration {min_w}-{max_w} từ — giọng BLV sôi nổi, cuốn hút.
9. Tag chọn 1 trong: ⚽ TRẬN ĐẤU, 🏆 GIẢI ĐẤU, 🔄 CHUYỂN NHƯỢNG, 👤 NGÔI SAO,
   🎯 CHIẾN THUẬT, 🇻🇳 BÓNG ĐÁ VN, ⚡ BREAKING. Đa dạng, không lặp liên tiếp.
10. Giữ nguyên tên cầu thủ, CLB. Việt hóa giải đấu (Premier League → Ngoại hạng Anh).
11. Số liệu giữ nguyên (3-1, hat-trick, 90+5'). KHÔNG dùng "Hôm nay", "Mới đây".
12. Mỗi scene 1 góc nhìn riêng — KHÔNG lặp ý giữa các scene.

FORMAT OUTPUT (đúng JSON, KHÔNG thêm gì):
{{
  "scenes": [
    {{"headline": "...", "subtext": "...", "narration": "...", "tag": "..."}}
  ]
}}"""


def _count_words(text: str) -> int:
    return len(text.strip().split())


def _validate_scene(scene: dict, narration_range: tuple[int, int]) -> list[str]:
    errors = []
    headline = scene.get("headline", "").strip()
    subtext = scene.get("subtext", "").strip()
    narration = scene.get("narration", "").strip()
    tag = scene.get("tag", "").strip()
    min_w, max_w = narration_range

    if not headline:
        errors.append("headline rỗng")
    elif len(headline) > MAX_HEADLINE_CHARS:
        errors.append(f"headline quá dài ({len(headline)} > {MAX_HEADLINE_CHARS} ký tự)")
    elif _count_words(headline) > MAX_HEADLINE_WORDS:
        errors.append(f"headline quá nhiều từ ({_count_words(headline)} > {MAX_HEADLINE_WORDS})")

    if not subtext:
        errors.append("subtext rỗng")
    elif len(subtext) > MAX_SUBTEXT_CHARS:
        errors.append(f"subtext quá dài ({len(subtext)} > {MAX_SUBTEXT_CHARS} ký tự)")
    elif _count_words(subtext) > MAX_SUBTEXT_WORDS:
        errors.append(f"subtext quá nhiều từ ({_count_words(subtext)} > {MAX_SUBTEXT_WORDS})")

    if not narration:
        errors.append("narration rỗng")
    else:
        nw = _count_words(narration)
        if nw < min_w:
            errors.append(f"narration quá ngắn ({nw} < {min_w} từ)")
        elif nw > max_w:
            errors.append(f"narration quá dài ({nw} > {max_w} từ)")

    if tag not in VALID_TAGS:
        errors.append(f"tag không hợp lệ: '{tag}'")
    return errors


def _extract_json(text: str) -> dict:
    # Strip Gemini thinking blocks
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try markdown code block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try raw JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start:end+1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Try fixing common issues: trailing commas, unescaped newlines
            candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
            candidate = re.sub(r"\n", " ", candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
    raise ValueError(f"Không parse được JSON:\n{text[:500]}")


def _call_gemini(title: str, body: str, num_scenes: int,
                 retry_feedback: Optional[str] = None) -> dict:
    if genai is None:
        raise RuntimeError("google-genai chưa cài")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Thiếu GEMINI_API_KEY")

    client = genai.Client(api_key=api_key)
    user_msg = f"TIÊU ĐỀ:\n{title}\n\nNỘI DUNG:\n{body[:4000]}\n\nSinh đúng {num_scenes} scenes."
    if retry_feedback:
        user_msg += f"\n\nLƯU Ý: {retry_feedback}"

    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_msg,
        config=genai_types.GenerateContentConfig(
            system_instruction=_build_system_prompt(num_scenes),
            max_output_tokens=4096,
            temperature=0.4,
        ),
    )
    return _extract_json(resp.text)


def _gemini_fallback(title: str, body: str, num_scenes: int) -> dict:
    """Fallback với prompt đơn giản hơn — ít lỗi validation hơn."""
    if genai is None:
        raise RuntimeError("google-genai chưa cài")
    min_w, max_w = _narration_word_range(num_scenes)
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
    prompt = f"""Tạo {num_scenes} scenes video TikTok bóng đá từ bài báo này.

Bài: {title}
Nội dung: {body[:2000]}

Yêu cầu mỗi scene:
- headline: tối đa 6 từ, ngắn gọn, giật gân (KHÔNG được dài hơn)
- subtext: tối đa 10 từ, bổ sung cho headline
- narration: {min_w}-{max_w} từ, giọng BLV sôi nổi
- tag: chọn 1 trong [⚽ TRẬN ĐẤU, 🏆 GIẢI ĐẤU, 🔄 CHUYỂN NHƯỢNG, 👤 NGÔI SAO, 🎯 CHIẾN THUẬT, 🇻🇳 BÓNG ĐÁ VN, ⚡ BREAKING]

Scene 1 phải là hook mạnh thu hút người xem tiếp. Đa dạng tag giữa các scenes.

Trả về JSON:
{{"scenes": [{{"headline": "...", "subtext": "...", "narration": "...", "tag": "..."}}]}}"""

    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            max_output_tokens=2048,
            temperature=0.3,
        ),
    )
    return _extract_json(resp.text)


def generate_script(title: str, body: str, num_scenes: int,
                    max_retries: int = 3) -> list[dict]:
    """
    Sinh script num_scenes scenes.

    Args:
        title: tiêu đề tiếng Việt
        body: nội dung tiếng Việt
        num_scenes: số scenes = số hình từ bài
    """
    if num_scenes < 1:
        raise ValueError(f"num_scenes phải ≥ 1, nhận: {num_scenes}")

    narration_range = _narration_word_range(num_scenes)
    print(f"  [script_gen] num_scenes={num_scenes}, narration {narration_range[0]}-{narration_range[1]} từ/scene")

    last_errors = None
    feedback = None

    for attempt in range(max_retries):
        try:
            print(f"  [script_gen] Gọi Gemini API (lần {attempt + 1}/{max_retries})...")
            result = _call_gemini(title, body, num_scenes, retry_feedback=feedback)
            scenes_raw = result.get("scenes", [])

            if len(scenes_raw) != num_scenes:
                feedback = f"Cần đúng {num_scenes} scenes, output có {len(scenes_raw)}."
                last_errors = [feedback]
                print(f"  [script_gen] ⚠ {feedback}, retry...")
                continue

            all_errors = []
            for i, s in enumerate(scenes_raw):
                errs = _validate_scene(s, narration_range)
                if errs:
                    all_errors.extend([f"Scene {i+1}: {e}" for e in errs])

            if not all_errors:
                scenes = []
                for i, s in enumerate(scenes_raw):
                    scenes.append({
                        "id": f"{i+1:02d}",
                        "headline": s["headline"].strip(),
                        "subtext": s["subtext"].strip(),
                        "narration": s["narration"].strip(),
                        "tag": s["tag"].strip(),
                        "accent": ACCENT_ROTATION[i % len(ACCENT_ROTATION)],
                    })
                print(f"  [script_gen] ✓ Sinh {num_scenes} scenes thành công")
                return scenes
            else:
                last_errors = all_errors
                feedback = (
                    "Vi phạm giới hạn:\n" + "\n".join(f"- {e}" for e in all_errors[:5]) +
                    f"\nViết NGẮN HƠN. Narration {narration_range[0]}-{narration_range[1]} từ."
                )
                print(f"  [script_gen] ⚠ {len(all_errors)} lỗi, retry...")
                time.sleep(1)

        except Exception as e:
            print(f"  [script_gen] ⚠ Gemini lỗi: {e}")
            last_errors = [str(e)]
            time.sleep(2 ** attempt)

    print("  [script_gen] Fallback Gemini simple prompt...")
    try:
        result = _gemini_fallback(title, body, num_scenes)
        scenes = []
        for i, s in enumerate(result["scenes"]):
            scenes.append({
                "id": f"{i+1:02d}",
                "headline": s["headline"],
                "subtext": s["subtext"],
                "narration": s["narration"],
                "tag": s["tag"],
                "accent": ACCENT_ROTATION[i % len(ACCENT_ROTATION)],
            })
        print("  [script_gen] ✓ Fallback OK")
        return scenes
    except Exception as e:
        raise RuntimeError(
            f"script_gen failed sau {max_retries} retry + fallback. "
            f"Errors: {last_errors}. Fallback: {e}"
        )

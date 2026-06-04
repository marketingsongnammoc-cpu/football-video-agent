"""
translator.py — Dịch bài tiếng Anh/Tây Ban Nha sang tiếng Việt bằng Gemini Flash.

Quy tắc:
- Giữ nguyên tên cầu thủ, CLB
- Việt hóa giải đấu (Premier League → Ngoại hạng Anh, La Liga giữ nguyên)
- Giữ nguyên: clean sheet, hat-trick, VAR, offside, số liệu (3-1, 90+5')
- Viết lại theo tone Việt — KHÔNG dịch sát
- Tone tabloid → giật gân nhưng lịch sự (không soi mói cá nhân)

Retry 3 lần với exponential backoff. Fail → raise RuntimeError.
"""

from __future__ import annotations
import os
import re
import sys
import time
from typing import Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None


SYSTEM_PROMPT_VI = """Bạn là biên dịch viên báo bóng đá Việt Nam.
Nhiệm vụ: dịch bài báo bóng đá từ tiếng Anh / Tây Ban Nha sang tiếng Việt.

QUY TẮC:
1. Giữ nguyên: tên cầu thủ, CLB (vd: "Manchester United", "Real Madrid").
2. Việt hóa giải đấu phổ biến: Premier League → "Ngoại hạng Anh", Champions League → "Champions League", La Liga giữ nguyên, Bundesliga giữ nguyên.
3. Việt hóa vị trí: striker → tiền đạo, defender → hậu vệ, midfielder → tiền vệ.
4. Giữ nguyên thuật ngữ: clean sheet, hat-trick, VAR, offside, penalty.
5. Giữ nguyên số liệu: 3-1, 90+5', tỉ số, phút.
6. Tone báo thể thao VN — sống động, không khô khan. KHÔNG dịch sát từng câu.
7. Output ĐÚNG format sau (text thuần, KHÔNG markdown, KHÔNG giải thích):

TIÊU ĐỀ:
[Tiêu đề tiếng Việt]

NỘI DUNG:
[Nội dung tiếng Việt, giữ paragraph break bằng dòng trống]"""


def _call_gemini_translate(title_en: str, body_en: str, source_lang: str) -> tuple[str, str]:
    if genai is None:
        raise RuntimeError("google-genai package chưa cài")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Thiếu GEMINI_API_KEY")

    client = genai.Client(api_key=api_key)
    lang_name = {"en": "tiếng Anh", "es": "tiếng Tây Ban Nha"}.get(source_lang, source_lang)
    user_msg = (
        f"Dịch bài báo {lang_name} dưới đây sang tiếng Việt theo quy tắc đã nêu.\n\n"
        f"TITLE:\n{title_en}\n\n"
        f"BODY:\n{body_en[:4000]}"
    )

    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_msg,
        config=genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT_VI,
            max_output_tokens=3000,
            temperature=0.3,
        ),
    )
    text = resp.text

    m_title = re.search(r"TIÊU ĐỀ:\s*(.+?)(?:\n\nNỘI DUNG:|$)", text, re.DOTALL | re.IGNORECASE)
    m_body  = re.search(r"NỘI DUNG:\s*(.+)", text, re.DOTALL | re.IGNORECASE)
    if not m_title or not m_body:
        raise ValueError(f"Không parse được output dịch:\n{text[:300]}")

    return m_title.group(1).strip(), m_body.group(1).strip()


def _heuristic_check_vi(text: str, threshold: float = 0.7) -> bool:
    """Heuristic: text có vẻ tiếng Việt nếu chứa nhiều ký tự có dấu."""
    if not text:
        return False
    vi_chars = re.findall(
        r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀ-Ỹ]",
        text,
    )
    return len(vi_chars) / max(len(text), 1) > 0.02


def translate_article(title: str, body: str, source_lang: str, max_retries: int = 3) -> tuple[str, str]:
    """
    Dịch (title, body) sang tiếng Việt.

    Returns: (title_vi, body_vi)
    Raises: RuntimeError nếu fail sau retry.
    """
    if source_lang == "vi":
        return title, body

    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            print(f"  [translator] Dịch {source_lang}→vi (lần {attempt + 1}/{max_retries})...")
            title_vi, body_vi = _call_gemini_translate(title, body, source_lang)
            if not _heuristic_check_vi(body_vi):
                raise ValueError("Output không có vẻ là tiếng Việt")
            print(f"  [translator] ✓ Dịch thành công")
            return title_vi, body_vi
        except Exception as e:
            last_error = e
            print(f"  [translator] ⚠ Lỗi: {e}. Retry...")
            time.sleep(2 ** attempt)

    raise RuntimeError(f"Translator fail sau {max_retries} lần. Lỗi cuối: {last_error}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(r"d:\claude\football-video-agent\config\.env")
    title = "Manchester United crash to shock defeat against Brentford"
    body = "Manchester United fell to a surprising 3-1 defeat against Brentford at the Gtech Community Stadium on Saturday..."
    t, b = translate_article(title, body, "en")
    print("TITLE:", t)
    print("BODY:", b[:300])

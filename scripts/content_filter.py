"""
content_filter.py — Filter 2 tầng cho nguồn tabloid.

Tầng 1: regex blacklist trong URL / tiêu đề (nhanh, không cần API)
Tầng 2: Claude classifier kiểm tra body sau khi fetch

Bài fail filter → caller skip, log vào skipped.json.
"""

from __future__ import annotations
import os
import re

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None


# Tầng 1: regex blacklist
BLACKLIST_PATTERNS = re.compile(
    r"\b("
    # Vợ / bạn gái / quan hệ
    r"wife|wives|girlfriend|gf|wag|wags|partner|fiancée|fiancee|"
    r"vợ|bạn gái|hôn thê|tình cảm|tình tay ba|"
    # Con cái / trẻ vị thành niên
    r"child|children|kid|kids|son|daughter|baby|babies|toddler|niño|niña|hijo|hija|"
    r"con trai|con gái|con cái|trẻ em|trẻ nhỏ|vị thành niên|"
    # Bạo lực gia đình / lạm dụng
    r"domestic abuse|domestic violence|abuse|assault|"
    r"bạo hành|bạo lực gia đình|lạm dụng|"
    # Underage
    r"underage|minor|teenager dating|"
    r"chưa thành niên|dưới tuổi"
    r")\b",
    re.IGNORECASE,
)


def passes_tier1(url: str, title: str) -> tuple[bool, str | None]:
    """
    Tầng 1: kiểm tra URL + title.
    Returns: (passed, reason_if_failed)
    """
    text = f"{url} {title}"
    m = BLACKLIST_PATTERNS.search(text)
    if m:
        return False, f"tier1_blacklist:{m.group(1).lower()}"
    return True, None


CLAUDE_FILTER_PROMPT = """Bạn là người kiểm duyệt nội dung.
Đọc bài báo dưới đây và phân loại có thuộc các loại bị cấm KHÔNG.

CÁC LOẠI BỊ CẤM:
A. Scandal liên quan gia đình, vợ/bạn gái, chuyện riêng tư vợ chồng cầu thủ
B. Tin về con cái cầu thủ (kể cả tích cực — sinh nhật, đi học, v.v.)
C. Bạo lực gia đình, lạm dụng tình dục/thể chất
D. Nội dung liên quan trẻ vị thành niên dưới 18 tuổi

GIỮ LẠI (KHÔNG cấm):
- Lối sống xa hoa (xe, đồng hồ, biệt thự — của bản thân cầu thủ)
- Drama phòng thay đồ giữa cầu thủ với HLV/đồng đội
- Tin đồn chuyển nhượng
- Phản ứng cầu thủ trên MXH về bóng đá
- Phong độ, tâm trạng, nghỉ thi đấu, chấn thương
- Tiệc tùng / sự kiện cá nhân (không liên quan con/gia đình)

OUTPUT: chỉ trả về 1 ký tự duy nhất:
- "Y" nếu bài thuộc loại bị cấm (A/B/C/D)
- "N" nếu không thuộc loại nào — giữ lại
"""


def passes_tier2(title: str, body: str) -> tuple[bool, str | None]:
    """
    Tầng 2: Claude classifier. Chỉ chạy khi tier1 đã pass.
    Returns: (passed, reason_if_failed)
    """
    if genai is None:
        return True, None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return True, None

    try:
        client = genai.Client(api_key=api_key)
        user_msg = f"TIÊU ĐỀ:\n{title}\n\nNỘI DUNG (rút gọn):\n{body[:2000]}"
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_msg,
            config=genai_types.GenerateContentConfig(
                system_instruction=CLAUDE_FILTER_PROMPT,
                max_output_tokens=5,
                temperature=0.0,
            ),
        )
        verdict = resp.text.strip().upper()
        if verdict.startswith("Y"):
            return False, "tier2_gemini_classifier_reject"
        return True, None
    except Exception as e:
        print(f"  [content_filter] tier2 Gemini lỗi: {e}. Bỏ qua tier 2.")
        return True, None


def check_article(url: str, title: str, body: str, is_tabloid: bool) -> tuple[bool, str | None]:
    """
    Kiểm tra bài có pass cả 2 tầng không.

    Args:
        is_tabloid: True nếu là nguồn tabloid → chạy đầy đủ filter

    Returns: (passed, reason_if_failed)
    """
    if not is_tabloid:
        # Nguồn chính thống → bỏ qua filter tabloid
        return True, None

    # Tier 1
    passed, reason = passes_tier1(url, title)
    if not passed:
        return False, reason

    # Tier 2
    passed, reason = passes_tier2(title, body)
    if not passed:
        return False, reason

    return True, None

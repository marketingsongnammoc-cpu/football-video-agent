"""
scripts/hot_scorer.py — Chấm điểm độ HOT cho bài viết bóng đá.

Hỗ trợ cả tiêu đề tiếng Việt (nguồn VN) và tiếng Anh (nguồn quốc tế).
Ưu tiên: Siêu sao (Messi/Ronaldo/Yamal) > World Cup 2026 > C1 > Tin shock/chuyển nhượng
Loại bỏ: soi kèo, dự đoán, lịch thi đấu

Ghi chú: ĐTQG Việt Nam hiện không thi đấu → không ưu tiên.
Bật lại khi ĐTQG VN có lịch thi đấu trở lại.
"""

from __future__ import annotations

_SCORE_RULES: list[tuple[list[str], int]] = [
    # Tier 1A — Siêu sao cực nổi tiếng (đảm bảo views)
    (["messi", "ronaldo", "yamal", "lamine yamal"], 30),
    (["mbappe", "mbappé", "vinicius", "vinicius jr", "haaland", "bellingham"], 25),
    (["salah", "de bruyne", "neymar", "lewandowski", "pedri", "saka",
      "rashford", "rodri", "kylian"], 20),

    # Tier 1B — World Cup 2026 (sự kiện lớn nhất)
    (["world cup 2026", "world cup", "fifa world cup", "vòng loại world cup",
      "world cup qualifier", "world cup squad", "world cup final"], 28),

    # Tier 1C — Champions League (C1)
    (["champions league", "cúp c1", "c1", "ucl final", "ucl semi",
      "chung kết c1", "bán kết c1", "champions league final",
      "champions league semi"], 25),

    # Tier 2A — Chuyển nhượng xác nhận (VI + EN)
    (["chốt hợp đồng", "ký hợp đồng", "chính thức", "hoàn tất", "xác nhận chuyển nhượng",
      "rời barca", "rời real", "rời man", "gia nhập"], 20),
    (["confirmed", "done deal", "signs for", "agrees deal", "completes move",
      "transfer complete", "officially joins", "medical done", "joins"], 20),

    # Tier 2B — Tin nóng nhân sự (VI + EN)
    (["sa thải", "bổ nhiệm", "từ chức", "chia tay clb", "hủy hợp đồng"], 20),
    (["sacked", "fired", "appointed", "resigns", "quits", "leaves club",
      "new manager", "new coach", "takeover"], 20),

    # Tier 2C — Scandal / Tin sốc
    (["bị tấn công", "scandal", "bắt giữ", "điều tra", "phạt nặng",
      "bị đuổi", "thẻ đỏ tranh cãi", "cãi nhau", "đánh nhau"], 18),
    (["arrested", "investigation", "banned", "red card controversy",
      "fight", "attack", "scandal", "suspended"], 18),

    # Tier 2D — Chấn thương nghiêm trọng
    (["phẫu thuật", "chấn thương nặng", "chia tay mùa giải", "lỡ world cup",
      "surgery", "out for season", "serious injury", "miss world cup",
      "miss euros", "career threatening"], 18),

    # Tier 2E — Kỷ lục / kỳ tích
    (["hat-trick", "kỷ lục", "lịch sử", "lần đầu tiên", "vô địch", "lên ngôi", "danh hiệu",
      "record", "history", "first ever", "trophy", "title", "champion"], 15),

    # Tier 3A — Giải lớn khác
    (["europa league", "conference league", "copa del rey", "fa cup final",
      "carabao cup final", "serie a", "la liga", "bundesliga"], 12),
    (["premier league", "ngoại hạng anh", "ligue 1"], 10),

    # Tier 3B — ĐTQG Việt Nam (tạm giảm — không đá hiện tại)
    (["đội tuyển việt nam", "đtqg", "tuyển việt nam", "tuyển quốc gia"], 10),
    (["u23 việt", "u20 việt", "u17 việt", "đội tuyển u23", "đội tuyển u20"], 8),
    (["aff cup", "asian cup", "sea games", "asean cup"], 10),

    # Tier 3C — Bóng đá VN nội địa
    (["v-league", "v.league", "hà nội fc", "hagl", "viettel", "b.bình dương"], 5),

    # Tier 4 — Kết quả thông thường
    (["kết quả", "tỷ số", "bàn thắng", "chiến thắng"], 3),
    (["scores", "wins", "beats", "draws", "defeats"], 3),
]

_BLACKLIST_TITLE: list[str] = [
    # Tiếng Việt — soi kèo / dự đoán
    "soi kèo", "dự đoán", "nhận định trước trận", "kèo nhà cái",
    "lịch thi đấu", "lịch phát sóng", "xem trực tiếp ở đâu",
    "trực tiếp bóng đá", "link xem",
    # Tiếng Việt — preview / hứa hẹn trước trận
    "trước trận", "trước khi thi đấu", "hứa hẹn", "tự tin sẽ",
    "sẽ ghi bàn", "sẽ vô địch", "sẽ thắng", "quyết tâm",
    "chuẩn bị cho", "chờ đợi", "sắp diễn ra", "sắp đối đầu",
    "nhận định", "dự kiến đội hình",
    # Tiếng Việt — điểm tin / tổng hợp / listicle
    "điểm tin", "tổng hợp", "nhìn lại", "hành trình",
    "top ", "danh sách", "những điều", " điều bạn",
    " lý do ", " cầu thủ xuất sắc", " cầu thủ hay nhất",
    "một năm", "sau khi",
    # Tiếng Anh — preview / pre-match
    "will score", "promises", "vows to", "ahead of", "before the",
    "set to ", "hopes to", "confident of", "targeting",
    "preview", "predicted xi", "predicted lineup", "team news",
    "press conference", "what to expect",
    # Tiếng Anh — listicle / roundup
    "quiz", "fantasy", "predict", "best xi", "all you need to know",
    "history of", "live stream", "watch online", "where to watch",
    "top 10", "top 5", "top 20", "10 ", "five ", "ten ",
    "players to watch", "players who", "things you",
    "reasons why", "facts about", "in numbers", "by numbers",
    "ranked", "ranking", "power ranking", "rating",
    "round up", "roundup", "wrap up", "wrapup",
    "best players", "worst players", "every ", "all the ",
]

_PENALTY_RULES: list[tuple[list[str], int]] = [
    (["bảng xếp hạng", "thống kê", "số liệu", "phong độ 5 trận",
      "stats", "statistics", "rankings"], 10),
]


def score_article(title: str, position: int = 99) -> int:
    """
    Chấm điểm bài viết theo tiêu đề + vị trí (recency).
    position: vị trí trong danh sách homepage (0 = mới nhất).
    Score = -99 nghĩa là loại bỏ.
    """
    t = title.lower()
    if any(kw in t for kw in _BLACKLIST_TITLE):
        return -99
    score = 0
    for keywords, pts in _SCORE_RULES:
        if any(kw in t for kw in keywords):
            score += pts
    for keywords, pts in _PENALTY_RULES:
        if any(kw in t for kw in keywords):
            score -= pts
    # Recency boost: bài mới hơn được ưu tiên hơn nếu điểm ngang nhau
    if position <= 3:
        score += 20
    elif position <= 7:
        score += 12
    elif position <= 14:
        score += 6
    return score


def pick_hottest(articles: list[dict], processed: dict) -> dict | None:
    """Chọn bài hot nhất chưa xử lý từ list [{url, title}]."""
    candidates = []
    for a in articles:
        if a["url"] in processed:
            continue
        s = score_article(a.get("title", ""))
        if s >= 5:
            candidates.append((s, a))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]

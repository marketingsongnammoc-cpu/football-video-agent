# Football Video Agent — Hướng dẫn cho Claude Code

## Phạm vi làm việc
**Chỉ đọc và thao tác trong thư mục này:** `D:\claude\football-video-agent\`

Không dùng bất kỳ tool nào thuộc dự án khác:
- **KHÔNG dùng** `mcp__post-bridge__*` (thuộc AquaZone)
- **KHÔNG dùng** `mcp__claude_ai_Google_Drive__*` (thuộc AquaZone)
- **KHÔNG đọc** file ngoài folder này

---

## Tổng quan dự án
Tự động tạo video tin tức bóng đá và đăng lên TikTok, Facebook, YouTube.

**Pipeline:** Fetch bài báo → Dịch (nếu EN/ES) → Tải ảnh → Sinh script → Render frame → TTS voice → Compose video → Đăng WoopSocial

---

## Cách chạy

```bash
python main.py                          # Auto-fetch, tạo 1 video
python main.py --max 3                  # Tạo tối đa 3 video
python main.py --url "https://..."      # Bài cụ thể
python main.py --source vnexpress       # 1 nguồn cụ thể
python main.py --branch vn              # Chỉ nhánh VN
python main.py --dry-run                # Chỉ sinh script, không render
python main.py --no-publish             # Tạo video nhưng không đăng
python main.py --recompose <folder>     # Re-compose từ folder có sẵn
python publish_one.py <folder>          # Đăng 1 video từ folder đã render
python random_scheduler.py              # Sinh lịch ngẫu nhiên cho hôm nay
```

---

## Cấu trúc thư mục

```
D:\claude\football-video-agent\
├── main.py                  ← Entry point
├── publish_one.py           ← Đăng thủ công 1 video
├── random_scheduler.py      ← Tạo lịch đăng ngẫu nhiên hàng ngày
├── smart_runner.py          ← Chạy qua cửa sổ 30 phút (legacy)
├── config/
│   ├── .env                 ← API keys
│   └── sources.json         ← Nguồn tin (enable/disable từng nguồn)
├── scripts/
│   ├── fetcher/             ← Adapter từng nguồn tin
│   ├── content_filter.py    ← Lọc bài (Gemini)
│   ├── translator.py        ← Dịch EN/ES → VI (Gemini)
│   ├── script_gen.py        ← Sinh script scenes (Gemini, fallback Claude Haiku)
│   ├── scene_renderer.py    ← Render frame ảnh + overlay
│   ├── composer.py          ← Ghép video ffmpeg
│   ├── voice_gen.py         ← TTS (Vbee + Google TTS fallback)
│   ├── hot_scorer.py        ← Chấm điểm độ hot bài báo
│   ├── image_finder.py      ← Tìm ảnh Pexels (Mode B)
│   └── publisher.py         ← Đăng lên WoopSocial
├── data/
│   ├── processed.json       ← URL đã xử lý (tránh trùng)
│   └── skipped.json         ← URL bị skip + lý do
├── logs/
│   └── daily.log            ← Log toàn bộ hoạt động (UTF-16)
└── output/
    └── YYYY-MM-DD_HHMMSS_slug/   ← Folder mỗi video
        ├── video.mp4
        ├── script.json
        ├── source.json
        ├── images/
        ├── audio/
        └── frames/
```

---

## API Keys (config/.env)

| Key | Dùng cho |
|-----|---------|
| `ANTHROPIC_API_KEY` | Claude API (fallback script_gen) |
| `GEMINI_API_KEY` | Dịch, sinh script, content filter (main) |
| `WOOPSOCIAL_API_KEY` | Đăng video lên mạng xã hội |
| `GOOGLE_TTS_API_KEY` | Google TTS voice (primary) |
| `VBEE_APP_ID` + `VBEE_TOKEN` | Vbee TTS voice (primary pool) |
| `PEXELS_API_KEY` | Tìm ảnh Mode B |
| `FPT_TTS_API_KEY` | FPT TTS (legacy, không dùng chính) |

---

## Nguồn tin (config/sources.json)

Hiện chỉ **vnexpress** enabled. Các nguồn khác disabled:

| Nguồn | Branch | Ngôn ngữ | Trạng thái |
|-------|--------|----------|-----------|
| vnexpress | vn | vi | ✅ enabled |
| bongda | vn | vi | disabled |
| tuoitre | vn | vi | disabled |
| thanhnien | vn | vi | disabled |
| goal | international | en | disabled |
| thesun/dailymail/mirror | tabloid | en | disabled |
| marca/donbalon | tabloid | es | disabled |

---

## WoopSocial — Kênh đăng

**CHỈ đăng lên 3 kênh thể thao này:**

| Platform | Account ID | Tên kênh |
|----------|-----------|---------|
| FACEBOOK | 129140003941908480 | Tin Nhanh Thể thao |
| TIKTOK | 129136862328520704 | thethao247vnn |
| YOUTUBE | 130161624014127104 | Tin Nhanh Thể Thao 247 |

**KHÔNG đăng** lên kênh sức khỏe (suckhoe24747, Quà Tặng Cho Sức Khoẻ).

**Lưu ý YouTube:** WoopSocial có quota giới hạn 6 video/ngày cho YouTube API (lỗi 429). Đây là lỗi phía WoopSocial, không phải lỗi code. Facebook và TikTok không bị ảnh hưởng.

---

## Lịch chạy (Task Scheduler)

`random_scheduler.py` chạy lúc 00:05 mỗi ngày → sinh 4 giờ ngẫu nhiên (06:00–23:00, cách nhau ≥3 tiếng) → tạo Windows Task `FootballRandom_YYYYMMDD_HHMM`.

Xem lịch hôm nay:
```powershell
schtasks /query /fo LIST | Select-String -Pattern "Football" -Context 0,5
```

---

## Chiến lược nội dung (Hot Scorer)

Ưu tiên theo điểm:
1. **Tier 1:** Messi/Ronaldo/Yamal (30đ) · World Cup 2026 (28đ) · Champions League (25đ)
2. **Tier 2:** Chuyển nhượng xác nhận · Sa thải/bổ nhiệm HLV (20đ)
3. **Loại bỏ:** soi kèo, dự đoán, lịch thi đấu

ĐTQG Việt Nam hiện không ưu tiên (không có lịch thi đấu).

---

## Kiểm tra log

```powershell
# Xem log gần nhất (UTF-16)
Get-Content "D:\claude\football-video-agent\logs\daily.log" | Select-Object -Last 50

# Tìm lỗi
Get-Content "D:\claude\football-video-agent\logs\daily.log" | Where-Object { $_ -match "FAILED|Error|lỗi" } | Select-Object -Last 20
```

---

## Kiểm tra bài đã tạo

```powershell
# Bài hôm nay
Get-ChildItem "D:\claude\football-video-agent\output" -Directory | Where-Object { $_.Name -like "$(Get-Date -Format 'yyyy-MM-dd')*" }
```

---

## Kiểm tra post WoopSocial

```powershell
$h = @{ "Authorization" = "Bearer $env:WOOPSOCIAL_API_KEY"; "Content-Type" = "application/json" }
$post = Invoke-RestMethod -Uri "https://api.woopsocial.com/v1/posts/<POST_ID>" -Headers $h
$post.socialAccountPosts | Select-Object platform, deliveryStatus, errorMessage
```

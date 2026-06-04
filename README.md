# football-video-agent

Agent tạo video tin tức bóng đá tiếng Việt 9:16 (TikTok/Reels/Shorts) tự động từ bài báo.

**Số scenes = số hình trong bài** (lấy hết, không giới hạn). Mỗi scene = 1 hình.

## Cài đặt

### 1. Python packages

```bash
pip install -r requirements.txt
```

### 2. ffmpeg (bắt buộc cho video)

- Windows: download từ https://ffmpeg.org/download.html → thêm vào PATH
- macOS: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

### 3. Anthropic API key

```bash
cp config/.env.example config/.env
# Mở config/.env và điền ANTHROPIC_API_KEY
```

### 4. Google Cloud Text-to-Speech

**Bước 1 — Bật API**: Google Cloud Console → APIs & Services → Library → tìm "Text-to-Speech API" → Enable

**Bước 2 — Tạo Service Account**:
1. IAM & Admin → Service Accounts → Create Service Account
2. Đặt tên (vd: `football-tts`)
3. Role: `Cloud Text-to-Speech User`
4. Create Key → JSON → download file
5. Lưu file vào `config/google-credentials.json`

**Bước 3 — Trỏ env tới file**: Trong `config/.env`:
```
GOOGLE_APPLICATION_CREDENTIALS=config/google-credentials.json
```

**Hoặc cách 2 — dev local**: `gcloud auth application-default login` rồi bỏ dòng `GOOGLE_APPLICATION_CREDENTIALS` trong `.env`.

### 5. Test setup

```bash
# Test renderer + composer (không cần API)
python test_composer.py

# Test Google TTS (cần auth)
python scripts/voice_gen.py
```

## Chạy

```bash
# Auto-fetch 10 nguồn theo priority
python main.py

# 1 nhánh
python main.py --branch vn          # 5 nguồn VN
python main.py --branch tabloid     # 5 nguồn tabloid

# 1 nguồn cụ thể
python main.py --source vnexpress

# URL chỉ định (auto-detect adapter)
python main.py --url "https://vnexpress.net/..."

# Mode B — text thủ công (image_finder hiện stub)
python main.py --text "Hà Nội FC vừa thắng Hải Phòng..."

# Dry-run: chỉ sinh script, không render/voice/video
python main.py --dry-run

# Re-compose từ folder có sẵn
python main.py --recompose output/2026-05-15_143022_slug

# Nhiều bài 1 lượt
python main.py --max 5
```

## Pipeline

```
URL → fetcher → tải HẾT hình → script_gen (N scenes) → voice_gen → render → composer → MP4
```

Số scenes = số hình tải thành công. Narration tự co giãn:
- 3 scenes  → 35-50 từ/scene (~10s/scene)
- 5 scenes  → 25-35 từ/scene (~7s/scene)
- 8 scenes  → 18-25 từ/scene (~5s/scene)
- 12+ scenes → 10-16 từ/scene (~3.5s/scene)

## Cấu trúc output

```
output/
└── 2026-05-15_143022_real-madrid-thang/
    ├── video.mp4              ← Video cuối cùng
    ├── script.json            ← N scenes (gồm narration, headline, image_url)
    ├── source.json            ← Metadata bài gốc
    ├── images/
    │   ├── scene_01.jpg       ← N hình gốc
    │   ├── scene_02.jpg
    │   └── ...
    ├── audio/
    │   ├── scene_01.mp3       ← N file voice
    │   ├── scene_02.mp3
    │   └── ...
    └── frames/
        ├── bg_01.jpg          ← Hình base 936×1664 (để composer Ken Burns)
        ├── overlay_01.png     ← Text overlay 720×1280 trong suốt
        └── ...
```

## Nguồn báo

**Nhánh VN (tin chính thống):**
1. bongda.com.vn (priority #1)
2. VnExpress Thể Thao
3. Tuổi Trẻ Thể Thao
4. Thanh Niên Thể Thao
5. Bóng Đá Plus

**Nhánh Tabloid (tin shock đời sống cầu thủ):**
6. The Sun
7. Daily Mail
8. The Mirror
9. Marca (TBN)
10. Don Balon (TBN)

## Tính năng

**Frame:**
- 720×1280 (9:16 dọc)
- Hình full-bleed (không có dải đen)
- Text overlay với gradient mềm trên & dưới
- Smart word-wrap: không cắt giữa từ
- KHÔNG logo / watermark / source / tag trong frame

**Motion (Ken Burns):**
- zoom_in / zoom_out / pan_left / pan_right ngẫu nhiên mỗi scene
- 2 scenes liên tiếp không trùng motion
- Hình base 1.3x frame size để có dư cho motion

**Voice:**
- Google Cloud TTS (vi-VN-Neural2-D, giọng nam Neural2 cao cấp)
- speaking_rate 1.1 (nhanh hơn 10% cho tone thể thao)
- Generate song song qua ThreadPoolExecutor

**Content filter (tabloid):**
- Tầng 1: regex blacklist (wife/girlfriend/child/scandal/v.v.)
- Tầng 2: Claude Haiku classifier kiểm tra body

## Voice Google TTS

Voice mặc định: `vi-VN-Neural2-D` (nam, Neural2 cao cấp)

Các voice VN khác có thể đổi trong `scripts/voice_gen.py` hoặc qua tham số:
- Neural2: `vi-VN-Neural2-A` (nữ), `vi-VN-Neural2-D` (nam)
- Wavenet: `vi-VN-Wavenet-A,B,C,D`
- Standard: `vi-VN-Standard-A,B,C,D` (cơ bản, rẻ nhất)

Xem danh sách đầy đủ: chạy `python scripts/voice_gen.py`

## Trạng thái implementation

| Module | Trạng thái |
|--------|-----------|
| scene_renderer.py | ✅ Hoàn thiện |
| composer.py | ✅ Hoàn thiện (Ken Burns) |
| script_gen.py | ✅ Hoàn thiện (dynamic N scenes) |
| voice_gen.py | ✅ Hoàn thiện (Google TTS) |
| translator.py | ✅ Hoàn thiện |
| content_filter.py | ✅ Hoàn thiện |
| fetcher/vn/vnexpress.py | ✅ Hoàn thiện |
| fetcher/vn/tuoitre.py | ✅ Hoàn thiện |
| fetcher/vn/bongda.py | 🟡 Stub — cần inspect HTML |
| fetcher/vn/thanhnien.py | 🟡 Stub |
| fetcher/vn/bongdaplus.py | 🟡 Stub |
| fetcher/tabloid/* | 🟡 Stub — cần inspect HTML |
| image_finder.py | 🟡 Stub — chưa tích hợp web search |
| main.py | ✅ Hoàn thiện |

## Việc cần làm khi triển khai

1. **Inspect HTML** nguồn còn stub → fine-tune regex trong adapter
2. **Cài fonts** Segoe UI Bold/Regular vào `assets/fonts/` (hoặc dùng font fallback có sẵn của hệ)
3. **Test với bài thật**: `python main.py --url "<url>"`
4. **Tinh chỉnh** content filter sau khi chạy thực tế với nguồn tabloid

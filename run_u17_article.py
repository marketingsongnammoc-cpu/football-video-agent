"""Chạy 1 lần: đăng bài U17 VN thua Australia 0-3 — ảnh thật từ bongda.com.vn"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv("config/.env")

from main import process_article
from scripts.fetcher import load_sources_config, get_adapter
from scripts.fetcher.base import Article

CONFIG_PATH = "config/sources.json"

TITLE = "5 nguyên nhân khiến U17 Việt Nam thua đậm Australia 0-3 ở tứ kết châu Á"

BODY = """Rạng sáng 17/5, U17 Việt Nam để thua Australia 0-3 và dừng bước ở tứ kết giải U17 châu Á 2026. Tỷ số phản ánh đúng thực tế trận đấu — nhưng vì sao một đội vừa thắng chính Australia chỉ ba tuần trước lại thua đậm đến vậy? Dưới đây là những nguyên nhân cốt lõi.

1. Australia "lột xác" hoàn toàn — Việt Nam vẫn là đội cũ
Đây là điểm mấu chốt khiến trận tứ kết hoàn toàn khác trận bán kết Đông Nam Á hồi tháng 4.
Sau thất bại 1-2 trước Việt Nam tại Indonesia, HLV Carl Veart của Australia đã thay tới 8 vị trí trong đội hình xuất phát, chỉ giữ lại ba cầu thủ. Quan trọng hơn, ông bổ sung một loạt tên tuổi đang ăn tập tại châu Âu: thủ môn Charlie Wilson-Papps (Brighton, Ngoại hạng Anh), hậu vệ Harrison Bond (Red Bull Salzburg), tiền đạo Gabriel Lombardi (Parma). Sự xuất hiện của những cầu thủ được đào tạo ở môi trường châu Âu đã nâng đẳng cấp tổng thể của Australia lên rõ rệt — về tư duy chiến thuật, kỹ năng cá nhân lẫn bản lĩnh thi đấu đỉnh cao.
Trong khi đó, U17 Việt Nam gần như giữ nguyên bộ khung đã dùng suốt giải, không có thêm phương án nào mới. Australia biết rõ cách Việt Nam chơi, còn Việt Nam phải đối mặt với một đối thủ hoàn toàn mới.

2. Chênh lệch thể hình và thể lực — bài toán không có lời giải trong một đêm
U17 Việt Nam là đội có chiều cao trung bình thấp nhất trong 8 đội vào tứ kết với chỉ 173,9 cm, trong khi Australia sở hữu chiều cao trung bình lên tới 179,3 cm — hơn tới 5,4 cm.
Sự chênh lệch này trở thành vũ khí trực tiếp trong trận đấu. Australia liên tục khai thác bóng bổng, ném biên dài, phạt góc và những pha tranh chấp tay đôi — đúng những điểm yếu nhất của các cầu thủ nhỏ con Việt Nam. Bàn thắng mở tỷ số của O'Carroll ở phút 40 xuất phát từ đúng một quả ném biên dài vào vòng cấm mà hàng thủ Việt Nam không thể phá bóng dứt khoát.

3. Việt Nam đã kiệt sức — Australia còn nguyên vẹn sức lực
Đây là bất lợi về cơ cấu giải đấu mà Việt Nam không thể kiểm soát.
Do Triều Tiên rút lui khỏi bảng D, Australia chỉ phải thi đấu 2 trận vòng bảng thay vì 3. Trong khi đó, Việt Nam phải chiến đấu qua đủ 3 trận căng thẳng — thắng Yemen, thua ngược Hàn Quốc 1-4, và lội ngược dòng kịch tính thắng UAE 3-2 để giành vé World Cup — trước khi bước vào tứ kết. Sau một tháng liên tục thi đấu cả giải Đông Nam Á lẫn giải châu Á, các cầu thủ trẻ Việt Nam đã rõ ràng không còn thể lực như ban đầu.
HLV Cristiano Roland sau trận thừa nhận thẳng: "Thầy biết thể lực là vấn đề rất quan trọng với đội." Sự xuống sức thể hiện rõ nhất ở hiệp hai, khi Việt Nam dâng cao tìm bàn gỡ nhưng lại liên tục bị Australia phản công để thủng lưới ở phút 60 và 75.

4. Australia đã "bắt bài" — chiến thuật triệt tiêu tốc độ Việt Nam
Ở giải Đông Nam Á, Việt Nam thắng Australia nhờ lối chơi phối hợp nhanh, chuyển trạng thái đột ngột và tấn công ra sau hàng thủ đối phương. Australia đã học thuộc bài học đó.
Lần này, đội bóng xứ chuột túi thi đấu theo kiểu hoàn toàn khác: không vội vã, không để Việt Nam có không gian chuyển trạng thái, và đặc biệt là kiểm soát chặt "nhạc trưởng" Chu Ngọc Nguyễn Lực — cầu thủ sáng tạo nhất của Việt Nam. Khi Nguyễn Lực bị vô hiệu hóa, lối chơi phối hợp của Việt Nam trở nên thiếu đường dẫn bóng và mất đi sức sáng tạo vốn có.
Thủ môn Charlie Wilson-Papps — người được đào tạo từ lò Brighton — cũng đóng góp quan trọng khi chơi rất bình tĩnh trong việc kiểm soát và triển khai bóng từ tuyến dưới, giúp Australia giảm áp lực pressing của Việt Nam.

5. Kém duyên trước khung thành — bỏ lỡ những cơ hội vàng
Dù bị áp đảo về thể hình, Việt Nam vẫn tạo ra được một số cơ hội ở hiệp một. Phút 22, Văn Dương chọc khe để Sỹ Bách thoát xuống nhưng cú dứt điểm bị hậu vệ cản phá. Sau bàn thua đầu tiên, Minh Thủy khiến thủ môn Wilson-Papps phải vất vả cứu bóng, rồi pha đi bóng lắt léo của Sỹ Bách lại bị trung vệ Milliner chặn đứng xuất sắc.
Nếu một trong những cơ hội đó vào lưới, cục diện trận đấu có thể hoàn toàn khác. Tiếc thay, ngày hôm đó không phải ngày của Việt Nam trước khung thành. Sự kém duyên trong dứt điểm cộng hưởng với áp lực tổng thể buộc Việt Nam phải dâng cao ở hiệp hai, và chính điều đó lại tạo ra khoảng trống để Australia phản công và ghi thêm hai bàn thắng.

Nhìn lại: Thất bại đáng tiếc nhưng không đáng xấu hổ
Thua 0-3 trước Australia là kết quả đau, nhưng nhìn vào toàn bộ bức tranh, U17 Việt Nam đã có một hành trình đáng tự hào. Chỉ trong một tháng, thầy trò HLV Cristiano Roland vô địch Đông Nam Á, rồi tiến vào tứ kết giải châu Á với tư cách đội đứng đầu bảng, và quan trọng hơn cả — đã giành tấm vé lịch sử dự U17 World Cup 2026 lần đầu tiên trong lịch sử bóng đá Việt Nam.
Trận thua trước Australia cho thấy khoảng cách về thể chất, chiều sâu lực lượng và kinh nghiệm vẫn còn tồn tại. Nhưng đó cũng chính là bài học quý giá nhất mà lứa cầu thủ này cần mang theo khi bước vào U17 World Cup tại Qatar vào tháng 11 năm nay.
"Chúng ta đã cho cả thế giới thấy rằng Việt Nam biết chơi bóng đá và chơi bằng sự dũng cảm" — HLV Cristiano Roland."""

IMG_URL = "https://bongda.com.vn/u17-viet-nam-lo-hen-voi-ban-ket-chau-a-sau-tran-thua-australia-d831785.html"

if __name__ == "__main__":
    # Lấy ảnh thật từ bài tường thuật trận đấu
    configs = load_sources_config(CONFIG_PATH)
    adapter = get_adapter("bongda", configs)
    source_article = adapter.fetch_article(IMG_URL)
    print(f"  → Lấy được {len(source_article.images)} ảnh từ bongda.com.vn")

    # Ghép ảnh thật + nội dung phân tích của user
    article = Article(
        title=TITLE,
        body=BODY,
        images=source_article.images,
        url=f"manual_u17_analysis_{int(time.time())}",
        source_name="manual",
        language="vi",
    )
    process_article(article, is_tabloid=False)

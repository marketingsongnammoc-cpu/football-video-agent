"""
Sinh 4 giờ ngẫu nhiên trong ngày, cách nhau tối thiểu 3 tiếng.
Chạy mỗi ngày lúc 00:05 qua Task Scheduler (FootballVideo_Daily).
Tạo 4 one-time schtasks cho ngày hôm đó.
"""
import random
import subprocess
import datetime
import logging
import sys

LOG_FILE = r"D:\claude\football-video-agent\logs\daily.log"
BAT_FILE = r"D:\claude\football-video-agent\run_daily.bat"
TASK_PREFIX = "FootballRandom"

WINDOW_START = 6 * 60   # 06:00 → 360 phút từ nửa đêm
WINDOW_END   = 23 * 60  # 23:00 → 1380 phút từ nửa đêm
MIN_GAP      = 3 * 60   # 3 tiếng = 180 phút
N_POSTS      = 4

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [SCHEDULER] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def generate_times(n=N_POSTS, start=WINDOW_START, end=WINDOW_END, min_gap=MIN_GAP):
    """Uniform random n times in [start, end] với khoảng cách >= min_gap."""
    slack = (end - start) - (n - 1) * min_gap
    if slack < 0:
        raise ValueError("Cửa sổ thời gian không đủ rộng cho yêu cầu khoảng cách tối thiểu")

    # Chọn n điểm ngẫu nhiên trong [0, slack], sort
    cuts = sorted(random.randint(0, slack) for _ in range(n))

    times = []
    for i, c in enumerate(cuts):
        t = start + c + i * min_gap
        times.append(t)
    return times


def minutes_to_hhmm(minutes):
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def delete_old_tasks():
    result = subprocess.run(
        ["schtasks", "/query", "/fo", "csv", "/nh"],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if TASK_PREFIX in line:
            task_name = line.split(",")[0].strip('"')
            subprocess.run(
                ["schtasks", "/delete", "/tn", task_name, "/f"],
                capture_output=True
            )
            logging.info(f"Đã xóa task cũ: {task_name}")


def create_task(task_name, run_date, run_time_hhmm):
    """Tạo one-time task chạy vào ngày giờ chỉ định."""
    cmd = [
        "schtasks", "/create", "/tn", task_name,
        "/tr", BAT_FILE,
        "/sc", "once",
        "/sd", run_date,   # MM/DD/YYYY
        "/st", run_time_hhmm,
        "/f",
        "/rl", "highest",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logging.info(f"Tạo task: {task_name} lúc {run_date} {run_time_hhmm}")
    else:
        logging.error(f"Lỗi tạo task {task_name}: {result.stderr.strip()}")


def main():
    today = datetime.date.today()
    date_str = today.strftime("%m/%d/%Y")  # định dạng schtasks

    logging.info(f"=== Random Scheduler bắt đầu cho {today.isoformat()} ===")

    # Xóa task cũ còn sót
    delete_old_tasks()

    # Sinh giờ ngẫu nhiên
    times = generate_times()

    logging.info(f"Lịch hôm nay: {[minutes_to_hhmm(t) for t in times]}")
    print(f"Schedule {today.isoformat()}: {[minutes_to_hhmm(t) for t in times]}")

    for i, t in enumerate(times, 1):
        hhmm = minutes_to_hhmm(t)
        task_name = f"{TASK_PREFIX}_{today.strftime('%Y%m%d')}_{hhmm.replace(':', '')}"
        create_task(task_name, date_str, hhmm)

    logging.info("=== Random Scheduler hoàn tất ===")


if __name__ == "__main__":
    main()

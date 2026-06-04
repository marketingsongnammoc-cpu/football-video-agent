"""
Chay moi 30 phut qua Task Scheduler.
Doc schedule.json (4 gio ngau nhien/ngay, cach nhau >= 3 tieng).
Neu gio hien tai trung voi mot slot chua dang (trong cua so 30 phut), chay main.py.
"""
import json
import random
import subprocess
import sys
import datetime
from pathlib import Path

BASE_DIR   = Path(r"D:\claude\football-video-agent")
SCHED_FILE = BASE_DIR / "data" / "schedule.json"
LOG_FILE   = BASE_DIR / "logs" / "daily.log"

WINDOW_START = 6 * 60    # 06:00
WINDOW_END   = 23 * 60   # 23:00
MIN_GAP      = 3 * 60    # 180 phut
N_POSTS      = 4
WINDOW_MIN   = 30         # cua so chap nhan (phut)


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [RUNNER] {msg}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip())


def generate_times():
    slack = (WINDOW_END - WINDOW_START) - (N_POSTS - 1) * MIN_GAP
    cuts = sorted(random.randint(0, slack) for _ in range(N_POSTS))
    return [WINDOW_START + c + i * MIN_GAP for i, c in enumerate(cuts)]


def minutes_to_hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def load_or_create_schedule():
    today = datetime.date.today().isoformat()
    if SCHED_FILE.exists():
        data = json.loads(SCHED_FILE.read_text(encoding="utf-8"))
        if data.get("date") == today:
            return data

    # Tao moi cho hom nay
    times = generate_times()
    data = {
        "date": today,
        "slots": [{"time": minutes_to_hhmm(t), "done": False} for t in times],
    }
    SCHED_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCHED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Lich moi: {[s['time'] for s in data['slots']]}")
    return data


def save_schedule(data):
    SCHED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def should_run(slot_hhmm, now_minutes):
    h, m = map(int, slot_hhmm.split(":"))
    slot_minutes = h * 60 + m
    return slot_minutes <= now_minutes < slot_minutes + WINDOW_MIN


def main():
    now = datetime.datetime.now()
    now_minutes = now.hour * 60 + now.minute

    data = load_or_create_schedule()
    ran = False

    for slot in data["slots"]:
        if slot["done"]:
            continue
        if should_run(slot["time"], now_minutes):
            log(f"Bat dau dang bai (slot {slot['time']})")
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "main.py"), "--max", "1"],
                cwd=str(BASE_DIR),
            )
            slot["done"] = True
            save_schedule(data)
            log(f"Hoan tat slot {slot['time']} (exit={result.returncode})")
            ran = True
            break  # moi lan chay chi dang 1 bai

    if not ran:
        remaining = [s["time"] for s in data["slots"] if not s["done"]]
        log(f"Khong co slot nao can chay luc {now.strftime('%H:%M')}. Con lai: {remaining}")


if __name__ == "__main__":
    main()

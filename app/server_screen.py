"""Сводка сервера на настольном экране: забрать JSON, нарисовать, отправить на плату.

    .venv/Scripts/python app/server_screen.py     # отдельно, с журналом в консоли

Обычно работает внутри приложения в трее (app/tray.py), отдельным потоком.

Адрес сводки лежит в %LOCALAPPDATA%\\desk-light\\config.json:

    {"status_url": "http://<адрес сервера>:8787/status"}

Нет файла или адреса — экран не используется. Что должен отдавать сервер, описано в
docs/STATUS-API.md.
"""

import json
import os
import threading
import time
import urllib.request

from screen import Screen
from summary_view import render, render_offline

PERIOD_S = 3.0   # как часто спрашиваем сервер
STALE_S = 15.0   # сводка старше — на экране «нет связи», а не застывшие цифры
TIMEOUT_S = 2.5

state = {"screen": False, "server": False, "note": "не запущено"}


def folder():
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "desk-light")


def status_url():
    try:
        with open(os.path.join(folder(), "config.json"), encoding="utf-8") as f:
            return json.load(f).get("status_url") or ""
    except Exception:
        return ""


def fetch(url):
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
        return json.load(response)


def comma(number, digits=1):
    return ("%.*f" % (digits, number)).replace(".", ",")


def uptime(seconds):
    if seconds is None:
        return ""
    if seconds >= 2 * 86400:
        return "%d дн" % (seconds // 86400)
    if seconds >= 3600:
        return "%d ч" % (seconds // 3600)
    return "%d мин" % (seconds // 60)


def clients(n):
    if n % 10 == 1 and n % 100 != 11:
        return "клиент"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "клиента"
    return "клиентов"


def to_view(status):
    """Ответ сервера -> то, что рисует summary_view. Чего нет, остаётся None: будет прочерк."""
    gpu = status.get("gpu") or {}
    queue = status.get("queue") or {}
    meetings = status.get("meetings") or {}
    today = status.get("today") or {}
    units = status.get("units") or {}
    backup = status.get("backup") or {}
    used, total = gpu.get("mem_used_mb"), gpu.get("mem_total_mb")
    temp = status.get("cpu_temp")
    if today:
        line = "сегодня %s ч аудио · %d %s" % (comma(today["hours"]), today["clients"],
                                               clients(today["clients"]))
    else:
        line = "сегодня —"
    return {
        "host": status.get("host", "сервер"),
        "ok": bool(status.get("api_ok")),
        "uptime": uptime(status.get("uptime_s")),
        "clock": time.strftime("%H:%M", time.localtime(status.get("time", time.time()))),
        "gpu_load": gpu.get("load"),
        "gpu_temp": gpu.get("temp"),
        "gpu_mem_used": None if used is None else comma(used / 1024),
        "gpu_mem_total": None if total is None else round(total / 1024),
        "gpu_watts": gpu.get("watts"),
        "cpu_load": status.get("cpu_load"),
        "cpu_temp": None if temp is None else round(temp),
        "queued": queue.get("queued"),
        "running": queue.get("running"),
        "agents": meetings.get("agents"),
        "agents_max": meetings.get("max"),
        "today": line,
        "lamps": [
            ("API", status.get("api_ok")),
            ("туннель", units.get("asr-tunnel-front")),
            ("встречи", units.get("telemost-orchestrator")),
            ("бэкап", backup.get("ok")),
            ("вент.", units.get("fanctl")),
        ],
    }


def note(screen_ok, server_ok, text):
    """Состояние для значка в трее и файл рядом с настройками: видно, жив ли экран."""
    changed = (state["screen"], state["server"], state["note"]) != (screen_ok, server_ok, text)
    state.update(screen=screen_ok, server=server_ok, note=text)
    if not changed:
        return
    print("экран: %s" % text, flush=True)
    try:
        with open(os.path.join(folder(), "screen-status.json"), "w", encoding="utf-8") as f:
            json.dump(dict(state, at=time.strftime("%Y-%m-%d %H:%M:%S")), f, ensure_ascii=False)
    except Exception:
        pass


def run(url):
    screen = Screen()
    image = render_offline("нет связи с сервером", "сводки ещё не было")
    good_at, good_clock = None, ""
    while True:
        started = time.time()
        try:
            view = to_view(fetch(url))
            image = render(view)
            good_at, good_clock = started, view["clock"]
            server_ok, text = True, "сводка идёт"
        except Exception as error:
            server_ok, text = False, "сервер не отвечает: %s" % str(error)[:80]
            if good_at is None or started - good_at > STALE_S:
                since = "последняя сводка в %s" % good_clock if good_clock else "сводки ещё не было"
                image = render_offline("нет связи с сервером", since)
        try:
            screen.show(image)
            note(True, server_ok, text)
        except Exception as error:
            screen.close()
            note(False, server_ok, "плата экрана не найдена: %s" % str(error)[:80])
        time.sleep(max(0.2, PERIOD_S - (time.time() - started)))


def start():
    """Запустить в фоне. Возвращает False, если адрес сводки не задан."""
    url = status_url()
    if not url:
        note(False, False, "адрес сводки не задан в config.json")
        return False
    threading.Thread(target=run, args=(url,), daemon=True).start()
    return True


if __name__ == "__main__":
    address = status_url()
    if not address:
        raise SystemExit("Нет адреса сводки: %s" % os.path.join(folder(), "config.json"))
    run(address)

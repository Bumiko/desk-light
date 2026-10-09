"""Как выглядит сводка сервера на экране 320x240. Только рисование, без сети и железа.

    .venv/Scripts/python app/summary_view.py   # сохранить образец в preview.png
"""

import os

from PIL import Image, ImageDraw, ImageFont

SIZE = (320, 240)
BACK, TILE = (9, 12, 16), (22, 28, 36)
TEXT, DIM = (235, 240, 245), (130, 140, 152)
GREEN, AMBER, RED, GREY = (63, 185, 80), (224, 164, 40), (248, 81, 73), (90, 98, 108)

_FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _cache:
        try:
            name = "segoeuib.ttf" if bold else "segoeui.ttf"
            _cache[key] = ImageFont.truetype(os.path.join(_FONTS, name), size)
        except OSError:
            _cache[key] = ImageFont.load_default(size)
    return _cache[key]


def shade(percent, warn=70, bad=90):
    if percent is None:
        return GREY
    return RED if percent >= bad else AMBER if percent >= warn else GREEN


def show(value, suffix=""):
    return "—" if value is None else "%s%s" % (value, suffix)


def load_tile(draw, box, title, percent, note):
    """Большая плитка: название, проценты крупно, полоска, строка подробностей."""
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=6, fill=TILE)
    draw.text((left + 8, top + 3), title, font=font(15), fill=DIM)
    draw.text((right - 8, top + 30), show(percent, "%"), font=font(40, True), fill=TEXT,
              anchor="rm")
    bar = (left + 8, top + 56, right - 8, top + 62)
    draw.rounded_rectangle(bar, radius=3, fill=BACK)
    if percent:
        width = max(4, (bar[2] - bar[0]) * min(percent, 100) // 100)
        draw.rounded_rectangle((bar[0], bar[1], bar[0] + width, bar[3]), radius=3,
                               fill=shade(percent))
    draw.text((left + 8, bottom - 6), note, font=font(15), fill=DIM, anchor="ls")


def count_tile(draw, box, title, value, ink=TEXT):
    """Малая плитка: число крупно, подпись под ним."""
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=6, fill=TILE)
    middle = (left + right) // 2
    draw.text((middle, top + 24), value, font=font(34, True), fill=ink, anchor="mm")
    draw.text((middle, bottom - 6), title, font=font(14), fill=DIM, anchor="ms")


def render(data, demo=False):
    """Картинка сводки. data — словарь; чего нет, то рисуется прочерком."""
    get = data.get
    image = Image.new("RGB", SIZE, BACK)
    draw = ImageDraw.Draw(image)

    # шапка: имя, сколько работает, время сводки
    draw.ellipse((6, 9, 16, 19), fill=GREEN if get("ok", True) else RED)
    draw.text((22, 14), get("host", "сервер"), font=font(17, True), fill=TEXT, anchor="lm")
    right = get("clock", "")
    if get("uptime"):
        right = "работает %s   %s" % (get("uptime"), right)
    draw.text((314, 14), right, font=font(14), fill=DIM, anchor="rm")
    if demo:
        draw.rounded_rectangle((118, 4, 166, 24), radius=4, fill=RED)
        draw.text((142, 14), "ДЕМО", font=font(13, True), fill=TEXT, anchor="mm")

    gpu_note = "%s°  %s/%s ГБ  %s Вт" % (show(get("gpu_temp")), show(get("gpu_mem_used")),
                                         show(get("gpu_mem_total")), show(get("gpu_watts")))
    load_tile(draw, (4, 30, 158, 116), "GPU", get("gpu_load"), gpu_note)
    load_tile(draw, (162, 30, 316, 116), "CPU", get("cpu_load"),
              "сокет %s°" % show(get("cpu_temp")))

    queued, running = get("queued"), get("running")
    agents, agents_max = get("agents"), get("agents_max")
    count_tile(draw, (4, 120, 105, 192), "в очереди", show(queued),
               AMBER if queued else TEXT)
    count_tile(draw, (109, 120, 211, 192), "в работе", show(running),
               GREEN if running else TEXT)
    meetings = "—" if agents is None else "%s/%s" % (agents, show(agents_max))
    count_tile(draw, (215, 120, 316, 192), "встречи", meetings, GREEN if agents else TEXT)

    # подвал: итог дня и лампочки служб
    draw.text((6, 208), get("today", ""), font=font(15), fill=TEXT, anchor="lm")
    x = 6
    for name, state in get("lamps", []):
        ink = GREY if state is None else GREEN if state else RED
        draw.ellipse((x, 224, x + 8, 232), fill=ink)
        draw.text((x + 12, 228), name, font=font(13), fill=DIM, anchor="lm")
        x += 20 + int(draw.textlength(name, font=font(13)))
    return image


def render_offline(reason, since=""):
    """Серый экран: сводки нет. Застывшие цифры показывать нельзя."""
    image = Image.new("RGB", SIZE, (30, 32, 36))
    draw = ImageDraw.Draw(image)
    draw.text((160, 100), reason, font=font(30, True), fill=(190, 194, 200), anchor="mm")
    if since:
        draw.text((160, 140), since, font=font(16), fill=DIM, anchor="mm")
    return image


DEMO = {
    "host": "gpu-server", "uptime": "18 ч", "clock": "14:32",
    "gpu_load": 34, "gpu_temp": 52, "gpu_mem_used": "5,1", "gpu_mem_total": 12,
    "gpu_watts": 140, "cpu_load": 12, "cpu_temp": 34,
    "queued": 2, "running": 1, "agents": 1, "agents_max": 3,
    "today": "сегодня 3,4 ч аудио · 4 клиента",
    "lamps": [("API", True), ("туннель", True), ("встречи", True), ("бэкап", False),
              ("вент.", True)],
}

if __name__ == "__main__":
    render(DEMO, demo=True).save("preview.png")
    render_offline("нет связи с сервером", "последняя сводка в 14:32").save("preview-offline.png")
    print("preview.png, preview-offline.png")

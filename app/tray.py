"""Подсветка клавиатуры: значок в трее и горячие клавиши.

    .venv/Scripts/pythonw app/tray.py

Горячие клавиши:
    Ctrl+Alt+L           включить или выключить
    Ctrl+Alt+PgUp/PgDn   ярче или тусклее, 40 шагов; клавишу можно держать зажатой

Связь с платой держится сама: раз в несколько секунд состояние подтверждается заново,
так что после перетыкания кабеля или перезагрузки платы свет возвращается без участия
человека. Если приложение закрыть, плата через 15 секунд погасит ленту сама.
"""

import ctypes
import json
import os
import threading
import time
from ctypes import wintypes

import pystray
from PIL import Image, ImageDraw

from link import find

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, os.pardir, "state.json")

PRESETS = [50, 100, 200, 350, 500, 700, 1000]  # быстрые уровни в меню, шкала 0..1000
MIN_LEVEL, MAX_LEVEL, STEP = 25, 1000, 25      # горячими клавишами — мелким шагом
DEFAULT_LEVEL = 200
HEARTBEAT_S = 3.0   # плата гасит ленту, если молчать дольше 15 секунд
RECONNECT_S = 5.0


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(data):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class Lights:
    """Состояние подсветки и связь с платой."""

    def __init__(self):
        self.level = int(load_state().get("level", DEFAULT_LEVEL))
        self.on = False
        self.connected = False
        self.board = None
        self.lock = threading.Lock()
        self.pending = threading.Event()
        self.on_change = lambda: None

    def _send(self, command):
        """Отправить команду, при обрыве один раз переподключиться."""
        with self.lock:
            for _ in range(2):
                try:
                    if self.board is None:
                        self.board = find(timeout=2.0)
                    answer = self.board.send(command)
                    if answer:
                        self.connected = True
                        return answer
                except Exception:
                    pass
                if self.board is not None:
                    self.board.close()
                    self.board = None
            self.connected = False
            return None

    def apply(self):
        self._send(("SET %d" % self.level) if self.on else "OFF")
        self.on_change()

    def toggle(self):
        self.on = not self.on
        self.apply()

    def turn(self, on):
        self.on = bool(on)
        self.apply()

    def set_level(self, level):
        self.level = max(MIN_LEVEL, min(MAX_LEVEL, int(level)))
        self.on = True
        self.pending.set()

    def step(self, direction):
        """Ярче (+1) или тусклее (−1) на один мелкий шаг; клавишу можно держать зажатой."""
        self.set_level(self.level + STEP * direction)

    def applier_loop(self):
        """Шаги прилетают пачками при зажатой клавише: шлём последнее значение,
        не чаще двадцати раз в секунду, чтобы не забивать порт."""
        while True:
            self.pending.wait()
            self.pending.clear()
            self.apply()
            save_state({"level": self.level})
            time.sleep(0.05)

    def heartbeat_loop(self):
        """Подтверждать состояние: это и сторож связи, и защита от перезагрузки платы."""
        while True:
            was = self.connected
            answer = self._send(("SET %d" % self.level) if self.on else "OFF")
            if self.connected != was:
                self.on_change()
            time.sleep(HEARTBEAT_S if answer else RECONNECT_S)


def make_icon(on, connected):
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if not connected:
        body = (196, 84, 72, 255)
    elif on:
        body = (250, 214, 120, 255)
    else:
        body = (124, 132, 140, 255)
    draw.rounded_rectangle((8, 24, 56, 38), radius=6, fill=body)
    if on and connected:
        for x in range(16, 57, 12):
            draw.line((x, 42, x - 5, 58), fill=(250, 214, 120, 200), width=4)
    return image


# --- горячие клавиши Windows -------------------------------------------------
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
VK_L, VK_PRIOR, VK_NEXT = 0x4C, 0x21, 0x22
WM_HOTKEY = 0x0312

HOTKEYS = [
    # у клавиш яркости нет MOD_NOREPEAT: их можно держать зажатыми
    (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_L, "Ctrl+Alt+L", "toggle"),
    (MOD_CONTROL | MOD_ALT, VK_PRIOR, "Ctrl+Alt+PgUp", "brighter"),
    (MOD_CONTROL | MOD_ALT, VK_NEXT, "Ctrl+Alt+PgDn", "dimmer"),
]


def hotkey_loop(handlers):
    """Регистрация и разбор сочетаний — обязательно в одном потоке."""
    user32 = ctypes.windll.user32
    for number, (mods, vk, name, _) in enumerate(HOTKEYS, start=1):
        if not user32.RegisterHotKey(None, number, mods, vk):
            print("Сочетание %s занято другой программой" % name, flush=True)
    message = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
        if message.message == WM_HOTKEY:
            index = message.wParam - 1
            if 0 <= index < len(HOTKEYS):
                handlers[HOTKEYS[index][3]]()


def main():
    lights = Lights()
    icon = pystray.Icon("desk-light", make_icon(False, False), "Подсветка клавиатуры")

    def refresh():
        icon.icon = make_icon(lights.on, lights.connected)
        if not lights.connected:
            icon.title = "Подсветка: плата не найдена"
        elif lights.on:
            icon.title = "Подсветка: включена, %d%%" % (lights.level // 10)
        else:
            icon.title = "Подсветка: выключена"

    lights.on_change = refresh

    def level_item(level):
        nearest = lambda: min(PRESETS, key=lambda p: abs(p - lights.level))
        return pystray.MenuItem(
            "%d%%" % (level // 10),
            lambda i, item: lights.set_level(level),
            checked=lambda item: lights.on and nearest() == level,
            radio=True,
        )

    def quit_app(i, item):
        lights.turn(False)
        icon.stop()

    icon.menu = pystray.Menu(
        pystray.MenuItem("Включить или выключить", lambda i, item: lights.toggle(), default=True),
        pystray.Menu.SEPARATOR,
        *[level_item(level) for level in PRESETS],
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Выход", quit_app),
    )

    handlers = {
        "toggle": lights.toggle,
        "brighter": lambda: lights.step(+1),
        "dimmer": lambda: lights.step(-1),
    }
    threading.Thread(target=hotkey_loop, args=(handlers,), daemon=True).start()
    threading.Thread(target=lights.heartbeat_loop, daemon=True).start()
    threading.Thread(target=lights.applier_loop, daemon=True).start()

    print("Подсветка запущена. Ctrl+Alt+L — вкл/выкл, Ctrl+Alt+PgUp/PgDn — яркость.",
          flush=True)
    icon.run(setup=lambda i: refresh())


if __name__ == "__main__":
    main()

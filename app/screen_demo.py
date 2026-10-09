"""Образец сводки на настоящем экране, с выдуманными цифрами и плашкой «ДЕМО».

    .venv/Scripts/python app/screen_demo.py [минут]

Цифры меняются раз в две секунды: видно, как экран обновляется кусками. Когда программа
завершается, плата через 15 секунд сама пишет «нет связи».
"""

import random
import sys
import time

from screen import Screen
from summary_view import DEMO, render

minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 5
screen = Screen()
data = dict(DEMO)
deadline = time.time() + minutes * 60
while time.time() < deadline:
    data["clock"] = time.strftime("%H:%M")
    data["gpu_load"] = max(0, min(100, data["gpu_load"] + random.randint(-12, 12)))
    data["cpu_load"] = max(0, min(100, data["cpu_load"] + random.randint(-6, 6)))
    data["gpu_temp"] = 45 + data["gpu_load"] // 4
    data["gpu_watts"] = 40 + data["gpu_load"] * 2
    data["queued"] = random.choice([0, 0, 1, 2, 3])
    data["running"] = 1 if data["queued"] or random.random() < 0.5 else 0
    try:
        started = time.time()
        sent = screen.show(render(data, demo=True))
        print("%6d байт за %.2f с" % (sent, time.time() - started), flush=True)
    except Exception as error:
        print("связь с экраном потеряна: %s" % error, flush=True)
        screen.close()
    time.sleep(2)
screen.close()

"""Прогон железа: связь, полярность модуля и рабочий диапазон яркости.

    python app/selftest.py [частота_ШИМ]

Смотреть надо на ленту, сверяясь с тем, что печатается в консоли. Главное — на каком
значении duty лента гаснет: ниже этого порога оптопара PC817 уже не успевает открыться.
"""

import sys
import time

from link import find

# геометрический спуск: так порог находится за десяток шагов
DUTY_STEPS = [20000, 14000, 10000, 7000, 5000, 3500, 2500, 1800, 1200, 900,
              600, 400, 300, 200, 140, 100, 70, 50, 35, 25, 18, 12, 8, 5, 3, 2, 1]


def step(board, command, hold, note=""):
    answer = board.send(command)
    print("  %-12s -> %-22s %s" % (command, answer, note), flush=True)
    time.sleep(hold)


def main(argv):
    board = find()
    print("Плата:", board.port, "|", board.send("PING"))
    if argv:
        print("Частота ШИМ:", board.send("FREQ %s" % argv[0]))
    print("Состояние:", board.send("STATE"))

    print("\n1. Темнота и три вспышки — проверяем, что лента вообще слушается")
    step(board, "OFF", 2, "лента тёмная")
    for i in range(3):
        step(board, "SET 1000", 0.4, "вспышка %d" % (i + 1))
        step(board, "OFF", 0.4)

    print("\n2. Ступеньки яркости (шкала 0..1000, с гаммой)")
    for level in (1000, 500, 250, 100, 50):
        step(board, "SET %d" % level, 3, "уровень %d" % level)

    print("\n3. Плавный спуск по сырому ШИМ — запомни, на каком числе погасло")
    for duty in DUTY_STEPS:
        board.send("RAW %d" % duty)
        print("  duty %5d" % duty, flush=True)
        time.sleep(0.9)

    step(board, "OFF", 0, "конец прогона")
    board.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

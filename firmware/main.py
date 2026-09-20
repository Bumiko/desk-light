"""desk-lights: прошивка платы RP2040-Zero (MicroPython).

Читает команды-строки с USB (тот же порт, что и REPL) и крутит ШИМ на модуле HW-532
(ключ D4184 с оптопарой PC817). Протокол описан в docs/PROTOCOL.md.
Заливается в корень платы как main.py.
"""

import select
import sys
import time

from machine import PWM, Pin

VERSION = "desk-light v1"

PWM_PIN = 0          # GP0 -> вход PWM модуля
PWM_FREQ = 400       # Гц. Оптопара PC817 медленная: чем выше частота, тем раньше
                     # обрывается низ яркости. 400 Гц — компромисс без видимого
                     # мерцания. Подбирается командой FREQ.
INVERT = False       # True, если модуль включает ленту при низком уровне
MAX_DUTY = 1.0       # потолок по току, доля от полной яркости
MIN_DUTY = 0.015     # доля ШИМ на самом тусклом уровне шкалы: ниже оптопара уже не
                     # успевает открыться и свет просто пропадает
FADE_MS = 250        # длительность плавного перехода
TICK_MS = 10         # шаг основного цикла
IDLE_OFF_MS = 10000  # нет команд дольше этого — гасим ленту (приложение пишет раз в 3 с)

out = PWM(Pin(PWM_PIN))
out.freq(PWM_FREQ)

level = 300          # запомненная яркость, 0..1000
is_on = False
cur = 0.0            # фактическая яркость с учётом плавности
target = 0.0
raw = None           # наладочный режим: ШИМ выставлен напрямую, гамма и плавность не работают
last_rx = time.ticks_ms()


def write_duty(duty):
    duty = 0 if duty < 0 else (65535 if duty > 65535 else int(duty))
    out.duty_u16(65535 - duty if INVERT else duty)


def apply(value):
    """Выставить ШИМ по значению яркости 0..1000.

    Шкала логарифмическая: уровень 1 даёт ровно MIN_DUTY, уровень 1000 — полную
    яркость. Так весь ход ручки попадает в рабочую зону оптопары, а на глаз шаг
    яркости ощущается ровным.
    """
    v = 0.0 if value < 0 else (1000.0 if value > 1000 else value)
    if v <= 0:
        write_duty(0)
        return
    write_duty(MIN_DUTY ** (1.0 - v / 1000.0) * MAX_DUTY * 65535)


def fade_step():
    """Один шаг плавного перехода к target."""
    global cur
    if raw is not None or cur == target:
        return
    delta = 1000.0 * TICK_MS / FADE_MS
    if abs(target - cur) <= delta:
        cur = target
    else:
        cur += delta if target > cur else -delta
    apply(cur)


def status():
    return "OK on %d" % level if is_on else "OK off"


def handle(line):
    global level, is_on, target, raw, INVERT
    parts = line.split()
    if not parts:
        return None
    cmd = parts[0].upper()

    if cmd == "PING":
        return "PONG " + VERSION
    if cmd == "STATE":
        return "STATE on=%d level=%d freq=%d inv=%d" % (
            1 if is_on else 0, level, out.freq(), 1 if INVERT else 0)

    # наладочные команды: подбор частоты и проверка полярности модуля
    if cmd == "FREQ":
        try:
            hz = int(parts[1])
        except (IndexError, ValueError):
            return "ERR freq"
        hz = 50 if hz < 50 else (20000 if hz > 20000 else hz)
        out.freq(hz)
        return "OK freq %d" % hz
    if cmd == "INV":
        try:
            INVERT = parts[1] == "1"
        except IndexError:
            return "ERR inv"
        apply(cur)
        return "OK inv %d" % (1 if INVERT else 0)
    if cmd == "RAW":
        try:
            duty = int(parts[1])
        except (IndexError, ValueError):
            return "ERR raw"
        raw = duty
        write_duty(duty)
        return "OK raw %d" % duty

    if cmd == "ON":
        is_on = True
    elif cmd == "OFF":
        is_on = False
    elif cmd == "TOGGLE":
        is_on = not is_on
    elif cmd == "SET":
        if len(parts) < 2:
            return "ERR set"
        try:
            value = int(parts[1])
        except ValueError:
            return "ERR set"
        value = 0 if value < 0 else (1000 if value > 1000 else value)
        if value == 0:
            is_on = False
        else:
            level = value
            is_on = True
    else:
        return "ERR unknown"

    raw = None
    target = level if is_on else 0
    return status()


poller = select.poll()
poller.register(sys.stdin, select.POLLIN)
buf = ""
apply(0)

while True:
    # чтение ограничено пачкой символов: если ноутбук сняли с подставки, отвалившийся
    # USB может отдавать пустоту бесконечно, и цикл никогда не дошёл бы до сторожа
    for _ in range(64):
        if not poller.poll(0):
            break
        ch = sys.stdin.read(1)
        if not ch:
            is_on = False       # хост исчез: гасим сразу, не дожидаясь сторожа
            target = 0
            break
        if ch in ("\n", "\r"):
            if buf:
                answer = handle(buf)
                last_rx = time.ticks_ms()
                buf = ""
                if answer:
                    print(answer)
        elif len(buf) < 64:
            buf += ch
    if is_on and time.ticks_diff(time.ticks_ms(), last_rx) > IDLE_OFF_MS:
        is_on = False
        target = 0
    fade_step()
    time.sleep_ms(TICK_MS)

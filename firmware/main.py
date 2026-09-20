"""desk-lights: прошивка платы RP2040-Zero (MicroPython).

Читает команды-строки с USB (тот же порт, что и REPL) и крутит ШИМ на модуле D4184.
Протокол описан в docs/PROTOCOL.md. Заливается в корень платы как main.py.
"""

import select
import sys
import time

from machine import PWM, Pin

VERSION = "desk-light v1"

PWM_PIN = 0          # GP0 -> сигнальный вход модуля
PWM_FREQ = 2000      # Гц: ниже 1 кГц заметно мерцание, выше модуль не успевает открываться
MAX_DUTY = 1.0       # потолок по току, доля от полной яркости
GAMMA = 2.2          # чтобы шаг яркости ощущался ровным
FADE_MS = 250        # длительность плавного перехода
TICK_MS = 10         # шаг основного цикла
IDLE_OFF_MS = 15000  # нет команд дольше этого — гасим ленту

out = PWM(Pin(PWM_PIN))
out.freq(PWM_FREQ)

level = 300          # запомненная яркость, 0..1000
is_on = False
cur = 0.0            # фактическая яркость с учётом плавности
target = 0.0
last_rx = time.ticks_ms()


def apply(value):
    """Выставить ШИМ по значению яркости 0..1000."""
    v = 0.0 if value < 0 else (1000.0 if value > 1000 else value)
    out.duty_u16(int(((v / 1000.0) ** GAMMA) * MAX_DUTY * 65535))


def fade_step():
    """Один шаг плавного перехода к target."""
    global cur
    if cur == target:
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
    global level, is_on, target
    parts = line.split()
    if not parts:
        return None
    cmd = parts[0].upper()
    if cmd == "PING":
        return "PONG " + VERSION
    if cmd == "STATE":
        return "STATE on=%d level=%d" % (1 if is_on else 0, level)
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
    target = level if is_on else 0
    return status()


poller = select.poll()
poller.register(sys.stdin, select.POLLIN)
buf = ""
apply(0)

while True:
    while poller.poll(0):
        ch = sys.stdin.read(1)
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

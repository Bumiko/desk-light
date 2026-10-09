"""desk-display: прошивка платы с экраном ST7789 240x320 (MicroPython).

Плата ничего не рисует сама: компьютер присылает готовые куски картинки, плата кладёт
их на экран. Вид экрана меняется на компьютере, прошивку трогать не надо.

Команды — строки, ответ тоже строка. Полный список — docs/PROTOCOL.md.

    PING              -> PONG desk-display v1
    ROT n             -> OK 320 240        поворот 0..3
    BL n              -> OK                яркость подсветки 0..1000
    BLIT x y w h      -> GO                теперь компьютер шлёт w*h*2 байт точек RGB565
                      -> OK <эпоха>        точки приняты
    KEEP              -> OK <эпоха>        «картинка та же, я жив»

Эпоха растёт каждый раз, когда плата сама затирает экран надписью «нет связи».
Компьютер видит новую эпоху и присылает картинку целиком.

Сторожа два. Нет BLIT и KEEP дольше IDLE_MS — на экране «нет связи»: застывшие цифры
хуже пустого экрана. Плата зависла на чтении (компьютер пропал посреди картинки) —
таймер перезагружает её, и после старта на экране та же надпись.
"""

import os
import select
import sys
import time

import framebuf
import machine
import micropython
from machine import PWM, SPI, Pin, Timer

import banner

VERSION = "desk-display v1"
ROTATIONS = (0x00, 0x60, 0xC0, 0xA0)  # MADCTL: стоя, лёжа, стоя вверх ногами, лёжа наоборот
IDLE_MS = 15000        # столько молчания — и на экране «нет связи»
STALL_MS = 4000        # столько без движения в главном цикле — перезагрузка
IDLE_LEVEL = 250       # яркость подсветки на экране «нет связи», 0..1000
STRIP = 40             # высота полосы, которой плата рисует сама
CHUNK = 1024
PAYLOAD_MS = 2000      # столько ждём продолжения картинки, потом считаем её оборванной

spi = SPI(0, baudrate=40_000_000, polarity=0, phase=0, sck=Pin(2), mosi=Pin(3))
res = Pin(4, Pin.OUT, value=1)
dc = Pin(5, Pin.OUT, value=0)
cs = Pin(6, Pin.OUT, value=1)
bl = PWM(Pin(7))
bl.freq(1000)
bl.duty_u16(0)

rotation = 1
width, height = 320, 240
level = 1000
epoch = int.from_bytes(os.urandom(2), "little")  # после перезагрузки эпоха заведомо другая
last_rx = time.ticks_ms()
idle = False
fed = time.ticks_ms()
armed = False

strip = bytearray(320 * STRIP * 2)
chunk = bytearray(CHUNK)
chunk_view = memoryview(chunk)
stdin = sys.stdin.buffer
poller = select.poll()
poller.register(sys.stdin, select.POLLIN)


def feed():
    global fed
    fed = time.ticks_ms()


def guard(timer):
    if armed and time.ticks_diff(time.ticks_ms(), fed) > STALL_MS:
        machine.reset()


def write(command, data=None):
    cs(0)
    dc(0)
    spi.write(bytes([command]))
    if data is not None:
        dc(1)
        spi.write(data)
    cs(1)


def window(x, y, w, h):
    x2, y2 = x + w - 1, y + h - 1
    write(0x2A, bytes([x >> 8, x & 0xFF, x2 >> 8, x2 & 0xFF]))
    write(0x2B, bytes([y >> 8, y & 0xFF, y2 >> 8, y2 & 0xFF]))


def backlight(value):
    bl.duty_u16(max(0, min(1000, value)) * 65535 // 1000)


def rotate(n):
    global rotation, width, height
    rotation = n % 4
    width, height = (320, 240) if rotation % 2 else (240, 320)
    write(0x36, bytes([ROTATIONS[rotation]]))


def init():
    res(0)
    time.sleep_ms(50)
    res(1)
    time.sleep_ms(150)
    write(0x01)
    time.sleep_ms(150)
    write(0x11)
    time.sleep_ms(120)
    write(0x3A, b"\x55")
    rotate(rotation)
    write(0x21)  # IPS-матрице нужна инверсия, иначе цвета негативом
    write(0x13)
    write(0x29)


def swap(c):
    return ((c & 0xFF) << 8) | (c >> 8)


def show_idle():
    """Серый экран с надписью «нет связи» и притушенная подсветка."""
    global epoch, idle
    back, ink = swap(0x2104), swap(0xBDF7)
    fb = framebuf.FrameBuffer(strip, width, STRIP, framebuf.RGB565)
    sign = framebuf.FrameBuffer(bytearray(banner.DATA), banner.W, banner.H, framebuf.MONO_HLSB)
    palette = framebuf.FrameBuffer(bytearray(4), 2, 1, framebuf.RGB565)
    palette.pixel(0, 0, back)
    palette.pixel(1, 0, ink)
    sx, sy = (width - banner.W) // 2, (height - banner.H) // 2
    view = memoryview(strip)[: width * STRIP * 2]
    for top in range(0, height, STRIP):
        fb.fill(back)
        fb.blit(sign, sx, sy - top, -1, palette)
        window(0, top, width, STRIP)
        write(0x2C, view)
        feed()
    backlight(IDLE_LEVEL)
    epoch += 1
    idle = True


def alive():
    global last_rx, idle
    last_rx = time.ticks_ms()
    if idle:
        idle = False
        backlight(level)


def blit(x, y, w, h):
    """Принять w*h*2 байт и переложить их на экран, не копя в памяти.

    Среди точек встречается байт 3, а для MicroPython это Ctrl+C, причём ловит он его
    в момент прихода по USB. Поэтому сначала глушим Ctrl+C и только потом отвечаем GO:
    компьютер шлёт точки после этого ответа, не раньше.
    """
    left = w * h * 2
    window(x, y, w, h)
    cs(0)
    dc(0)
    spi.write(b"\x2c")
    dc(1)
    micropython.kbd_intr(-1)
    sys.stdout.write("GO\n")
    waiting = time.ticks_ms()
    try:
        while left:
            feed()
            got = stdin.readinto(chunk_view[: CHUNK if left > CHUNK else left])
            if got:
                spi.write(chunk_view[:got])
                left -= got
                waiting = time.ticks_ms()
            elif time.ticks_diff(time.ticks_ms(), waiting) > PAYLOAD_MS:
                return False  # компьютер пропал; на сборке 1.29 чтение ждёт само, и сюда
                # не доходит: тогда плату перезагружает сторож guard
            else:
                poller.poll(20)
    finally:
        micropython.kbd_intr(3)
        cs(1)
    return True


def handle(line):
    global level
    parts = line.upper().split()
    if not parts:
        return None
    cmd = parts[0]
    try:
        args = [int(p) for p in parts[1:]]
    except ValueError:
        return "ERR number"
    if cmd == "PING":
        return "PONG " + VERSION
    if cmd == "KEEP":
        alive()
        return "OK %d" % epoch
    if cmd == "BLIT" and len(args) == 4:
        x, y, w, h = args
        if x < 0 or y < 0 or w < 1 or h < 1 or x + w > width or y + h > height:
            return "ERR window"
        alive()
        if not blit(x, y, w, h):
            show_idle()
            return "ERR timeout"
        return "OK %d" % epoch
    if cmd == "ROT" and len(args) == 1:
        rotate(args[0])
        return "OK %d %d" % (width, height)
    if cmd == "BL" and len(args) == 1:
        level = max(0, min(1000, args[0]))
        if not idle:
            backlight(level)
        return "OK"
    if cmd == "STATE":
        return "STATE rot=%d size=%dx%d bl=%d epoch=%d idle=%d" % (
            rotation, width, height, level, epoch, idle)
    return "ERR unknown"


def main():
    global armed
    init()
    show_idle()
    timer = Timer(period=500, mode=Timer.PERIODIC, callback=guard)
    armed = True
    buf = b""
    try:
        while True:
            feed()
            for _ in range(64):
                if not poller.poll(0):
                    break
                ch = stdin.read(1)
                if not ch:
                    break
                if ch == b"\r":
                    continue
                if ch == b"\n":  # именно \n: за ним в потоке могут сразу идти точки
                    if buf:
                        try:
                            answer = handle(buf.decode())
                        except Exception as e:
                            answer = "ERR %s" % e
                        buf = b""
                        if answer:
                            sys.stdout.write(answer + "\n")
                elif len(buf) < 64:
                    buf += ch
            if not idle and time.ticks_diff(time.ticks_ms(), last_rx) > IDLE_MS:
                show_idle()
            time.sleep_ms(5)
    finally:
        # Ctrl+C от mpremote: сторож не должен перезагрузить плату посреди заливки файлов
        armed = False
        timer.deinit()


main()

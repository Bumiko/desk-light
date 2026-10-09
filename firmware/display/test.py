"""Проверка экрана ST7789 240x320: рамка по краям, цветные полосы с подписями.

    .venv/Scripts/python -m mpremote connect COM6 run firmware/display/test.py

Экран лежит горизонтально, 320x240. Что должно быть видно — в docs/WIRING-DISPLAY.md.
"""

import time

import framebuf
from machine import PWM, SPI, Pin

W, H, STRIP = 320, 240, 40
MADCTL = 0x60  # горизонтально; если картинка вверх ногами — 0xA0

spi = SPI(0, baudrate=40_000_000, polarity=0, phase=0, sck=Pin(2), mosi=Pin(3))
res = Pin(4, Pin.OUT, value=1)
dc = Pin(5, Pin.OUT, value=0)
cs = Pin(6, Pin.OUT, value=1)
bl = PWM(Pin(7))
bl.freq(1000)
bl.duty_u16(0)


def write(command, data=None):
    cs(0)
    dc(0)
    spi.write(bytes([command]))
    if data is not None:
        dc(1)
        spi.write(data)
    cs(1)


def color(r, g, b):
    """RGB565 со старшим байтом вперёд: так его ждёт экран."""
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


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
    write(0x36, bytes([MADCTL]))
    write(0x21)  # IPS-матрице нужна инверсия, иначе цвета негативом
    write(0x13)
    write(0x29)
    time.sleep_ms(50)


buf = bytearray(W * STRIP * 2)
fb = framebuf.FrameBuffer(buf, W, STRIP, framebuf.RGB565)
glyphs = framebuf.FrameBuffer(bytearray(W // 8 * 8), W, 8, framebuf.MONO_HLSB)


def text(s, x, y, c, scale=2):
    glyphs.fill(0)
    glyphs.text(s, 0, 0, 1)
    for gy in range(8):
        for gx in range(len(s) * 8):
            if glyphs.pixel(gx, gy):
                fb.fill_rect(x + gx * scale, y + gy * scale, scale, scale, c)


def show(row):
    y = row * STRIP
    write(0x2A, bytes([0, 0, (W - 1) >> 8, (W - 1) & 0xFF]))
    write(0x2B, bytes([y >> 8, y & 0xFF, (y + STRIP - 1) >> 8, (y + STRIP - 1) & 0xFF]))
    write(0x2C, buf)


WHITE, BLACK = color(255, 255, 255), color(0, 0, 0)
ROWS = [
    (BLACK, WHITE, "TOP LEFT"),
    (color(255, 0, 0), WHITE, "RED"),
    (color(0, 255, 0), BLACK, "GREEN"),
    (color(0, 0, 255), WHITE, "BLUE"),
    (WHITE, BLACK, "WHITE"),
    (BLACK, WHITE, "desk-display OK"),
]

init()
for row, (back, ink, label) in enumerate(ROWS):
    fb.fill(back)
    text(label, 10, 12, ink)
    frame = color(255, 255, 0)
    fb.vline(0, 0, STRIP, frame)
    fb.vline(W - 1, 0, STRIP, frame)
    if row == 0:
        fb.hline(0, 0, W, frame)
    if row == len(ROWS) - 1:
        fb.hline(0, STRIP - 1, W, frame)
    show(row)
bl.duty_u16(65535)
print("TEST DONE")

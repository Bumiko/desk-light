"""Поиск платы и обмен строками по COM-порту."""

import time

import serial
from serial.tools import list_ports

VID_PID = (0x2E8A, 0x0005)  # RP2040 с MicroPython
GREETING = "desk-light"


class Board:
    """Открытый COM-порт платы: одна команда — один ответ."""

    def __init__(self, port, timeout=1.0):
        self.port = port
        self.ser = serial.Serial(port, 115200, timeout=timeout)

    def send(self, command):
        self.ser.reset_input_buffer()
        self.ser.write((command.strip() + "\r\n").encode())
        return self.ser.readline().decode(errors="replace").strip()

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


def candidates():
    """Порты по убыванию вероятности: сначала совпавшие по VID:PID."""
    ports = [p for p in list_ports.comports() if p.device != "COM1"]
    ports.sort(key=lambda p: (p.vid, p.pid) != VID_PID)
    return [p.device for p in ports]


def find(timeout=3.0):
    """Найти плату по ответу на PING. Бросает RuntimeError, если не нашлась."""
    deadline = time.time() + timeout
    seen = []
    while time.time() < deadline:
        for port in candidates():
            seen.append(port)
            try:
                board = Board(port)
            except Exception:
                continue
            try:
                if GREETING in board.send("PING"):
                    return board
            except Exception:
                pass
            board.close()
        time.sleep(0.3)
    raise RuntimeError(
        "Плата не найдена. Проверены порты: %s" % (", ".join(sorted(set(seen))) or "нет ни одного")
    )

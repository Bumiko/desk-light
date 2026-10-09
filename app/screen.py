"""Экран на второй плате: отправка картинки кусками, только то, что изменилось."""

import time

from PIL import Image, ImageChops

from link import find

GREETING = "desk-display"
BAND = 16  # высота полосы, в которой ищем изменившиеся точки


def rgb565(image):
    """Точки в том виде, в каком их ждёт экран: 2 байта, старший первым."""
    r, g, b = image.convert("RGB").split()
    high = ImageChops.add(r.point(lambda v: v & 0xF8), g.point(lambda v: v >> 5))
    low = ImageChops.add(g.point(lambda v: (v & 0x1C) << 3), b.point(lambda v: v >> 3))
    return Image.merge("LA", (high, low)).tobytes()


class Screen:
    """Связь с платой экрана. Любая ошибка обмена — исключение, связь считается потерянной."""

    def __init__(self, rotation=1, brightness=1000):
        self.rotation = rotation
        self.brightness = brightness
        self.board = None
        self.size = (320, 240)
        self.shown = None   # что сейчас на экране, по нашему мнению
        self.epoch = None   # сколько раз плата сама затирала экран

    def connect(self, timeout=3.0):
        self.close()
        board = find(timeout=timeout, greeting=GREETING)
        board.ser.timeout = 5.0
        board.ser.write_timeout = 5.0
        self.board = board
        answer = self._ask("ROT %d" % self.rotation).split()
        self.size = (int(answer[1]), int(answer[2]))
        self._ask("BL %d" % self.brightness)
        self.shown = None
        self.epoch = None

    def close(self):
        if self.board is not None:
            self.board.close()
            self.board = None

    def _ask(self, command, payload=None):
        """Команда и ответ. Точки уходят вторым заходом, после того как плата ответит GO:
        она должна успеть заглушить Ctrl+C, иначе байт 3 среди точек её прервёт."""
        ser = self.board.ser
        ser.reset_input_buffer()
        ser.write(command.encode() + b"\n")
        answer = ser.readline().decode(errors="replace").strip()
        if payload is not None and answer == "GO":
            ser.write(payload)
            answer = ser.readline().decode(errors="replace").strip()
        if not answer.startswith("OK"):
            raise RuntimeError("плата экрана ответила %r на %s" % (answer, command.split()[0]))
        return answer

    def _epoch(self, answer):
        """Плата затёрла экран сама — значит, наша память о нём неверна."""
        epoch = int(answer.split()[1])
        if epoch != self.epoch:
            if self.epoch is not None:
                self.shown = None
            self.epoch = epoch

    def show(self, image):
        """Показать картинку. Возвращает число отправленных байт."""
        if self.board is None:
            self.connect()
        image = image.convert("RGB")
        if image.size != self.size:
            raise ValueError("картинка %s, экран %s" % (image.size, self.size))
        # эпоху узнаём до сравнения: вдруг плата успела нарисовать «нет связи»
        self._epoch(self._ask("KEEP"))
        width, height = self.size
        sent = 0
        if self.shown is None:
            rects = [(0, 0, width, height)]
        else:
            diff = ImageChops.difference(image, self.shown)
            rects = []
            for top in range(0, height, BAND):
                box = diff.crop((0, top, width, min(top + BAND, height))).getbbox()
                if box:
                    rects.append((box[0], top + box[1], box[2], top + box[3]))
        for left, top, right, bottom in rects:
            data = rgb565(image.crop((left, top, right, bottom)))
            self._ask("BLIT %d %d %d %d" % (left, top, right - left, bottom - top), data)
            sent += len(data)
        self.shown = image
        return sent

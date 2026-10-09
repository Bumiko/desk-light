"""Картинка «нет связи» для прошивки экрана.

    .venv/Scripts/python scripts/make_banner.py

На плате нет русского шрифта, поэтому надпись рисуется здесь и зашивается в прошивку
готовыми точками: firmware/display/banner.py.
"""

import os

from PIL import Image, ImageDraw, ImageFont

TEXT = "нет связи"
FONT = r"C:\Windows\Fonts\segoeuib.ttf"
SIZE = 48

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
font = ImageFont.truetype(FONT, SIZE)
left, top, right, bottom = font.getbbox(TEXT)
width = (right - left + 7) // 8 * 8
height = bottom - top
image = Image.new("1", (width, height), 0)
ImageDraw.Draw(image).text((-left, -top), TEXT, font=font, fill=1)

with open(os.path.join(root, "firmware", "display", "banner.py"), "w", encoding="utf-8",
          newline="\n") as f:
    f.write('"""Надпись «%s» точками. Собрано scripts/make_banner.py, руками не править."""\n\n'
            % TEXT)
    f.write("W = %d\nH = %d\nDATA = %r\n" % (width, height, image.tobytes()))
print("banner %dx%d, %d байт" % (width, height, len(image.tobytes())))

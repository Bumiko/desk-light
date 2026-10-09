# Подсветка клавиатуры (desk-lights)

Белая лента 5 В под монитором подсвечивает клавиатуру. Включение и яркость — горячими
клавишами на ноутбуке: приложение в трее шлёт команды плате по USB.

## Железо
| Узел | Что | Примечание |
|---|---|---|
| Плата | Waveshare RP2040-Zero, MicroPython | USB-C в хаб: это и питание, и COM-порт |
| Ключ | Модуль HW-532: D4184 + оптопара PC817 | ШИМ с `GP0`, коммутирует минус ленты |
| Лента | белая 5 В, ~50 см, 2 контакта | около 0,5 А на максимуме |
| Питание | тот же USB с хаба | отдельного блока питания нет |

Схема пайки — `docs/WIRING.md`.

## Раскладка
- `firmware/main.py` — прошивка платы: ШИМ, плавные переходы, разбор команд. Заливается
  в корень платы под именем `main.py`.
- `app/tray.py` — приложение: значок в трее и горячие клавиши. `app/link.py` — поиск
  платы и обмен строками. `app/cli.py` — одна команда из консоли. `app/selftest.py` —
  прогон железа: вспышки, ступеньки яркости, поиск порога оптопары.
- `firmware/display/main.py` — прошивка второй платы, с экраном: принимает куски картинки
  и кладёт их на экран. Заливается вместе с `banner.py` (надпись «нет связи», собирается
  `scripts/make_banner.py`). `firmware/display/test.py` — проверка экрана полосами.
- `app/screen.py` — отправка картинки на экран кусками. `app/summary_view.py` — как
  выглядит сводка сервера (только рисование). `app/server_screen.py` — забрать сводку,
  нарисовать, отправить; работает потоком внутри `tray.py`. `app/screen_demo.py` —
  образец на экране с выдуманными цифрами.
- `docs/STATUS-API.md` — что должен отдавать сервер. Сама служба на сервере лежит в его
  репозитории (vtexte, `infra/gpu-server/desk-status/`), не здесь.
- `docs/PROTOCOL.md` — команды между приложением и платой. Меняешь протокол — правь оба
  конца и этот файл.
- `docs/WIRING.md` — схема пайки подсветки. `docs/WIRING-DISPLAY.md` — схема пайки
  экрана (вторая плата). `docs/ROADMAP.md` — куда идём.
  `docs/FINDINGS.md` — журнал находок.

## Запуск и проверка
```
.venv/Scripts/pythonw app/tray.py        # приложение в трее, без окна консоли
.venv/Scripts/python app/cli.py ping     # ждём PONG desk-light v1
.venv/Scripts/python app/cli.py set 200  # лента слабо светится
.venv/Scripts/python app/selftest.py     # прогон железа
```
Порт у платы занимается монопольно: пока запущен `tray.py`, ни `cli.py`, ни вторая копия
приложения плату не увидят.

Экран: адрес сводки — в `%LOCALAPPDATA%\desk-light\config.json`, там же
`screen-status.json` — что приложение думает про экран и сервер прямо сейчас.
```
.venv/Scripts/python app/server_screen.py   # сводка на экран отдельно, с журналом
.venv/Scripts/python app/screen_demo.py 5   # образец с выдуманными цифрами, 5 минут
```
Плата экрана заливается так (порт свой): `mpremote connect COM6 cp firmware/display/banner.py
:banner.py + cp firmware/display/main.py :main.py + reset`. Перед заливкой закрыть
приложение в трее: оно держит порт.

Автозапуск при входе в систему — ярлык в папке автозагрузки Windows:
```
powershell -ExecutionPolicy Bypass -File scripts\autostart.ps1           # поставить
powershell -ExecutionPolicy Bypass -File scripts\autostart.ps1 -Remove   # убрать
```

## Публикация
Репозиторий: https://github.com/Bumiko/desk-light — публичный, лицензия MIT.
Новая версия приложения:
```
.venv/Scripts/python -m PyInstaller --noconfirm --onefile --windowed --name desk-light \
  --hidden-import pystray._win32 --distpath dist --workpath build --specpath build app/tray.py
gh release create v1.1 dist/desk-light.exe --notes "что изменилось"
```

## Запреты и договорённости
- COM-порт не хардкодить. Плат две, у обеих VID:PID `2E8A:101F`; различает их только
  ответ на `PING`: `desk-light` — подсветка, `desk-display` — экран.
- Точки на экран шлём только после ответа `GO` (см. `docs/PROTOCOL.md`): иначе байт 3
  среди точек прервёт прошивку как Ctrl+C.
- Адрес сервера в репозиторий не кладём: репозиторий публичный, адрес живёт в
  `config.json` на машине.
- Экран не должен показывать застывшие цифры: нет свежих данных — серый экран. На плате
  за это отвечают два сторожа в `firmware/display/main.py`, не убирать.
- Потолок тока задаётся в прошивке (`MAX_DUTY`) — не поднимать без замера потребления.
- Вся система на 5 В: ни лента, ни модуль не подключаются к 12 В.
- Скрипты PowerShell сохраняем в UTF-8 **с BOM**: без него Windows PowerShell 5.1 читает
  файл как ANSI и спотыкается на русских буквах.
- Хаб питается сам, поэтому плата живёт и без ноутбука. Гасит ленту прошивка: нет команд
  дольше `IDLE_OFF_MS` — свет выключается. Логику «ноутбук ушёл» держим на плате, а не в
  приложении, иначе лента останется гореть.
- `.venv/`, `build/`, `dist/`, `*.uf2` и `state.json` в git не кладём: собранный exe
  раздаётся через Releases, а запомненная яркость живёт в `%LOCALAPPDATA%\desk-light`.
- Значок трея: если передаёшь pystray свою функцию `setup`, в ней обязателен
  `tray.visible = True` — иначе приложение работает, а значка нет.

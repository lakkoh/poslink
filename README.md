# poslink

CLI-утилита + Python-библиотека: сократить ссылку через [clck.ru](https://clck.ru), сгенерировать QR-код с текстом, напечатать на POS-термопринтере.

```
URL → clck.ru → короткая ссылка → QR + текст → печать (escpos)
```

## Установка

```bash
git clone <repo> && cd poslink
pip install -e .
```

После установки команда `poslink` доступна глобально.

### Зависимости

Устанавливаются автоматически: `requests`, `qrcode`, `Pillow`, `python-escpos`.

## CLI

```bash
poslink --device usb "https://example.com"
poslink --device net:192.168.1.50 "https://example.com"
poslink --device serial:COM3:9600 "https://example.com"
poslink --device usb:0416:5011 -o qr.png "https://example.com"
poslink --device usb --no-print --label "" "https://example.com"
```

### Аргументы

| Аргумент | Описание |
|---|---|
| `URL` | Ссылка для сокращения через clck.ru |

### Устройство (`--device`)

| Формат | Пример | Описание |
|---|---|---|
| `usb` | `--device usb` | Первый найденный USB-принтер |
| `usb:VID:PID` | `--device usb:0416:5011` | USB-принтер по VID:PID |
| `net:HOST` | `--device net:192.168.1.50` | Сетевой принтер (порт 9100) |
| `net:HOST:PORT` | `--device net:10.0.0.5:9101` | Сетевой принтер, свой порт |
| `serial:PORT` | `--device serial:COM3` | COM-порт (9600 бод) |
| `serial:PORT:BAUD` | `--device serial:/dev/ttyUSB0:19200` | COM-порт, свой baudrate |
| `win:PORT` | `--device win:USB001` | Прямой вывод в порт Windows (без libusb) |
| `/path/to/device` | `--device /dev/usb/lp0` | Файл устройства (Linux) |

### Параметры изображения

| Опция | По умолч. | Описание |
|---|---|---|
| `--width` | `384` | Ширина холста в px |
| `--height` | — | Макс. высота; если не влезает → предупреждение + обрезка |
| `--qr-size` | `6` | Размер модуля QR-кода в px |
| `--margin` | `10` | Общий отступ от края до контента |
| `--margin-{top,bottom,left,right}` | — | Индивидуальные отступы |

### Текст

| Опция | По умолч. | Описание |
|---|---|---|
| `--label` | `"Ссылка:"` | Текст над URL; `""` = без заголовка |
| `--label-chip` | выкл | Подложка (фон) под текстом |
| `--font` | системный | Путь к TTF-шрифту |
| `--font-size` | `12` | Размер шрифта в pt |
| `--label-gap` | `3` | Отступ между label и URL в px |
| `--no-scheme` | выкл | Не показывать `https://` в ссылке |

### Рамка обрезки

| Опция | По умолч. | Описание |
|---|---|---|
| `--cut-frame` | выкл | Пунктирный прямоугольник для ручной обрезки |
| `--cut-margin` | `5` | Отступ рамки от края изображения |

### Режимы

| Опция | Описание |
|---|---|
| `-o, --output FILE` | Сохранить QR-изображение в PNG |
| `--no-print` | Не печатать, только вывести короткую ссылку в stdout |
| `--verbose` | Подробный вывод |
| `--version` | Показать версию |

## Python API

```python
from poslink import Poslink

p = Poslink(
    "https://example.com",
    device="usb",
    label="Ссылка:",
    label_chip=True,
    width=384,
    qr_size=6,
    no_scheme=True,
)

p.shorten()     # → "https://clck.ru/abc123"
p.render()      # → PIL.Image (1-bit, ч/б)
p.save("qr.png")
p.print()       # печать на POS-принтер
p.run()         # сократить → сгенерировать → напечатать/сохранить
```

### Конструктор

```python
Poslink(
    url: str,
    *,
    device: str | None = None,
    output: str | None = None,
    label: str = "Ссылка:",
    label_chip: bool = False,
    width: int = 384,
    height: int | None = None,
    qr_size: int = 6,
    cut_frame: bool = False,
    cut_margin: int = 5,
    margin: int = 10,
    margin_top: int | None = None,
    margin_bottom: int | None = None,
    margin_left: int | None = None,
    margin_right: int | None = None,
    font: str | None = None,
    font_size: int = 12,
    label_gap: int = 3,
    no_scheme: bool = False,
    verbose: bool = False,
)
```

## Макет изображения

```
← ---------- width ----------- →
┌──────────────────────────────┐  margin_top
│  ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆   │  ← cut_frame (пунктир)
┆  ┆                          ┆  ┆
┆  ┆    ╔══════════════╗      ┆  ┆  QR (qr_size × 29 модулей)
┆  ┆    ║              ║      ┆  ┆
┆  ┆    ╚══════════════╝      ┆  ┆
┆  ┆    ┌────────────────┐    ┆  ┆  label_chip (опционально)
┆  ┆    │ Ссылка:         │    ┆  ┆  текст, центрирован по строкам
┆  ┆    │ clck.ru/abc123  │    ┆  ┆
┆  ┆    └────────────────┘    ┆  ┆
┆  ┆                          ┆  ┆
│  ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆   │  ← cut_frame
│                              │  margin_bottom
└──────────────────────────────┘
```

Каждая строка текста центрируется независимо. Если контент не влезает в `--height` — предупреждение в stderr и обрезка; изображение всё равно генерируется.

## Формат устройства

Парсинг `--device` в статическом методе `Poslink.parse_device(fmt)`:

```python
Poslink.parse_device("usb:0416:5011")
# → {"type": "usb", "vid": 0x0416, "pid": 0x5011}

Poslink.parse_device("net:192.168.1.50:9101")
# → {"type": "net", "host": "192.168.1.50", "port": 9101}
```

## Установка на другие ПК

```bash
# Вариант 1: скопировать и установить
pip install /путь/к/poslink

# Вариант 2: собрать wheel
python -m build
pip install dist/poslink-*.whl

# Вариант 3: просто скопировать poslink.py
python poslink.py --device ... "https://..."
```

## Совместимость

| ОС | USB (pyusb) | USB (win:) | Network | Serial | Bluetooth* |
|---|---|---|---|---|---|
| Linux | ✓ (libusb) | — | ✓ | ✓ | ✓ (через serial) |
| Windows | ✓ (libusb-package) | ✓ (напрямую) | ✓ | ✓ | ✓ (через serial) |

\* Bluetooth — после сопряжения через последовательный порт (`serial:COM5` или `serial:/dev/rfcomm0`)

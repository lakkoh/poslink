# poslink

Скрипт: получить ссылку → сократить через clck.ru → сгенерировать QR с текстом → напечатать на POS-принтере.

Один файл (`poslink.py`), он же CLI, он же импортируемый модуль.

## Constraints

- Не запускай скрипты/утилиты и не редактируй AGENTS.md без согласования.
- Не делай коммиты самостоятельно.
- Всё согласовывай.
- `--device` обязателен (автоопределения нет).

## Структура

```
poslink/
  pyproject.toml    # pip install -e ., entry point poslink → poslink:main
  poslink.py        # class Poslink + CLI (argparse)
```

## CLI

```bash
poslink --device usb "https://example.com"
poslink --device net:192.168.1.50 "https://example.com"
poslink --device serial:COM3:9600 "https://example.com"
poslink --device usb:0416:5011 -o qr.png "https://example.com"
poslink --device usb --no-print --label "" "https://example.com"
```

### Позиционные

| Аргумент | Описание |
|---|---|
| `URL` | Ссылка для сокращения через clck.ru |

### Устройство

| Опция | Описание |
|---|---|
| `--device FORMAT` | **(обязательно)** Формат: `usb[:VID:PID]`, `net:HOST[:PORT]`, `serial:PORT[:BAUD]`, `/path/to/device` |

### Размеры и отступы

| Опция | По умолч. | Описание |
|---|---|---|
| `--width` | `384` | Ширина холста в px |
| `--height` | — | Макс. высота; если не влезает → ошибка |
| `--qr-size` | `6` | Размер модуля QR-кода в px |
| `--margin` | `10` | Общий отступ от края до контента |
| `--margin-top` | — | Переопределяет `--margin` для верха |
| `--margin-bottom` | — | (аналогично) |
| `--margin-left` | — | |
| `--margin-right` | — | |

### Рамка обрезки

| Опция | По умолч. | Описание |
|---|---|---|
| `--cut-frame` | выкл | Пунктирный прямоугольник для ручной обрезки |
| `--cut-margin` | `5` | Отступ рамки от края изображения |

### Текст

| Опция | По умолч. | Описание |
|---|---|---|
| `--label` | `"Ссылка:"` | Текст над URL; `""` = без заголовка |
| `--label-chip` | выкл | Подложка (фон) под текстом |
| `--font` | системный | Путь к TTF-шрифту |
| `--font-size` | `12` | Размер шрифта в pt |
| `--label-gap` | `3` | Отступ между label и URL в px |
| `--no-scheme` | выкл | Не показывать `https://` в ссылке |

### Режимы

| Опция | Описание |
|---|---|
| `-o, --output FILE` | Сохранить QR-изображение в PNG |
| `--no-print` | Не печатать, только вывести короткую ссылку в stdout |
| `--verbose` | Подробный вывод |
| `--version` | Показать версию |

## Класс Poslink (API)

```python
class Poslink:
    def __init__(self, url: str, *, device=None, output=None, label="Ссылка:",
                 label_chip=False, width=384, height=None, qr_size=6,
                 cut_frame=False, cut_margin=5, margin=10,
                 margin_top=None, margin_bottom=None,
                 margin_left=None, margin_right=None,
                 font=None, font_size=12, label_gap=3, no_scheme=False, verbose=False):
        ...

    def shorten(self) -> str
        # GET https://clck.ru/--?url=... → response.text
        # Возвращает короткую ссылку

    def render(self) -> Image.Image
        # Генерирует PIL Image (1-bit, ч/б)
        # Если height задан и контент не влезает → RuntimeError

    def save(self, path: str)
        # self.render().save(path)

    def print(self)
        # self.render() → масштаб (принтер) → escpos.print_image()

    def run(self)
        # shorten() → render() → print() / save() / stdout
```

## Макет изображения

```
← ---------- width (384) ----------- →
┌────────────────────────────────────┐  margin_top
│  ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆  │  ← cut_frame (опционально, пунктир)
┆  ┆                                ┆  ┆
┆  ┆      ╔══════════════╗          ┆  ┆  QR size = qr_size * 29 modules
┆  ┆      ║              ║          ┆  ┆
┆  ┆      ╚══════════════╝          ┆  ┆  отступ ~8px
┆  ┆      ┌──────────────────┐      ┆  ┆  label_chip (опционально)
┆  ┆      │ Ссылка:           │      ┆  ┆  font_size (pt → px)
┆  ┆      │ https://clck.ru/…│      ┆  ┆
┆  ┆      └──────────────────┘      ┆  ┆
┆  ┆                                ┆  ┆
│  ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆ ┆  │  ← cut_frame
│                                    │  margin_bottom
└────────────────────────────────────┘
```

## Слой заливки

1. Белый фон
2. Пунктирная рамка (если `--cut-frame`)
3. QR-код (чёрный по белому, центрирован)
4. Подложка под текст (если `--label-chip`, серый фон с rounded rect)
5. Текст (label + URL, центрирован)

## Если контент не влезает в `--height`

Предупреждение в stderr + обрезка изображения до указанной высоты. Изображение всё равно генерируется и сохраняется/печатается.

## Формат устройства (парсинг `--device`)

| Формат | Парсинг | escpos-класс |
|---|---|---|
| `win:PORT` | `win:USB001` → path="USB001" | `File("USB001")` (напрямую в порт Windows) |
| `usb` | — | `Usb(0x04b8, 0x0202)` с авто-VID/PID? |
| `usb:VID:PID` | `usb:0416:5011` → VID=0x0416, PID=0x5011 | `Usb(0x0416, 0x5011)` |
| `net:HOST` | `net:192.168.1.50` → host, port=9100 | `Network("192.168.1.50", 9100)` |
| `net:HOST:PORT` | `net:192.168.1.50:9101` | `Network("192.168.1.50", 9101)` |
| `serial:PORT` | `serial:COM3` → port, baud=9600 | `Serial("COM3", 9600)` |
| `serial:PORT:BAUD` | `serial:/dev/ttyUSB0:19200` | `Serial("/dev/ttyUSB0", 19200)` |
| `/path` | содержит `/` или `\` | `File("/dev/usb/lp0")` или `Serial(...)` |

Парсинг в статическом методе `Poslink.parse_device(fmt) → dict`.

## Зависимости

```toml
dependencies = [
    "requests",
    "qrcode[pil]",
    "Pillow",
    "python-escpos",
    "pyusb",
    "pyserial",
    "libusb-package",
]
```

Python >= 3.10.

## Тесты

Нет CI, тестов пока нет.

import sys
import argparse
import textwrap
import requests
import qrcode
from PIL import Image, ImageDraw, ImageFont

try:
    import libusb_package
except ImportError:
    pass
else:
    import os
    _libusb_dir = os.path.dirname(libusb_package.__file__)
    if _libusb_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _libusb_dir + os.pathsep + os.environ.get("PATH", "")

from escpos import printer as escpos_printer


__version__ = "0.1.0"


def _load_font(font_path, font_size_px):
    if font_path:
        return ImageFont.truetype(font_path, font_size_px)
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "DejaVuSans.ttf",
        "LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, font_size_px)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _pt_to_px(pt, dpi=203):
    return round(pt * dpi / 72.0)


def _dither_rect(draw, x, y, w, h, step=4):
    for py in range(y, y + h):
        for px in range(x, x + w):
            if (px + py) % (step * 2) < step:
                draw.point((px, py), fill=0)


class Poslink:
    def __init__(self, url, *, device=None, output=None, label="\u0421\u0441\u044b\u043b\u043a\u0430:",
                 label_chip=False, width=384, height=None, qr_size=6,
                 cut_frame=False, cut_margin=5, margin=10,
                 margin_top=None, margin_bottom=None,
                 margin_left=None, margin_right=None,
                 font=None, font_size=12, label_gap=3, no_scheme=False, verbose=False):
        self.url = url
        self.device = device
        self.output = output
        self.label = label
        self.label_chip = label_chip
        self.no_scheme = no_scheme
        self.width = width
        self.height = height
        self.qr_size = qr_size
        self.cut_frame = cut_frame
        self.cut_margin = cut_margin
        self.margin = margin
        self.margin_top = margin_top if margin_top is not None else margin
        self.margin_bottom = margin_bottom if margin_bottom is not None else margin
        self.margin_left = margin_left if margin_left is not None else margin
        self.margin_right = margin_right if margin_right is not None else margin
        self.font_path = font
        self.font_size = font_size
        self.label_gap = label_gap
        self.verbose = verbose

    def shorten(self):
        if self.verbose:
            print(f"[poslink] \u0421\u043e\u043a\u0440\u0430\u0449\u0435\u043d\u0438\u0435: {self.url}", file=sys.stderr)
        r = requests.get("https://clck.ru/--", params={"url": self.url})
        r.raise_for_status()
        short = r.text.strip()
        if self.verbose:
            print(f"[poslink] \u041a\u043e\u0440\u043e\u0442\u043a\u0430\u044f \u0441\u0441\u044b\u043b\u043a\u0430: {short}", file=sys.stderr)
        return short

    def render(self):
        short = self.shorten()
        qr_img = self._make_qr(short)
        text_lines = self._get_text_lines(short)
        return self._compose(qr_img, text_lines)

    def _make_qr(self, text):
        qr = qrcode.QRCode(box_size=self.qr_size, border=4)
        qr.add_data(text)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").convert("1")

    def _get_text_lines(self, short_url):
        lines = []
        if self.label:
            lines.append(self.label)
        display = short_url
        if self.no_scheme:
            for prefix in ("https://", "http://"):
                if display.startswith(prefix):
                    display = display[len(prefix):]
                    break
        lines.append(display)
        return lines

    def _compose(self, qr_img, text_lines):
        W = self.width
        MT = self.margin_top
        MB = self.margin_bottom
        ML = self.margin_left
        MR = self.margin_right
        content_w = W - ML - MR

        font_px = _pt_to_px(self.font_size)
        font = _load_font(self.font_path, font_px)
        line_gap = self.label_gap

        tmp = Image.new("1", (1, 1))
        tmp_draw = ImageDraw.Draw(tmp)
        tw = []
        th = []
        for line in text_lines:
            bbox = tmp_draw.textbbox((0, 0), line, font=font)
            tw.append(bbox[2] - bbox[0])
            th.append(bbox[3] - bbox[1])

        max_text_w = max(tw) if tw else 0
        if max_text_w > content_w:
            print(
                f"\u041f\u0440\u0435\u0434\u0443\u043f\u0440\u0435\u0436\u0434\u0435\u043d\u0438\u0435: \u0442\u0435\u043a\u0441\u0442 "
                f"({max_text_w} px) \u0448\u0438\u0440\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e\u0439 \u043e\u0431\u043b\u0430\u0441\u0442\u0438 "
                f"({content_w} px). \u0423\u0432\u0435\u043b\u0438\u0447\u044c\u0442\u0435 --width \u0438\u043b\u0438 "
                "\u0443\u043c\u0435\u043d\u044c\u0448\u0438\u0442\u0435 \u0440\u0430\u0437\u043c\u0435\u0440 \u0448\u0440\u0438\u0444\u0442\u0430.",
                file=sys.stderr,
            )

        total_text_h = sum(th) + line_gap * (len(th) - 1)

        chip_pad_x = 8
        chip_pad_y = 4
        chip_w = max_text_w + 2 * chip_pad_x
        chip_h = total_text_h + 2 * chip_pad_y

        qr_w, qr_h = qr_img.size
        gap = 10
        required_height = MT + qr_h + gap + chip_h + MB

        if self.height is not None and required_height > self.height:
            print(
                f"\u041f\u0440\u0435\u0434\u0443\u043f\u0440\u0435\u0436\u0434\u0435\u043d\u0438\u0435: \u043a\u043e\u043d\u0442\u0435\u043d\u0442 "
                f"({required_height} px) \u043d\u0435 \u0432\u043b\u0435\u0437\u0430\u0435\u0442 \u0432 "
                f"\u0432\u044b\u0441\u043e\u0442\u0443 ({self.height} px). "
                f"\u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 \u0431\u0443\u0434\u0435\u0442 \u043e\u0431\u0440\u0435\u0437\u0430\u043d\u043e. "
                "\u0423\u0432\u0435\u043b\u0438\u0447\u044c\u0442\u0435 --height, "
                "\u0443\u043c\u0435\u043d\u044c\u0448\u0438\u0442\u0435 --qr-size "
                "\u0438\u043b\u0438 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 --output \u0434\u043b\u044f \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438.",
                file=sys.stderr,
            )

        final_h = required_height if self.height is None else self.height

        img = Image.new("1", (W, final_h), 1)
        draw = ImageDraw.Draw(img)

        if self.cut_frame:
            CM = self.cut_margin
            dot_step = 6
            for x in range(CM, W - CM, dot_step):
                draw.point((x, CM), fill=0)
                draw.point((x, final_h - CM - 1), fill=0)
            for y in range(CM, final_h - CM, dot_step):
                draw.point((CM, y), fill=0)
                draw.point((W - CM - 1, y), fill=0)

        qr_x = ML + (content_w - qr_w) // 2
        qr_y = MT
        img.paste(qr_img, (qr_x, qr_y))

        text_y = qr_y + qr_h + gap

        if self.label_chip and text_lines:
            chip_text_x = ML + (content_w - chip_w) // 2
            chip_y = text_y - chip_pad_y
            _dither_rect(draw, chip_text_x, chip_y, chip_w, chip_h, step=4)

        cur_y = text_y
        for i, line in enumerate(text_lines):
            line_x = ML + (content_w - tw[i]) // 2
            draw.text((line_x, cur_y), line, font=font, fill=0)
            cur_y += th[i] + line_gap

        return img

    def save(self, path):
        self.render().save(path)

    def _print_img(self, img):
        dev = self._get_printer()
        dev.image(img)
        dev.cut()

    def _get_printer(self):
        if not self.device:
            raise RuntimeError("--device \u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d")
        info = self.parse_device(self.device)
        t = info["type"]
        try:
            if t == "usb":
                if info.get("vid") is not None and info.get("pid") is not None:
                    return escpos_printer.Usb(info["vid"], info["pid"])
                return escpos_printer.Usb(0x04b8, 0x0202)
            elif t == "net":
                return escpos_printer.Network(info["host"], info.get("port", 9100))
            elif t == "serial":
                return escpos_printer.Serial(info["port"], info.get("baud", 9600))
            elif t == "file":
                return escpos_printer.File(info["path"])
            else:
                raise RuntimeError(f"\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u044b\u0439 \u0442\u0438\u043f \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u0430: {t}")
        except Exception as e:
            raise RuntimeError(f"\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u043a {self.device}: {e}") from e

    @staticmethod
    def parse_device(fmt):
        if fmt.startswith("usb"):
            if ":" in fmt:
                parts = fmt.split(":")
                if len(parts) == 3:
                    return {"type": "usb", "vid": int(parts[1], 16), "pid": int(parts[2], 16)}
            return {"type": "usb"}
        elif fmt.startswith("net:"):
            rest = fmt[4:]
            if ":" in rest:
                host, port = rest.rsplit(":", 1)
                return {"type": "net", "host": host, "port": int(port)}
            return {"type": "net", "host": rest, "port": 9100}
        elif fmt.startswith("serial:"):
            rest = fmt[7:]
            if ":" in rest:
                port, baud = rest.rsplit(":", 1)
                try:
                    return {"type": "serial", "port": port, "baud": int(baud)}
                except ValueError:
                    pass
            return {"type": "serial", "port": rest, "baud": 9600}
        elif fmt.startswith("win:"):
            return {"type": "file", "path": fmt[4:]}
        elif "/" in fmt or "\\" in fmt:
            return {"type": "file", "path": fmt}
        else:
            raise ValueError(
                f"\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u044b\u0439 \u0444\u043e\u0440\u043c\u0430\u0442 \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u0430: {fmt}. "
                "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 usb[:VID:PID], "
                "net:HOST[:PORT], serial:PORT[:BAUD], win:PORT \u0438\u043b\u0438 /path/to/device"
            )

    def run(self):
        short = self.shorten()
        do_print = bool(self.device)
        do_save = bool(self.output)
        if do_save or do_print:
            qr_img = self._make_qr(short)
            text_lines = self._get_text_lines(short)
            img = self._compose(qr_img, text_lines)
            if do_save:
                img.save(self.output)
                if self.verbose:
                    print(f"[poslink] \u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e: {self.output}", file=sys.stderr)
            if do_print:
                self._print_img(img)
        else:
            print(short)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="poslink",
        description="\u0421\u043e\u043a\u0440\u0430\u0449\u0435\u043d\u0438\u0435 \u0441\u0441\u044b\u043b\u043e\u043a \u0447\u0435\u0440\u0435\u0437 clck.ru, \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f QR, \u043f\u0435\u0447\u0430\u0442\u044c \u043d\u0430 POS-\u043f\u0440\u0438\u043d\u0442\u0435\u0440\u0435",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            \u041f\u0440\u0438\u043c\u0435\u0440\u044b:
              poslink --device usb "https://example.com"
              poslink --device net:192.168.1.50 "https://example.com"
              poslink --device serial:COM3:9600 -o qr.png "https://example.com"
              poslink --device win:USB001 "https://example.com"
        """),
    )
    parser.add_argument("url", help="\u0421\u0441\u044b\u043b\u043a\u0430 \u0434\u043b\u044f \u0441\u043e\u043a\u0440\u0430\u0449\u0435\u043d\u0438\u044f")
    parser.add_argument("--device", "-d", metavar="FORMAT",
                        help="\u0424\u043e\u0440\u043c\u0430\u0442: usb[:VID:PID] | net:HOST[:PORT] | serial:PORT[:BAUD] | win:PORT | /path")
    parser.add_argument("-o", "--output", metavar="FILE",
                        help="\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c QR-\u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 \u0432 PNG")
    parser.add_argument("--no-print", action="store_true",
                        help="\u041d\u0435 \u043f\u0435\u0447\u0430\u0442\u0430\u0442\u044c, \u0442\u043e\u043b\u044c\u043a\u043e \u0432\u044b\u0432\u043e\u0434 \u043a\u043e\u0440\u043e\u0442\u043a\u043e\u0439 \u0441\u0441\u044b\u043b\u043a\u0438 \u0432 stdout")
    parser.add_argument("--label", default="\u0421\u0441\u044b\u043b\u043a\u0430:",
                        help='\u0422\u0435\u043a\u0441\u0442 \u043d\u0430\u0434 \u0441\u0441\u044b\u043b\u043a\u043e\u0439 (\u043f\u043e \u0443\u043c\u043e\u043b\u0447. "\u0421\u0441\u044b\u043b\u043a\u0430:"; "" = \u0431\u0435\u0437 \u0437\u0430\u0433\u043e\u043b\u043e\u0432\u043a\u0430)')
    parser.add_argument("--label-chip", action="store_true",
                        help="\u0420\u0438\u0441\u043e\u0432\u0430\u0442\u044c \u043f\u043e\u0434\u043b\u043e\u0436\u043a\u0443 \u043f\u043e\u0434 \u0442\u0435\u043a\u0441\u0442\u043e\u043c")
    parser.add_argument("--no-scheme", action="store_true",
                        help="\u041d\u0435 \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c https:// \u0432 \u0441\u0441\u044b\u043b\u043a\u0435")
    parser.add_argument("--width", type=int, default=384,
                        help="\u0428\u0438\u0440\u0438\u043d\u0430 \u0445\u043e\u043b\u0441\u0442\u0430 \u0432 px (\u043f\u043e \u0443\u043c\u043e\u043b\u0447. 384)")
    parser.add_argument("--height", type=int, default=None,
                        help="\u041c\u0430\u043a\u0441. \u0432\u044b\u0441\u043e\u0442\u0430; \u0435\u0441\u043b\u0438 \u043d\u0435 \u0432\u043b\u0435\u0437\u0430\u0435\u0442 \u2192 \u043e\u0448\u0438\u0431\u043a\u0430")
    parser.add_argument("--qr-size", type=int, default=6,
                        help="\u0420\u0430\u0437\u043c\u0435\u0440 \u043c\u043e\u0434\u0443\u043b\u044f QR \u0432 px (\u043f\u043e \u0443\u043c\u043e\u043b\u0447. 6)")
    parser.add_argument("--cut-frame", action="store_true",
                        help="\u041f\u0443\u043d\u043a\u0442\u0438\u0440\u043d\u044b\u0439 \u043f\u0440\u044f\u043c\u043e\u0443\u0433\u043e\u043b\u044c\u043d\u0438\u043a \u0434\u043b\u044f \u043e\u0431\u0440\u0435\u0437\u043a\u0438")
    parser.add_argument("--cut-margin", type=int, default=5,
                        help="\u041e\u0442\u0441\u0442\u0443\u043f \u0440\u0430\u043c\u043a\u0438 \u043e\u0442 \u043a\u0440\u0430\u044f (\u043f\u043e \u0443\u043c\u043e\u043b\u0447. 5)")
    parser.add_argument("--margin", type=int, default=10,
                        help="\u041e\u0431\u0449\u0438\u0439 \u043e\u0442\u0441\u0442\u0443\u043f (\u043f\u043e \u0443\u043c\u043e\u043b\u0447. 10)")
    parser.add_argument("--margin-top", type=int,
                        help="\u041e\u0442\u0441\u0442\u0443\u043f \u0441\u0432\u0435\u0440\u0445\u0443 (\u043f\u0435\u0440\u0435\u043e\u043f\u0440\u0435\u0434\u0435\u043b\u044f\u0435\u0442 --margin)")
    parser.add_argument("--margin-bottom", type=int,
                        help="\u041e\u0442\u0441\u0442\u0443\u043f \u0441\u043d\u0438\u0437\u0443")
    parser.add_argument("--margin-left", type=int,
                        help="\u041e\u0442\u0441\u0442\u0443\u043f \u0441\u043b\u0435\u0432\u0430")
    parser.add_argument("--margin-right", type=int,
                        help="\u041e\u0442\u0441\u0442\u0443\u043f \u0441\u043f\u0440\u0430\u0432\u0430")
    parser.add_argument("--font", type=str,
                        help="\u041f\u0443\u0442\u044c \u043a TTF-\u0448\u0440\u0438\u0444\u0442\u0443")
    parser.add_argument("--font-size", type=int, default=12,
                        help="\u0420\u0430\u0437\u043c\u0435\u0440 \u0448\u0440\u0438\u0444\u0442\u0430 \u0432 pt (\u043f\u043e \u0443\u043c\u043e\u043b\u0447. 12)")
    parser.add_argument("--label-gap", type=int, default=3,
                        help="\u041e\u0442\u0441\u0442\u0443\u043f \u043c\u0435\u0436\u0434\u0443 label \u0438 URL \u0432 px (\u043f\u043e \u0443\u043c\u043e\u043b\u0447. 3)")
    parser.add_argument("--verbose", action="store_true",
                        help="\u041f\u043e\u0434\u0440\u043e\u0431\u043d\u044b\u0439 \u0432\u044b\u0432\u043e\u0434")
    return parser


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if "--version" in argv:
        print(f"poslink v{__version__}")
        return

    parser = parse_args()
    args = parser.parse_args(argv)

    if not args.device and not args.output and not args.no_print:
        parser.print_help()
        print(file=sys.stderr)
        print("\u041e\u0448\u0438\u0431\u043a\u0430: \u0443\u043a\u0430\u0436\u0438\u0442\u0435 --device \u0434\u043b\u044f \u043f\u0435\u0447\u0430\u0442\u0438, --output \u0434\u043b\u044f \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u044f \u0438\u043b\u0438 --no-print", file=sys.stderr)
        sys.exit(1)

    try:
        p = Poslink(
            url=args.url,
            device=args.device,
            output=args.output,
            label=args.label,
            label_chip=args.label_chip,
            width=args.width,
            height=args.height,
            qr_size=args.qr_size,
            cut_frame=args.cut_frame,
            cut_margin=args.cut_margin,
            margin=args.margin,
            margin_top=args.margin_top,
            margin_bottom=args.margin_bottom,
            margin_left=args.margin_left,
            margin_right=args.margin_right,
            font=args.font,
            font_size=args.font_size,
            label_gap=args.label_gap,
            no_scheme=args.no_scheme,
            verbose=args.verbose,
        )
        if args.no_print:
            short = p.shorten()
            print(short)
        else:
            p.run()
    except RuntimeError as e:
        print(f"\u041e\u0448\u0438\u0431\u043a\u0430: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(f"\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u0435\u0442\u0438: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

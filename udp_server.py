import argparse
import socket
from typing import Callable, List, Optional
import threading

from display_protocol import Command, Opcode, ProtocolError, parse_commands

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 9999
MAX_DATAGRAM = 65535
HEX_PREVIEW_BYTES = 32

# Імена параметрів кожної команди (у тому порядку, в якому їх повертає parse_commands).
PARAM_NAMES = {
    Opcode.CLEAR_DISPLAY: ("color",),
    Opcode.DRAW_PIXEL: ("x0", "y0", "color"),
    Opcode.DRAW_LINE: ("x0", "y0", "x1", "y1", "color"),
    Opcode.DRAW_RECTANGLE: ("x0", "y0", "w", "h", "color"),
    Opcode.FILL_RECTANGLE: ("x0", "y0", "w", "h", "color"),
    Opcode.DRAW_ELLIPSE: ("x0", "y0", "radius_x", "radius_y", "color"),
    Opcode.FILL_ELLIPSE: ("x0", "y0", "radius_x", "radius_y", "color"),
    Opcode.DRAW_CIRCLE: ("x0", "y0", "radius", "color"),
    Opcode.FILL_CIRCLE: ("x0", "y0", "radius", "color"),
    Opcode.DRAW_ROUNDED_RECTANGLE: ("x0", "y0", "w", "h", "radius", "color"),
    Opcode.FILL_ROUNDED_RECTANGLE: ("x0", "y0", "w", "h", "radius", "color"),
    Opcode.DRAW_TEXT: ("x0", "y0", "color", "font_number", "text"),
    Opcode.DRAW_IMAGE: ("x0", "y0", "w", "h", "data"),
    Opcode.SET_ORIENTATION: ("orientation",),
    Opcode.GET_WIDTH: (),
    Opcode.GET_HEIGHT: (),
}


def format_value(name: str, value) -> str:
    if name == "color":
        return "0x{:04X}".format(value)
    if isinstance(value, bytes):
        return "<{} байт>".format(len(value))
    if isinstance(value, str):
        return repr(value)
    return str(value)


def format_command(command: Command) -> str:
    names = PARAM_NAMES[command.opcode]
    params = " ".join(
        "{}={}".format(name, format_value(name, value))
        for name, value in zip(names, command.arguments)
    )
    return "{} {}".format(command.opcode.name, params).rstrip()


def describe_packet(data: bytes) -> List[str]:
    """Рядки для виводу в консоль: команди пакета або повідомлення про помилку."""
    try:
        commands = parse_commands(data)
    except ProtocolError as error:
        return ["ПОМИЛКА: {}".format(error)]
    if not commands:
        return ["Порожній пакет: команд немає"]
    return [format_command(command) for command in commands]


def hex_preview(data: bytes) -> str:
    text = " ".join("{:02X}".format(b) for b in data[:HEX_PREVIEW_BYTES])
    return text + (" …" if len(data) > HEX_PREVIEW_BYTES else "")


def handle_datagram(data: bytes, address, out: Callable[[str], None] = print) -> None:
    out("[{}:{}] пакет {} байт: {}".format(address[0], address[1], len(data), hex_preview(data)))
    try:
        lines = describe_packet(data)
    except Exception as error:  # сервер має пережити будь-який пакет
        lines = ["ВНУТРІШНЯ ПОМИЛКА: {!r}".format(error)]
    for line in lines:
        out("  " + line)


def serve(sock: socket.socket, stop_event: Optional[threading.Event] = None,
          out: Callable[[str], None] = print) -> None:
    """Приймає пакети, поки не встановлено stop_event (або вічно, якщо його немає)."""
    sock.settimeout(0.2)
    while stop_event is None or not stop_event.is_set():
        try:
            data, address = sock.recvfrom(MAX_DATAGRAM)
        except socket.timeout:
            continue
        except ConnectionResetError:  # Windows: ICMP-відповідь на раніше надісланий пакет
            continue
        handle_datagram(data, address, out)


def main() -> None:
    parser = argparse.ArgumentParser(description="UDP-сервер дисплейного модуля")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.host, args.port))
        print("UDP-сервер слухає {}:{}. Зупинка: Ctrl+C".format(args.host, args.port))
        try:
            serve(sock)
        except KeyboardInterrupt:
            print("\nСервер зупинено")


if __name__ == "__main__":
    main()

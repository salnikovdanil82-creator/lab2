import argparse
import socket

DEMO_PACKETS = [
    ("правильна: clear display", "01 00 00"),
    ("правильна: draw pixel (10, 20, red)", "02 0A 00 14 00 00 F8"),
    ("правильна: fill rectangle", "05 0A 00 14 00 64 00 32 00 E0 07"),
    ("правильна: draw text \"Hi\"", "0C 0A 00 0A 00 00 F8 01 02 00 48 69"),
    ("правильна: кілька команд в одному пакеті", "0E 01 0F 10"),
    ("ПОМИЛКА: невідомий opcode", "7F"),
    ("ПОМИЛКА: обрізана команда draw pixel", "02 0A 00"),
    ("ПОМИЛКА: orientation = 4", "0E 04"),
    ("ПОМИЛКА: від'ємна ширина прямокутника", "04 00 00 00 00 FF FF 0A 00 00 F8"),
    ("ПОМИЛКА: некоректний UTF-8 у тексті", "0C 00 00 00 00 00 00 00 01 00 FF"),
    ("порожній пакет", ""),
    ("правильна після помилок: draw circle", "08 32 00 32 00 19 00 00 F8"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Тестовий UDP-клієнт")
    parser.add_argument("packets", nargs="*", help="пакети в hex, наприклад \"02 0A 00 14 00 00 F8\"")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9999)
    args = parser.parse_args()

    if args.packets:
        items = [("користувацький пакет", text) for text in args.packets]
    else:
        items = DEMO_PACKETS

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for title, hex_text in items:
            data = bytes.fromhex(hex_text)
            sock.sendto(data, (args.host, args.port))
            print("надіслано ({} байт): {}".format(len(data), title))


if __name__ == "__main__":
    main()

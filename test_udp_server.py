import socket
import threading
import time
import unittest

from udp_server import describe_packet, format_command, serve
from display_protocol import Command, Opcode


class DescribePacketTests(unittest.TestCase):
    def test_valid_command_shows_name_and_parameters(self):
        lines = describe_packet(bytes.fromhex("02 0A 00 14 00 00 F8"))
        self.assertEqual(lines, ["DRAW_PIXEL x0=10 y0=20 color=0xF800"])

    def test_multiple_commands_in_one_packet(self):
        lines = describe_packet(bytes.fromhex("0E 01 0F 10"))
        self.assertEqual(lines, ["SET_ORIENTATION orientation=1", "GET_WIDTH", "GET_HEIGHT"])

    def test_text_and_image_formatting(self):
        text = describe_packet(bytes.fromhex("0C 0A 00 0A 00 00 F8 01 02 00 48 69"))
        self.assertEqual(text, ["DRAW_TEXT x0=10 y0=10 color=0xF800 font_number=1 text='Hi'"])
        image = describe_packet(bytes.fromhex("0D 00 00 00 00 02 00 01 00 00 F8 E0 07"))
        self.assertEqual(image, ["DRAW_IMAGE x0=0 y0=0 w=2 h=1 data=<4 байт>"])

    def test_empty_packet(self):
        self.assertEqual(describe_packet(b""), ["Порожній пакет: команд немає"])

    def test_invalid_packets_give_error_message(self):
        for hex_text in ("7F", "02 0A 00", "0E 04", "04 00 00 00 00 FF FF 0A 00 00 F8",
                         "0C 00 00 00 00 00 00 00 01 00 FF"):
            with self.subTest(hex_text):
                lines = describe_packet(bytes.fromhex(hex_text))
                self.assertEqual(len(lines), 1)
                self.assertTrue(lines[0].startswith("ПОМИЛКА:"))

    def test_format_command_without_arguments(self):
        self.assertEqual(format_command(Command(Opcode.GET_HEIGHT, ())), "GET_HEIGHT")


class ServerOverUdpTests(unittest.TestCase):
    def test_server_survives_invalid_packets(self):
        output = []
        stop = threading.Event()
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_sock.bind(("127.0.0.1", 0))
        port = server_sock.getsockname()[1]
        thread = threading.Thread(target=serve, args=(server_sock, stop, output.append))
        thread.start()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                for hex_text in ("02 0A 00 14 00 00 F8", "7F", "", "0F"):
                    client.sendto(bytes.fromhex(hex_text), ("127.0.0.1", port))
            deadline = time.time() + 3
            while time.time() < deadline and not any("GET_WIDTH" in line for line in output):
                time.sleep(0.05)
        finally:
            stop.set()
            thread.join()
            server_sock.close()

        text = "\n".join(output)
        self.assertIn("DRAW_PIXEL x0=10 y0=20 color=0xF800", text)
        self.assertIn("ПОМИЛКА: Unknown opcode 0x7F", text)
        self.assertIn("Порожній пакет", text)
        self.assertIn("GET_WIDTH", text)  # після помилок сервер ще працює


if __name__ == "__main__":
    unittest.main()

from dataclasses import dataclass
from enum import IntEnum
import struct
from typing import Any, Tuple


class Opcode(IntEnum):
    CLEAR_DISPLAY = 0x01
    DRAW_PIXEL = 0x02
    DRAW_LINE = 0x03
    DRAW_RECTANGLE = 0x04
    FILL_RECTANGLE = 0x05
    DRAW_ELLIPSE = 0x06
    FILL_ELLIPSE = 0x07
    DRAW_CIRCLE = 0x08
    FILL_CIRCLE = 0x09
    DRAW_ROUNDED_RECTANGLE = 0x0A
    FILL_ROUNDED_RECTANGLE = 0x0B
    DRAW_TEXT = 0x0C
    DRAW_IMAGE = 0x0D
    SET_ORIENTATION = 0x0E
    GET_WIDTH = 0x0F
    GET_HEIGHT = 0x10


@dataclass(frozen=True)
class Command:
    opcode: Opcode
    arguments: Tuple[Any, ...]


class ProtocolError(ValueError):
    """Raised when a byte buffer is not a valid protocol command stream."""


_FIXED_FORMATS = {
    Opcode.CLEAR_DISPLAY: "<H",
    Opcode.DRAW_PIXEL: "<hhH",
    Opcode.DRAW_LINE: "<hhhhH",
    Opcode.DRAW_RECTANGLE: "<hhhhH",
    Opcode.FILL_RECTANGLE: "<hhhhH",
    Opcode.DRAW_ELLIPSE: "<hhhhH",
    Opcode.FILL_ELLIPSE: "<hhhhH",
    Opcode.DRAW_CIRCLE: "<hhhH",
    Opcode.FILL_CIRCLE: "<hhhH",
    Opcode.DRAW_ROUNDED_RECTANGLE: "<hhhhhH",
    Opcode.FILL_ROUNDED_RECTANGLE: "<hhhhhH",
    Opcode.SET_ORIENTATION: "<B",
    Opcode.GET_WIDTH: "<",
    Opcode.GET_HEIGHT: "<",
}


def _require(data: memoryview, offset: int, length: int, opcode: Opcode) -> None:
    if len(data) - offset < length:
        raise ProtocolError(
            "Truncated {} command at byte {}: expected {} more byte(s)".format(
                opcode.name, offset, length - (len(data) - offset)
            )
        )


def _validate_geometry(opcode: Opcode, values: Tuple[int, ...], offset: int) -> None:
    if opcode in (Opcode.DRAW_RECTANGLE, Opcode.FILL_RECTANGLE):
        width, height = values[2:4]
        if width <= 0 or height <= 0:
            raise ProtocolError("Rectangle dimensions must be positive at byte {}".format(offset))
    elif opcode in (Opcode.DRAW_ELLIPSE, Opcode.FILL_ELLIPSE):
        if values[2] < 0 or values[3] < 0:
            raise ProtocolError("Ellipse radii must be non-negative at byte {}".format(offset))
    elif opcode in (Opcode.DRAW_CIRCLE, Opcode.FILL_CIRCLE):
        if values[2] < 0:
            raise ProtocolError("Circle radius must be non-negative at byte {}".format(offset))
    elif opcode in (Opcode.DRAW_ROUNDED_RECTANGLE, Opcode.FILL_ROUNDED_RECTANGLE):
        width, height, radius = values[2:5]
        if width <= 0 or height <= 0:
            raise ProtocolError("Rectangle dimensions must be positive at byte {}".format(offset))
        if radius < 0 or radius > min(width, height) // 2:
            raise ProtocolError("Rounded rectangle radius is out of range at byte {}".format(offset))


def parse_commands(data: Any) -> Tuple[Command, ...]:
    """Parse a complete bytes-like command stream into an immutable tuple.

    Raises ProtocolError if any opcode, field, or command body is invalid.
    """
    try:
        view = memoryview(data).cast("B")
    except (TypeError, ValueError) as error:
        raise TypeError("data must be a contiguous bytes-like object") from error

    commands = []
    offset = 0
    while offset < len(view):
        command_offset = offset
        raw_opcode = view[offset]
        offset += 1
        try:
            opcode = Opcode(raw_opcode)
        except ValueError as error:
            raise ProtocolError(
                "Unknown opcode 0x{:02X} at byte {}".format(raw_opcode, command_offset)
            ) from error

        if opcode == Opcode.DRAW_TEXT:
            header = struct.Struct("<hhHBH")
            _require(view, offset, header.size, opcode)
            x0, y0, color, font_number, text_length = header.unpack_from(view, offset)
            offset += header.size
            _require(view, offset, text_length, opcode)
            text_offset = offset
            try:
                text = bytes(view[offset:offset + text_length]).decode("utf-8", errors="strict")
            except UnicodeDecodeError as error:
                raise ProtocolError("Invalid UTF-8 text at byte {}".format(text_offset)) from error
            offset += text_length
            commands.append(Command(opcode, (x0, y0, color, font_number, text)))
            continue

        if opcode == Opcode.DRAW_IMAGE:
            header = struct.Struct("<hhhh")
            _require(view, offset, header.size, opcode)
            x0, y0, width, height = header.unpack_from(view, offset)
            offset += header.size
            if width <= 0 or height <= 0:
                raise ProtocolError("Image dimensions must be positive at byte {}".format(command_offset))
            data_length = width * height * 2
            _require(view, offset, data_length, opcode)
            image_data = bytes(view[offset:offset + data_length])
            offset += data_length
            commands.append(Command(opcode, (x0, y0, width, height, image_data)))
            continue

        value_format = _FIXED_FORMATS[opcode]
        value_struct = struct.Struct(value_format)
        _require(view, offset, value_struct.size, opcode)
        values = value_struct.unpack_from(view, offset)
        offset += value_struct.size

        if opcode in (Opcode.DRAW_RECTANGLE, Opcode.FILL_RECTANGLE,
                      Opcode.DRAW_ELLIPSE, Opcode.FILL_ELLIPSE,
                      Opcode.DRAW_CIRCLE, Opcode.FILL_CIRCLE,
                      Opcode.DRAW_ROUNDED_RECTANGLE, Opcode.FILL_ROUNDED_RECTANGLE):
            _validate_geometry(opcode, values, command_offset)
        elif opcode == Opcode.SET_ORIENTATION and values[0] not in range(4):
            raise ProtocolError("Orientation must be between 0 and 3 at byte {}".format(command_offset))

        commands.append(Command(opcode, values))

    return tuple(commands)

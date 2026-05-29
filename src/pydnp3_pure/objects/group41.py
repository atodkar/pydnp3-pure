"""Object Group 41: Analog Output Command Block."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler
from .types import AnalogOutputCommand


@register_handler
class Group41Handler(ObjectGroupHandler):
    """Analog Output Block (Group 41, Variations 1-4).

    V1: 32-bit signed int(4) + status(1) = 5B
    V2: 16-bit signed int(2) + status(1) = 3B
    V3: float(4) + status(1) = 5B
    V4: double(8) + status(1) = 9B
    """

    @property
    def group(self) -> int:
        return 41

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1, 2, 3, 4)

    def parse(
        self, variation: int, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[AnalogOutputCommand]:
        commands: list[AnalogOutputCommand] = []
        for i in range(count):
            if qualifier == Qualifier.INDEX_8:
                idx = buf.read_uint8()
            elif qualifier == Qualifier.INDEX_16:
                idx = buf.read_uint16()
            else:
                idx = start + i

            value: int | float

            if variation == 1:
                value = buf.read_int32()
            elif variation == 2:
                value = buf.read_int16()
            elif variation == 3:
                value = buf.read_float32()
            elif variation == 4:
                value = buf.read_float64()
            else:
                continue

            status = buf.read_uint8()
            commands.append(AnalogOutputCommand(index=idx, value=value, status=status))
        return commands

    def serialize(
        self, variation: int, qualifier: Qualifier,
        points: list[AnalogOutputCommand], buf: WriteBuffer,
    ) -> None:
        for cmd in points:
            if qualifier == Qualifier.INDEX_8:
                buf.write_uint8(cmd.index)
            elif qualifier == Qualifier.INDEX_16:
                buf.write_uint16(cmd.index)

            if variation == 1:
                buf.write_int32(int(cmd.value))
            elif variation == 2:
                buf.write_int16(int(cmd.value))
            elif variation == 3:
                buf.write_float32(float(cmd.value))
            elif variation == 4:
                buf.write_float64(float(cmd.value))

            buf.write_uint8(cmd.status)

    def point_size(self, variation: int) -> int:
        return {1: 5, 2: 3, 3: 5, 4: 9}.get(variation, -1)

"""Object Group 20: Binary Counters."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler
from .types import CounterPoint


@register_handler
class Group20Handler(ObjectGroupHandler):
    """Binary Counter (Group 20, Variations 1, 2, 5, 6).

    V1: flags(1) + 32-bit unsigned(4) = 5 bytes
    V2: flags(1) + 16-bit unsigned(2) = 3 bytes
    V5: 32-bit unsigned, no flags = 4 bytes
    V6: 16-bit unsigned, no flags = 2 bytes
    """

    @property
    def group(self) -> int:
        return 20

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1, 2, 5, 6)

    def parse(
        self, variation: int, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[CounterPoint]:
        points: list[CounterPoint] = []
        for i in range(count):
            if qualifier in (Qualifier.INDEX_8, Qualifier.INDEX_16):
                idx = buf.read_uint8() if qualifier == Qualifier.INDEX_8 else buf.read_uint16()
            else:
                idx = start + i

            if variation == 1:
                flags = buf.read_uint8()
                value = buf.read_uint32()
            elif variation == 2:
                flags = buf.read_uint8()
                value = buf.read_uint16()
            elif variation == 5:
                flags = 0x01
                value = buf.read_uint32()
            elif variation == 6:
                flags = 0x01
                value = buf.read_uint16()
            else:
                continue

            points.append(CounterPoint(index=idx, value=value, flags=flags))
        return points

    def serialize(
        self, variation: int, qualifier: Qualifier, points: list[CounterPoint], buf: WriteBuffer
    ) -> None:
        for point in points:
            if qualifier == Qualifier.INDEX_8:
                buf.write_uint8(point.index)
            elif qualifier == Qualifier.INDEX_16:
                buf.write_uint16(point.index)

            if variation in (1, 2):
                buf.write_uint8(point.flags)

            if variation in (1, 5):
                buf.write_uint32(point.value)
            elif variation in (2, 6):
                buf.write_uint16(point.value & 0xFFFF)

    def point_size(self, variation: int) -> int:
        return {1: 5, 2: 3, 5: 4, 6: 2}.get(variation, -1)

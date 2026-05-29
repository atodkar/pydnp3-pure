"""Object Group 21: Frozen Counters."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler
from .types import CounterPoint, DNP3Timestamp


@register_handler
class Group21Handler(ObjectGroupHandler):
    """Frozen Counter (Group 21, Variations 1, 2, 5, 6, 9, 10).

    V1: flags(1) + 32-bit(4) = 5B
    V2: flags(1) + 16-bit(2) = 3B
    V5: flags(1) + 32-bit(4) + time(6) = 11B
    V6: flags(1) + 16-bit(2) + time(6) = 9B
    V9: 32-bit, no flags = 4B
    V10: 16-bit, no flags = 2B
    """

    @property
    def group(self) -> int:
        return 21

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1, 2, 5, 6, 9, 10)

    def parse(
        self, variation: int, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[CounterPoint]:
        points: list[CounterPoint] = []
        for i in range(count):
            if qualifier in (Qualifier.INDEX_8, Qualifier.INDEX_16):
                idx = buf.read_uint8() if qualifier == Qualifier.INDEX_8 else buf.read_uint16()
            else:
                idx = start + i

            flags = 0x01
            timestamp = None

            if variation in (1, 2, 5, 6):
                flags = buf.read_uint8()

            if variation in (1, 5, 9):
                value = buf.read_uint32()
            else:
                value = buf.read_uint16()

            if variation in (5, 6):
                ms_low = buf.read_uint32()
                ms_high = buf.read_uint16()
                ms = ms_low | (ms_high << 32)
                timestamp = DNP3Timestamp(ms_since_epoch=ms).to_datetime()

            points.append(CounterPoint(index=idx, value=value, flags=flags, timestamp=timestamp))
        return points

    def serialize(
        self, variation: int, qualifier: Qualifier, points: list[CounterPoint], buf: WriteBuffer
    ) -> None:
        for point in points:
            if qualifier == Qualifier.INDEX_8:
                buf.write_uint8(point.index)
            elif qualifier == Qualifier.INDEX_16:
                buf.write_uint16(point.index)

            if variation in (1, 2, 5, 6):
                buf.write_uint8(point.flags)

            if variation in (1, 5, 9):
                buf.write_uint32(point.value)
            else:
                buf.write_uint16(point.value & 0xFFFF)

            if variation in (5, 6):
                ts = (DNP3Timestamp.from_datetime(point.timestamp)
                      if point.timestamp else DNP3Timestamp(0))
                buf.write_uint32(ts.ms_since_epoch & 0xFFFFFFFF)
                buf.write_uint16((ts.ms_since_epoch >> 32) & 0xFFFF)

    def point_size(self, variation: int) -> int:
        return {1: 5, 2: 3, 5: 11, 6: 9, 9: 4, 10: 2}.get(variation, -1)

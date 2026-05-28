"""Object Group 2: Binary Input Events."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler
from .types import BinaryPoint, DNP3Timestamp


@register_handler
class Group2Handler(ObjectGroupHandler):
    """Binary Input Event (Group 2, Variations 1-3)."""

    @property
    def group(self) -> int:
        return 2

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1, 2, 3)

    def parse(
        self, variation: int, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[BinaryPoint]:
        points: list[BinaryPoint] = []
        for i in range(count):
            if qualifier in (Qualifier.INDEX_8, Qualifier.INDEX_16):
                idx = buf.read_uint8() if qualifier == Qualifier.INDEX_8 else buf.read_uint16()
            else:
                idx = start + i

            flags = buf.read_uint8()
            value = bool(flags & 0x80)
            timestamp = None

            if variation >= 2:
                # 6-byte absolute timestamp (ms since epoch)
                ms_low = buf.read_uint32()
                ms_high = buf.read_uint16()
                ms = ms_low | (ms_high << 32)
                timestamp = DNP3Timestamp(ms_since_epoch=ms).to_datetime()

            points.append(BinaryPoint(index=idx, value=value, flags=flags & 0x7F, timestamp=timestamp))
        return points

    def serialize(
        self, variation: int, qualifier: Qualifier, points: list[BinaryPoint], buf: WriteBuffer
    ) -> None:
        for point in points:
            if qualifier == Qualifier.INDEX_8:
                buf.write_uint8(point.index)
            elif qualifier == Qualifier.INDEX_16:
                buf.write_uint16(point.index)

            flags = point.flags & 0x7F
            if point.value:
                flags |= 0x80
            buf.write_uint8(flags)

            if variation >= 2:
                ts = DNP3Timestamp.from_datetime(point.timestamp) if point.timestamp else DNP3Timestamp(0)
                buf.write_uint32(ts.ms_since_epoch & 0xFFFFFFFF)
                buf.write_uint16((ts.ms_since_epoch >> 32) & 0xFFFF)

    def point_size(self, variation: int) -> int:
        if variation == 1:
            return 1
        elif variation == 2:
            return 7  # 1 flags + 6 timestamp
        return 7

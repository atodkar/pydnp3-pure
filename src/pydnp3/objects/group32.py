"""Object Group 32: Analog Input Events."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler
from .types import AnalogPoint, DNP3Timestamp


@register_handler
class Group32Handler(ObjectGroupHandler):
    """Analog Input Event (Group 32, Variations 1-8).

    V1: flags(1) + 32-bit int(4) = 5B
    V2: flags(1) + 16-bit int(2) = 3B
    V3: flags(1) + 32-bit int(4) + time(6) = 11B
    V4: flags(1) + 16-bit int(2) + time(6) = 9B
    V5: flags(1) + float(4) = 5B
    V6: flags(1) + double(8) = 9B
    V7: flags(1) + float(4) + time(6) = 11B
    V8: flags(1) + double(8) + time(6) = 15B
    """

    @property
    def group(self) -> int:
        return 32

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1, 2, 3, 4, 5, 6, 7, 8)

    def parse(
        self, variation: int, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[AnalogPoint]:
        points: list[AnalogPoint] = []
        for i in range(count):
            if qualifier in (Qualifier.INDEX_8, Qualifier.INDEX_16):
                idx = buf.read_uint8() if qualifier == Qualifier.INDEX_8 else buf.read_uint16()
            else:
                idx = start + i

            flags = buf.read_uint8()
            value: int | float
            timestamp = None

            if variation in (1, 3):
                value = buf.read_int32()
            elif variation in (2, 4):
                value = buf.read_int16()
            elif variation in (5, 7):
                value = buf.read_float32()
            elif variation in (6, 8):
                value = buf.read_float64()
            else:
                continue

            if variation in (3, 4, 7, 8):
                ms_low = buf.read_uint32()
                ms_high = buf.read_uint16()
                ms = ms_low | (ms_high << 32)
                timestamp = DNP3Timestamp(ms_since_epoch=ms).to_datetime()

            points.append(AnalogPoint(index=idx, value=value, flags=flags, timestamp=timestamp))
        return points

    def serialize(
        self, variation: int, qualifier: Qualifier, points: list[AnalogPoint], buf: WriteBuffer
    ) -> None:
        for point in points:
            if qualifier == Qualifier.INDEX_8:
                buf.write_uint8(point.index)
            elif qualifier == Qualifier.INDEX_16:
                buf.write_uint16(point.index)

            buf.write_uint8(point.flags)

            if variation in (1, 3):
                buf.write_int32(int(point.value))
            elif variation in (2, 4):
                buf.write_int16(int(point.value))
            elif variation in (5, 7):
                buf.write_float32(float(point.value))
            elif variation in (6, 8):
                buf.write_float64(float(point.value))

            if variation in (3, 4, 7, 8):
                ts = (DNP3Timestamp.from_datetime(point.timestamp)
                      if point.timestamp else DNP3Timestamp(0))
                buf.write_uint32(ts.ms_since_epoch & 0xFFFFFFFF)
                buf.write_uint16((ts.ms_since_epoch >> 32) & 0xFFFF)

    def point_size(self, variation: int) -> int:
        return {1: 5, 2: 3, 3: 11, 4: 9, 5: 5, 6: 9, 7: 11, 8: 15}.get(variation, -1)

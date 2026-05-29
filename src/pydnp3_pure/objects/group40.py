"""Object Group 40: Analog Output Status."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler
from .types import AnalogPoint


@register_handler
class Group40Handler(ObjectGroupHandler):
    """Analog Output Status (Group 40, Variations 1-4).

    V1: flags(1) + 32-bit signed int(4) = 5B
    V2: flags(1) + 16-bit signed int(2) = 3B
    V3: flags(1) + float(4) = 5B
    V4: flags(1) + double(8) = 9B
    """

    @property
    def group(self) -> int:
        return 40

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1, 2, 3, 4)

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

            points.append(AnalogPoint(index=idx, value=value, flags=flags))
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

            if variation == 1:
                buf.write_int32(int(point.value))
            elif variation == 2:
                buf.write_int16(int(point.value))
            elif variation == 3:
                buf.write_float32(float(point.value))
            elif variation == 4:
                buf.write_float64(float(point.value))

    def point_size(self, variation: int) -> int:
        return {1: 5, 2: 3, 3: 5, 4: 9}.get(variation, -1)

"""Object Group 10: Binary Output Status."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler
from .types import BinaryPoint


@register_handler
class Group10Handler(ObjectGroupHandler):
    """Binary Output Status (Group 10, Variations 1-2)."""

    @property
    def group(self) -> int:
        return 10

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1, 2)

    def parse(
        self, variation: int, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[BinaryPoint]:
        if variation == 1:
            return self._parse_packed(qualifier, count, start, buf)
        return self._parse_flags(qualifier, count, start, buf)

    def serialize(
        self, variation: int, qualifier: Qualifier, points: list[BinaryPoint], buf: WriteBuffer
    ) -> None:
        if variation == 1:
            self._serialize_packed(points, buf)
        else:
            self._serialize_flags(qualifier, points, buf)

    def point_size(self, variation: int) -> int:
        if variation == 1:
            return -1
        return 1

    def _parse_packed(
        self, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[BinaryPoint]:
        points: list[BinaryPoint] = []
        current_byte = 0
        for i in range(count):
            bit_idx = i % 8
            if bit_idx == 0:
                current_byte = buf.read_uint8()
            value = bool((current_byte >> bit_idx) & 1)
            points.append(BinaryPoint(index=start + i, value=value))
        return points

    def _parse_flags(
        self, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[BinaryPoint]:
        points: list[BinaryPoint] = []
        for i in range(count):
            if qualifier in (Qualifier.INDEX_8, Qualifier.INDEX_16):
                idx = buf.read_uint8() if qualifier == Qualifier.INDEX_8 else buf.read_uint16()
            else:
                idx = start + i
            flags = buf.read_uint8()
            value = bool(flags & 0x80)
            points.append(BinaryPoint(index=idx, value=value, flags=flags & 0x7F))
        return points

    def _serialize_packed(self, points: list[BinaryPoint], buf: WriteBuffer) -> None:
        current_byte = 0
        for i, point in enumerate(points):
            bit_idx = i % 8
            if point.value:
                current_byte |= 1 << bit_idx
            if bit_idx == 7 or i == len(points) - 1:
                buf.write_uint8(current_byte)
                current_byte = 0

    def _serialize_flags(
        self, qualifier: Qualifier, points: list[BinaryPoint], buf: WriteBuffer
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

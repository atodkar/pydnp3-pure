"""Object Group 1: Binary Inputs."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler
from .types import BinaryPoint


@register_handler
class Group1Handler(ObjectGroupHandler):
    """Binary Input (Group 1, Variations 1-2)."""

    @property
    def group(self) -> int:
        return 1

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1, 2)

    def parse(
        self, variation: int, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[BinaryPoint]:
        if variation == 1:
            return self._parse_v1(qualifier, count, start, buf)
        elif variation == 2:
            return self._parse_v2(qualifier, count, start, buf)
        return []

    def serialize(
        self, variation: int, qualifier: Qualifier, points: list[BinaryPoint], buf: WriteBuffer
    ) -> None:
        if variation == 1:
            self._serialize_v1(qualifier, points, buf)
        elif variation == 2:
            self._serialize_v2(qualifier, points, buf)

    def point_size(self, variation: int) -> int:
        if variation == 1:
            return -1  # Bit-packed, variable
        return 1  # V2: 1 byte flags

    def _parse_v1(
        self, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[BinaryPoint]:
        """Variation 1: Packed format (1 bit per point, 8 per byte)."""
        points: list[BinaryPoint] = []
        for i in range(count):
            i // 8
            bit_idx = i % 8
            if bit_idx == 0:
                current_byte = buf.read_uint8()
            value = bool((current_byte >> bit_idx) & 1)
            points.append(BinaryPoint(index=start + i, value=value))
        return points

    def _parse_v2(
        self, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[BinaryPoint]:
        """Variation 2: With flags (1 byte per point)."""
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

    def _serialize_v1(
        self, qualifier: Qualifier, points: list[BinaryPoint], buf: WriteBuffer
    ) -> None:
        """Serialize packed binary points (8 per byte)."""
        current_byte = 0
        for i, point in enumerate(points):
            bit_idx = i % 8
            if point.value:
                current_byte |= 1 << bit_idx
            if bit_idx == 7 or i == len(points) - 1:
                buf.write_uint8(current_byte)
                current_byte = 0

    def _serialize_v2(
        self, qualifier: Qualifier, points: list[BinaryPoint], buf: WriteBuffer
    ) -> None:
        """Serialize binary points with flags."""
        for point in points:
            if qualifier == Qualifier.INDEX_8:
                buf.write_uint8(point.index)
            elif qualifier == Qualifier.INDEX_16:
                buf.write_uint16(point.index)
            flags = point.flags & 0x7F
            if point.value:
                flags |= 0x80
            buf.write_uint8(flags)

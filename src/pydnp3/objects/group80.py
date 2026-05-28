"""Object Group 80: Internal Indications."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler


@register_handler
class Group80Handler(ObjectGroupHandler):
    """Internal Indications (Group 80, Variation 1).

    Used to write IIN bits (e.g., clear restart bit).
    V1: Packed bits, 1 bit per IIN flag.
    """

    @property
    def group(self) -> int:
        return 80

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1,)

    def parse(
        self, variation: int, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[tuple[int, bool]]:
        """Returns list of (bit_index, value) tuples."""
        results: list[tuple[int, bool]] = []
        current_byte = 0
        for i in range(count):
            bit_idx = i % 8
            if bit_idx == 0:
                current_byte = buf.read_uint8()
            value = bool((current_byte >> bit_idx) & 1)
            results.append((start + i, value))
        return results

    def serialize(
        self, variation: int, qualifier: Qualifier, points: list[tuple[int, bool]], buf: WriteBuffer
    ) -> None:
        current_byte = 0
        for i, (_, value) in enumerate(points):
            bit_idx = i % 8
            if value:
                current_byte |= 1 << bit_idx
            if bit_idx == 7 or i == len(points) - 1:
                buf.write_uint8(current_byte)
                current_byte = 0

    def point_size(self, variation: int) -> int:
        return -1  # Bit-packed

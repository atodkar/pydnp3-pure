"""Object Group 50: Time and Date."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler
from .types import DNP3Timestamp


@register_handler
class Group50Handler(ObjectGroupHandler):
    """Time and Date (Group 50, Variations 1, 4).

    V1: 48-bit ms since epoch (6 bytes)
    V4: Indexed absolute time (with index prefix)
    """

    @property
    def group(self) -> int:
        return 50

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1, 4)

    def parse(
        self, variation: int, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[DNP3Timestamp]:
        timestamps: list[DNP3Timestamp] = []
        for _ in range(count):
            ms_low = buf.read_uint32()
            ms_high = buf.read_uint16()
            ms = ms_low | (ms_high << 32)
            timestamps.append(DNP3Timestamp(ms_since_epoch=ms))
        return timestamps

    def serialize(
        self, variation: int, qualifier: Qualifier, points: list[DNP3Timestamp], buf: WriteBuffer
    ) -> None:
        for ts in points:
            buf.write_uint32(ts.ms_since_epoch & 0xFFFFFFFF)
            buf.write_uint16((ts.ms_since_epoch >> 32) & 0xFFFF)

    def point_size(self, variation: int) -> int:
        return 6

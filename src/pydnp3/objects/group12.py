"""Object Group 12: Binary Output Command (CROB)."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler
from .types import CROB


@register_handler
class Group12Handler(ObjectGroupHandler):
    """Control Relay Output Block (Group 12, Variation 1).

    CROB structure: control(1) + count(1) + onTime(4) + offTime(4) + status(1) = 11 bytes
    """

    CROB_SIZE = 11

    @property
    def group(self) -> int:
        return 12

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1,)

    def parse(
        self, variation: int, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[tuple[int, CROB]]:
        """Returns list of (point_index, CROB) tuples."""
        results: list[tuple[int, CROB]] = []
        for i in range(count):
            if qualifier == Qualifier.INDEX_8:
                idx = buf.read_uint8()
            elif qualifier == Qualifier.INDEX_16:
                idx = buf.read_uint16()
            else:
                idx = start + i

            control = buf.read_uint8()
            crob_count = buf.read_uint8()
            on_time = buf.read_uint32()
            off_time = buf.read_uint32()
            status = buf.read_uint8()

            crob = CROB(
                control=control,
                count=crob_count,
                on_time_ms=on_time,
                off_time_ms=off_time,
                status=status,
            )
            results.append((idx, crob))
        return results

    def serialize(
        self, variation: int, qualifier: Qualifier, points: list[tuple[int, CROB]], buf: WriteBuffer
    ) -> None:
        for idx, crob in points:
            if qualifier == Qualifier.INDEX_8:
                buf.write_uint8(idx)
            elif qualifier == Qualifier.INDEX_16:
                buf.write_uint16(idx)
            buf.write_uint8(crob.control)
            buf.write_uint8(crob.count)
            buf.write_uint32(crob.on_time_ms)
            buf.write_uint32(crob.off_time_ms)
            buf.write_uint8(crob.status)

    def point_size(self, variation: int) -> int:
        return self.CROB_SIZE

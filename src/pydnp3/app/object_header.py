"""DNP3 Object Header parsing and building."""

from __future__ import annotations

from dataclasses import dataclass

from ..util.buffer import ReadBuffer, WriteBuffer
from .constants import Qualifier


@dataclass(slots=True)
class ObjectHeader:
    """Parsed DNP3 object header with range/count info resolved."""

    group: int
    variation: int
    qualifier: Qualifier
    start: int       # First point index (for start/stop qualifiers)
    stop: int        # Last point index (for start/stop qualifiers)
    count: int       # Number of objects

    @property
    def has_index_prefix(self) -> bool:
        return self.qualifier in (Qualifier.INDEX_8, Qualifier.INDEX_16, Qualifier.INDEX_32)

    @property
    def index_size(self) -> int:
        if self.qualifier == Qualifier.INDEX_8:
            return 1
        elif self.qualifier == Qualifier.INDEX_16:
            return 2
        elif self.qualifier == Qualifier.INDEX_32:
            return 4
        return 0


def parse_object_header(buf: ReadBuffer) -> ObjectHeader:
    """Parse an object header from the buffer, advancing the offset."""
    group = buf.read_uint8()
    variation = buf.read_uint8()
    qualifier = Qualifier(buf.read_uint8())

    start = 0
    stop = 0
    count = 0

    if qualifier == Qualifier.RANGE_8_START_STOP:
        start = buf.read_uint8()
        stop = buf.read_uint8()
        count = stop - start + 1
    elif qualifier == Qualifier.RANGE_16_START_STOP:
        start = buf.read_uint16()
        stop = buf.read_uint16()
        count = stop - start + 1
    elif qualifier == Qualifier.RANGE_32_START_STOP:
        start = buf.read_uint32()
        stop = buf.read_uint32()
        count = stop - start + 1
    elif qualifier == Qualifier.ALL_POINTS:
        count = 0  # All points — count determined by database
    elif qualifier == Qualifier.COUNT_8:
        count = buf.read_uint8()
    elif qualifier == Qualifier.COUNT_16:
        count = buf.read_uint16()
    elif qualifier == Qualifier.COUNT_32:
        count = buf.read_uint32()
    elif qualifier == Qualifier.INDEX_8:
        count = buf.read_uint8()
    elif qualifier == Qualifier.INDEX_16:
        count = buf.read_uint16()
    elif qualifier == Qualifier.INDEX_32:
        count = buf.read_uint32()
    elif qualifier == Qualifier.FREE_FORMAT_8:
        count = buf.read_uint8()
    elif qualifier == Qualifier.FREE_FORMAT_16:
        count = buf.read_uint16()

    return ObjectHeader(
        group=group,
        variation=variation,
        qualifier=qualifier,
        start=start,
        stop=stop,
        count=count,
    )


def write_object_header(buf: WriteBuffer, header: ObjectHeader) -> None:
    """Write an object header to the buffer."""
    buf.write_uint8(header.group)
    buf.write_uint8(header.variation)
    buf.write_uint8(int(header.qualifier))

    if header.qualifier == Qualifier.RANGE_8_START_STOP:
        buf.write_uint8(header.start)
        buf.write_uint8(header.stop)
    elif header.qualifier == Qualifier.RANGE_16_START_STOP:
        buf.write_uint16(header.start)
        buf.write_uint16(header.stop)
    elif header.qualifier == Qualifier.ALL_POINTS:
        pass
    elif header.qualifier == Qualifier.COUNT_8:
        buf.write_uint8(header.count)
    elif header.qualifier == Qualifier.COUNT_16:
        buf.write_uint16(header.count)
    elif header.qualifier in (Qualifier.INDEX_8, Qualifier.INDEX_16):
        if header.qualifier == Qualifier.INDEX_8:
            buf.write_uint8(header.count)
        else:
            buf.write_uint16(header.count)

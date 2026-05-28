"""DNP3 Application Layer fragment parsing and building."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..objects.registry import get_handler
from ..util.buffer import ReadBuffer, WriteBuffer
from .constants import FunctionCode, Qualifier
from .header import AppControl, AppHeader, IIN
from .object_header import ObjectHeader, parse_object_header, write_object_header


@dataclass(slots=True)
class ObjectData:
    """Parsed object header with its associated data points."""

    header: ObjectHeader
    points: list[Any] = field(default_factory=list)


@dataclass(slots=True)
class AppMessage:
    """A complete DNP3 application-layer message (request or response)."""

    header: AppHeader
    objects: list[ObjectData] = field(default_factory=list)

    @property
    def function(self) -> FunctionCode:
        return self.header.function

    @property
    def is_response(self) -> bool:
        return self.header.is_response


def parse_fragment(data: bytes | bytearray | memoryview) -> AppMessage:
    """Parse a complete application-layer fragment into an AppMessage."""
    buf = ReadBuffer(data)

    # Parse application header
    ac = AppControl.from_byte(buf.read_uint8())
    fc = FunctionCode(buf.read_uint8())

    iin = None
    if fc.is_response:
        iin = IIN.from_bytes(buf.read_bytes(2))

    app_header = AppHeader(control=ac, function=fc, iin=iin)

    # Parse object headers and their data
    objects: list[ObjectData] = []
    while buf.remaining > 0:
        obj_header = parse_object_header(buf)
        handler = get_handler(obj_header.group)

        if handler is None or obj_header.count == 0:
            objects.append(ObjectData(header=obj_header))
            continue

        points = handler.parse(
            variation=obj_header.variation,
            qualifier=obj_header.qualifier,
            count=obj_header.count,
            start=obj_header.start,
            buf=buf,
        )
        objects.append(ObjectData(header=obj_header, points=points))

    return AppMessage(header=app_header, objects=objects)


def build_response(
    seq: int,
    iin: IIN,
    objects: list[ObjectData],
    unsolicited: bool = False,
    confirm: bool = False,
) -> bytes:
    """Build a response fragment from object data."""
    buf = WriteBuffer(2048)

    ac = AppControl.single_fragment(seq=seq, con=confirm, uns=unsolicited)
    buf.write_uint8(ac.to_byte())
    buf.write_uint8(
        int(FunctionCode.UNSOLICITED_RESPONSE if unsolicited else FunctionCode.RESPONSE)
    )
    buf.write_bytes(iin.to_bytes())

    for obj_data in objects:
        write_object_header(buf, obj_data.header)
        handler = get_handler(obj_data.header.group)
        if handler and obj_data.points:
            handler.serialize(
                variation=obj_data.header.variation,
                qualifier=obj_data.header.qualifier,
                points=obj_data.points,
                buf=buf,
            )

    return buf.as_bytes()


def build_request(
    function: FunctionCode,
    seq: int,
    objects: list[ObjectData],
) -> bytes:
    """Build a request fragment."""
    buf = WriteBuffer(2048)

    ac = AppControl.single_fragment(seq=seq)
    buf.write_uint8(ac.to_byte())
    buf.write_uint8(int(function))

    for obj_data in objects:
        write_object_header(buf, obj_data.header)
        handler = get_handler(obj_data.header.group)
        if handler and obj_data.points:
            handler.serialize(
                variation=obj_data.header.variation,
                qualifier=obj_data.header.qualifier,
                points=obj_data.points,
                buf=buf,
            )

    return buf.as_bytes()

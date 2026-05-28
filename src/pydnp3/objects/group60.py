"""Object Group 60: Class Data Objects (used in read requests)."""

from __future__ import annotations

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer
from .base import ObjectGroupHandler
from .registry import register_handler


@register_handler
class Group60Handler(ObjectGroupHandler):
    """Class Data Objects (Group 60, Variations 1-4).

    V1: Class 0 (static data)
    V2: Class 1 events
    V3: Class 2 events
    V4: Class 3 events

    These are used only in read requests to specify which class of data to return.
    They carry no data payload.
    """

    @property
    def group(self) -> int:
        return 60

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (1, 2, 3, 4)

    def parse(
        self, variation: int, qualifier: Qualifier, count: int, start: int, buf: ReadBuffer
    ) -> list[int]:
        # Class objects carry no data; the variation itself is the information
        return [variation]

    def serialize(
        self, variation: int, qualifier: Qualifier, points: list[int], buf: WriteBuffer
    ) -> None:
        # No data payload for class objects
        pass

    def point_size(self, variation: int) -> int:
        return 0

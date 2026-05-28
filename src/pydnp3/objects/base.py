"""Abstract base class for DNP3 object group handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..app.constants import Qualifier
from ..util.buffer import ReadBuffer, WriteBuffer


class ObjectGroupHandler(ABC):
    """Base class for object group handlers.

    Each handler knows how to parse and serialize data for one object group
    across its supported variations.
    """

    @property
    @abstractmethod
    def group(self) -> int:
        """The DNP3 object group number this handler supports."""
        ...

    @property
    @abstractmethod
    def supported_variations(self) -> tuple[int, ...]:
        """Tuple of variation numbers this handler can parse/serialize."""
        ...

    @abstractmethod
    def parse(
        self,
        variation: int,
        qualifier: Qualifier,
        count: int,
        start: int,
        buf: ReadBuffer,
    ) -> list[Any]:
        """Parse `count` data objects from the buffer.

        Args:
            variation: Object variation number
            qualifier: Qualifier determining index encoding
            count: Number of objects to parse
            start: Starting point index (for start/stop qualifiers)
            buf: ReadBuffer positioned at start of object data

        Returns:
            List of parsed data point objects
        """
        ...

    @abstractmethod
    def serialize(
        self,
        variation: int,
        qualifier: Qualifier,
        points: list[Any],
        buf: WriteBuffer,
    ) -> None:
        """Serialize data points into the buffer.

        Args:
            variation: Object variation number
            qualifier: Qualifier determining index encoding
            points: List of data point objects to serialize
            buf: WriteBuffer to append serialized data to
        """
        ...

    def point_size(self, variation: int) -> int:
        """Return fixed size in bytes per point for the given variation.

        Returns -1 for variable-size objects.
        """
        return -1

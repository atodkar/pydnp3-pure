"""Event buffer for Class 1/2/3 events."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Event:
    """A recorded change event for a data point."""

    group: int
    variation: int
    index: int
    value: Any
    flags: int
    event_class: int
    timestamp_ms: int = 0


class EventBuffer:
    """Per-class event queues with configurable max depth and FIFO overflow."""

    def __init__(
        self,
        class_1_max: int = 1000,
        class_2_max: int = 1000,
        class_3_max: int = 1000,
    ) -> None:
        self._buffers: dict[int, deque[Event]] = {
            1: deque(maxlen=class_1_max),
            2: deque(maxlen=class_2_max),
            3: deque(maxlen=class_3_max),
        }
        self._overflow = False

    def add(self, event: Event) -> None:
        """Add an event to the appropriate class buffer."""
        buf = self._buffers.get(event.event_class)
        if buf is None:
            return
        if len(buf) == buf.maxlen:
            self._overflow = True
        buf.append(event)

    def get_class_events(self, event_class: int) -> list[Event]:
        """Get all events for a given class (non-destructive peek)."""
        buf = self._buffers.get(event_class)
        if buf is None:
            return []
        return list(buf)

    def confirm_class(self, event_class: int) -> None:
        """Remove all events for a class (called after master confirms)."""
        buf = self._buffers.get(event_class)
        if buf is not None:
            buf.clear()

    def confirm_all(self) -> None:
        """Clear all event buffers."""
        for buf in self._buffers.values():
            buf.clear()
        self._overflow = False

    @property
    def has_class_1(self) -> bool:
        return len(self._buffers[1]) > 0

    @property
    def has_class_2(self) -> bool:
        return len(self._buffers[2]) > 0

    @property
    def has_class_3(self) -> bool:
        return len(self._buffers[3]) > 0

    @property
    def has_events(self) -> bool:
        return any(len(buf) > 0 for buf in self._buffers.values())

    @property
    def overflow(self) -> bool:
        return self._overflow

    @property
    def total_count(self) -> int:
        return sum(len(buf) for buf in self._buffers.values())

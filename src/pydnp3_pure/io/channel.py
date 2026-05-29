"""Channel protocol abstraction for DNP3 communication."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class IChannel(ABC):
    """Abstract bidirectional byte channel for DNP3 communication."""

    @abstractmethod
    async def open(self) -> None:
        """Open the channel connection."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the channel connection."""
        ...

    @abstractmethod
    def send(self, data: bytes) -> None:
        """Send raw bytes over the channel."""
        ...

    @abstractmethod
    def set_receive_callback(self, callback: Callable[[bytes], None]) -> None:
        """Set the callback for incoming data."""
        ...

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Return whether the channel is currently open."""
        ...

"""DNP3 Application Layer: connects transport fragments to session logic."""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..transport.layer import TransportLayer
from .fragment import AppMessage, parse_fragment

logger = logging.getLogger(__name__)


class ApplicationLayer:
    """Bridges transport layer fragments to application-level message handling.

    Receive: Parses transport fragments into AppMessage objects.
    Transmit: Serializes and sends fragments via the transport layer.
    """

    def __init__(
        self,
        transport: TransportLayer,
        on_message: Callable[[AppMessage], None],
    ) -> None:
        self._transport = transport
        self._on_message = on_message

    def on_fragment_received(self, fragment: bytes) -> None:
        """Called by the transport layer when a complete fragment arrives."""
        try:
            message = parse_fragment(fragment)
            self._on_message(message)
        except (ValueError, IndexError) as e:
            logger.warning("Failed to parse application fragment: %s", e)

    def send_fragment(self, fragment: bytes, direction: bool = False) -> None:
        """Send a serialized fragment down through the transport layer."""
        self._transport.send_fragment(fragment, direction=direction)

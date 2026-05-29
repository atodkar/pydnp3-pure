"""DNP3 Link Layer state machine for frame reception."""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum, auto

from .constants import HEADER_SIZE, MAX_USER_DATA, MIN_LENGTH_FIELD, SYNC_1, SYNC_2
from .frame import LinkFrame, LinkHeader, extract_user_data, parse_header, wire_frame_size

logger = logging.getLogger(__name__)


class _State(Enum):
    SYNC_HUNT = auto()
    HEADER = auto()
    BODY = auto()


class LinkLayer:
    """Stateful receiver that assembles raw bytes into validated LinkFrames.

    Feed bytes via `data_received()`. Complete frames are delivered to
    the `on_frame` callback.
    """

    def __init__(self, on_frame: Callable[[LinkFrame], None]) -> None:
        self._on_frame = on_frame
        self._state = _State.SYNC_HUNT
        self._buf = bytearray()
        self._header: LinkHeader | None = None
        self._expected_body_size = 0

    def reset(self) -> None:
        self._state = _State.SYNC_HUNT
        self._buf.clear()
        self._header = None
        self._expected_body_size = 0

    def data_received(self, data: bytes | bytearray | memoryview) -> None:
        """Process incoming bytes. May deliver zero or more frames via callback."""
        self._buf.extend(data)

        while True:
            if self._state == _State.SYNC_HUNT:
                if not self._hunt_sync():
                    break
            elif self._state == _State.HEADER:
                if not self._process_header():
                    break
            elif self._state == _State.BODY:
                if not self._process_body():
                    break

    def _hunt_sync(self) -> bool:
        """Search for sync bytes. Returns True if state advanced."""
        while len(self._buf) >= 2:
            idx = self._buf.find(bytes([SYNC_1, SYNC_2]))
            if idx < 0:
                # Keep last byte in case it's SYNC_1 for next chunk
                if self._buf and self._buf[-1] == SYNC_1:
                    self._buf = bytearray([SYNC_1])
                else:
                    self._buf.clear()
                return False

            if idx > 0:
                del self._buf[:idx]

            self._state = _State.HEADER
            return True
        return False

    def _process_header(self) -> bool:
        """Try to parse a complete header. Returns True if state advanced."""
        if len(self._buf) < HEADER_SIZE:
            return False

        header = parse_header(self._buf[:HEADER_SIZE])
        if header is None:
            logger.debug("Link header CRC failed, returning to sync hunt")
            del self._buf[:1]
            self._state = _State.SYNC_HUNT
            return True

        if header.length < MIN_LENGTH_FIELD:
            logger.debug("Invalid length field %d", header.length)
            del self._buf[:1]
            self._state = _State.SYNC_HUNT
            return True

        user_data_len = header.user_data_length
        if user_data_len > MAX_USER_DATA:
            logger.debug("User data length %d exceeds maximum", user_data_len)
            del self._buf[:1]
            self._state = _State.SYNC_HUNT
            return True

        self._header = header

        if user_data_len == 0:
            # Link-only frame (no user data)
            frame = LinkFrame(header=header, user_data=b"")
            del self._buf[:HEADER_SIZE]
            self._state = _State.SYNC_HUNT
            self._on_frame(frame)
            return True

        # Calculate expected body bytes on wire
        self._expected_body_size = wire_frame_size(user_data_len) - HEADER_SIZE
        del self._buf[:HEADER_SIZE]
        self._state = _State.BODY
        return True

    def _process_body(self) -> bool:
        """Try to extract body data. Returns True if state advanced."""
        if len(self._buf) < self._expected_body_size:
            return False

        assert self._header is not None
        body_bytes = bytes(self._buf[: self._expected_body_size])
        del self._buf[: self._expected_body_size]

        user_data = extract_user_data(body_bytes, self._header.user_data_length)
        if user_data is None:
            logger.debug("Body CRC validation failed")
            self._state = _State.SYNC_HUNT
            return True

        frame = LinkFrame(header=self._header, user_data=user_data)
        self._header = None
        self._state = _State.SYNC_HUNT
        self._on_frame(frame)
        return True

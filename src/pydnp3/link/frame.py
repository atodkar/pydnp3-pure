"""DNP3 Link Frame: serialization and parsing with CRC block handling."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .constants import (
    BLOCK_SIZE,
    CRC_SIZE,
    CTRL_DIR_MASK,
    CTRL_FCB_MASK,
    CTRL_FCV_MASK,
    CTRL_FUNC_MASK,
    CTRL_PRM_MASK,
    DATA_BLOCK_SIZE,
    HEADER_DATA_SIZE,
    HEADER_SIZE,
    MIN_LENGTH_FIELD,
    SYNC_1,
    SYNC_2,
)
from .crc import append_crc, compute_crc, verify_crc


@dataclass(slots=True)
class LinkHeader:
    """Parsed DNP3 link layer header."""

    length: int
    direction: bool
    primary: bool
    fcb: bool
    fcv: bool
    function: int
    destination: int
    source: int

    @property
    def user_data_length(self) -> int:
        return self.length - MIN_LENGTH_FIELD

    @property
    def control_byte(self) -> int:
        ctrl = self.function & CTRL_FUNC_MASK
        if self.direction:
            ctrl |= CTRL_DIR_MASK
        if self.primary:
            ctrl |= CTRL_PRM_MASK
        if self.fcb:
            ctrl |= CTRL_FCB_MASK
        if self.fcv:
            ctrl |= CTRL_FCV_MASK
        return ctrl

    @classmethod
    def from_control_byte(cls, length: int, ctrl: int, destination: int, source: int) -> LinkHeader:
        return cls(
            length=length,
            direction=bool(ctrl & CTRL_DIR_MASK),
            primary=bool(ctrl & CTRL_PRM_MASK),
            fcb=bool(ctrl & CTRL_FCB_MASK),
            fcv=bool(ctrl & CTRL_FCV_MASK),
            function=ctrl & CTRL_FUNC_MASK,
            destination=destination,
            source=source,
        )


@dataclass(slots=True)
class LinkFrame:
    """A complete DNP3 link frame with header and user data."""

    header: LinkHeader
    user_data: bytes

    def serialize(self) -> bytes:
        """Serialize to wire format with CRC blocks."""
        buf = bytearray()

        # Header: sync + length + control + dest + source
        header_block = bytearray(HEADER_DATA_SIZE)
        header_block[0] = SYNC_1
        header_block[1] = SYNC_2
        header_block[2] = self.header.length
        header_block[3] = self.header.control_byte
        struct.pack_into("<H", header_block, 4, self.header.destination)
        struct.pack_into("<H", header_block, 6, self.header.source)
        buf.extend(header_block)
        # CRC over header (bytes 0-7)
        crc = compute_crc(header_block)
        buf.append(crc & 0xFF)
        buf.append((crc >> 8) & 0xFF)

        # User data: split into 16-byte blocks, each with its own CRC
        data = self.user_data
        offset = 0
        while offset < len(data):
            block = data[offset : offset + DATA_BLOCK_SIZE]
            buf.extend(block)
            crc = compute_crc(block)
            buf.append(crc & 0xFF)
            buf.append((crc >> 8) & 0xFF)
            offset += DATA_BLOCK_SIZE

        return bytes(buf)

    @classmethod
    def create(
        cls,
        destination: int,
        source: int,
        primary: bool,
        function: int,
        user_data: bytes = b"",
        direction: bool = True,
        fcb: bool = False,
        fcv: bool = False,
    ) -> LinkFrame:
        """Create a new link frame."""
        header = LinkHeader(
            length=MIN_LENGTH_FIELD + len(user_data),
            direction=direction,
            primary=primary,
            fcb=fcb,
            fcv=fcv,
            function=function,
            destination=destination,
            source=source,
        )
        return cls(header=header, user_data=user_data)


def parse_header(data: bytes | bytearray | memoryview) -> LinkHeader | None:
    """Parse a 10-byte link header (including CRC). Returns None if CRC fails."""
    if len(data) < HEADER_SIZE:
        return None

    if data[0] != SYNC_1 or data[1] != SYNC_2:
        return None

    if not verify_crc(data[:HEADER_SIZE]):
        return None

    length = data[2]
    ctrl = data[3]
    destination = struct.unpack_from("<H", data, 4)[0]
    source = struct.unpack_from("<H", data, 6)[0]

    return LinkHeader.from_control_byte(length, ctrl, destination, source)


def extract_user_data(raw_frame: bytes | bytearray | memoryview, user_data_length: int) -> bytes | None:
    """Extract and validate user data from CRC-blocked body bytes.

    `raw_frame` should start after the 10-byte header (i.e., the body portion).
    Returns the extracted user data with CRCs stripped, or None if any CRC fails.
    """
    result = bytearray()
    offset = 0
    remaining = user_data_length

    while remaining > 0:
        block_data_size = min(remaining, DATA_BLOCK_SIZE)
        block_with_crc = raw_frame[offset : offset + block_data_size + CRC_SIZE]

        if len(block_with_crc) < block_data_size + CRC_SIZE:
            return None

        if not verify_crc(block_with_crc):
            return None

        result.extend(block_with_crc[:block_data_size])
        offset += block_data_size + CRC_SIZE
        remaining -= block_data_size

    return bytes(result)


def wire_frame_size(user_data_length: int) -> int:
    """Calculate total bytes on wire for a frame with given user data length."""
    if user_data_length == 0:
        return HEADER_SIZE

    full_blocks = user_data_length // DATA_BLOCK_SIZE
    remainder = user_data_length % DATA_BLOCK_SIZE
    body_size = full_blocks * BLOCK_SIZE
    if remainder > 0:
        body_size += remainder + CRC_SIZE

    return HEADER_SIZE + body_size

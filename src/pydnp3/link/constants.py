"""DNP3 Data Link Layer constants."""

from __future__ import annotations

from enum import IntEnum

# Sync bytes marking start of every link frame
SYNC_1 = 0x05
SYNC_2 = 0x64

# Frame size constants
HEADER_SIZE = 10  # 2 sync + 1 len + 1 ctrl + 2 dst + 2 src + 2 crc
HEADER_DATA_SIZE = 8  # Header bytes covered by CRC (excludes CRC itself)
DATA_BLOCK_SIZE = 16  # User data bytes per CRC block
CRC_SIZE = 2
BLOCK_SIZE = DATA_BLOCK_SIZE + CRC_SIZE  # 18 bytes per block on wire
MAX_FRAME_LENGTH = 292  # Max total frame bytes on wire
MAX_USER_DATA = 250  # Max user data bytes (length field max 255, minus 5 for header fields)
MIN_LENGTH_FIELD = 5  # Minimum length field value (header fields only, no user data)

# Control byte masks
CTRL_DIR_MASK = 0x80   # Direction: 1 = master→outstation
CTRL_PRM_MASK = 0x40   # Primary message: 1 = from initiator
CTRL_FCB_MASK = 0x20   # Frame Count Bit
CTRL_FCV_MASK = 0x10   # Frame Count Valid (primary) / Data Flow Control (secondary)
CTRL_FUNC_MASK = 0x0F  # Function code (4 bits)

# Broadcast addresses
BROADCAST_NO_CONFIRM = 0xFFFD
BROADCAST_CONFIRM = 0xFFFE
BROADCAST_ALL = 0xFFFF
SELF_ADDRESS = 0xFFFC


class PrimaryFunction(IntEnum):
    """Link layer function codes for primary (initiating) frames."""
    RESET_LINK = 0
    TEST_LINK = 2
    CONFIRMED_USER_DATA = 3
    UNCONFIRMED_USER_DATA = 4
    REQUEST_LINK_STATUS = 9


class SecondaryFunction(IntEnum):
    """Link layer function codes for secondary (responding) frames."""
    ACK = 0
    NACK = 1
    LINK_STATUS = 11
    NOT_SUPPORTED = 15

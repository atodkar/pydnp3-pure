"""DNP3 Transport Layer constants."""

from __future__ import annotations

# Transport header bit masks (1-byte header)
TH_FIR = 0x40       # First segment of a fragment
TH_FIN = 0x80       # Final segment of a fragment
TH_SEQ_MASK = 0x3F  # 6-bit sequence number (0-63)

# Maximum transport segment payload (excluding 1-byte transport header)
# Link frame max user data = 250, minus 1 byte transport header = 249
MAX_PAYLOAD_PER_SEGMENT = 249

# Maximum reassembled fragment size (application layer limit)
MAX_FRAGMENT_SIZE = 2048

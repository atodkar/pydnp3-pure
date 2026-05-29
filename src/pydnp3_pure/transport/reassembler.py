"""DNP3 Transport Layer fragment reassembly (receive direction)."""

from __future__ import annotations

import logging

from .constants import MAX_FRAGMENT_SIZE, TH_FIN, TH_FIR, TH_SEQ_MASK

logger = logging.getLogger(__name__)


class Reassembler:
    """Reassembles transport segments into complete application-layer fragments.

    Validates FIR/FIN sequencing and 6-bit sequence number continuity.
    """

    def __init__(self, max_fragment_size: int = MAX_FRAGMENT_SIZE) -> None:
        self._max_size = max_fragment_size
        self._buffer = bytearray()
        self._expected_seq: int | None = None
        self._active = False

    def reset(self) -> None:
        self._buffer.clear()
        self._expected_seq = None
        self._active = False

    def add_segment(self, segment: bytes | bytearray | memoryview) -> bytes | None:
        """Process a transport segment (with 1-byte header).

        Returns the complete reassembled fragment when FIN is received,
        or None if more segments are needed.
        """
        if len(segment) < 1:
            logger.debug("Empty transport segment received")
            return None

        header = segment[0]
        fir = bool(header & TH_FIR)
        fin = bool(header & TH_FIN)
        seq = header & TH_SEQ_MASK
        payload = segment[1:]

        if fir:
            if self._active:
                logger.debug("FIR received while assembly in progress, restarting")
            self._buffer.clear()
            self._buffer.extend(payload)
            self._expected_seq = (seq + 1) & TH_SEQ_MASK
            self._active = True
        else:
            if not self._active:
                logger.debug("Non-FIR segment without active reassembly, discarding")
                return None

            if seq != self._expected_seq:
                logger.debug(
                    "Sequence mismatch: expected %d, got %d",
                    self._expected_seq, seq
                )
                self.reset()
                return None

            self._buffer.extend(payload)
            self._expected_seq = (seq + 1) & TH_SEQ_MASK

        if len(self._buffer) > self._max_size:
            logger.debug("Fragment exceeds max size %d, discarding", self._max_size)
            self.reset()
            return None

        if fin:
            result = bytes(self._buffer)
            self.reset()
            return result

        return None

"""DNP3 Transport Layer fragment segmentation (transmit direction)."""

from __future__ import annotations

from .constants import MAX_PAYLOAD_PER_SEGMENT, TH_FIN, TH_FIR, TH_SEQ_MASK


class Segmenter:
    """Segments application-layer fragments into transport-sized chunks.

    Each chunk gets a 1-byte transport header with FIR/FIN/SEQ fields.
    """

    def __init__(self, max_payload: int = MAX_PAYLOAD_PER_SEGMENT) -> None:
        self._max_payload = max_payload
        self._sequence = 0

    @property
    def sequence(self) -> int:
        return self._sequence

    def reset(self) -> None:
        self._sequence = 0

    def segment(self, fragment: bytes | bytearray) -> list[bytes]:
        """Split a fragment into transport segments, each with a header byte."""
        segments: list[bytes] = []
        offset = 0
        total = len(fragment)

        if total == 0:
            # Single empty segment with FIR+FIN
            header = TH_FIR | TH_FIN | (self._sequence & TH_SEQ_MASK)
            self._sequence = (self._sequence + 1) & TH_SEQ_MASK
            return [bytes([header])]

        while offset < total:
            chunk_size = min(self._max_payload, total - offset)
            chunk = fragment[offset : offset + chunk_size]

            header = self._sequence & TH_SEQ_MASK
            if offset == 0:
                header |= TH_FIR
            if offset + chunk_size >= total:
                header |= TH_FIN

            segments.append(bytes([header]) + chunk)
            self._sequence = (self._sequence + 1) & TH_SEQ_MASK
            offset += chunk_size

        return segments

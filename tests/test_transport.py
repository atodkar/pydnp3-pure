"""Tests for DNP3 Transport Layer."""

from pydnp3.transport.constants import MAX_PAYLOAD_PER_SEGMENT, TH_FIN, TH_FIR, TH_SEQ_MASK
from pydnp3.transport.reassembler import Reassembler
from pydnp3.transport.segmenter import Segmenter


class TestReassembler:
    def setup_method(self):
        self.reassembler = Reassembler()

    def test_single_segment(self):
        """FIR+FIN in one segment."""
        header = TH_FIR | TH_FIN | 0  # seq=0
        segment = bytes([header]) + b"Hello"
        result = self.reassembler.add_segment(segment)
        assert result == b"Hello"

    def test_two_segments(self):
        """FIR then FIN."""
        seg1 = bytes([TH_FIR | 0]) + b"Hello"  # seq=0, FIR only
        seg2 = bytes([TH_FIN | 1]) + b" World"  # seq=1, FIN only

        assert self.reassembler.add_segment(seg1) is None
        result = self.reassembler.add_segment(seg2)
        assert result == b"Hello World"

    def test_three_segments(self):
        """FIR, middle, FIN."""
        seg1 = bytes([TH_FIR | 0]) + b"A"
        seg2 = bytes([1]) + b"B"  # No FIR or FIN
        seg3 = bytes([TH_FIN | 2]) + b"C"

        assert self.reassembler.add_segment(seg1) is None
        assert self.reassembler.add_segment(seg2) is None
        result = self.reassembler.add_segment(seg3)
        assert result == b"ABC"

    def test_sequence_wraparound(self):
        """Sequence wraps from 63 to 0."""
        seg1 = bytes([TH_FIR | 63]) + b"X"  # seq=63
        seg2 = bytes([TH_FIN | 0]) + b"Y"   # seq=0 (wraps)

        assert self.reassembler.add_segment(seg1) is None
        result = self.reassembler.add_segment(seg2)
        assert result == b"XY"

    def test_sequence_mismatch_discards(self):
        """Out-of-order sequence resets reassembly."""
        seg1 = bytes([TH_FIR | 0]) + b"A"
        seg2 = bytes([TH_FIN | 5]) + b"B"  # Expected seq=1, got 5

        assert self.reassembler.add_segment(seg1) is None
        result = self.reassembler.add_segment(seg2)
        assert result is None

    def test_fir_restarts_assembly(self):
        """New FIR while assembly in progress restarts."""
        seg1 = bytes([TH_FIR | 0]) + b"old"
        seg2 = bytes([TH_FIR | TH_FIN | 5]) + b"new"

        assert self.reassembler.add_segment(seg1) is None
        result = self.reassembler.add_segment(seg2)
        assert result == b"new"

    def test_non_fir_without_active_discards(self):
        """Segment without FIR when no assembly active is discarded."""
        seg = bytes([TH_FIN | 0]) + b"data"
        result = self.reassembler.add_segment(seg)
        assert result is None

    def test_empty_segment(self):
        result = self.reassembler.add_segment(b"")
        assert result is None

    def test_max_size_exceeded(self):
        reassembler = Reassembler(max_fragment_size=10)
        seg1 = bytes([TH_FIR | 0]) + b"12345678"
        seg2 = bytes([TH_FIN | 1]) + b"90A"  # Total = 11 > max 10

        assert reassembler.add_segment(seg1) is None
        result = reassembler.add_segment(seg2)
        assert result is None


class TestSegmenter:
    def setup_method(self):
        self.segmenter = Segmenter()

    def test_small_fragment_single_segment(self):
        fragment = b"Hello"
        segments = self.segmenter.segment(fragment)
        assert len(segments) == 1
        header = segments[0][0]
        assert header & TH_FIR
        assert header & TH_FIN
        assert (header & TH_SEQ_MASK) == 0
        assert segments[0][1:] == b"Hello"

    def test_empty_fragment(self):
        segments = self.segmenter.segment(b"")
        assert len(segments) == 1
        header = segments[0][0]
        assert header & TH_FIR
        assert header & TH_FIN

    def test_exact_max_payload(self):
        fragment = bytes(MAX_PAYLOAD_PER_SEGMENT)
        segments = self.segmenter.segment(fragment)
        assert len(segments) == 1

    def test_two_segments(self):
        fragment = bytes(MAX_PAYLOAD_PER_SEGMENT + 1)
        segments = self.segmenter.segment(fragment)
        assert len(segments) == 2
        assert segments[0][0] & TH_FIR
        assert not (segments[0][0] & TH_FIN)
        assert not (segments[1][0] & TH_FIR)
        assert segments[1][0] & TH_FIN

    def test_sequence_increments(self):
        fragment = bytes(MAX_PAYLOAD_PER_SEGMENT * 3)
        segments = self.segmenter.segment(fragment)
        assert len(segments) == 3
        assert (segments[0][0] & TH_SEQ_MASK) == 0
        assert (segments[1][0] & TH_SEQ_MASK) == 1
        assert (segments[2][0] & TH_SEQ_MASK) == 2

    def test_round_trip_with_reassembler(self):
        """Segmenter output should reassemble to original."""
        original = bytes(range(256)) * 4  # 1024 bytes
        segmenter = Segmenter()
        reassembler = Reassembler()

        segments = segmenter.segment(original)
        result = None
        for seg in segments:
            result = reassembler.add_segment(seg)

        assert result == original

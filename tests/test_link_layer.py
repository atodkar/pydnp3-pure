"""Tests for DNP3 Link Layer state machine."""

from pydnp3_pure.link.constants import PrimaryFunction
from pydnp3_pure.link.frame import LinkFrame
from pydnp3_pure.link.layer import LinkLayer


class TestLinkLayer:
    def setup_method(self):
        self.received_frames: list[LinkFrame] = []
        self.layer = LinkLayer(on_frame=self.received_frames.append)

    def test_receive_link_only_frame(self):
        frame = LinkFrame.create(
            destination=1, source=2, primary=True,
            function=PrimaryFunction.REQUEST_LINK_STATUS,
        )
        raw = frame.serialize()
        self.layer.data_received(raw)
        assert len(self.received_frames) == 1
        assert self.received_frames[0].header.function == PrimaryFunction.REQUEST_LINK_STATUS

    def test_receive_data_frame(self):
        payload = b"\xC0\x01\x3C\x02\x06"  # Typical app layer read class 1
        frame = LinkFrame.create(
            destination=1, source=0, primary=True,
            function=PrimaryFunction.UNCONFIRMED_USER_DATA,
            user_data=payload,
        )
        raw = frame.serialize()
        self.layer.data_received(raw)
        assert len(self.received_frames) == 1
        assert self.received_frames[0].user_data == payload

    def test_receive_fragmented_bytes(self):
        """Simulate bytes arriving in small chunks."""
        payload = bytes(range(20))
        frame = LinkFrame.create(
            destination=1, source=0, primary=True,
            function=PrimaryFunction.UNCONFIRMED_USER_DATA,
            user_data=payload,
        )
        raw = frame.serialize()

        # Feed one byte at a time
        for byte in raw:
            self.layer.data_received(bytes([byte]))

        assert len(self.received_frames) == 1
        assert self.received_frames[0].user_data == payload

    def test_receive_multiple_frames(self):
        frames_data = []
        for i in range(3):
            frame = LinkFrame.create(
                destination=1, source=i, primary=True,
                function=PrimaryFunction.UNCONFIRMED_USER_DATA,
                user_data=bytes([i] * 5),
            )
            frames_data.append(frame.serialize())

        combined = b"".join(frames_data)
        self.layer.data_received(combined)
        assert len(self.received_frames) == 3

    def test_garbage_before_sync(self):
        """Garbage bytes before valid frame should be skipped."""
        payload = b"\x01\x02\x03"
        frame = LinkFrame.create(
            destination=1, source=0, primary=True,
            function=PrimaryFunction.UNCONFIRMED_USER_DATA,
            user_data=payload,
        )
        raw = b"\xFF\xFE\xFD\xFC" + frame.serialize()
        self.layer.data_received(raw)
        assert len(self.received_frames) == 1
        assert self.received_frames[0].user_data == payload

    def test_corrupted_header_crc(self):
        frame = LinkFrame.create(
            destination=1, source=0, primary=True,
            function=PrimaryFunction.UNCONFIRMED_USER_DATA,
            user_data=b"\x01\x02",
        )
        raw = bytearray(frame.serialize())
        raw[9] ^= 0xFF  # Corrupt header CRC
        self.layer.data_received(raw)
        assert len(self.received_frames) == 0

    def test_reset_clears_state(self):
        # Feed partial frame
        frame = LinkFrame.create(
            destination=1, source=0, primary=True,
            function=PrimaryFunction.UNCONFIRMED_USER_DATA,
            user_data=b"\x01\x02\x03",
        )
        raw = frame.serialize()
        self.layer.data_received(raw[:5])  # Partial
        self.layer.reset()
        self.layer.data_received(raw)  # Full frame
        assert len(self.received_frames) == 1

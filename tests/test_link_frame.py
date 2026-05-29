"""Tests for DNP3 Link Frame parsing and serialization."""

from pydnp3_pure.link.constants import MIN_LENGTH_FIELD, SYNC_1, SYNC_2, PrimaryFunction
from pydnp3_pure.link.crc import compute_crc
from pydnp3_pure.link.frame import (
    LinkFrame,
    LinkHeader,
    extract_user_data,
    parse_header,
    wire_frame_size,
)


def _make_raw_header(length=5, ctrl=0xC4, dst=1, src=0):
    """Build a raw 10-byte header with valid CRC."""
    import struct
    header = bytearray([SYNC_1, SYNC_2, length, ctrl])
    header.extend(struct.pack("<H", dst))
    header.extend(struct.pack("<H", src))
    crc = compute_crc(header)
    header.append(crc & 0xFF)
    header.append((crc >> 8) & 0xFF)
    return bytes(header)


class TestLinkHeader:
    def test_parse_valid_header(self):
        raw = _make_raw_header(length=5, ctrl=0xC4, dst=1, src=1024)
        header = parse_header(raw)
        assert header is not None
        assert header.length == 5
        assert header.destination == 1
        assert header.source == 1024
        assert header.direction is True  # 0xC4 bit 7
        assert header.primary is True  # 0xC4 bit 6
        assert header.function == 4  # Unconfirmed user data

    def test_parse_invalid_sync(self):
        raw = bytearray(_make_raw_header())
        raw[0] = 0x00
        assert parse_header(raw) is None

    def test_parse_bad_crc(self):
        raw = bytearray(_make_raw_header())
        raw[9] ^= 0xFF
        assert parse_header(raw) is None

    def test_parse_too_short(self):
        assert parse_header(b"\x05\x64\x05") is None

    def test_control_byte_round_trip(self):
        header = LinkHeader(
            length=10, direction=True, primary=True,
            fcb=True, fcv=True, function=4,
            destination=100, source=200,
        )
        ctrl = header.control_byte
        assert ctrl & 0x80  # DIR
        assert ctrl & 0x40  # PRM
        assert ctrl & 0x20  # FCB
        assert ctrl & 0x10  # FCV
        assert (ctrl & 0x0F) == 4


class TestLinkFrame:
    def test_create_link_only_frame(self):
        frame = LinkFrame.create(
            destination=1, source=2,
            primary=True,
            function=PrimaryFunction.REQUEST_LINK_STATUS,
        )
        assert frame.header.length == MIN_LENGTH_FIELD
        assert frame.user_data == b""

    def test_serialize_link_only(self):
        frame = LinkFrame.create(
            destination=1, source=2, primary=True,
            function=PrimaryFunction.REQUEST_LINK_STATUS,
        )
        raw = frame.serialize()
        assert len(raw) == 10  # Header only
        assert raw[0] == SYNC_1
        assert raw[1] == SYNC_2

    def test_serialize_with_small_payload(self):
        payload = b"\x01\x02\x03\x04\x05"
        frame = LinkFrame.create(
            destination=1, source=2, primary=True,
            function=PrimaryFunction.UNCONFIRMED_USER_DATA,
            user_data=payload,
        )
        raw = frame.serialize()
        # 10 header + 5 data + 2 CRC = 17
        assert len(raw) == 17

    def test_serialize_16_byte_block(self):
        payload = bytes(range(16))
        frame = LinkFrame.create(
            destination=1, source=2, primary=True,
            function=PrimaryFunction.UNCONFIRMED_USER_DATA,
            user_data=payload,
        )
        raw = frame.serialize()
        # 10 header + 16 data + 2 CRC = 28
        assert len(raw) == 28

    def test_serialize_multiple_blocks(self):
        payload = bytes(range(32))
        frame = LinkFrame.create(
            destination=1, source=2, primary=True,
            function=PrimaryFunction.UNCONFIRMED_USER_DATA,
            user_data=payload,
        )
        raw = frame.serialize()
        # 10 header + 18 (16+2 CRC) + 18 (16+2 CRC) = 46
        assert len(raw) == 46

    def test_round_trip(self):
        payload = b"Hello DNP3 World!!"  # 18 bytes = 16 + 2 (two blocks)
        frame = LinkFrame.create(
            destination=1000, source=2000, primary=True,
            function=PrimaryFunction.UNCONFIRMED_USER_DATA,
            user_data=payload, direction=True, fcb=True,
        )
        raw = frame.serialize()

        # Parse header
        header = parse_header(raw[:10])
        assert header is not None
        assert header.destination == 1000
        assert header.source == 2000
        assert header.direction is True
        assert header.fcb is True

        # Parse body
        body_data = extract_user_data(raw[10:], header.user_data_length)
        assert body_data == payload


class TestWireFrameSize:
    def test_no_data(self):
        assert wire_frame_size(0) == 10

    def test_one_byte(self):
        assert wire_frame_size(1) == 10 + 1 + 2  # header + 1 data + CRC

    def test_16_bytes(self):
        assert wire_frame_size(16) == 10 + 16 + 2

    def test_17_bytes(self):
        assert wire_frame_size(17) == 10 + 18 + 1 + 2  # full block + partial

    def test_max_250(self):
        # 250 bytes = 15 full blocks (15*18) + 10 bytes partial (10+2)
        assert wire_frame_size(250) == 10 + 15 * 18 + 10 + 2

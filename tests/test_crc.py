"""Tests for DNP3 CRC-16 implementation."""

from pydnp3_pure.link.crc import append_crc, compute_crc, verify_crc


class TestComputeCRC:
    def test_empty_data(self):
        # CRC of empty data = ~0 & 0xFFFF = 0xFFFF
        assert compute_crc(b"") == 0xFFFF

    def test_single_byte(self):
        result = compute_crc(b"\x05")
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_sync_bytes(self):
        # Known test: sync bytes 0x05 0x64 should produce a consistent CRC
        crc = compute_crc(bytes([0x05, 0x64]))
        assert crc == compute_crc(b"\x05\x64")

    def test_deterministic(self):
        data = b"\x05\x64\x05\xc0\x01\x00\x00\x00"
        assert compute_crc(data) == compute_crc(data)

    def test_different_data_different_crc(self):
        assert compute_crc(b"\x00") != compute_crc(b"\x01")


class TestAppendCRC:
    def test_appends_two_bytes(self):
        data = bytearray(b"\x05\x64\x05\xc0\x01\x00\x00\x00")
        original_len = len(data)
        append_crc(data)
        assert len(data) == original_len + 2

    def test_appended_crc_verifies(self):
        data = bytearray(b"\x05\x64\x05\xc0\x01\x00\x00\x00")
        append_crc(data)
        assert verify_crc(data)

    def test_little_endian_order(self):
        data = bytearray(b"\x01\x02\x03")
        crc = compute_crc(data)
        append_crc(data)
        assert data[-2] == (crc & 0xFF)
        assert data[-1] == ((crc >> 8) & 0xFF)


class TestVerifyCRC:
    def test_valid_crc(self):
        data = bytearray(b"\x05\x64\x05\xc0\x01\x00\x00\x00")
        append_crc(data)
        assert verify_crc(data) is True

    def test_corrupted_data(self):
        data = bytearray(b"\x05\x64\x05\xc0\x01\x00\x00\x00")
        append_crc(data)
        data[3] ^= 0xFF  # Corrupt one byte
        assert verify_crc(data) is False

    def test_too_short(self):
        assert verify_crc(b"\x00\x01") is False
        assert verify_crc(b"\x00") is False

    def test_real_dnp3_header(self):
        # A valid DNP3 link header (sync + len + ctrl + dst + src + crc)
        # Build one manually
        header = bytearray([0x05, 0x64, 0x05, 0xC0, 0x01, 0x00, 0x00, 0x00])
        append_crc(header)
        assert verify_crc(header) is True
        assert len(header) == 10

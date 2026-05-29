"""Tests for DNP3 Object Group handlers."""

import struct

from pydnp3_pure.app.constants import Qualifier
from pydnp3_pure.objects import get_handler
from pydnp3_pure.objects.types import AnalogPoint, BinaryPoint
from pydnp3_pure.util.buffer import ReadBuffer, WriteBuffer


class TestGroup1BinaryInput:
    def test_parse_v1_packed(self):
        handler = get_handler(1)
        # 8 binary points packed into 1 byte: 0b10101010
        buf = ReadBuffer(bytes([0xAA]))
        points = handler.parse(1, Qualifier.RANGE_8_START_STOP, 8, 0, buf)
        assert len(points) == 8
        assert points[0].value is False  # bit 0
        assert points[1].value is True   # bit 1
        assert points[7].value is True   # bit 7

    def test_parse_v2_with_flags(self):
        handler = get_handler(1)
        # Two points: flags byte with STATE bit
        buf = ReadBuffer(bytes([0x81, 0x01]))  # ON+ONLINE, OFF+ONLINE
        points = handler.parse(2, Qualifier.RANGE_8_START_STOP, 2, 0, buf)
        assert points[0].value is True
        assert points[1].value is False
        assert points[0].flags == 0x01  # ONLINE

    def test_serialize_v1_round_trip(self):
        handler = get_handler(1)
        points = [BinaryPoint(index=i, value=(i % 2 == 0)) for i in range(8)]
        buf = WriteBuffer()
        handler.serialize(1, Qualifier.RANGE_8_START_STOP, points, buf)
        # Reparse
        rbuf = ReadBuffer(buf.as_bytes())
        parsed = handler.parse(1, Qualifier.RANGE_8_START_STOP, 8, 0, rbuf)
        for orig, back in zip(points, parsed):
            assert orig.value == back.value


class TestGroup12CROB:
    def test_parse_crob(self):
        handler = get_handler(12)
        # Build CROB: control=3(LATCH_ON), count=1, onTime=1000, offTime=500, status=0
        data = bytearray()
        data.append(5)     # index (8-bit)
        data.append(0x03)  # control: LATCH_ON
        data.append(1)     # count
        data.extend(struct.pack("<I", 1000))  # on_time
        data.extend(struct.pack("<I", 500))   # off_time
        data.append(0)     # status

        buf = ReadBuffer(bytes(data))
        results = handler.parse(1, Qualifier.INDEX_8, 1, 0, buf)
        assert len(results) == 1
        idx, crob = results[0]
        assert idx == 5
        assert crob.control == 0x03
        assert crob.on_time_ms == 1000
        assert crob.off_time_ms == 500
        assert crob.is_latch_on


class TestGroup30AnalogInput:
    def test_parse_v1_32bit(self):
        handler = get_handler(30)
        data = bytearray()
        data.append(0x01)  # flags: ONLINE
        data.extend(struct.pack("<i", -12345))
        buf = ReadBuffer(bytes(data))
        points = handler.parse(1, Qualifier.RANGE_8_START_STOP, 1, 0, buf)
        assert len(points) == 1
        assert points[0].value == -12345
        assert points[0].flags == 0x01

    def test_parse_v2_16bit(self):
        handler = get_handler(30)
        data = bytearray()
        data.append(0x01)
        data.extend(struct.pack("<h", 500))
        buf = ReadBuffer(bytes(data))
        points = handler.parse(2, Qualifier.RANGE_8_START_STOP, 1, 0, buf)
        assert points[0].value == 500

    def test_parse_v5_float(self):
        handler = get_handler(30)
        data = bytearray()
        data.append(0x01)
        data.extend(struct.pack("<f", 3.14))
        buf = ReadBuffer(bytes(data))
        points = handler.parse(5, Qualifier.RANGE_8_START_STOP, 1, 0, buf)
        assert abs(points[0].value - 3.14) < 0.001

    def test_serialize_v2_round_trip(self):
        handler = get_handler(30)
        points = [AnalogPoint(index=i, value=i * 10, flags=0x01) for i in range(5)]
        buf = WriteBuffer()
        handler.serialize(2, Qualifier.RANGE_8_START_STOP, points, buf)
        rbuf = ReadBuffer(buf.as_bytes())
        parsed = handler.parse(2, Qualifier.RANGE_8_START_STOP, 5, 0, rbuf)
        for orig, back in zip(points, parsed):
            assert orig.value == back.value


class TestGroup41AnalogOutput:
    def test_parse_v2_with_index(self):
        handler = get_handler(41)
        data = bytearray()
        data.append(3)  # 8-bit index
        data.extend(struct.pack("<h", -250))
        data.append(0)  # status
        buf = ReadBuffer(bytes(data))
        results = handler.parse(2, Qualifier.INDEX_8, 1, 0, buf)
        assert len(results) == 1
        assert results[0].index == 3
        assert results[0].value == -250
        assert results[0].status == 0


class TestGroup20Counter:
    def test_parse_v1(self):
        handler = get_handler(20)
        data = bytearray()
        data.append(0x01)  # flags
        data.extend(struct.pack("<I", 99999))
        buf = ReadBuffer(bytes(data))
        points = handler.parse(1, Qualifier.RANGE_8_START_STOP, 1, 0, buf)
        assert points[0].value == 99999
        assert points[0].flags == 0x01

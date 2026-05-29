"""Tests for DNP3 Application Layer parsing."""

from pydnp3_pure.app.constants import FunctionCode, Qualifier
from pydnp3_pure.app.fragment import ObjectData, build_request, build_response, parse_fragment
from pydnp3_pure.app.header import IIN
from pydnp3_pure.app.object_header import ObjectHeader


class TestParseFragment:
    def test_read_class0_request(self):
        """Parse a Class 0 integrity poll: READ obj60v1 qualifier ALL."""
        # AC=0xC0 (FIR+FIN, seq=0), FC=0x01 (READ), Obj60v1 qual=0x06 (ALL)
        data = bytes([0xC0, 0x01, 0x3C, 0x01, 0x06])
        msg = parse_fragment(data)
        assert msg.function == FunctionCode.READ
        assert msg.header.control.fir is True
        assert msg.header.control.fin is True
        assert len(msg.objects) == 1
        assert msg.objects[0].header.group == 60
        assert msg.objects[0].header.variation == 1
        assert msg.objects[0].header.qualifier == Qualifier.ALL_POINTS

    def test_read_multi_class_request(self):
        """Parse a read request for Class 1, 2, and 3 events."""
        data = bytes([
            0xC1, 0x01,           # AC (FIR+FIN, seq=1), FC=READ
            0x3C, 0x02, 0x06,    # Obj60v2 ALL (Class 1)
            0x3C, 0x03, 0x06,    # Obj60v3 ALL (Class 2)
            0x3C, 0x04, 0x06,    # Obj60v4 ALL (Class 3)
        ])
        msg = parse_fragment(data)
        assert msg.function == FunctionCode.READ
        assert len(msg.objects) == 3
        assert msg.objects[0].header.group == 60
        assert msg.objects[0].header.variation == 2
        assert msg.objects[1].header.variation == 3
        assert msg.objects[2].header.variation == 4

    def test_response_with_iin(self):
        """Parse a response with IIN bits."""
        data = bytes([
            0xC0, 0x81,          # AC (FIR+FIN, seq=0), FC=RESPONSE
            0x80, 0x00,          # IIN: DEVICE_RESTART
        ])
        msg = parse_fragment(data)
        assert msg.is_response
        assert msg.header.iin is not None
        assert msg.header.iin.device_restart is True

    def test_response_with_analog_data(self):
        """Parse a response containing Analog Input V2 (flags + int16)."""
        import struct
        data = bytearray([
            0xC0, 0x81,          # Response header
            0x00, 0x00,          # IIN (clear)
            0x1E, 0x02,          # Group 30, Variation 2
            0x00,                # Qualifier: 8-bit start/stop
            0x00, 0x02,          # Start=0, Stop=2 (3 points)
        ])
        # 3 analog points: flags(1) + int16(2) each
        for i in range(3):
            data.append(0x01)  # flags = ONLINE
            data.extend(struct.pack("<h", (i + 1) * 100))

        msg = parse_fragment(bytes(data))
        assert len(msg.objects) == 1
        obj = msg.objects[0]
        assert obj.header.group == 30
        assert obj.header.variation == 2
        assert len(obj.points) == 3
        assert obj.points[0].value == 100
        assert obj.points[1].value == 200
        assert obj.points[2].value == 300


class TestBuildRequest:
    def test_build_integrity_poll(self):
        """Build a Class 0 read request."""
        obj = ObjectData(
            header=ObjectHeader(
                group=60, variation=1,
                qualifier=Qualifier.ALL_POINTS,
                start=0, stop=0, count=0,
            )
        )
        data = build_request(FunctionCode.READ, seq=0, objects=[obj])
        assert data[0] == 0xC0  # FIR+FIN, seq=0
        assert data[1] == 0x01  # READ
        assert data[2] == 60   # Group
        assert data[3] == 1    # Variation
        assert data[4] == 0x06  # ALL_POINTS qualifier


class TestBuildResponse:
    def test_build_empty_response(self):
        """Build a response with just IIN, no objects."""
        iin = IIN.startup()
        data = build_response(seq=0, iin=iin, objects=[])
        assert data[0] == 0xC0  # FIR+FIN
        assert data[1] == 0x81  # RESPONSE
        assert data[2] == 0x80  # IIN1: DEVICE_RESTART
        assert data[3] == 0x00  # IIN2: clear

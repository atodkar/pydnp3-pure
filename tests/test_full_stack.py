"""Full-stack integration test: bytes → link → transport → app → typed objects."""

import struct

from pydnp3.app.constants import FunctionCode, Qualifier
from pydnp3.app.fragment import ObjectData, build_response, parse_fragment
from pydnp3.app.header import IIN
from pydnp3.app.object_header import ObjectHeader
from pydnp3.link.constants import PrimaryFunction
from pydnp3.link.frame import LinkFrame
from pydnp3.link.layer import LinkLayer
from pydnp3.objects.types import AnalogPoint
from pydnp3.transport.reassembler import Reassembler


class TestFullStack:
    def test_raw_bytes_to_parsed_request(self):
        """Simulate receiving a raw DNP3 integrity poll from the wire."""
        # Build an integrity poll (READ Class 0): AC=0xC0, FC=0x01, Obj60v1 qual=ALL
        app_fragment = bytes([0xC0, 0x01, 0x3C, 0x01, 0x06])

        # Wrap in transport (FIR+FIN, seq=0)
        transport_segment = bytes([0xC0]) + app_fragment  # 0xC0 = FIR|FIN|seq=0

        # Wrap in link frame
        frame = LinkFrame.create(
            destination=1, source=0, primary=True,
            function=PrimaryFunction.UNCONFIRMED_USER_DATA,
            user_data=transport_segment,
            direction=True,
        )
        wire_bytes = frame.serialize()

        # Now simulate receiving these bytes
        received_frames = []
        link_layer = LinkLayer(on_frame=received_frames.append)
        link_layer.data_received(wire_bytes)

        assert len(received_frames) == 1
        rx_frame = received_frames[0]

        # Transport reassembly
        reassembler = Reassembler()
        fragment = reassembler.add_segment(rx_frame.user_data)
        assert fragment is not None

        # Application layer parse
        msg = parse_fragment(fragment)
        assert msg.function == FunctionCode.READ
        assert msg.header.control.fir is True
        assert msg.header.control.fin is True
        assert len(msg.objects) == 1
        assert msg.objects[0].header.group == 60
        assert msg.objects[0].header.variation == 1

    def test_build_response_and_parse_back(self):
        """Build a response with analog data, serialize to wire, parse back."""
        # Build response with 3 analog inputs
        points = [
            AnalogPoint(index=0, value=100, flags=0x01),
            AnalogPoint(index=1, value=-200, flags=0x01),
            AnalogPoint(index=2, value=32000, flags=0x01),
        ]
        obj_data = ObjectData(
            header=ObjectHeader(
                group=30, variation=2,
                qualifier=Qualifier.RANGE_8_START_STOP,
                start=0, stop=2, count=3,
            ),
            points=points,
        )

        iin = IIN.startup()
        response_bytes = build_response(seq=5, iin=iin, objects=[obj_data])

        # Wrap in transport
        from pydnp3.transport.segmenter import Segmenter
        segmenter = Segmenter()
        segments = segmenter.segment(response_bytes)
        assert len(segments) == 1  # Small enough for one segment

        # Wrap in link frame
        frame = LinkFrame.create(
            destination=0, source=1, primary=True,
            function=PrimaryFunction.UNCONFIRMED_USER_DATA,
            user_data=segments[0],
            direction=False,
        )
        wire = frame.serialize()

        # Parse back through full stack
        received = []
        link = LinkLayer(on_frame=received.append)
        link.data_received(wire)

        reassembler = Reassembler()
        fragment = reassembler.add_segment(received[0].user_data)
        assert fragment is not None

        msg = parse_fragment(fragment)
        assert msg.function == FunctionCode.RESPONSE
        assert msg.header.iin.device_restart is True
        assert msg.header.control.seq == 5
        assert len(msg.objects) == 1

        parsed_points = msg.objects[0].points
        assert len(parsed_points) == 3
        assert parsed_points[0].value == 100
        assert parsed_points[1].value == -200
        assert parsed_points[2].value == 32000

    def test_large_fragment_multi_frame(self):
        """Fragment larger than one link frame requires multiple frames."""
        # Create a fragment with many analog points (over 249 bytes)
        points = [AnalogPoint(index=i, value=i * 10, flags=0x01) for i in range(100)]
        obj_data = ObjectData(
            header=ObjectHeader(
                group=30, variation=2,
                qualifier=Qualifier.RANGE_8_START_STOP,
                start=0, stop=99, count=100,
            ),
            points=points,
        )
        response_bytes = build_response(seq=0, iin=IIN(), objects=[obj_data])

        # Segment into transport chunks
        from pydnp3.transport.segmenter import Segmenter
        segmenter = Segmenter()
        segments = segmenter.segment(response_bytes)
        assert len(segments) > 1  # Multiple segments needed

        # Reassemble
        reassembler = Reassembler()
        result = None
        for seg in segments:
            result = reassembler.add_segment(seg)

        assert result is not None
        msg = parse_fragment(result)
        assert len(msg.objects[0].points) == 100

    def test_direct_operate_analog_output(self):
        """Parse a Direct Operate command with analog output."""
        # Direct Operate (FC=5), Obj41v2 (16-bit AO), indexed
        app_data = bytearray([
            0xC0, 0x05,          # AC: FIR+FIN seq=0, FC: DIRECT_OPERATE
            0x29, 0x02,          # Group 41, Variation 2
            0x17,                # Qualifier: 8-bit index prefix
            0x02,                # Count: 2 points
        ])
        # Point 0: index=3, value=1000, status=0
        app_data.append(3)
        app_data.extend(struct.pack("<h", 1000))
        app_data.append(0)
        # Point 1: index=5, value=-500, status=0
        app_data.append(5)
        app_data.extend(struct.pack("<h", -500))
        app_data.append(0)

        msg = parse_fragment(bytes(app_data))
        assert msg.function == FunctionCode.DIRECT_OPERATE
        assert len(msg.objects) == 1
        commands = msg.objects[0].points
        assert len(commands) == 2
        assert commands[0].index == 3
        assert commands[0].value == 1000
        assert commands[1].index == 5
        assert commands[1].value == -500

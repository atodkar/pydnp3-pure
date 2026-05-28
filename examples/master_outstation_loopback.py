"""Example: In-process master ↔ outstation loopback test.

Demonstrates the full protocol stack without any network by directly
connecting master output to outstation input and vice versa.
"""

import asyncio
import sys
sys.path.insert(0, "src")

from pydnp3.app.constants import CommandStatus, FunctionCode
from pydnp3.app.fragment import AppMessage, parse_fragment
from pydnp3.link.layer import LinkLayer
from pydnp3.link.frame import LinkFrame
from pydnp3.transport.layer import TransportLayer
from pydnp3.transport.segmenter import Segmenter
from pydnp3.transport.reassembler import Reassembler
from pydnp3.app.layer import ApplicationLayer
from pydnp3.objects.types import CROB
from pydnp3.outstation.config import OutstationConfig
from pydnp3.outstation.database import PointDatabase
from pydnp3.outstation.handler import IOutstationHandler
from pydnp3.outstation.session import OutstationSession
from pydnp3.master.config import MasterConfig
from pydnp3.master.handler import IMasterHandler
from pydnp3.master.session import MasterSession


class SimpleOutstationHandler(IOutstationHandler):
    def __init__(self, db: PointDatabase):
        self._db = db

    def on_direct_operate_binary(self, index: int, crob: CROB) -> CommandStatus:
        self._db.update_binary_output(index, crob.is_latch_on)
        return CommandStatus.SUCCESS

    def on_direct_operate_analog(self, index: int, value: float) -> CommandStatus:
        self._db.update_analog_output(index, value)
        return CommandStatus.SUCCESS


class SimpleMasterHandler(IMasterHandler):
    def __init__(self):
        self.responses: list[AppMessage] = []

    def on_response_received(self, message: AppMessage) -> None:
        self.responses.append(message)


def main():
    """Run a full loopback: master sends requests, outstation responds."""

    # --- Outstation setup ---
    os_config = OutstationConfig(address=10, master_address=1)
    db = PointDatabase()
    db.add_analog_input(0, value=100.5)
    db.add_analog_input(1, value=200.0)
    db.add_analog_input(2, value=-50.25)
    db.add_binary_output(0, value=False)
    db.add_binary_output(1, value=True)
    db.add_counter(0, value=42)
    db.add_analog_output(0, value=0.0)

    os_handler = SimpleOutstationHandler(db)

    # Transport: outstation → master (bytes flow through here)
    outstation_to_master: list[bytes] = []
    master_to_outstation: list[bytes] = []

    def os_send_fragment(fragment: bytes):
        # Segment → frame → wire bytes
        seg = Segmenter()
        segments = seg.segment(fragment)
        for s in segments:
            frame = LinkFrame.create(
                destination=os_config.master_address,
                source=os_config.address,
                primary=True, function=4, user_data=s,
            )
            outstation_to_master.append(frame.serialize())

    os_session = OutstationSession(
        config=os_config, database=db,
        handler=os_handler, send_fragment=os_send_fragment,
    )

    # --- Master setup ---
    ms_config = MasterConfig(address=1, outstation_address=10)
    ms_handler = SimpleMasterHandler()

    def ms_send_fragment(fragment: bytes):
        seg = Segmenter()
        segments = seg.segment(fragment)
        for s in segments:
            frame = LinkFrame.create(
                destination=ms_config.outstation_address,
                source=ms_config.address,
                primary=True, function=4, user_data=s, direction=True,
            )
            master_to_outstation.append(frame.serialize())

    ms_session = MasterSession(
        config=ms_config, handler=ms_handler,
        send_fragment=ms_send_fragment,
    )

    # --- Delivery functions ---
    def deliver_to_outstation():
        """Deliver all queued master→outstation bytes."""
        os_link = LinkLayer(on_frame=lambda f: None)
        os_reasm = Reassembler()
        frames = []
        os_link = LinkLayer(on_frame=frames.append)
        for data in master_to_outstation:
            os_link.data_received(data)
        master_to_outstation.clear()
        for frame in frames:
            fragment = os_reasm.add_segment(frame.user_data)
            if fragment:
                msg = parse_fragment(fragment)
                os_session.on_message(msg)

    def deliver_to_master():
        """Deliver all queued outstation→master bytes."""
        ms_link = LinkLayer(on_frame=lambda f: None)
        ms_reasm = Reassembler()
        frames = []
        ms_link = LinkLayer(on_frame=frames.append)
        for data in outstation_to_master:
            ms_link.data_received(data)
        outstation_to_master.clear()
        for frame in frames:
            fragment = ms_reasm.add_segment(frame.user_data)
            if fragment:
                msg = parse_fragment(fragment)
                ms_session.on_message(msg)

    # --- Test scenario ---
    print("=" * 60)
    print("DNP3 Master ↔ Outstation Loopback Demo")
    print("=" * 60)

    # 1. Integrity poll
    print("\n[1] Master sends integrity poll (Class 0 read)...")
    ms_session.send_integrity_poll()
    deliver_to_outstation()
    deliver_to_master()

    resp = ms_handler.responses[-1]
    print(f"    Response: {len(resp.objects)} object groups")
    for obj in resp.objects:
        print(f"      Group {obj.header.group} Var {obj.header.variation}: "
              f"{len(obj.points)} points")
        for pt in obj.points:
            print(f"        index={pt.index}, value={pt.value}, flags=0x{pt.flags:02X}")

    # 2. Direct Operate analog output
    print("\n[2] Master sends Direct Operate (AO index=0, value=99.9)...")
    ms_session.send_direct_operate_analog(index=0, value=99.9)
    deliver_to_outstation()
    deliver_to_master()

    resp = ms_handler.responses[-1]
    if resp.objects:
        cmd = resp.objects[0].points[0]
        print(f"    Response status: {CommandStatus(cmd.status).name}")
    print(f"    DB AO[0] is now: {db.get_analog_outputs()[0].value}")

    # 3. Direct Operate binary output
    print("\n[3] Master sends Direct Operate (BO index=0, LATCH_ON)...")
    crob = CROB(control=0x03, count=1, on_time_ms=0, off_time_ms=0)
    ms_session.send_direct_operate_binary(index=0, crob=crob)
    deliver_to_outstation()
    deliver_to_master()

    resp = ms_handler.responses[-1]
    if resp.objects:
        _, result_crob = resp.objects[0].points[0]
        print(f"    Response status: {CommandStatus(result_crob.status).name}")
    print(f"    DB BO[0] is now: {db.get_binary_outputs()[0].value}")

    # 4. Event poll after change
    print("\n[4] Updating AI[0] to generate event, then event poll...")
    db.update_analog_input(0, 999.0)
    ms_session.send_event_poll()
    deliver_to_outstation()
    deliver_to_master()

    resp = ms_handler.responses[-1]
    print(f"    Response: {len(resp.objects)} event object groups")
    for obj in resp.objects:
        print(f"      Group {obj.header.group}: {len(obj.points)} events")

    print("\n" + "=" * 60)
    print("All operations completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()

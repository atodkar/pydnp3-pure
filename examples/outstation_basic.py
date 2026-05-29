"""Example: Basic DNP3 outstation over TCP.

This outstation has 5 analog inputs, 2 binary outputs, and 1 counter.
It accepts connections from a master and responds to polls and controls.
"""

import asyncio
import logging

from pydnp3_pure.app.constants import CommandStatus
from pydnp3_pure.io.tcp_server import TcpServer
from pydnp3_pure.link.layer import LinkLayer
from pydnp3_pure.link.frame import LinkFrame
from pydnp3_pure.transport.layer import TransportLayer
from pydnp3_pure.app.layer import ApplicationLayer
from pydnp3_pure.app.fragment import parse_fragment
from pydnp3_pure.objects.types import CROB
from pydnp3_pure.outstation.config import OutstationConfig
from pydnp3_pure.outstation.database import PointDatabase
from pydnp3_pure.outstation.handler import IOutstationHandler
from pydnp3_pure.outstation.session import OutstationSession

logging.basicConfig(level=logging.INFO)


class MyOutstationHandler(IOutstationHandler):
    """Application-specific control handler."""

    def __init__(self, db: PointDatabase):
        self._db = db

    def on_direct_operate_binary(self, index: int, crob: CROB) -> CommandStatus:
        print(f"  Binary Output [{index}] = {'ON' if crob.is_latch_on else 'OFF'}")
        self._db.update_binary_output(index, crob.is_latch_on)
        return CommandStatus.SUCCESS

    def on_direct_operate_analog(self, index: int, value: float) -> CommandStatus:
        print(f"  Analog Output [{index}] = {value}")
        self._db.update_analog_output(index, value)
        return CommandStatus.SUCCESS

    def on_freeze(self) -> None:
        print("  Freeze counters requested")


async def main():
    # Configure outstation
    config = OutstationConfig(address=10, master_address=1)

    # Set up point database
    db = PointDatabase()
    for i in range(5):
        db.add_analog_input(i, value=float(i * 10))
    db.add_binary_output(0, value=False)
    db.add_binary_output(1, value=False)
    db.add_counter(0, value=0)

    handler = MyOutstationHandler(db)

    # Create TCP server (master connects to us)
    server = TcpServer(host="127.0.0.1", port=20000)

    # Wire up the protocol stack
    def send_frame(frame: LinkFrame):
        server.send(frame.serialize())

    transport = TransportLayer(
        on_fragment=lambda f: None,  # Set below
        send_frame=send_frame,
        local_address=config.address,
        remote_address=config.master_address,
    )

    session = OutstationSession(
        config=config,
        database=db,
        handler=handler,
        send_fragment=lambda f: transport.send_fragment(f),
    )

    app_layer = ApplicationLayer(
        transport=transport,
        on_message=session.on_message,
    )
    transport._on_fragment = app_layer.on_fragment_received

    link_layer = LinkLayer(on_frame=transport.on_frame_received)
    server.set_receive_callback(link_layer.data_received)

    # Start server
    await server.open()
    print(f"Outstation listening on 127.0.0.1:20000 (address={config.address})")
    print("Waiting for master connection...")

    # Simulate updating analog inputs periodically
    try:
        counter = 0
        while True:
            await asyncio.sleep(2.0)
            counter += 1
            db.update_analog_input(0, float(counter * 5))
            db.update_counter(0, counter)
    except KeyboardInterrupt:
        pass
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(main())

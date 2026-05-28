"""Example: Basic DNP3 master that polls an outstation.

Connects to an outstation, performs integrity polls, and sends controls.
"""

import asyncio
import logging

from pydnp3.app.constants import CommandStatus
from pydnp3.app.fragment import AppMessage
from pydnp3.io.tcp_client import TcpClient
from pydnp3.link.layer import LinkLayer
from pydnp3.link.frame import LinkFrame
from pydnp3.transport.layer import TransportLayer
from pydnp3.app.layer import ApplicationLayer
from pydnp3.objects.types import CROB, AnalogOutputCommand
from pydnp3.master.config import MasterConfig
from pydnp3.master.handler import IMasterHandler
from pydnp3.master.session import MasterSession

logging.basicConfig(level=logging.INFO)


class MyMasterHandler(IMasterHandler):
    """Application-specific response handler."""

    def on_response_received(self, message: AppMessage) -> None:
        print(f"\n  Response received (FC={message.function.name}):")
        for obj in message.objects:
            print(f"    Group {obj.header.group} Var {obj.header.variation}: "
                  f"{len(obj.points)} points")
            for point in obj.points[:5]:  # Show first 5
                print(f"      {point}")

    def on_unsolicited_response(self, message: AppMessage) -> None:
        print(f"\n  Unsolicited response! Objects: {len(message.objects)}")

    def on_timeout(self) -> None:
        print("  Response timeout!")


async def main():
    config = MasterConfig(address=1, outstation_address=10)

    # Create TCP client (we connect to the outstation)
    client = TcpClient(host="127.0.0.1", port=20000)

    # Wire up protocol stack
    def send_frame(frame: LinkFrame):
        client.send(frame.serialize())

    transport = TransportLayer(
        on_fragment=lambda f: None,
        send_frame=send_frame,
        local_address=config.address,
        remote_address=config.outstation_address,
    )

    handler = MyMasterHandler()
    session = MasterSession(
        config=config,
        handler=handler,
        send_fragment=lambda f: transport.send_fragment(f, direction=True),
    )

    app_layer = ApplicationLayer(
        transport=transport,
        on_message=session.on_message,
    )
    transport._on_fragment = app_layer.on_fragment_received

    link_layer = LinkLayer(on_frame=transport.on_frame_received)
    client.set_receive_callback(link_layer.data_received)

    # Connect
    await client.open()
    print(f"Connected to outstation at 127.0.0.1:20000")

    # Perform integrity poll
    print("\nSending integrity poll...")
    session.send_integrity_poll()
    await asyncio.sleep(1.0)

    # Send event poll
    print("\nSending event poll...")
    session.send_event_poll()
    await asyncio.sleep(1.0)

    # Send Direct Operate on analog output
    print("\nSending Direct Operate (AO index=0, value=42.5)...")
    session.send_direct_operate_analog(index=0, value=42.5)
    await asyncio.sleep(1.0)

    # Send Direct Operate on binary output
    print("\nSending Direct Operate (BO index=0, LATCH_ON)...")
    crob = CROB(control=0x03, count=1, on_time_ms=0, off_time_ms=0)
    session.send_direct_operate_binary(index=0, crob=crob)
    await asyncio.sleep(1.0)

    await client.close()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())

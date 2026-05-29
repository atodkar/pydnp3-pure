"""DNP3 Outstation over TLS — listens for master connections with mutual TLS auth.

Run this first, then run master_tls.py in another terminal (or use the combined script).
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pydnp3_pure.app.constants import CommandStatus
from pydnp3_pure.io.tcp_server import TcpServer
from pydnp3_pure.io.tls import TlsConfig, create_tls_context
from pydnp3_pure.link.layer import LinkLayer
from pydnp3_pure.link.frame import LinkFrame
from pydnp3_pure.transport.layer import TransportLayer
from pydnp3_pure.app.layer import ApplicationLayer
from pydnp3_pure.objects.types import CROB
from pydnp3_pure.outstation.config import OutstationConfig
from pydnp3_pure.outstation.database import PointDatabase
from pydnp3_pure.outstation.handler import IOutstationHandler
from pydnp3_pure.outstation.session import OutstationSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s [OS] %(message)s")
log = logging.getLogger("outstation_tls")

CERTS_DIR = Path(__file__).parent / "certs"


class MyOutstationHandler(IOutstationHandler):
    def __init__(self, db: PointDatabase):
        self._db = db

    def on_direct_operate_binary(self, index: int, crob: CROB) -> CommandStatus:
        value = crob.is_latch_on
        log.info("BO[%d] direct operate -> %s", index, value)
        self._db.update_binary_output(index, value)
        return CommandStatus.SUCCESS

    def on_direct_operate_analog(self, index: int, value: float) -> CommandStatus:
        log.info("AO[%d] direct operate -> %.2f", index, value)
        self._db.update_analog_output(index, value)
        return CommandStatus.SUCCESS

    def on_freeze(self) -> None:
        log.info("Freeze counters requested")


async def run_outstation():
    config = OutstationConfig(address=10, master_address=1)

    db = PointDatabase()
    db.add_analog_input(0, value=120.5)
    db.add_analog_input(1, value=230.0)
    db.add_analog_input(2, value=-15.75)
    db.add_analog_output(0, value=0.0)
    db.add_analog_output(1, value=50.0)
    db.add_binary_output(0, value=False)
    db.add_binary_output(1, value=True)
    db.add_counter(0, value=100)

    handler = MyOutstationHandler(db)

    tls_config = TlsConfig(
        ca_cert_path=str(CERTS_DIR / "ca.pem"),
        client_cert_path=str(CERTS_DIR / "server.pem"),
        client_key_path=str(CERTS_DIR / "server-key.pem"),
        verify_hostname=False,
    )
    ssl_ctx = create_tls_context(tls_config, server_side=True)

    server = TcpServer(host="127.0.0.1", port=20001, ssl_context=ssl_ctx)

    def send_frame(frame: LinkFrame):
        server.send(frame.serialize())

    transport = TransportLayer(
        on_fragment=lambda f: None,
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

    await server.open()
    log.info("Outstation listening on 127.0.0.1:20001 (TLS enabled, address=%d)", config.address)
    log.info("Waiting for master connection...")

    try:
        counter = 0
        while True:
            await asyncio.sleep(2.0)
            counter += 1
            new_val = 120.5 + counter * 0.5
            db.update_analog_input(0, new_val)
            db.update_counter(0, 100 + counter)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await server.close()
        log.info("Outstation stopped.")


if __name__ == "__main__":
    asyncio.run(run_outstation())

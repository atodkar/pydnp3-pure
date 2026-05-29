"""DNP3 Master over TLS — connects to outstation with mutual TLS auth.

Run outstation_tls.py first, then run this script.
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pydnp3_pure.app.fragment import AppMessage
from pydnp3_pure.app.layer import ApplicationLayer
from pydnp3_pure.io.tcp_client import TcpClient
from pydnp3_pure.io.tls import TlsConfig, create_tls_context
from pydnp3_pure.link.frame import LinkFrame
from pydnp3_pure.link.layer import LinkLayer
from pydnp3_pure.master.config import MasterConfig
from pydnp3_pure.master.handler import IMasterHandler
from pydnp3_pure.master.session import MasterSession
from pydnp3_pure.objects.types import CROB
from pydnp3_pure.transport.layer import TransportLayer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MS] %(message)s")
log = logging.getLogger("master_tls")

CERTS_DIR = Path(__file__).parent / "certs"


class MyMasterHandler(IMasterHandler):
    def __init__(self):
        self.responses: list[AppMessage] = []

    def on_response_received(self, message: AppMessage) -> None:
        self.responses.append(message)
        log.info("Response received (FC=%s), %d object groups",
                 message.function.name, len(message.objects))
        for obj in message.objects:
            log.info("  Group %d Var %d: %d points",
                     obj.header.group, obj.header.variation, len(obj.points))
            for pt in obj.points[:10]:
                log.info("    %s", pt)


async def run_master():
    config = MasterConfig(address=1, outstation_address=10)

    tls_config = TlsConfig(
        ca_cert_path=str(CERTS_DIR / "ca.pem"),
        client_cert_path=str(CERTS_DIR / "client.pem"),
        client_key_path=str(CERTS_DIR / "client-key.pem"),
        verify_hostname=False,
    )
    ssl_ctx = create_tls_context(tls_config, server_side=False)

    client = TcpClient(
        host="127.0.0.1",
        port=20001,
        ssl_context=ssl_ctx,
        server_hostname="localhost",
    )

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

    await client.open()
    log.info("Master connected to outstation at 127.0.0.1:20001 (TLS)")

    # 1. Integrity poll — read all static data
    log.info("--- Integrity Poll (Class 0 Read) ---")
    session.send_integrity_poll()
    await asyncio.sleep(0.5)

    # 2. Direct Operate — set analog output
    log.info("--- Direct Operate: AO[0] = 77.7 ---")
    session.send_direct_operate_analog(index=0, value=77.7)
    await asyncio.sleep(0.5)

    log.info("--- Direct Operate: AO[1] = -12.3 ---")
    session.send_direct_operate_analog(index=1, value=-12.3)
    await asyncio.sleep(0.5)

    # 3. Direct Operate — set binary outputs
    log.info("--- Direct Operate: BO[0] = LATCH_ON ---")
    crob_on = CROB(control=0x03, count=1, on_time_ms=0, off_time_ms=0)
    session.send_direct_operate_binary(index=0, crob=crob_on)
    await asyncio.sleep(0.5)

    log.info("--- Direct Operate: BO[1] = LATCH_OFF ---")
    crob_off = CROB(control=0x04, count=1, on_time_ms=0, off_time_ms=0)
    session.send_direct_operate_binary(index=1, crob=crob_off)
    await asyncio.sleep(0.5)

    # 4. Second integrity poll — verify changes took effect
    log.info("--- Second Integrity Poll (verify changes) ---")
    session.send_integrity_poll()
    await asyncio.sleep(0.5)

    # 5. Event poll — check for analog input change events
    log.info("--- Event Poll (Class 1/2/3) ---")
    session.send_event_poll()
    await asyncio.sleep(0.5)

    await client.close()
    log.info("Master disconnected.")

    return handler.responses


if __name__ == "__main__":
    asyncio.run(run_master())

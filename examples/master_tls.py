"""DNP3 Master over TLS in redundant listener mode.

Starts two TLS server channels (primary + secondary) that accept outstation
connections. Both channels run the same DNP3 poll cycle and use the same
server certificate chain for mutual TLS.

This mirrors dual-homed master endpoints where an external outstation connects
to two independent ports using the same client certificate.
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pydnp3_pure.app.fragment import AppMessage
from pydnp3_pure.app.layer import ApplicationLayer
from pydnp3_pure.io.tcp_server import TcpServer
from pydnp3_pure.io.tls import TlsConfig, create_tls_context
from pydnp3_pure.link.frame import LinkFrame
from pydnp3_pure.link.layer import LinkLayer
from pydnp3_pure.master.config import MasterConfig
from pydnp3_pure.master.handler import IMasterHandler
from pydnp3_pure.master.session import MasterSession
from pydnp3_pure.transport.layer import TransportLayer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MS] %(message)s")
log = logging.getLogger("master_tls")

CERTS_DIR = Path(__file__).parent / "certs"
PRIMARY_PORT = 20001
SECONDARY_PORT = 20002


class MyMasterHandler(IMasterHandler):
    def __init__(self, channel_name: str):
        self.channel_name = channel_name
        self.responses: list[AppMessage] = []

    def on_response_received(self, message: AppMessage) -> None:
        self.responses.append(message)
        log.info(
            "[%s] Response received (FC=%s), %d object groups",
            self.channel_name,
            message.function.name,
            len(message.objects),
        )
        for obj in message.objects:
            log.info(
                "[%s]   Group %d Var %d: %d points",
                self.channel_name,
                obj.header.group,
                obj.header.variation,
                len(obj.points),
            )
            for pt in obj.points[:10]:
                log.info("[%s]     %s", self.channel_name, pt)


class RedundantMasterChannel:
    def __init__(self, name: str, port: int, ssl_ctx):
        self.name = name
        self.port = port
        self._ao_step = 0
        self.config = MasterConfig(address=1, outstation_address=10)
        self.server = TcpServer(host="0.0.0.0", port=port, ssl_context=ssl_ctx)

        self.transport = TransportLayer(
            on_fragment=lambda f: None,
            send_frame=self._send_frame,
            local_address=self.config.address,
            remote_address=self.config.outstation_address,
        )
        self.handler = MyMasterHandler(channel_name=name)
        self.session = MasterSession(
            config=self.config,
            handler=self.handler,
            send_fragment=lambda f: self.transport.send_fragment(f, direction=True),
        )

        self.app_layer = ApplicationLayer(
            transport=self.transport,
            on_message=self.session.on_message,
        )
        self.transport._on_fragment = self.app_layer.on_fragment_received

        self.link_layer = LinkLayer(on_frame=self.transport.on_frame_received)
        self.server.set_receive_callback(self.link_layer.data_received)

    def _send_frame(self, frame: LinkFrame) -> None:
        self.server.send(frame.serialize())

    async def open(self) -> None:
        await self.server.open()
        log.info("[%s] Listening on 0.0.0.0:%d (TLS mutual auth)", self.name, self.port)

    async def close(self) -> None:
        await self.server.close()

    async def poll_cycle(self) -> None:
        while True:
            await self.server.wait_for_connection()
            if not self.server.is_open:
                await asyncio.sleep(0.2)
                continue

            log.info("[%s] Outstation connected on port %d", self.name, self.port)
            try:
                ao_index = self._ao_step % 2
                ao_value = 77.7 if ao_index == 0 else -12.3
                self.session.send_direct_operate_analog(index=ao_index, value=ao_value)
                log.info(
                    "[%s] Sent AO direct-operate every 2s: AO[%d] = %.2f",
                    self.name,
                    ao_index,
                    ao_value,
                )

                self.session.send_analog_input_scan(start=0, stop=2, variation=5)
                log.info("[%s] Sent explicit AI scan every 2s: Group30Var5 range 0..2", self.name)

                self._ao_step += 1
                await asyncio.sleep(2.0)
            except Exception:
                log.exception("[%s] Poll cycle error", self.name)
                await asyncio.sleep(1.0)


def build_server_tls_context():
    tls_config = TlsConfig(
        ca_cert_path=str(CERTS_DIR / "ca.pem"),
        client_cert_path=str(CERTS_DIR / "server.pem"),
        client_key_path=str(CERTS_DIR / "server-key.pem"),
        verify_hostname=False,
    )
    return create_tls_context(tls_config, server_side=True)


async def run_master_redundant():
    primary = RedundantMasterChannel(
        "PRIMARY", PRIMARY_PORT, build_server_tls_context()
    )
    secondary = RedundantMasterChannel(
        "SECONDARY", SECONDARY_PORT, build_server_tls_context()
    )

    await primary.open()
    await secondary.open()

    log.info("Redundant TLS master started.")
    log.info("External outstation may connect to both ports with the same client cert.")
    log.info("Primary endpoint:   0.0.0.0:%d", PRIMARY_PORT)
    log.info("Secondary endpoint: 0.0.0.0:%d", SECONDARY_PORT)

    try:
        await asyncio.gather(primary.poll_cycle(), secondary.poll_cycle())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await primary.close()
        await secondary.close()
        log.info("Redundant TLS master stopped.")


if __name__ == "__main__":
    asyncio.run(run_master_redundant())

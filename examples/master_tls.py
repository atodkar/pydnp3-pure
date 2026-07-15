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

# Keep console clean for operator input; signal activity is logged to files.
logging.basicConfig(level=logging.CRITICAL)
log = logging.getLogger("master_tls")

CERTS_DIR = Path(__file__).parent / "certs"
LOG_DIR = Path(__file__).parent / "logs"
PRIMARY_PORT = 20001
SECONDARY_PORT = 20002


def build_signal_logger(channel_name: str) -> tuple[logging.Logger, Path]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_path = LOG_DIR / f"{channel_name.lower()}_signals.log"

    logger = logging.getLogger(f"master_tls.signals.{channel_name.lower()}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    handler = logging.FileHandler(file_path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)

    return logger, file_path


class MyMasterHandler(IMasterHandler):
    def __init__(self, channel_name: str, signal_log: logging.Logger):
        self.channel_name = channel_name
        self.signal_log = signal_log
        self.responses: list[AppMessage] = []

    def on_response_received(self, message: AppMessage) -> None:
        self.responses.append(message)
        self.signal_log.info(
            "[%s] Response received (FC=%s), %d object groups",
            self.channel_name,
            message.function.name,
            len(message.objects),
        )
        for obj in message.objects:
            self.signal_log.info(
                "[%s]   Group %d Var %d: %d points",
                self.channel_name,
                obj.header.group,
                obj.header.variation,
                len(obj.points),
            )
            for pt in obj.points[:10]:
                self.signal_log.info("[%s]     %s", self.channel_name, pt)


class RedundantMasterChannel:
    def __init__(self, name: str, port: int, ssl_ctx):
        self.name = name
        self.port = port
        self._ao_step = 0
        self._enabled = True
        self._listening = False
        self.signal_log, self.log_file_path = build_signal_logger(name)
        self.config = MasterConfig(address=1, outstation_address=10)
        self.server = TcpServer(host="0.0.0.0", port=port, ssl_context=ssl_ctx)

        self.transport = TransportLayer(
            on_fragment=lambda f: None,
            send_frame=self._send_frame,
            local_address=self.config.address,
            remote_address=self.config.outstation_address,
        )
        self.handler = MyMasterHandler(channel_name=name, signal_log=self.signal_log)
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
        if self._listening:
            return
        await self.server.open()
        self._listening = True
        self.signal_log.info(
            "[%s] Channel listening on 0.0.0.0:%d (TLS mutual auth)",
            self.name,
            self.port,
        )

    async def close(self) -> None:
        if not self._listening:
            return
        await self.server.close()
        self._listening = False
        self.signal_log.info("[%s] Channel listener stopped", self.name)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def is_listening(self) -> bool:
        return self._listening

    async def enable(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        await self.open()
        self.signal_log.info("[%s] Channel enabled", self.name)

    async def disable(self) -> None:
        if not self._enabled:
            return
        self._enabled = False
        await self.close()
        self.signal_log.info("[%s] Channel disabled", self.name)

    def status_text(self) -> str:
        state = "ENABLED" if self._enabled else "DISABLED"
        listening = "LISTENING" if self._listening else "DOWN"
        connected = "CONNECTED" if self.server.is_open else "NO_CLIENT"
        return (
            f"{self.name}: {state}, {listening}, {connected}, "
            f"port={self.port}, log={self.log_file_path.name}"
        )

    async def _wait_until_ready(self) -> bool:
        if not self._enabled:
            await asyncio.sleep(0.2)
            return False

        if not self._listening:
            await self.open()

        try:
            await asyncio.wait_for(self.server.wait_for_connection(), timeout=1.0)
        except asyncio.TimeoutError:
            return False

        if not self.server.is_open:
            await asyncio.sleep(0.2)
            return False

        return True

    async def _run_active_connection(self, connection_id: int) -> None:
        self.signal_log.info(
            "[%s] Outstation connected on port %d (connection_id=%d)",
            self.name,
            self.port,
            connection_id,
        )

        while self._enabled and self.server.is_open and self.server.connection_id == connection_id:
            try:
                ao_index = self._ao_step % 2
                ao_value = 77.7 if ao_index == 0 else -12.3
                self.session.send_direct_operate_analog(index=ao_index, value=ao_value)
                self.signal_log.info(
                    "[%s] Sent AO direct-operate every 2s: AO[%d] = %.2f",
                    self.name,
                    ao_index,
                    ao_value,
                )

                self.session.send_analog_input_scan(start=0, stop=2, variation=5)
                self.signal_log.info(
                    "[%s] Sent explicit AI scan every 2s: Group30Var5 range 0..2",
                    self.name,
                )

                self._ao_step += 1
                await asyncio.sleep(2.0)
            except Exception:
                self.signal_log.exception("[%s] Poll cycle error", self.name)
                await asyncio.sleep(1.0)

        self.signal_log.info(
            "[%s] Connection ended (connection_id=%d), waiting for reconnect",
            self.name,
            connection_id,
        )

    async def poll_cycle(self) -> None:
        while True:
            ready = await self._wait_until_ready()
            if not ready:
                continue

            await self._run_active_connection(self.server.connection_id)


async def operator_console(
    primary: RedundantMasterChannel,
    secondary: RedundantMasterChannel,
    shutdown_event: asyncio.Event,
) -> None:
    def print_status() -> None:
        print(primary.status_text())
        print(secondary.status_text())

    def quit_console() -> None:
        shutdown_event.set()

    command_handlers = {
        "status": print_status,
        "down primary": primary.disable,
        "down secondary": secondary.disable,
        "up primary": primary.enable,
        "up secondary": secondary.enable,
        "quit": quit_console,
        "exit": quit_console,
    }

    print(
        "Runtime control enabled: type 'status', 'down primary', 'down secondary', "
        "'up primary', 'up secondary', 'quit'"
    )
    while not shutdown_event.is_set():
        try:
            raw = await asyncio.to_thread(input, "master-control> ")
        except EOFError:
            shutdown_event.set()
            return

        cmd = raw.strip().lower()
        if not cmd:
            continue

        handler = command_handlers.get(cmd)
        if handler is None:
            print(f"Unknown command: {cmd}")
            print("Valid commands: status | down primary | down secondary | up primary | up secondary | quit")
            continue

        result = handler()
        if asyncio.iscoroutine(result):
            await result


def build_server_tls_context():
    tls_config = TlsConfig(
        ca_cert_path=str(CERTS_DIR / "ca.pem"),
        client_cert_path=str(CERTS_DIR / "server.pem"),
        client_key_path=str(CERTS_DIR / "server-key.pem"),
        verify_hostname=False,
    )
    return create_tls_context(tls_config, server_side=True)


async def run_master_redundant():
    shutdown_event = asyncio.Event()

    primary = RedundantMasterChannel(
        "PRIMARY", PRIMARY_PORT, build_server_tls_context()
    )
    secondary = RedundantMasterChannel(
        "SECONDARY", SECONDARY_PORT, build_server_tls_context()
    )

    await primary.open()
    await secondary.open()

    primary.signal_log.info("Signal log file initialized: %s", primary.log_file_path)
    secondary.signal_log.info("Signal log file initialized: %s", secondary.log_file_path)

    tasks = [
        asyncio.create_task(primary.poll_cycle(), name="primary-poll"),
        asyncio.create_task(secondary.poll_cycle(), name="secondary-poll"),
        asyncio.create_task(
            operator_console(primary, secondary, shutdown_event),
            name="operator-console",
        ),
    ]

    try:
        await shutdown_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await primary.close()
        await secondary.close()
        log.info("Redundant TLS master stopped.")


if __name__ == "__main__":
    asyncio.run(run_master_redundant())

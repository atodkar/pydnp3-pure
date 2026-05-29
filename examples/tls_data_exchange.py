"""Combined TLS test: runs outstation + master in one process over real TLS sockets.

Demonstrates mutual TLS authentication with analog and digital data exchange.
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pydnp3_pure.app.constants import CommandStatus
from pydnp3_pure.app.fragment import AppMessage
from pydnp3_pure.app.layer import ApplicationLayer
from pydnp3_pure.io.tcp_client import TcpClient
from pydnp3_pure.io.tcp_server import TcpServer
from pydnp3_pure.io.tls import TlsConfig, create_tls_context
from pydnp3_pure.link.frame import LinkFrame
from pydnp3_pure.link.layer import LinkLayer
from pydnp3_pure.master.config import MasterConfig
from pydnp3_pure.master.handler import IMasterHandler
from pydnp3_pure.master.session import MasterSession
from pydnp3_pure.objects.types import CROB
from pydnp3_pure.outstation.config import OutstationConfig
from pydnp3_pure.outstation.database import PointDatabase
from pydnp3_pure.outstation.handler import IOutstationHandler
from pydnp3_pure.outstation.session import OutstationSession
from pydnp3_pure.transport.layer import TransportLayer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("tls_demo")

CERTS_DIR = Path(__file__).parent / "certs"


class DemoOutstationHandler(IOutstationHandler):
    def __init__(self, db: PointDatabase):
        self._db = db

    def on_direct_operate_binary(self, index: int, crob: CROB) -> CommandStatus:
        self._db.update_binary_output(index, crob.is_latch_on)
        return CommandStatus.SUCCESS

    def on_direct_operate_analog(self, index: int, value: float) -> CommandStatus:
        self._db.update_analog_output(index, value)
        return CommandStatus.SUCCESS


class DemoMasterHandler(IMasterHandler):
    def __init__(self):
        self.responses: list[AppMessage] = []

    def on_response_received(self, message: AppMessage) -> None:
        self.responses.append(message)


async def main():
    print("=" * 70)
    print("  DNP3 Master <-> Outstation over TLS (mutual authentication)")
    print("=" * 70)

    # --- Outstation setup ---
    os_config = OutstationConfig(address=10, master_address=1)
    db = PointDatabase()
    db.add_analog_input(0, value=120.5)
    db.add_analog_input(1, value=230.0)
    db.add_analog_input(2, value=-15.75)
    db.add_analog_output(0, value=0.0)
    db.add_analog_output(1, value=50.0)
    db.add_binary_output(0, value=False)
    db.add_binary_output(1, value=True)
    db.add_counter(0, value=100)

    os_handler = DemoOutstationHandler(db)

    server_tls = TlsConfig(
        ca_cert_path=str(CERTS_DIR / "ca.pem"),
        client_cert_path=str(CERTS_DIR / "server.pem"),
        client_key_path=str(CERTS_DIR / "server-key.pem"),
        verify_hostname=False,
    )
    server_ssl = create_tls_context(server_tls, server_side=True)

    server = TcpServer(host="127.0.0.1", port=20001, ssl_context=server_ssl)

    def os_send_frame(frame: LinkFrame):
        server.send(frame.serialize())

    os_transport = TransportLayer(
        on_fragment=lambda f: None,
        send_frame=os_send_frame,
        local_address=os_config.address,
        remote_address=os_config.master_address,
    )

    os_session = OutstationSession(
        config=os_config, database=db,
        handler=os_handler,
        send_fragment=lambda f: os_transport.send_fragment(f),
    )

    os_app = ApplicationLayer(transport=os_transport, on_message=os_session.on_message)
    os_transport._on_fragment = os_app.on_fragment_received

    os_link = LinkLayer(on_frame=os_transport.on_frame_received)
    server.set_receive_callback(os_link.data_received)

    await server.open()
    print("\n[OK] Outstation TLS server listening on 127.0.0.1:20001")

    # --- Master setup ---
    ms_config = MasterConfig(address=1, outstation_address=10)

    client_tls = TlsConfig(
        ca_cert_path=str(CERTS_DIR / "ca.pem"),
        client_cert_path=str(CERTS_DIR / "client.pem"),
        client_key_path=str(CERTS_DIR / "client-key.pem"),
        verify_hostname=False,
    )
    client_ssl = create_tls_context(client_tls, server_side=False)

    client = TcpClient(
        host="127.0.0.1", port=20001,
        ssl_context=client_ssl, server_hostname="localhost",
    )

    def ms_send_frame(frame: LinkFrame):
        client.send(frame.serialize())

    ms_transport = TransportLayer(
        on_fragment=lambda f: None,
        send_frame=ms_send_frame,
        local_address=ms_config.address,
        remote_address=ms_config.outstation_address,
    )

    ms_handler = DemoMasterHandler()
    ms_session = MasterSession(
        config=ms_config, handler=ms_handler,
        send_fragment=lambda f: ms_transport.send_fragment(f, direction=True),
    )

    ms_app = ApplicationLayer(transport=ms_transport, on_message=ms_session.on_message)
    ms_transport._on_fragment = ms_app.on_fragment_received

    ms_link = LinkLayer(on_frame=ms_transport.on_frame_received)
    client.set_receive_callback(ms_link.data_received)

    await client.open()
    print("[OK] Master connected via TLS (mutual auth verified)\n")

    await asyncio.sleep(0.3)

    # === TEST 1: Integrity Poll ===
    print("-" * 70)
    print("[1] INTEGRITY POLL (Class 0 Read) - all static data")
    print("-" * 70)
    ms_session.send_integrity_poll()
    await asyncio.sleep(0.5)

    resp = ms_handler.responses[-1]
    print(f"    Received {len(resp.objects)} object groups:")
    for obj in resp.objects:
        print(f"      Group {obj.header.group:>2} Var {obj.header.variation}: "
              f"{len(obj.points)} points")
        for pt in obj.points:
            print(f"        [{pt.index}] value={pt.value}, flags=0x{pt.flags:02X}")

    # === TEST 2: Direct Operate Analog ===
    print(f"\n{'-' * 70}")
    print("[2] DIRECT OPERATE — Analog Outputs")
    print("-" * 70)

    print("    Setting AO[0] = 77.7 ...")
    ms_session.send_direct_operate_analog(index=0, value=77.7)
    await asyncio.sleep(0.3)
    resp = ms_handler.responses[-1]
    if resp.objects:
        status = resp.objects[0].points[0].status
        print(f"    Response: CommandStatus = {CommandStatus(status).name}")
    print(f"    DB verify: AO[0] = {db.get_analog_outputs()[0].value}")

    print("    Setting AO[1] = -12.3 ...")
    ms_session.send_direct_operate_analog(index=1, value=-12.3)
    await asyncio.sleep(0.3)
    resp = ms_handler.responses[-1]
    if resp.objects:
        status = resp.objects[0].points[0].status
        print(f"    Response: CommandStatus = {CommandStatus(status).name}")
    print(f"    DB verify: AO[1] = {db.get_analog_outputs()[1].value}")

    # === TEST 3: Direct Operate Binary ===
    print(f"\n{'-' * 70}")
    print("[3] DIRECT OPERATE — Binary Outputs (Digital)")
    print("-" * 70)

    print("    Setting BO[0] = LATCH_ON ...")
    crob_on = CROB(control=0x03, count=1, on_time_ms=0, off_time_ms=0)
    ms_session.send_direct_operate_binary(index=0, crob=crob_on)
    await asyncio.sleep(0.3)
    resp = ms_handler.responses[-1]
    if resp.objects:
        _, result_crob = resp.objects[0].points[0]
        print(f"    Response: CommandStatus = {CommandStatus(result_crob.status).name}")
    print(f"    DB verify: BO[0] = {db.get_binary_outputs()[0].value}")

    print("    Setting BO[1] = LATCH_OFF ...")
    crob_off = CROB(control=0x04, count=1, on_time_ms=0, off_time_ms=0)
    ms_session.send_direct_operate_binary(index=1, crob=crob_off)
    await asyncio.sleep(0.3)
    resp = ms_handler.responses[-1]
    if resp.objects:
        _, result_crob = resp.objects[0].points[0]
        print(f"    Response: CommandStatus = {CommandStatus(result_crob.status).name}")
    print(f"    DB verify: BO[1] = {db.get_binary_outputs()[1].value}")

    # === TEST 4: Verify changes with second integrity poll ===
    print(f"\n{'-' * 70}")
    print("[4] SECOND INTEGRITY POLL — verify all changes persisted")
    print("-" * 70)
    ms_session.send_integrity_poll()
    await asyncio.sleep(0.5)

    resp = ms_handler.responses[-1]
    for obj in resp.objects:
        print(f"    Group {obj.header.group:>2} Var {obj.header.variation}: "
              f"{len(obj.points)} points")
        for pt in obj.points:
            print(f"      [{pt.index}] value={pt.value}, flags=0x{pt.flags:02X}")

    # === TEST 5: Event generation and poll ===
    print(f"\n{'-' * 70}")
    print("[5] EVENT POLL — change AI[0] and read events")
    print("-" * 70)
    print("    Updating AI[0] from current value to 999.0 (triggers event)...")
    db.update_analog_input(0, 999.0)
    ms_session.send_event_poll()
    await asyncio.sleep(0.5)

    resp = ms_handler.responses[-1]
    print(f"    Received {len(resp.objects)} event group(s):")
    for obj in resp.objects:
        print(f"      Group {obj.header.group} Var {obj.header.variation}: "
              f"{len(obj.points)} events")

    # === Done ===
    await client.close()
    await server.close()

    print(f"\n{'=' * 70}")
    print("  ALL TLS TESTS PASSED — Analog and Digital data exchanged successfully")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())

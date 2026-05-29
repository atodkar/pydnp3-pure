# pydnp3-pure

[![CI](https://github.com/anandtodkar/pydnp3-pure/actions/workflows/ci.yml/badge.svg)](https://github.com/anandtodkar/pydnp3-pure/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Pure Python DNP3 (IEEE 1815) library. No C++ bindings, no native DLLs — just `pip install` and go.

```bash
pip install pydnp3-pure
```

## 30-Second Example

**Poll an outstation and read analog values — in 6 lines of logic:**

```python
from pydnp3_pure.mock import create_loopback_pair

pair = create_loopback_pair()
pair.outstation.database.add_analog_input(0, value=72.5)
pair.outstation.database.add_binary_output(0, value=False)

pair.master.session.send_integrity_poll()
pair.exchange()

response = pair.master.handler.responses[0]
for obj in response.objects:
    for pt in obj.points:
        print(f"  [{pt.index}] = {pt.value}")
```

**Issue a control command:**

```python
from pydnp3_pure.objects.types import CROB

pair.master.session.send_direct_operate_binary(
    index=0, crob=CROB(control=0x03, count=1, on_time_ms=0, off_time_ms=0)
)
pair.exchange()
assert pair.outstation.database.get_binary_outputs()[0].value is True
```

## Use Cases

- **SCADA simulators** — Spin up virtual outstations for integration testing
- **Automated test scripts** — Validate master/outstation logic without physical hardware
- **IoT gateways** — Lightweight DNP3 endpoint on Raspberry Pi or edge devices
- **Protocol analysis** — Parse and debug DNP3 traffic with human-readable output
- **Education** — Learn DNP3 with immediate, runnable code

## Why pydnp3-pure?

| Feature | pydnp3-pure | C++-wrapped alternatives |
|---------|-------------|--------------------------|
| Install | `pip install pydnp3-pure` | Compile C++ toolchain |
| asyncio native | Yes | Threading/callbacks |
| Type hints | Full (mypy strict) | Partial or none |
| Data types | Python dataclasses + enums | Custom C++ wrappers |
| Debugging | Built-in protocol logger | External tools only |
| Testing | Built-in mock utilities | Requires hardware or simulator |
| Dependencies | Zero (stdlib only) | OpenDNP3, Boost, etc. |

## Built-in Debugging Tools

DNP3 troubleshooting is hard because raw bytecode is unreadable. pydnp3-pure includes tools to fix that:

```python
from pydnp3_pure.debug import enable_debug_logging, hex_dump, ProtocolLogger

# Turn on human-readable protocol logging
enable_debug_logging()
# Output: 14:23:01 [pydnp3_pure.protocol] INFO: TX READ Request [Class Objects] seq=1
#         14:23:01 [pydnp3_pure.protocol] INFO: RX RESPONSE [Analog Inputs: 3 pts] seq=1

# Wireshark-friendly hex dump
raw_frame = b"\x05\x64\x05\xc0\x01\x00\x0a\x00\xe0\xa4"
print(hex_dump(raw_frame))
# 0000  05 64 05 c0 01 00 0a 00  e0 a4                   .d........

# Wrap any session for automatic logging
logger = ProtocolLogger()
session.on_message = logger.wrap_rx(session.on_message)
```

## Built-in Mocking for Tests

Write unit tests for your DNP3 application without network or hardware:

```python
import pytest
from pydnp3_pure.mock import create_loopback_pair

def test_my_scada_logic():
    pair = create_loopback_pair()
    pair.outstation.database.add_analog_input(0, value=98.6)

    pair.master.session.send_integrity_poll()
    pair.exchange()

    response = pair.master.handler.responses[0]
    assert response.objects[0].points[0].value == 98.6
```

## Full Network Example

### Outstation (listens for master connections)

```python
import asyncio
from pydnp3_pure.app.constants import CommandStatus
from pydnp3_pure.objects.types import CROB
from pydnp3_pure.outstation.config import OutstationConfig
from pydnp3_pure.outstation.database import PointDatabase
from pydnp3_pure.outstation.handler import IOutstationHandler
from pydnp3_pure.outstation.session import OutstationSession
from pydnp3_pure.io.tcp_server import TcpServer
from pydnp3_pure.link.layer import LinkLayer
from pydnp3_pure.link.frame import LinkFrame
from pydnp3_pure.transport.layer import TransportLayer
from pydnp3_pure.app.layer import ApplicationLayer


class MyHandler(IOutstationHandler):
    def __init__(self, db: PointDatabase):
        self.db = db

    def on_direct_operate_binary(self, index: int, crob: CROB) -> CommandStatus:
        self.db.update_binary_output(index, crob.is_latch_on)
        return CommandStatus.SUCCESS

    def on_direct_operate_analog(self, index: int, value: float) -> CommandStatus:
        self.db.update_analog_output(index, value)
        return CommandStatus.SUCCESS


async def main():
    config = OutstationConfig(address=10, master_address=1)
    db = PointDatabase()
    db.add_analog_input(0, value=25.5)
    db.add_binary_output(0, value=False)

    handler = MyHandler(db)
    server = TcpServer(host="0.0.0.0", port=20000)

    def send_frame(frame: LinkFrame):
        server.send(frame.serialize())

    transport = TransportLayer(
        on_fragment=lambda f: None,
        send_frame=send_frame,
        local_address=config.address,
        remote_address=config.master_address,
    )

    session = OutstationSession(
        config=config, database=db, handler=handler,
        send_fragment=lambda f: transport.send_fragment(f),
    )

    app_layer = ApplicationLayer(transport=transport, on_message=session.on_message)
    transport._on_fragment = app_layer.on_fragment_received

    link_layer = LinkLayer(on_frame=transport.on_frame_received)
    server.set_receive_callback(link_layer.data_received)

    await server.open()
    print("Outstation running on port 20000")
    while True:
        await asyncio.sleep(1.0)

asyncio.run(main())
```

### Master (connects and polls)

```python
import asyncio
from pydnp3_pure.app.fragment import AppMessage
from pydnp3_pure.master.config import MasterConfig
from pydnp3_pure.master.handler import IMasterHandler
from pydnp3_pure.master.session import MasterSession
from pydnp3_pure.io.tcp_client import TcpClient
from pydnp3_pure.link.layer import LinkLayer
from pydnp3_pure.link.frame import LinkFrame
from pydnp3_pure.transport.layer import TransportLayer
from pydnp3_pure.app.layer import ApplicationLayer


class MyMasterHandler(IMasterHandler):
    def on_response_received(self, message: AppMessage) -> None:
        for obj in message.objects:
            for pt in obj.points:
                print(f"  [{pt.index}] = {pt.value}")


async def main():
    config = MasterConfig(address=1, outstation_address=10)
    client = TcpClient(host="127.0.0.1", port=20000)

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
        config=config, handler=handler,
        send_fragment=lambda f: transport.send_fragment(f, direction=True),
    )

    app_layer = ApplicationLayer(transport=transport, on_message=session.on_message)
    transport._on_fragment = app_layer.on_fragment_received

    link_layer = LinkLayer(on_frame=transport.on_frame_received)
    client.set_receive_callback(link_layer.data_received)

    await client.open()
    session.send_integrity_poll()
    await asyncio.sleep(1.0)
    await client.close()

asyncio.run(main())
```

### TLS Configuration

```python
from pydnp3_pure.io.tls import TlsConfig, create_tls_context
from pydnp3_pure.io.tcp_client import TcpClient

tls_config = TlsConfig(
    ca_cert_path="/path/to/ca.pem",
    client_cert_path="/path/to/client.pem",
    client_key_path="/path/to/client-key.pem",
    verify_hostname=True,
    server_hostname="dnp3.example.com",
)
ssl_ctx = create_tls_context(tls_config)

client = TcpClient(
    host="dnp3.example.com", port=20001,
    ssl_context=ssl_ctx, server_hostname="dnp3.example.com",
)
```

## Architecture

```
┌────────────────────────────────────────────┐
│  Application  (OutstationSession / Master) │  State machine + callbacks
├────────────────────────────────────────────┤
│  Application Layer  (APDU parse/build)     │  Object header dispatch
├────────────────────────────────────────────┤
│  Transport Layer  (reassemble/segment)     │  FIR/FIN/SEQ management
├────────────────────────────────────────────┤
│  Link Layer  (frame/CRC/state machine)     │  Sync detection + CRC-16
├────────────────────────────────────────────┤
│  Channel  (asyncio TCP/TLS)                │  Raw byte I/O
└────────────────────────────────────────────┘
```

### Package Structure

| Package | Responsibility |
|---------|---------------|
| `pydnp3_pure.link` | Data link layer: sync detection, CRC-16 DNP3, frame serialization |
| `pydnp3_pure.transport` | Transport layer: fragment reassembly (rx) and segmentation (tx) |
| `pydnp3_pure.app` | Application layer: function codes, qualifiers, object header parsing |
| `pydnp3_pure.objects` | Object group handlers: plugin registry for all DNP3 data types |
| `pydnp3_pure.outstation` | Outstation role: session state machine, point database, events |
| `pydnp3_pure.master` | Master role: polling, control commands, response processing |
| `pydnp3_pure.io` | Network I/O: async TCP client/server, TLS context builder |
| `pydnp3_pure.debug` | Human-readable protocol logging and Wireshark hex dump utilities |
| `pydnp3_pure.mock` | In-memory mocking utilities for unit testing without hardware |
| `pydnp3_pure.util` | Utilities: binary read/write buffers, async timers |

## Supported Object Groups

| Group | Name | Variations | Direction |
|-------|------|-----------|-----------|
| 1 | Binary Input | V1 (packed), V2 (flags) | Read |
| 2 | Binary Input Event | V1-V3 (with timestamp) | Event |
| 10 | Binary Output Status | V1 (packed), V2 (flags) | Read |
| 12 | CROB (Binary Control) | V1 (11-byte block) | Command |
| 20 | Binary Counter | V1, V2, V5, V6 | Read |
| 21 | Frozen Counter | V1, V2, V5, V6, V9, V10 | Read |
| 30 | Analog Input | V1-V6 (int16/32, float, double) | Read |
| 32 | Analog Input Event | V1-V8 (with timestamp) | Event |
| 40 | Analog Output Status | V1-V4 | Read |
| 41 | Analog Output Command | V1-V4 | Command |
| 50 | Time and Date | V1 (48-bit ms) | Read/Write |
| 60 | Class Data | V1-V4 (Class 0/1/2/3) | Request |
| 80 | IIN Bits | V1 (packed) | Write |

## Adding Custom Object Groups

```python
from pydnp3_pure.objects.base import ObjectGroupHandler
from pydnp3_pure.objects.registry import register_handler
from pydnp3_pure.util.buffer import ReadBuffer, WriteBuffer


@register_handler
class Group110Handler(ObjectGroupHandler):
    """Octet String (Group 110)."""

    @property
    def group(self) -> int:
        return 110

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (0,)

    def parse(self, variation, qualifier, count, start, buf: ReadBuffer):
        return [buf.read_bytes(variation).decode("ascii", errors="replace")
                for _ in range(count)]

    def serialize(self, variation, qualifier, points, buf: WriteBuffer):
        for s in points:
            buf.write_bytes(s.encode("ascii")[:variation])

    def point_size(self, variation: int) -> int:
        return variation
```

## Running Tests

```bash
pytest tests/ -v

# With coverage
pytest tests/ --cov=pydnp3_pure --cov-report=term-missing

# Specific module
pytest tests/test_full_stack.py -v
```

## Running Examples

```bash
# In-process loopback (no network needed)
python examples/master_outstation_loopback.py

# Network examples (two terminals)
python examples/outstation_basic.py   # Terminal 1
python examples/master_basic.py       # Terminal 2
```

## Design Decisions

1. **asyncio over threading** — DNP3 is event-driven; asyncio maps naturally and avoids GIL contention.
2. **Plugin registry for object groups** — Each group is a self-contained handler. Adding groups requires zero changes to core parsing.
3. **Zero-copy parsing with `memoryview`** — `ReadBuffer` wraps `struct.unpack_from` for efficient parsing without intermediate copies.
4. **Zero runtime dependencies** — Only Python stdlib. No version conflicts, no supply-chain risk.
5. **Composable protocol layers** — Each layer connects via callbacks, making it trivial to swap TCP for serial or inject logging.
6. **CRC-16 table from IEEE 870-5-1** — The exact 256-entry lookup table from the DNP3 spec ensures byte-level compatibility.

## Protocol Reference

### DNP3 Frame Format (Data Link Layer)
```
[0x05][0x64][Length][Control][Dest_L][Dest_H][Src_L][Src_H][CRC_L][CRC_H]
[Data Block 1 (16 bytes)][CRC_L][CRC_H]
...
[Final Block (≤16 bytes)][CRC_L][CRC_H]
```

### Transport Header (1 byte)
```
Bit 7: FIN (Final segment)
Bit 6: FIR (First segment)
Bits 5-0: Sequence number (0-63)
```

### Application Header
```
Request:  [App Control][Function Code][Object Headers...]
Response: [App Control][Function Code][IIN1][IIN2][Object Headers...]
```

## Contributing

We welcome contributions! Please see our [issue templates](.github/ISSUE_TEMPLATE/) for reporting bugs or requesting features.

## License

MIT

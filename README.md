# pydnp3

Pure Python DNP3 (IEEE 1815 / IEC 62351-5) protocol library supporting both **master** and **outstation** roles over TCP/TLS. No C++ dependencies, no native DLLs — just Python.

## Features

- **Complete protocol stack**: Data Link Layer (CRC-16) → Transport Layer (fragment reassembly) → Application Layer (object parsing)
- **Both roles**: Outstation (responds to master polls) and Master (initiates polls and controls)
- **13 object group handlers**: Binary Inputs/Outputs, Analog Inputs/Outputs, Counters, CROB, Events, Time, Class data, IIN
- **TLS 1.2+ support**: Built on Python's `ssl` module (OpenSSL) with certificate-based mutual authentication
- **Asyncio networking**: Non-blocking TCP client/server for high-performance I/O
- **Event-driven**: Change detection with Class 1/2/3 event buffering and unsolicited responses
- **Plugin architecture**: Add new object groups with a simple decorator — no core code changes needed
- **Zero runtime dependencies**: Uses only Python stdlib (asyncio, ssl, struct, enum, dataclasses)
- **Type-safe**: Full type annotations with dataclass slots for performance

## Installation

```bash
pip install -e .

# With development tools
pip install -e ".[dev]"
```

Requires **Python 3.10+**.

## Quick Start

### Outstation (responds to master)

```python
import asyncio
from pydnp3.app.constants import CommandStatus
from pydnp3.objects.types import CROB
from pydnp3.outstation.config import OutstationConfig
from pydnp3.outstation.database import PointDatabase
from pydnp3.outstation.handler import IOutstationHandler
from pydnp3.outstation.session import OutstationSession
from pydnp3.io.tcp_server import TcpServer
from pydnp3.link.layer import LinkLayer
from pydnp3.link.frame import LinkFrame
from pydnp3.transport.layer import TransportLayer
from pydnp3.app.layer import ApplicationLayer


class MyHandler(IOutstationHandler):
    def __init__(self, db):
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
    db.add_analog_input(1, value=100.0)
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

    # Update values over time
    counter = 0
    while True:
        await asyncio.sleep(1.0)
        counter += 1
        db.update_analog_input(0, float(counter))

asyncio.run(main())
```

### Master (polls outstation)

```python
import asyncio
from pydnp3.app.fragment import AppMessage
from pydnp3.objects.types import CROB
from pydnp3.master.config import MasterConfig
from pydnp3.master.handler import IMasterHandler
from pydnp3.master.session import MasterSession
from pydnp3.io.tcp_client import TcpClient
from pydnp3.link.layer import LinkLayer
from pydnp3.link.frame import LinkFrame
from pydnp3.transport.layer import TransportLayer
from pydnp3.app.layer import ApplicationLayer


class MyMasterHandler(IMasterHandler):
    def on_response_received(self, message: AppMessage) -> None:
        for obj in message.objects:
            print(f"Group {obj.header.group}: {len(obj.points)} points")
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

    # Integrity poll
    session.send_integrity_poll()
    await asyncio.sleep(1.0)

    # Direct Operate analog output
    session.send_direct_operate_analog(index=0, value=42.0)
    await asyncio.sleep(1.0)

    # Direct Operate binary output (LATCH_ON)
    crob = CROB(control=0x03, count=1, on_time_ms=0, off_time_ms=0)
    session.send_direct_operate_binary(index=0, crob=crob)
    await asyncio.sleep(1.0)

    await client.close()

asyncio.run(main())
```

### TLS Configuration

```python
from pydnp3.io.tls import TlsConfig, create_tls_context
from pydnp3.io.tcp_client import TcpClient

tls_config = TlsConfig(
    ca_cert_path="/path/to/ca.pem",
    client_cert_path="/path/to/client.pem",
    client_key_path="/path/to/client-key.pem",
    key_password="optional-passphrase",
    verify_hostname=True,
    server_hostname="dnp3.example.com",
)
ssl_ctx = create_tls_context(tls_config)

client = TcpClient(
    host="dnp3.example.com",
    port=20001,
    ssl_context=ssl_ctx,
    server_hostname="dnp3.example.com",
)
```

### Low-Level Protocol Parsing

```python
from pydnp3.link.crc import compute_crc, verify_crc
from pydnp3.link.frame import LinkFrame
from pydnp3.link.layer import LinkLayer
from pydnp3.transport.reassembler import Reassembler
from pydnp3.app.fragment import parse_fragment

# Parse raw bytes from a capture
raw_bytes = b"\x05\x64\x0a\xc4\x01\x00\x0a\x00..."

frames = []
link = LinkLayer(on_frame=frames.append)
link.data_received(raw_bytes)

for frame in frames:
    # Reassemble transport segments
    reassembler = Reassembler()
    fragment = reassembler.add_segment(frame.user_data)
    if fragment:
        msg = parse_fragment(fragment)
        print(f"FC={msg.function.name}, Objects={len(msg.objects)}")
        for obj in msg.objects:
            print(f"  Group {obj.header.group} Var {obj.header.variation}")
```

### In-Process Loopback (Testing)

```python
# See examples/master_outstation_loopback.py for a complete example that
# connects master ↔ outstation in-memory without any network.
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
| `pydnp3.link` | Data link layer: sync detection, CRC-16 DNP3, frame serialization |
| `pydnp3.transport` | Transport layer: fragment reassembly (rx) and segmentation (tx) |
| `pydnp3.app` | Application layer: function codes, qualifiers, object header parsing |
| `pydnp3.objects` | Object group handlers: plugin registry for all DNP3 data types |
| `pydnp3.outstation` | Outstation role: session state machine, point database, events |
| `pydnp3.master` | Master role: polling, control commands, response processing |
| `pydnp3.io` | Network I/O: async TCP client/server, TLS context builder |
| `pydnp3.util` | Utilities: binary read/write buffers, async timers |

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
from pydnp3.objects.base import ObjectGroupHandler
from pydnp3.objects.registry import register_handler
from pydnp3.app.constants import Qualifier
from pydnp3.util.buffer import ReadBuffer, WriteBuffer


@register_handler
class Group110Handler(ObjectGroupHandler):
    """Octet String (Group 110)."""

    @property
    def group(self) -> int:
        return 110

    @property
    def supported_variations(self) -> tuple[int, ...]:
        return (0,)  # Variable length

    def parse(self, variation, qualifier, count, start, buf: ReadBuffer):
        strings = []
        for i in range(count):
            data = buf.read_bytes(variation)  # Variation = string length
            strings.append(data.decode("ascii", errors="replace"))
        return strings

    def serialize(self, variation, qualifier, points, buf: WriteBuffer):
        for s in points:
            buf.write_bytes(s.encode("ascii")[:variation])

    def point_size(self, variation: int) -> int:
        return variation
```

## Supported Function Codes

| Code | Name | Direction |
|------|------|-----------|
| 0x01 | READ | Master → Outstation |
| 0x02 | WRITE | Master → Outstation |
| 0x03 | SELECT | Master → Outstation |
| 0x04 | OPERATE | Master → Outstation |
| 0x05 | DIRECT_OPERATE | Master → Outstation |
| 0x06 | DIRECT_OPERATE_NO_ACK | Master → Outstation |
| 0x07-0x0C | FREEZE variants | Master → Outstation |
| 0x0D | COLD_RESTART | Master → Outstation |
| 0x0E | WARM_RESTART | Master → Outstation |
| 0x14 | ENABLE_UNSOLICITED | Master → Outstation |
| 0x15 | DISABLE_UNSOLICITED | Master → Outstation |
| 0x17 | DELAY_MEASURE | Master → Outstation |
| 0x81 | RESPONSE | Outstation → Master |
| 0x82 | UNSOLICITED_RESPONSE | Outstation → Master |

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=pydnp3 --cov-report=term-missing

# Run specific test module
pytest tests/test_crc.py -v
pytest tests/test_full_stack.py -v
```

## Running Examples

```bash
# In-process loopback (no network needed)
python examples/master_outstation_loopback.py

# Network examples (run in two terminals)
# Terminal 1: Start outstation
python examples/outstation_basic.py

# Terminal 2: Connect master
python examples/master_basic.py
```

## Design Decisions

1. **asyncio over threading**: DNP3 is event-driven; asyncio maps naturally and avoids GIL contention for I/O-bound work.

2. **Plugin registry for object groups**: Each group is a self-contained handler. Adding new groups requires zero changes to core parsing logic.

3. **Zero-copy parsing with `memoryview`**: `ReadBuffer` wraps `struct.unpack_from` over memoryview for efficient parsing without intermediate byte copies.

4. **No runtime dependencies**: The core library uses only Python stdlib. This means no version conflicts, no supply-chain risk, and deployment anywhere Python runs.

5. **Protocol layers as composable classes**: Each layer (Link, Transport, App) is independent and testable. They connect via callbacks, making it trivial to swap TCP for serial or add logging middleware.

6. **CRC-16 table from IEEE 870-5-1**: The exact 256-entry lookup table from the DNP3 specification ensures byte-level compatibility with all compliant implementations.

## Protocol Reference

### DNP3 Frame Format (Data Link Layer)
```
[0x05][0x64][Length][Control][Dest_L][Dest_H][Src_L][Src_H][CRC_L][CRC_H]
[Data Block 1 (16 bytes)][CRC_L][CRC_H]
[Data Block 2 (16 bytes)][CRC_L][CRC_H]
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

## License

MIT

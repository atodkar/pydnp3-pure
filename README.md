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

Requires **Python 3.11+**.

## Quick Start

Use the example scripts as the primary entry point. They are complete, runnable,
and kept current with API changes.

| Scenario | Script |
|----------|--------|
| Master polling an outstation over TCP | [examples/master_basic.py](examples/master_basic.py) |
| Outstation server over TCP | [examples/outstation_basic.py](examples/outstation_basic.py) |
| In-process master/outstation loopback | [examples/master_outstation_loopback.py](examples/master_outstation_loopback.py) |
| Master over TLS | [examples/master_tls.py](examples/master_tls.py) |
| Outstation over TLS | [examples/outstation_tls.py](examples/outstation_tls.py) |
| TLS data exchange helper | [examples/tls_data_exchange.py](examples/tls_data_exchange.py) |

Typical workflow:

1. Start the outstation script.
2. Start the corresponding master script.
3. Observe integrity polls, control commands, and event responses.

For API details, see the core modules:

- [src/pydnp3/master/session.py](src/pydnp3/master/session.py)
- [src/pydnp3/outstation/session.py](src/pydnp3/outstation/session.py)
- [src/pydnp3/io/tls.py](src/pydnp3/io/tls.py)

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

The object model is extensible through handler registration. To add a custom
group:

1. Implement a handler by extending [src/pydnp3/objects/base.py](src/pydnp3/objects/base.py).
2. Register the handler through [src/pydnp3/objects/registry.py](src/pydnp3/objects/registry.py).
3. Implement parse and serialize logic for each supported variation.
4. Add tests under [tests/test_object_groups.py](tests/test_object_groups.py).

Existing handlers in [src/pydnp3/objects](src/pydnp3/objects) are the reference implementation pattern.

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

## Versioning and Release

Releases are designed around GitHub Actions and PyPI Trusted Publishing.

1. Update the version in [pyproject.toml](pyproject.toml).
2. Ensure CI is green in [.github/workflows/ci.yml](.github/workflows/ci.yml).
3. Commit and push to main.
4. Create a GitHub Release with a tag that matches the version (example: v0.1.1).
5. The publish workflow in [.github/workflows/publish.yml](.github/workflows/publish.yml) builds and uploads artifacts to PyPI.

### Local pre-release check

```bash
pip install -e ".[dev]"
ruff check .
mypy
pytest tests/ -v
python -m build
```

### PyPI Trusted Publisher setup (one-time)

Configure a Trusted Publisher in PyPI with:

- Owner: your GitHub user or organization
- Repository: this repository name
- Workflow: publish.yml
- Environment: pypi

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

[LICENSE](LICENSE)

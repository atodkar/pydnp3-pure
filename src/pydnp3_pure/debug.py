"""Built-in debugging and protocol analysis tools.

Provides human-readable logging of DNP3 traffic and Wireshark-friendly
hex dump utilities for protocol troubleshooting.
"""

from __future__ import annotations

import logging
from typing import Callable

from .app.constants import FunctionCode, ObjectGroup
from .app.fragment import AppMessage, ObjectData, parse_fragment


def enable_debug_logging(level: int = logging.DEBUG) -> None:
    """Enable human-readable debug logging for all pydnp3_pure modules.

    Sets up a StreamHandler with a clean format on the 'pydnp3_pure' root logger.
    """
    logger = logging.getLogger("pydnp3_pure")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)


def hex_dump(data: bytes, width: int = 16) -> str:
    """Format bytes as a Wireshark-friendly hex dump with ASCII sidebar.

    Example output:
        0000  05 64 05 c0 01 00 0a 00  e0 a4 c0 c1 01 3c 02 06  .d...........<..
        0010  3c 03 06 3c 04 06                                   <..<..
    """
    lines: list[str] = []
    for offset in range(0, len(data), width):
        chunk = data[offset:offset + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        if width == 16:
            hex_part = hex_part[:23] + "  " + hex_part[24:]
        hex_part = hex_part.ljust(width * 3 + 1)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{offset:04x}  {hex_part} {ascii_part}")
    return "\n".join(lines)


def hex_stream(data: bytes) -> str:
    """Format bytes as a space-separated hex string (copy into Wireshark)."""
    return " ".join(f"{b:02x}" for b in data)


_GROUP_NAMES: dict[int, str] = {
    1: "Binary Inputs",
    2: "Binary Input Events",
    10: "Binary Outputs",
    12: "CROB",
    20: "Counters",
    21: "Frozen Counters",
    30: "Analog Inputs",
    32: "Analog Input Events",
    40: "Analog Output Status",
    41: "Analog Output Command",
    50: "Time and Date",
    60: "Class Objects",
    80: "Internal Indications",
}


def _describe_objects(objects: list[ObjectData]) -> str:
    parts: list[str] = []
    for obj in objects:
        name = _GROUP_NAMES.get(obj.header.group, f"g{obj.header.group}")
        count = len(obj.points)
        parts.append(f"{name}: {count} pts" if count else name)
    return ", ".join(parts) if parts else "empty"


def _describe_message(msg: AppMessage) -> str:
    fc = msg.function
    seq = msg.header.control.seq
    obj_desc = _describe_objects(msg.objects)

    if fc == FunctionCode.READ:
        return f"READ Request [{obj_desc}] seq={seq}"
    elif fc == FunctionCode.RESPONSE:
        return f"RESPONSE [{obj_desc}] seq={seq}"
    elif fc == FunctionCode.UNSOLICITED_RESPONSE:
        return f"UNSOLICITED [{obj_desc}] seq={seq}"
    elif fc == FunctionCode.DIRECT_OPERATE:
        return f"DIRECT OPERATE [{obj_desc}] seq={seq}"
    elif fc == FunctionCode.SELECT:
        return f"SELECT [{obj_desc}] seq={seq}"
    elif fc == FunctionCode.OPERATE:
        return f"OPERATE [{obj_desc}] seq={seq}"
    elif fc == FunctionCode.CONFIRM:
        return f"CONFIRM seq={seq}"
    elif fc == FunctionCode.ENABLE_UNSOLICITED:
        return f"ENABLE UNSOLICITED seq={seq}"
    elif fc == FunctionCode.DISABLE_UNSOLICITED:
        return f"DISABLE UNSOLICITED seq={seq}"
    elif fc == FunctionCode.FREEZE:
        return f"FREEZE seq={seq}"
    elif fc == FunctionCode.COLD_RESTART:
        return f"COLD RESTART seq={seq}"
    elif fc == FunctionCode.WARM_RESTART:
        return f"WARM RESTART seq={seq}"
    else:
        return f"{fc.name} [{obj_desc}] seq={seq}"


class ProtocolLogger:
    """Logs human-readable summaries of DNP3 messages as they flow through the stack.

    Usage:
        from pydnp3_pure.debug import ProtocolLogger

        proto_log = ProtocolLogger()
        # Wrap your session's on_message callback:
        original_on_message = session.on_message
        session.on_message = proto_log.wrap_rx(original_on_message)
    """

    def __init__(self, logger_name: str = "pydnp3_pure.protocol") -> None:
        self._logger = logging.getLogger(logger_name)

    def log_tx(self, fragment: bytes) -> None:
        """Log an outgoing fragment."""
        try:
            msg = parse_fragment(fragment)
            self._logger.info("TX %s", _describe_message(msg))
        except Exception:
            self._logger.debug("TX [%d bytes, parse failed]", len(fragment))

    def log_rx(self, msg: AppMessage) -> None:
        """Log an incoming parsed message."""
        self._logger.info("RX %s", _describe_message(msg))

    def wrap_rx(self, callback: Callable[[AppMessage], None]) -> Callable[[AppMessage], None]:
        """Wrap a message callback to log before passing through."""
        def _wrapped(msg: AppMessage) -> None:
            self.log_rx(msg)
            callback(msg)
        return _wrapped

    def wrap_tx(self, send_fn: Callable[[bytes], None]) -> Callable[[bytes], None]:
        """Wrap a send_fragment function to log before sending."""
        def _wrapped(fragment: bytes) -> None:
            self.log_tx(fragment)
            send_fn(fragment)
        return _wrapped

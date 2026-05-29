"""Read and write buffers for binary protocol parsing using struct."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class ReadBuffer:
    """Zero-copy read buffer wrapping a bytes-like object with a moving offset."""

    __slots__ = ("_data", "_offset", "_length")

    def __init__(self, data: bytes | bytearray | memoryview) -> None:
        self._data = memoryview(data) if not isinstance(data, memoryview) else data
        self._offset = 0
        self._length = len(data)

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def remaining(self) -> int:
        return self._length - self._offset

    def read_uint8(self) -> int:
        val = self._data[self._offset]
        self._offset += 1
        return val

    def read_uint16(self) -> int:
        val: int = struct.unpack_from("<H", self._data, self._offset)[0]
        self._offset += 2
        return val

    def read_int16(self) -> int:
        val: int = struct.unpack_from("<h", self._data, self._offset)[0]
        self._offset += 2
        return val

    def read_uint32(self) -> int:
        val: int = struct.unpack_from("<I", self._data, self._offset)[0]
        self._offset += 4
        return val

    def read_int32(self) -> int:
        val: int = struct.unpack_from("<i", self._data, self._offset)[0]
        self._offset += 4
        return val

    def read_float32(self) -> float:
        val: float = struct.unpack_from("<f", self._data, self._offset)[0]
        self._offset += 4
        return val

    def read_float64(self) -> float:
        val: float = struct.unpack_from("<d", self._data, self._offset)[0]
        self._offset += 8
        return val

    def read_bytes(self, count: int) -> bytes:
        end = self._offset + count
        val = bytes(self._data[self._offset:end])
        self._offset = end
        return val

    def peek_uint8(self, ahead: int = 0) -> int:
        return self._data[self._offset + ahead]

    def skip(self, count: int) -> None:
        self._offset += count

    def seek(self, offset: int) -> None:
        self._offset = offset

    def slice(self, length: int) -> ReadBuffer:
        """Return a new ReadBuffer over the next `length` bytes without advancing."""
        return ReadBuffer(self._data[self._offset : self._offset + length])


class WriteBuffer:
    """Growable write buffer for building binary messages."""

    __slots__ = ("_buf",)

    def __init__(self, capacity: int = 292) -> None:
        self._buf = bytearray(capacity)
        self._buf.clear()

    @property
    def length(self) -> int:
        return len(self._buf)

    def write_uint8(self, val: int) -> None:
        self._buf.append(val & 0xFF)

    def write_uint16(self, val: int) -> None:
        self._buf.extend(struct.pack("<H", val & 0xFFFF))

    def write_int16(self, val: int) -> None:
        self._buf.extend(struct.pack("<h", val))

    def write_uint32(self, val: int) -> None:
        self._buf.extend(struct.pack("<I", val & 0xFFFFFFFF))

    def write_int32(self, val: int) -> None:
        self._buf.extend(struct.pack("<i", val))

    def write_float32(self, val: float) -> None:
        self._buf.extend(struct.pack("<f", val))

    def write_float64(self, val: float) -> None:
        self._buf.extend(struct.pack("<d", val))

    def write_bytes(self, data: bytes | bytearray) -> None:
        self._buf.extend(data)

    def as_bytes(self) -> bytes:
        return bytes(self._buf)

    def as_bytearray(self) -> bytearray:
        return self._buf

    def clear(self) -> None:
        self._buf.clear()

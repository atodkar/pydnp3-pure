"""DNP3 data types used across object group handlers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..app.constants import CommandStatus, ControlCode, PointFlags


@dataclass(slots=True)
class DataPoint:
    """A single DNP3 data point with value, flags, and optional timestamp."""

    index: int
    value: int | float
    flags: int = int(PointFlags.ONLINE)
    timestamp: datetime | None = None


@dataclass(slots=True)
class BinaryPoint:
    """Binary input/output point."""

    index: int
    value: bool
    flags: int = int(PointFlags.ONLINE)
    timestamp: datetime | None = None


@dataclass(slots=True)
class AnalogPoint:
    """Analog input/output point."""

    index: int
    value: int | float
    flags: int = int(PointFlags.ONLINE)
    timestamp: datetime | None = None


@dataclass(slots=True)
class CounterPoint:
    """Counter point (running or frozen)."""

    index: int
    value: int
    flags: int = int(PointFlags.ONLINE)
    timestamp: datetime | None = None


@dataclass(slots=True)
class CROB:
    """Control Relay Output Block for binary output commands."""

    control: int
    count: int
    on_time_ms: int
    off_time_ms: int
    status: int = CommandStatus.SUCCESS

    @property
    def op_type(self) -> int:
        return self.control & int(ControlCode.OP_TYPE_MASK)

    @property
    def is_pulse_on(self) -> bool:
        return self.op_type == ControlCode.PULSE_ON

    @property
    def is_latch_on(self) -> bool:
        return self.op_type == ControlCode.LATCH_ON

    @property
    def is_latch_off(self) -> bool:
        return self.op_type == ControlCode.LATCH_OFF


@dataclass(slots=True)
class AnalogOutputCommand:
    """Analog output command block."""

    index: int
    value: int | float
    status: int = CommandStatus.SUCCESS


@dataclass(slots=True)
class CommandResult:
    """Result of a control command with index and status."""

    index: int
    status: CommandStatus


@dataclass(slots=True)
class DNP3Timestamp:
    """DNP3 48-bit millisecond timestamp (ms since 1970-01-01 00:00:00 UTC)."""

    ms_since_epoch: int

    def to_datetime(self) -> datetime:
        return datetime.utcfromtimestamp(self.ms_since_epoch / 1000.0)

    @classmethod
    def from_datetime(cls, dt: datetime) -> DNP3Timestamp:
        return cls(ms_since_epoch=int(dt.timestamp() * 1000))

    @classmethod
    def now(cls) -> DNP3Timestamp:
        return cls.from_datetime(datetime.utcnow())

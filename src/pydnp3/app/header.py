"""DNP3 Application Layer header dataclasses."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    AC_CON,
    AC_FIN,
    AC_FIR,
    AC_SEQ_MASK,
    AC_UNS,
    FunctionCode,
    IIN1,
    IIN2,
)


@dataclass(slots=True)
class AppControl:
    """Application layer control byte fields."""

    fir: bool
    fin: bool
    con: bool
    uns: bool
    seq: int

    def to_byte(self) -> int:
        val = self.seq & AC_SEQ_MASK
        if self.fir:
            val |= AC_FIR
        if self.fin:
            val |= AC_FIN
        if self.con:
            val |= AC_CON
        if self.uns:
            val |= AC_UNS
        return val

    @classmethod
    def from_byte(cls, byte: int) -> AppControl:
        return cls(
            fir=bool(byte & AC_FIR),
            fin=bool(byte & AC_FIN),
            con=bool(byte & AC_CON),
            uns=bool(byte & AC_UNS),
            seq=byte & AC_SEQ_MASK,
        )

    @classmethod
    def single_fragment(cls, seq: int = 0, con: bool = False, uns: bool = False) -> AppControl:
        """Create control byte for a single-fragment message (FIR+FIN)."""
        return cls(fir=True, fin=True, con=con, uns=uns, seq=seq)


@dataclass(slots=True)
class IIN:
    """Internal Indications (16 bits, split into two bytes in responses)."""

    iin1: IIN1 = IIN1(0)
    iin2: IIN2 = IIN2(0)

    @property
    def device_restart(self) -> bool:
        return bool(self.iin1 & IIN1.DEVICE_RESTART)

    @device_restart.setter
    def device_restart(self, value: bool) -> None:
        if value:
            self.iin1 |= IIN1.DEVICE_RESTART
        else:
            self.iin1 &= ~IIN1.DEVICE_RESTART

    @property
    def need_time(self) -> bool:
        return bool(self.iin1 & IIN1.NEED_TIME)

    @property
    def class_1_events(self) -> bool:
        return bool(self.iin1 & IIN1.CLASS_1_EVENTS)

    @property
    def class_2_events(self) -> bool:
        return bool(self.iin1 & IIN1.CLASS_2_EVENTS)

    @property
    def class_3_events(self) -> bool:
        return bool(self.iin1 & IIN1.CLASS_3_EVENTS)

    def to_bytes(self) -> bytes:
        return bytes([int(self.iin1), int(self.iin2)])

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> IIN:
        return cls(iin1=IIN1(data[0]), iin2=IIN2(data[1]))

    @classmethod
    def startup(cls) -> IIN:
        """Default IIN for a freshly restarted outstation."""
        return cls(iin1=IIN1.DEVICE_RESTART)


@dataclass(slots=True)
class AppHeader:
    """Parsed application layer header."""

    control: AppControl
    function: FunctionCode
    iin: IIN | None = None  # Only present in responses

    @property
    def is_response(self) -> bool:
        return self.function.is_response

    def to_bytes(self) -> bytes:
        buf = bytearray([self.control.to_byte(), int(self.function)])
        if self.iin is not None:
            buf.extend(self.iin.to_bytes())
        return bytes(buf)

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> tuple[AppHeader, int]:
        """Parse header from bytes. Returns (header, bytes_consumed)."""
        control = AppControl.from_byte(data[0])
        function = FunctionCode(data[1])

        if function.is_response:
            iin = IIN.from_bytes(data[2:4])
            return cls(control=control, function=function, iin=iin), 4
        else:
            return cls(control=control, function=function), 2

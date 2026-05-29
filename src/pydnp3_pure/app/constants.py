"""DNP3 Application Layer constants: function codes, qualifiers, IIN bits, object groups."""

from __future__ import annotations

from enum import IntEnum, IntFlag


class FunctionCode(IntEnum):
    """DNP3 application layer function codes."""

    CONFIRM = 0x00
    READ = 0x01
    WRITE = 0x02
    SELECT = 0x03
    OPERATE = 0x04
    DIRECT_OPERATE = 0x05
    DIRECT_OPERATE_NO_ACK = 0x06
    FREEZE = 0x07
    FREEZE_NO_ACK = 0x08
    FREEZE_CLEAR = 0x09
    FREEZE_CLEAR_NO_ACK = 0x0A
    FREEZE_AT_TIME = 0x0B
    FREEZE_AT_TIME_NO_ACK = 0x0C
    COLD_RESTART = 0x0D
    WARM_RESTART = 0x0E
    INITIALIZE_DATA = 0x0F
    INITIALIZE_APPLICATION = 0x10
    START_APPLICATION = 0x11
    STOP_APPLICATION = 0x12
    SAVE_CONFIGURATION = 0x13
    ENABLE_UNSOLICITED = 0x14
    DISABLE_UNSOLICITED = 0x15
    ASSIGN_CLASS = 0x16
    DELAY_MEASURE = 0x17
    RECORD_CURRENT_TIME = 0x18
    OPEN_FILE = 0x19
    CLOSE_FILE = 0x1A
    DELETE_FILE = 0x1B
    GET_FILE_INFO = 0x1C
    AUTHENTICATE_FILE = 0x1D
    ABORT_FILE = 0x1E
    RESPONSE = 0x81
    UNSOLICITED_RESPONSE = 0x82

    @property
    def is_response(self) -> bool:
        return self >= 0x80


class Qualifier(IntEnum):
    """DNP3 object header qualifier codes defining range/index encoding."""

    RANGE_8_START_STOP = 0x00
    RANGE_16_START_STOP = 0x01
    RANGE_32_START_STOP = 0x02
    RANGE_8_ABSOLUTE = 0x03
    RANGE_16_ABSOLUTE = 0x04
    RANGE_32_ABSOLUTE = 0x05
    ALL_POINTS = 0x06
    COUNT_8 = 0x07
    COUNT_16 = 0x08
    COUNT_32 = 0x09
    INDEX_8 = 0x17
    INDEX_16 = 0x28
    INDEX_32 = 0x39
    FREE_FORMAT_8 = 0x1B
    FREE_FORMAT_16 = 0x5B


class IIN1(IntFlag):
    """Internal Indication byte 1 (high byte of IIN word)."""

    ALL_STATIONS = 0x01
    CLASS_1_EVENTS = 0x02
    CLASS_2_EVENTS = 0x04
    CLASS_3_EVENTS = 0x08
    NEED_TIME = 0x10
    LOCAL_CONTROL = 0x20
    DEVICE_TROUBLE = 0x40
    DEVICE_RESTART = 0x80


class IIN2(IntFlag):
    """Internal Indication byte 2 (low byte of IIN word)."""

    NO_FUNC_CODE_SUPPORT = 0x01
    OBJECT_UNKNOWN = 0x02
    PARAMETER_ERROR = 0x04
    EVENT_BUFFER_OVERFLOW = 0x08
    ALREADY_EXECUTING = 0x10
    CONFIG_CORRUPT = 0x20


class ObjectGroup(IntEnum):
    """DNP3 object group numbers."""

    BINARY_INPUT = 1
    BINARY_INPUT_EVENT = 2
    DOUBLE_BIT_INPUT = 3
    DOUBLE_BIT_INPUT_EVENT = 4
    BINARY_OUTPUT = 10
    BINARY_OUTPUT_EVENT = 11
    BINARY_OUTPUT_COMMAND = 12
    BINARY_OUTPUT_COMMAND_EVENT = 13
    COUNTER = 20
    FROZEN_COUNTER = 21
    COUNTER_EVENT = 22
    FROZEN_COUNTER_EVENT = 23
    ANALOG_INPUT = 30
    FROZEN_ANALOG_INPUT = 31
    ANALOG_INPUT_EVENT = 32
    FROZEN_ANALOG_INPUT_EVENT = 33
    ANALOG_INPUT_DEADBAND = 34
    ANALOG_OUTPUT_STATUS = 40
    ANALOG_OUTPUT_COMMAND = 41
    ANALOG_OUTPUT_EVENT = 42
    ANALOG_OUTPUT_COMMAND_EVENT = 43
    TIME_AND_DATE = 50
    TIME_AND_DATE_CTO = 51
    TIME_DELAY = 52
    CLASS_OBJECTS = 60
    FILE_IDENTIFIER = 70
    INTERNAL_INDICATIONS = 80
    OCTET_STRING = 110
    OCTET_STRING_EVENT = 111
    VIRTUAL_TERMINAL_OUTPUT = 112
    VIRTUAL_TERMINAL_EVENT = 113


class PointFlags(IntFlag):
    """DNP3 data quality flags (common to most point types)."""

    ONLINE = 0x01
    RESTART = 0x02
    COMM_LOST = 0x04
    REMOTE_FORCED = 0x08
    LOCAL_FORCED = 0x10
    OVER_RANGE = 0x20      # Analog: value exceeds range
    CHATTER_FILTER = 0x20  # Binary: chattering filter active
    REFERENCE_ERR = 0x40
    DISCONTINUITY = 0x40   # Counter: discontinuity detected
    STATE = 0x80           # Binary: value (ON=1, OFF=0)


class ControlCode(IntFlag):
    """CROB control code fields."""

    NUL = 0x00
    PULSE_ON = 0x01
    PULSE_OFF = 0x02
    LATCH_ON = 0x03
    LATCH_OFF = 0x04
    OP_TYPE_MASK = 0x0F
    QUEUE = 0x10
    CLEAR = 0x20
    PAIRED_CLOSE = 0x40
    PAIRED_TRIP = 0x80


class CommandStatus(IntEnum):
    """Status codes for control operations (CROB, Analog Output)."""

    SUCCESS = 0
    TIMEOUT = 1
    NO_SELECT = 2
    FORMAT_ERROR = 3
    NOT_SUPPORTED = 4
    ALREADY_ACTIVE = 5
    HARDWARE_ERROR = 6
    LOCAL = 7
    TOO_MANY_OPS = 8
    NOT_AUTHORIZED = 9
    AUTOMATION_INHIBIT = 10
    PROCESSING_LIMITED = 11
    OUT_OF_RANGE = 12
    DOWNSTREAM_LOCAL = 13
    ALREADY_COMPLETE = 14
    BLOCKED = 15
    CANCELLED = 16
    BLOCKED_OTHER_MASTER = 17
    DOWNSTREAM_FAIL = 18
    NON_PARTICIPATING = 126
    UNDEFINED = 127


# Application control byte masks
AC_FIR = 0x80
AC_FIN = 0x40
AC_CON = 0x20
AC_UNS = 0x10
AC_SEQ_MASK = 0x0F

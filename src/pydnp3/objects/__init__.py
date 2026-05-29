"""DNP3 Object Group Handlers.

Importing this package triggers registration of all built-in handlers.
"""

from . import (  # noqa: F401
    group1,
    group2,
    group10,
    group12,
    group20,
    group21,
    group30,
    group32,
    group40,
    group41,
    group50,
    group60,
    group80,
)
from .registry import get_handler, is_registered  # noqa: F401
from .types import (  # noqa: F401
    CROB,
    AnalogOutputCommand,
    AnalogPoint,
    BinaryPoint,
    CounterPoint,
    DataPoint,
    DNP3Timestamp,
)

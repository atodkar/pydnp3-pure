"""pydnp3_pure — Pure Python DNP3 protocol library.

Supports both master and outstation roles over TCP/TLS.

Submodules:
    pydnp3_pure.debug — Human-readable protocol logging and hex dump utilities.
    pydnp3_pure.mock  — In-memory mocking for unit testing without hardware.
"""

__version__ = "0.1.0"

from .app.constants import (  # noqa: F401
    CommandStatus,
    ControlCode,
    FunctionCode,
    ObjectGroup,
    PointFlags,
    Qualifier,
)
from .app.fragment import (  # noqa: F401
    AppMessage,
    ObjectData,
    build_request,
    build_response,
    parse_fragment,
)
from .app.header import IIN, AppControl, AppHeader  # noqa: F401
from .link.frame import LinkFrame, LinkHeader  # noqa: F401
from .link.layer import LinkLayer  # noqa: F401
from .objects.types import (  # noqa: F401
    CROB,
    AnalogOutputCommand,
    AnalogPoint,
    BinaryPoint,
    CounterPoint,
    DNP3Timestamp,
)
from .transport.layer import TransportLayer  # noqa: F401
from .transport.reassembler import Reassembler  # noqa: F401
from .transport.segmenter import Segmenter  # noqa: F401

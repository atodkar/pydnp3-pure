"""Built-in mocking utilities for testing DNP3 applications without hardware.

Provides pre-wired master/outstation pairs that communicate in-memory,
letting you unit-test your application logic without TCP connections.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .app.constants import CommandStatus
from .app.fragment import AppMessage, parse_fragment
from .link.frame import LinkFrame
from .link.layer import LinkLayer
from .master.config import MasterConfig
from .master.handler import IMasterHandler
from .master.session import MasterSession
from .objects.types import CROB
from .outstation.config import OutstationConfig
from .outstation.database import PointDatabase
from .outstation.handler import IOutstationHandler
from .outstation.session import OutstationSession
from .transport.reassembler import Reassembler
from .transport.segmenter import Segmenter


class MockChannel:
    """In-memory bidirectional byte pipe replacing TCP/TLS.

    Bytes written to one end appear in the other's receive buffer.
    Call ``deliver()`` to flush queued bytes to the peer.
    """

    def __init__(self) -> None:
        self._buffer: list[bytes] = []
        self._peer: MockChannel | None = None
        self._receive_callback: Callable[[bytes], None] | None = None

    def connect(self, peer: MockChannel) -> None:
        self._peer = peer
        peer._peer = self

    def send(self, data: bytes) -> None:
        if self._peer is not None:
            self._peer._buffer.append(data)

    def set_receive_callback(self, callback: Callable[[bytes], None]) -> None:
        self._receive_callback = callback

    def deliver(self) -> None:
        """Deliver all buffered bytes to the receive callback."""
        for data in self._buffer:
            if self._receive_callback:
                self._receive_callback(data)
        self._buffer.clear()

    @property
    def pending(self) -> int:
        return len(self._buffer)


class _DefaultOutstationHandler(IOutstationHandler):
    """Accepts all commands by default."""

    def __init__(self, db: PointDatabase) -> None:
        self._db = db

    def on_direct_operate_binary(self, index: int, crob: CROB) -> CommandStatus:
        self._db.update_binary_output(index, crob.is_latch_on)
        return CommandStatus.SUCCESS

    def on_direct_operate_analog(self, index: int, value: float) -> CommandStatus:
        self._db.update_analog_output(index, value)
        return CommandStatus.SUCCESS

    def on_select_binary(self, index: int, crob: CROB) -> CommandStatus:
        return CommandStatus.SUCCESS

    def on_operate_binary(self, index: int, crob: CROB) -> CommandStatus:
        self._db.update_binary_output(index, crob.is_latch_on)
        return CommandStatus.SUCCESS

    def on_select_analog(self, index: int, value: float) -> CommandStatus:
        return CommandStatus.SUCCESS

    def on_operate_analog(self, index: int, value: float) -> CommandStatus:
        self._db.update_analog_output(index, value)
        return CommandStatus.SUCCESS


class _DefaultMasterHandler(IMasterHandler):
    """Collects all responses for later assertion."""

    def __init__(self) -> None:
        self.responses: list[AppMessage] = []
        self.unsolicited: list[AppMessage] = []
        self.timeouts: int = 0

    def on_response_received(self, message: AppMessage) -> None:
        self.responses.append(message)

    def on_unsolicited_response(self, message: AppMessage) -> None:
        self.unsolicited.append(message)

    def on_timeout(self) -> None:
        self.timeouts += 1


def _make_send_fn(
    source: int, destination: int, queue: list[bytes], direction: bool
) -> Callable[[bytes], None]:
    def send_fragment(fragment: bytes) -> None:
        seg = Segmenter()
        for segment in seg.segment(fragment):
            frame = LinkFrame.create(
                destination=destination,
                source=source,
                primary=True,
                function=4,
                user_data=segment,
                direction=direction,
            )
            queue.append(frame.serialize())
    return send_fragment


def _deliver(queue: list[bytes]) -> AppMessage | None:
    """Parse queued frames into a single AppMessage (or None)."""
    link = LinkLayer(on_frame=lambda f: None)
    reasm = Reassembler()
    frames: list[LinkFrame] = []
    link = LinkLayer(on_frame=frames.append)
    for data in queue:
        link.data_received(data)
    queue.clear()
    for frame in frames:
        result = reasm.add_segment(frame.user_data)
        if result:
            return parse_fragment(result)
    return None


class MockOutstation:
    """Pre-wired outstation with in-memory transport for testing.

    Attributes:
        session: The underlying OutstationSession.
        database: The PointDatabase (add/update points here).
        handler: The command handler (override for custom behavior).
    """

    def __init__(
        self,
        database: PointDatabase | None = None,
        handler: IOutstationHandler | None = None,
        address: int = 10,
        master_address: int = 1,
    ) -> None:
        self.database = database or PointDatabase()
        self.handler = handler or _DefaultOutstationHandler(self.database)
        self.config = OutstationConfig(address=address, master_address=master_address)
        self._tx_queue: list[bytes] = []
        self.session = OutstationSession(
            config=self.config,
            database=self.database,
            handler=self.handler,
            send_fragment=_make_send_fn(
                address, master_address, self._tx_queue, direction=False
            ),
        )

    def receive(self, raw_frames: list[bytes]) -> None:
        """Feed raw frame bytes into the outstation (simulates network rx)."""
        link = LinkLayer(on_frame=lambda f: None)
        reasm = Reassembler()
        frames: list[LinkFrame] = []
        link = LinkLayer(on_frame=frames.append)
        for data in raw_frames:
            link.data_received(data)
        for frame in frames:
            fragment = reasm.add_segment(frame.user_data)
            if fragment:
                msg = parse_fragment(fragment)
                self.session.on_message(msg)

    def collect_response(self) -> list[bytes]:
        """Collect and clear outgoing frame bytes."""
        result = list(self._tx_queue)
        self._tx_queue.clear()
        return result


class MockMaster:
    """Pre-wired master with in-memory transport for testing.

    Attributes:
        session: The underlying MasterSession.
        handler: The response handler (check handler.responses).
    """

    def __init__(
        self,
        handler: _DefaultMasterHandler | None = None,
        address: int = 1,
        outstation_address: int = 10,
    ) -> None:
        self.handler = handler or _DefaultMasterHandler()
        self.config = MasterConfig(address=address, outstation_address=outstation_address)
        self._tx_queue: list[bytes] = []
        self.session = MasterSession(
            config=self.config,
            handler=self.handler,
            send_fragment=_make_send_fn(
                address, outstation_address, self._tx_queue, direction=True
            ),
        )

    def receive(self, raw_frames: list[bytes]) -> None:
        """Feed raw frame bytes into the master (simulates network rx)."""
        link = LinkLayer(on_frame=lambda f: None)
        reasm = Reassembler()
        frames: list[LinkFrame] = []
        link = LinkLayer(on_frame=frames.append)
        for data in raw_frames:
            link.data_received(data)
        for frame in frames:
            fragment = reasm.add_segment(frame.user_data)
            if fragment:
                msg = parse_fragment(fragment)
                self.session.on_message(msg)

    def collect_request(self) -> list[bytes]:
        """Collect and clear outgoing frame bytes."""
        result = list(self._tx_queue)
        self._tx_queue.clear()
        return result


@dataclass
class LoopbackPair:
    """A connected master+outstation pair for unit testing.

    Usage:
        pair = create_loopback_pair()
        pair.master.session.send_integrity_poll()
        pair.exchange()  # Delivers request and response
        assert len(pair.master.handler.responses) == 1
    """

    master: MockMaster
    outstation: MockOutstation

    def exchange(self) -> None:
        """Deliver master→outstation request, then outstation→master response."""
        request_frames = self.master.collect_request()
        if request_frames:
            self.outstation.receive(request_frames)
        response_frames = self.outstation.collect_response()
        if response_frames:
            self.master.receive(response_frames)


def create_loopback_pair(
    database: PointDatabase | None = None,
    outstation_handler: IOutstationHandler | None = None,
    master_address: int = 1,
    outstation_address: int = 10,
) -> LoopbackPair:
    """Create a connected master+outstation pair for unit testing.

    Returns a LoopbackPair with pre-wired in-memory transport.
    Call ``pair.exchange()`` after sending commands to deliver messages.

    Example:
        pair = create_loopback_pair()
        pair.outstation.database.add_analog_input(0, value=42.0)
        pair.master.session.send_integrity_poll()
        pair.exchange()
        response = pair.master.handler.responses[0]
        assert response.objects[0].points[0].value == 42.0
    """
    db = database or PointDatabase()
    outstation = MockOutstation(
        database=db,
        handler=outstation_handler,
        address=outstation_address,
        master_address=master_address,
    )
    master = MockMaster(
        address=master_address,
        outstation_address=outstation_address,
    )
    return LoopbackPair(master=master, outstation=outstation)

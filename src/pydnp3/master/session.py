"""Master station session - builds and sends requests, processes responses."""

from __future__ import annotations

import logging
from typing import Callable

from ..app.constants import CommandStatus, FunctionCode, Qualifier
from ..app.fragment import AppMessage, ObjectData, build_request, parse_fragment
from ..app.header import AppControl
from ..app.object_header import ObjectHeader
from ..objects.types import AnalogOutputCommand, CROB
from .config import MasterConfig
from .handler import IMasterHandler

logger = logging.getLogger(__name__)


class MasterSession:
    """DNP3 master session that initiates polls and commands."""

    def __init__(
        self,
        config: MasterConfig,
        handler: IMasterHandler,
        send_fragment: Callable[[bytes], None],
    ) -> None:
        self._config = config
        self._handler = handler
        self._send = send_fragment
        self._seq = 0

    def _next_seq(self) -> int:
        seq = self._seq
        self._seq = (self._seq + 1) & 0x0F
        return seq

    # --- Polling ---

    def send_integrity_poll(self) -> None:
        """Send a Class 0 (static data) read request."""
        obj = ObjectData(
            header=ObjectHeader(group=60, variation=1, qualifier=Qualifier.ALL_POINTS,
                                start=0, stop=0, count=0)
        )
        data = build_request(FunctionCode.READ, seq=self._next_seq(), objects=[obj])
        self._send(data)

    def send_event_poll(self, classes: tuple[int, ...] = (1, 2, 3)) -> None:
        """Send a Class 1/2/3 event read request."""
        objects = [
            ObjectData(
                header=ObjectHeader(group=60, variation=c + 1, qualifier=Qualifier.ALL_POINTS,
                                    start=0, stop=0, count=0)
            )
            for c in classes
        ]
        data = build_request(FunctionCode.READ, seq=self._next_seq(), objects=objects)
        self._send(data)

    def send_class_poll(self, class_num: int) -> None:
        """Send a single class read (0=static, 1-3=events)."""
        obj = ObjectData(
            header=ObjectHeader(group=60, variation=class_num + 1, qualifier=Qualifier.ALL_POINTS,
                                start=0, stop=0, count=0)
        )
        data = build_request(FunctionCode.READ, seq=self._next_seq(), objects=[obj])
        self._send(data)

    # --- Commands ---

    def send_direct_operate_binary(self, index: int, crob: CROB) -> None:
        """Send a Direct Operate for a binary output."""
        obj = ObjectData(
            header=ObjectHeader(group=12, variation=1, qualifier=Qualifier.INDEX_8,
                                start=0, stop=0, count=1),
            points=[(index, crob)],
        )
        data = build_request(FunctionCode.DIRECT_OPERATE, seq=self._next_seq(), objects=[obj])
        self._send(data)

    def send_direct_operate_analog(self, index: int, value: float, variation: int = 3) -> None:
        """Send a Direct Operate for an analog output."""
        cmd = AnalogOutputCommand(index=index, value=value, status=0)
        obj = ObjectData(
            header=ObjectHeader(group=41, variation=variation, qualifier=Qualifier.INDEX_8,
                                start=0, stop=0, count=1),
            points=[cmd],
        )
        data = build_request(FunctionCode.DIRECT_OPERATE, seq=self._next_seq(), objects=[obj])
        self._send(data)

    def send_select_binary(self, index: int, crob: CROB) -> None:
        """Send SELECT for binary output (first pass of SBO)."""
        obj = ObjectData(
            header=ObjectHeader(group=12, variation=1, qualifier=Qualifier.INDEX_8,
                                start=0, stop=0, count=1),
            points=[(index, crob)],
        )
        data = build_request(FunctionCode.SELECT, seq=self._next_seq(), objects=[obj])
        self._send(data)

    def send_operate_binary(self, index: int, crob: CROB) -> None:
        """Send OPERATE for binary output (second pass of SBO)."""
        obj = ObjectData(
            header=ObjectHeader(group=12, variation=1, qualifier=Qualifier.INDEX_8,
                                start=0, stop=0, count=1),
            points=[(index, crob)],
        )
        data = build_request(FunctionCode.OPERATE, seq=self._next_seq(), objects=[obj])
        self._send(data)

    def send_enable_unsolicited(self) -> None:
        """Enable unsolicited responses for all event classes."""
        objects = [
            ObjectData(header=ObjectHeader(group=60, variation=v, qualifier=Qualifier.ALL_POINTS,
                                           start=0, stop=0, count=0))
            for v in (2, 3, 4)
        ]
        data = build_request(FunctionCode.ENABLE_UNSOLICITED, seq=self._next_seq(), objects=objects)
        self._send(data)

    def send_disable_unsolicited(self) -> None:
        """Disable unsolicited responses."""
        objects = [
            ObjectData(header=ObjectHeader(group=60, variation=v, qualifier=Qualifier.ALL_POINTS,
                                           start=0, stop=0, count=0))
            for v in (2, 3, 4)
        ]
        data = build_request(FunctionCode.DISABLE_UNSOLICITED, seq=self._next_seq(), objects=objects)
        self._send(data)

    def send_confirm(self, seq: int) -> None:
        """Send application-layer confirm."""
        data = build_request(FunctionCode.CONFIRM, seq=seq, objects=[])
        self._send(data)

    # --- Response processing ---

    def on_message(self, message: AppMessage) -> None:
        """Process a response from the outstation."""
        if message.header.control.uns:
            self._handler.on_unsolicited_response(message)
            if message.header.control.con:
                self.send_confirm(message.header.control.seq)
        else:
            self._handler.on_response_received(message)

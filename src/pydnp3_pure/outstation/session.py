"""Outstation session state machine."""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Callable

from ..app.constants import CommandStatus, FunctionCode, Qualifier
from ..app.fragment import AppMessage, ObjectData, build_response, parse_fragment
from ..app.header import IIN
from ..app.object_header import ObjectHeader
from ..objects.types import AnalogOutputCommand, AnalogPoint, BinaryPoint, CounterPoint, CROB
from .config import OutstationConfig
from .database import PointDatabase
from .event_buffer import Event, EventBuffer
from .handler import IOutstationHandler

logger = logging.getLogger(__name__)


class _State(Enum):
    IDLE = auto()
    WAIT_CONFIRM = auto()


class OutstationSession:
    """DNP3 outstation session state machine.

    Processes incoming requests and generates responses.
    """

    def __init__(
        self,
        config: OutstationConfig,
        database: PointDatabase,
        handler: IOutstationHandler,
        send_fragment: Callable[[bytes], None],
    ) -> None:
        self._config = config
        self._db = database
        self._handler = handler
        self._send = send_fragment
        self._events = EventBuffer(
            class_1_max=config.class_1_events_max,
            class_2_max=config.class_2_events_max,
            class_3_max=config.class_3_events_max,
        )
        self._iin = IIN.startup()
        self._state = _State.IDLE
        self._seq = 0
        self._unsolicited_enabled = False

        # Register database event callback
        database._on_event = self._on_database_event

    @property
    def iin(self) -> IIN:
        return self._iin

    def clear_restart_iin(self) -> None:
        self._iin.device_restart = False

    def on_message(self, message: AppMessage) -> None:
        """Process an incoming application-layer message from the master."""
        fc = message.function

        if fc == FunctionCode.CONFIRM:
            self._handle_confirm(message)
            return

        if fc == FunctionCode.READ:
            self._handle_read(message)
        elif fc == FunctionCode.WRITE:
            self._handle_write(message)
        elif fc == FunctionCode.DIRECT_OPERATE:
            self._handle_direct_operate(message)
        elif fc == FunctionCode.DIRECT_OPERATE_NO_ACK:
            self._handle_direct_operate(message, no_ack=True)
        elif fc == FunctionCode.SELECT:
            self._handle_select(message)
        elif fc == FunctionCode.OPERATE:
            self._handle_operate(message)
        elif fc == FunctionCode.ENABLE_UNSOLICITED:
            self._handle_enable_unsolicited(message)
        elif fc == FunctionCode.DISABLE_UNSOLICITED:
            self._handle_disable_unsolicited(message)
        elif fc == FunctionCode.DELAY_MEASURE:
            self._handle_delay_measure(message)
        elif fc == FunctionCode.COLD_RESTART:
            self._handle_restart(message, cold=True)
        elif fc == FunctionCode.WARM_RESTART:
            self._handle_restart(message, cold=False)
        elif fc == FunctionCode.FREEZE:
            self._handle_freeze(message)
        else:
            self._send_error_response(message)

    def _handle_read(self, message: AppMessage) -> None:
        """Respond to a READ request."""
        response_objects: list[ObjectData] = []

        for obj in message.objects:
            group = obj.header.group
            var = obj.header.variation

            if group == 60:
                # Class read
                if var == 1:
                    response_objects.extend(self._read_class0())
                elif var in (2, 3, 4):
                    response_objects.extend(self._read_events(var - 1))
            elif group == 1:
                response_objects.append(self._read_binary_inputs(obj.header))
            elif group == 10:
                response_objects.append(self._read_binary_outputs(obj.header))
            elif group == 30:
                response_objects.append(self._read_analog_inputs(obj.header))
            elif group == 40:
                response_objects.append(self._read_analog_outputs(obj.header))
            elif group == 20:
                response_objects.append(self._read_counters(obj.header))
            elif group == 21:
                response_objects.append(self._read_frozen_counters(obj.header))

        self._update_iin_event_flags()
        seq = message.header.control.seq
        response = build_response(seq=seq, iin=self._iin, objects=response_objects)
        self._send(response)

    def _handle_write(self, message: AppMessage) -> None:
        """Handle WRITE request (typically for IIN clear or time sync)."""
        for obj in message.objects:
            if obj.header.group == 80 and obj.header.variation == 1:
                # Writing IIN bit 7 (restart) to 0 clears it
                if obj.points and not obj.points[0][1]:
                    self._iin.device_restart = False

        seq = message.header.control.seq
        response = build_response(seq=seq, iin=self._iin, objects=[])
        self._send(response)

    def _handle_direct_operate(self, message: AppMessage, no_ack: bool = False) -> None:
        """Handle Direct Operate commands."""
        response_objects: list[ObjectData] = []

        for obj in message.objects:
            if obj.header.group == 12:
                results = self._process_binary_controls(obj, direct=True)
                response_objects.append(results)
            elif obj.header.group == 41:
                results = self._process_analog_controls(obj, direct=True)
                response_objects.append(results)

        if not no_ack:
            seq = message.header.control.seq
            response = build_response(seq=seq, iin=self._iin, objects=response_objects)
            self._send(response)

    def _handle_select(self, message: AppMessage) -> None:
        """Handle SELECT (first pass of SBO)."""
        response_objects: list[ObjectData] = []

        for obj in message.objects:
            if obj.header.group == 12:
                results = self._process_binary_controls(obj, direct=False, select=True)
                response_objects.append(results)
            elif obj.header.group == 41:
                results = self._process_analog_controls(obj, direct=False, select=True)
                response_objects.append(results)

        seq = message.header.control.seq
        response = build_response(seq=seq, iin=self._iin, objects=response_objects)
        self._send(response)

    def _handle_operate(self, message: AppMessage) -> None:
        """Handle OPERATE (second pass of SBO)."""
        response_objects: list[ObjectData] = []

        for obj in message.objects:
            if obj.header.group == 12:
                results = self._process_binary_controls(obj, direct=False, select=False)
                response_objects.append(results)
            elif obj.header.group == 41:
                results = self._process_analog_controls(obj, direct=False, select=False)
                response_objects.append(results)

        seq = message.header.control.seq
        response = build_response(seq=seq, iin=self._iin, objects=response_objects)
        self._send(response)

    def _handle_enable_unsolicited(self, message: AppMessage) -> None:
        self._unsolicited_enabled = True
        seq = message.header.control.seq
        response = build_response(seq=seq, iin=self._iin, objects=[])
        self._send(response)

    def _handle_disable_unsolicited(self, message: AppMessage) -> None:
        self._unsolicited_enabled = False
        seq = message.header.control.seq
        response = build_response(seq=seq, iin=self._iin, objects=[])
        self._send(response)

    def _handle_delay_measure(self, message: AppMessage) -> None:
        """Respond with time delay (0 ms for simplicity)."""
        from ..objects.types import DNP3Timestamp
        obj = ObjectData(
            header=ObjectHeader(group=52, variation=2, qualifier=Qualifier.COUNT_8, start=0, stop=0, count=1),
            points=[],
        )
        seq = message.header.control.seq
        response = build_response(seq=seq, iin=self._iin, objects=[obj])
        self._send(response)

    def _handle_restart(self, message: AppMessage, cold: bool) -> None:
        if cold:
            delay = self._handler.on_cold_restart()
        else:
            delay = self._handler.on_warm_restart()
        seq = message.header.control.seq
        response = build_response(seq=seq, iin=self._iin, objects=[])
        self._send(response)

    def _handle_freeze(self, message: AppMessage) -> None:
        self._handler.on_freeze()
        seq = message.header.control.seq
        response = build_response(seq=seq, iin=self._iin, objects=[])
        self._send(response)

    def _handle_confirm(self, message: AppMessage) -> None:
        if self._state == _State.WAIT_CONFIRM:
            self._events.confirm_all()
            self._state = _State.IDLE

    def _send_error_response(self, message: AppMessage) -> None:
        from ..app.constants import IIN2
        iin = IIN(iin1=self._iin.iin1, iin2=self._iin.iin2 | IIN2.NO_FUNC_CODE_SUPPORT)
        seq = message.header.control.seq
        response = build_response(seq=seq, iin=iin, objects=[])
        self._send(response)

    # --- Read helpers ---

    def _read_class0(self) -> list[ObjectData]:
        """Read all static data (Class 0)."""
        objects: list[ObjectData] = []

        bis = self._db.get_binary_inputs()
        if bis:
            objects.append(ObjectData(
                header=ObjectHeader(group=1, variation=2, qualifier=Qualifier.RANGE_8_START_STOP,
                                    start=bis[0].index, stop=bis[-1].index, count=len(bis)),
                points=bis,
            ))

        bos = self._db.get_binary_outputs()
        if bos:
            objects.append(ObjectData(
                header=ObjectHeader(group=10, variation=2, qualifier=Qualifier.RANGE_8_START_STOP,
                                    start=bos[0].index, stop=bos[-1].index, count=len(bos)),
                points=bos,
            ))

        ais = self._db.get_analog_inputs()
        if ais:
            objects.append(ObjectData(
                header=ObjectHeader(group=30, variation=5, qualifier=Qualifier.RANGE_8_START_STOP,
                                    start=ais[0].index, stop=ais[-1].index, count=len(ais)),
                points=ais,
            ))

        aos = self._db.get_analog_outputs()
        if aos:
            objects.append(ObjectData(
                header=ObjectHeader(group=40, variation=3, qualifier=Qualifier.RANGE_8_START_STOP,
                                    start=aos[0].index, stop=aos[-1].index, count=len(aos)),
                points=aos,
            ))

        ctrs = self._db.get_counters()
        if ctrs:
            objects.append(ObjectData(
                header=ObjectHeader(group=20, variation=1, qualifier=Qualifier.RANGE_8_START_STOP,
                                    start=ctrs[0].index, stop=ctrs[-1].index, count=len(ctrs)),
                points=ctrs,
            ))

        fctrs = self._db.get_frozen_counters()
        if fctrs:
            objects.append(ObjectData(
                header=ObjectHeader(group=21, variation=1, qualifier=Qualifier.RANGE_8_START_STOP,
                                    start=fctrs[0].index, stop=fctrs[-1].index, count=len(fctrs)),
                points=fctrs,
            ))

        return objects

    def _read_events(self, event_class: int) -> list[ObjectData]:
        """Read events from the specified class."""
        events = self._events.get_class_events(event_class)
        if not events:
            return []

        objects: list[ObjectData] = []
        # Group events by type for proper object header generation
        ai_events = [e for e in events if e.group == 30]
        bi_events = [e for e in events if e.group == 1]

        if ai_events:
            points = [AnalogPoint(index=e.index, value=e.value, flags=e.flags) for e in ai_events]
            objects.append(ObjectData(
                header=ObjectHeader(group=32, variation=2, qualifier=Qualifier.INDEX_8,
                                    start=0, stop=0, count=len(points)),
                points=points,
            ))

        if bi_events:
            points_b = [BinaryPoint(index=e.index, value=e.value, flags=e.flags) for e in bi_events]
            objects.append(ObjectData(
                header=ObjectHeader(group=2, variation=1, qualifier=Qualifier.INDEX_8,
                                    start=0, stop=0, count=len(points_b)),
                points=points_b,
            ))

        return objects

    def _read_binary_inputs(self, header: ObjectHeader) -> ObjectData:
        points = self._db.get_binary_inputs(
            start=header.start if header.qualifier != Qualifier.ALL_POINTS else None,
            stop=header.stop if header.qualifier != Qualifier.ALL_POINTS else None,
        )
        return ObjectData(
            header=ObjectHeader(group=1, variation=2, qualifier=Qualifier.RANGE_8_START_STOP,
                                start=points[0].index if points else 0,
                                stop=points[-1].index if points else 0,
                                count=len(points)),
            points=points,
        )

    def _read_binary_outputs(self, header: ObjectHeader) -> ObjectData:
        points = self._db.get_binary_outputs(
            start=header.start if header.qualifier != Qualifier.ALL_POINTS else None,
            stop=header.stop if header.qualifier != Qualifier.ALL_POINTS else None,
        )
        return ObjectData(
            header=ObjectHeader(group=10, variation=2, qualifier=Qualifier.RANGE_8_START_STOP,
                                start=points[0].index if points else 0,
                                stop=points[-1].index if points else 0,
                                count=len(points)),
            points=points,
        )

    def _read_analog_inputs(self, header: ObjectHeader) -> ObjectData:
        points = self._db.get_analog_inputs(
            start=header.start if header.qualifier != Qualifier.ALL_POINTS else None,
            stop=header.stop if header.qualifier != Qualifier.ALL_POINTS else None,
        )
        return ObjectData(
            header=ObjectHeader(group=30, variation=5, qualifier=Qualifier.RANGE_8_START_STOP,
                                start=points[0].index if points else 0,
                                stop=points[-1].index if points else 0,
                                count=len(points)),
            points=points,
        )

    def _read_analog_outputs(self, header: ObjectHeader) -> ObjectData:
        points = self._db.get_analog_outputs(
            start=header.start if header.qualifier != Qualifier.ALL_POINTS else None,
            stop=header.stop if header.qualifier != Qualifier.ALL_POINTS else None,
        )
        return ObjectData(
            header=ObjectHeader(group=40, variation=3, qualifier=Qualifier.RANGE_8_START_STOP,
                                start=points[0].index if points else 0,
                                stop=points[-1].index if points else 0,
                                count=len(points)),
            points=points,
        )

    def _read_counters(self, header: ObjectHeader) -> ObjectData:
        points = self._db.get_counters(
            start=header.start if header.qualifier != Qualifier.ALL_POINTS else None,
            stop=header.stop if header.qualifier != Qualifier.ALL_POINTS else None,
        )
        return ObjectData(
            header=ObjectHeader(group=20, variation=1, qualifier=Qualifier.RANGE_8_START_STOP,
                                start=points[0].index if points else 0,
                                stop=points[-1].index if points else 0,
                                count=len(points)),
            points=points,
        )

    def _read_frozen_counters(self, header: ObjectHeader) -> ObjectData:
        points = self._db.get_frozen_counters(
            start=header.start if header.qualifier != Qualifier.ALL_POINTS else None,
            stop=header.stop if header.qualifier != Qualifier.ALL_POINTS else None,
        )
        return ObjectData(
            header=ObjectHeader(group=21, variation=1, qualifier=Qualifier.RANGE_8_START_STOP,
                                start=points[0].index if points else 0,
                                stop=points[-1].index if points else 0,
                                count=len(points)),
            points=points,
        )

    # --- Control helpers ---

    def _process_binary_controls(self, obj: ObjectData, direct: bool, select: bool = False) -> ObjectData:
        results: list[tuple[int, CROB]] = []
        for idx, crob in obj.points:
            if direct:
                status = self._handler.on_direct_operate_binary(idx, crob)
            elif select:
                status = self._handler.on_select_binary(idx, crob)
            else:
                status = self._handler.on_operate_binary(idx, crob)
            results.append((idx, CROB(
                control=crob.control, count=crob.count,
                on_time_ms=crob.on_time_ms, off_time_ms=crob.off_time_ms,
                status=int(status),
            )))
        return ObjectData(header=obj.header, points=results)

    def _process_analog_controls(self, obj: ObjectData, direct: bool, select: bool = False) -> ObjectData:
        results: list[AnalogOutputCommand] = []
        for cmd in obj.points:
            if direct:
                status = self._handler.on_direct_operate_analog(cmd.index, float(cmd.value))
            elif select:
                status = self._handler.on_select_analog(cmd.index, float(cmd.value))
            else:
                status = self._handler.on_operate_analog(cmd.index, float(cmd.value))
            results.append(AnalogOutputCommand(index=cmd.index, value=cmd.value, status=int(status)))
        return ObjectData(header=obj.header, points=results)

    # --- Event and IIN management ---

    def _on_database_event(self, group: int, index: int, point: object) -> None:
        """Called by the database when a value changes."""
        if isinstance(point, AnalogPoint):
            config = self._db._ai_config.get(index)
            event_class = config.event_class if config else 1
            self._events.add(Event(
                group=group, variation=2, index=index,
                value=point.value, flags=point.flags, event_class=event_class,
            ))
        elif isinstance(point, BinaryPoint):
            config = self._db._bi_config.get(index)
            event_class = config.event_class if config else 1
            self._events.add(Event(
                group=group, variation=1, index=index,
                value=point.value, flags=point.flags, event_class=event_class,
            ))

    def _update_iin_event_flags(self) -> None:
        from ..app.constants import IIN1
        if self._events.has_class_1:
            self._iin.iin1 |= IIN1.CLASS_1_EVENTS
        else:
            self._iin.iin1 &= ~IIN1.CLASS_1_EVENTS
        if self._events.has_class_2:
            self._iin.iin1 |= IIN1.CLASS_2_EVENTS
        else:
            self._iin.iin1 &= ~IIN1.CLASS_2_EVENTS
        if self._events.has_class_3:
            self._iin.iin1 |= IIN1.CLASS_3_EVENTS
        else:
            self._iin.iin1 &= ~IIN1.CLASS_3_EVENTS

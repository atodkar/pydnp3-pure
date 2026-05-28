"""Outstation point database with change detection."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable

from ..app.constants import PointFlags
from ..objects.types import AnalogPoint, BinaryPoint, CounterPoint


@dataclass
class PointConfig:
    """Configuration for a point in the database."""

    event_class: int = 1  # 1, 2, or 3
    deadband: float = 0.0  # For analog inputs (change threshold)
    default_variation: int = 0  # 0 = use handler default


class PointDatabase:
    """Thread-safe in-memory database for all DNP3 point types.

    Supports change detection for event generation.
    """

    def __init__(self, on_event: Callable[[int, int, object], None] | None = None) -> None:
        """
        Args:
            on_event: Callback(group, index, point) fired when a value changes.
        """
        self._lock = threading.Lock()
        self._on_event = on_event

        self._binary_inputs: dict[int, BinaryPoint] = {}
        self._binary_outputs: dict[int, BinaryPoint] = {}
        self._analog_inputs: dict[int, AnalogPoint] = {}
        self._analog_outputs: dict[int, AnalogPoint] = {}
        self._counters: dict[int, CounterPoint] = {}
        self._frozen_counters: dict[int, CounterPoint] = {}

        self._bi_config: dict[int, PointConfig] = {}
        self._ai_config: dict[int, PointConfig] = {}
        self._bo_config: dict[int, PointConfig] = {}
        self._counter_config: dict[int, PointConfig] = {}

    # --- Initialization ---

    def add_binary_input(self, index: int, value: bool = False, config: PointConfig | None = None) -> None:
        with self._lock:
            self._binary_inputs[index] = BinaryPoint(index=index, value=value)
            self._bi_config[index] = config or PointConfig()

    def add_binary_output(self, index: int, value: bool = False, config: PointConfig | None = None) -> None:
        with self._lock:
            self._binary_outputs[index] = BinaryPoint(index=index, value=value)
            self._bo_config[index] = config or PointConfig(event_class=2)

    def add_analog_input(self, index: int, value: float = 0.0, config: PointConfig | None = None) -> None:
        with self._lock:
            self._analog_inputs[index] = AnalogPoint(index=index, value=value)
            self._ai_config[index] = config or PointConfig()

    def add_analog_output(self, index: int, value: float = 0.0, config: PointConfig | None = None) -> None:
        with self._lock:
            self._analog_outputs[index] = AnalogPoint(index=index, value=value)

    def add_counter(self, index: int, value: int = 0, config: PointConfig | None = None) -> None:
        with self._lock:
            self._counters[index] = CounterPoint(index=index, value=value)
            self._frozen_counters[index] = CounterPoint(index=index, value=0)
            self._counter_config[index] = config or PointConfig(event_class=2)

    # --- Updates (trigger events on change) ---

    def update_binary_input(self, index: int, value: bool, flags: int = int(PointFlags.ONLINE)) -> None:
        with self._lock:
            point = self._binary_inputs.get(index)
            if point is None:
                return
            if point.value != value or point.flags != flags:
                point.value = value
                point.flags = flags
                if self._on_event:
                    self._on_event(1, index, BinaryPoint(index=index, value=value, flags=flags))

    def update_binary_output(self, index: int, value: bool, flags: int = int(PointFlags.ONLINE)) -> None:
        with self._lock:
            point = self._binary_outputs.get(index)
            if point is None:
                return
            point.value = value
            point.flags = flags

    def update_analog_input(self, index: int, value: float, flags: int = int(PointFlags.ONLINE)) -> None:
        with self._lock:
            point = self._analog_inputs.get(index)
            if point is None:
                return
            config = self._ai_config.get(index)
            deadband = config.deadband if config else 0.0
            if abs(point.value - value) > deadband or point.flags != flags:
                point.value = value
                point.flags = flags
                if self._on_event:
                    self._on_event(30, index, AnalogPoint(index=index, value=value, flags=flags))

    def update_analog_output(self, index: int, value: float, flags: int = int(PointFlags.ONLINE)) -> None:
        with self._lock:
            point = self._analog_outputs.get(index)
            if point is None:
                return
            point.value = value
            point.flags = flags

    def update_counter(self, index: int, value: int, flags: int = int(PointFlags.ONLINE)) -> None:
        with self._lock:
            point = self._counters.get(index)
            if point is None:
                return
            point.value = value
            point.flags = flags

    def freeze_counter(self, index: int) -> None:
        with self._lock:
            counter = self._counters.get(index)
            frozen = self._frozen_counters.get(index)
            if counter and frozen:
                frozen.value = counter.value
                frozen.flags = counter.flags

    # --- Reads (for responding to master polls) ---

    def get_binary_inputs(self, start: int | None = None, stop: int | None = None) -> list[BinaryPoint]:
        with self._lock:
            return self._get_range(self._binary_inputs, start, stop)

    def get_binary_outputs(self, start: int | None = None, stop: int | None = None) -> list[BinaryPoint]:
        with self._lock:
            return self._get_range(self._binary_outputs, start, stop)

    def get_analog_inputs(self, start: int | None = None, stop: int | None = None) -> list[AnalogPoint]:
        with self._lock:
            return self._get_range(self._analog_inputs, start, stop)

    def get_analog_outputs(self, start: int | None = None, stop: int | None = None) -> list[AnalogPoint]:
        with self._lock:
            return self._get_range(self._analog_outputs, start, stop)

    def get_counters(self, start: int | None = None, stop: int | None = None) -> list[CounterPoint]:
        with self._lock:
            return self._get_range(self._counters, start, stop)

    def get_frozen_counters(self, start: int | None = None, stop: int | None = None) -> list[CounterPoint]:
        with self._lock:
            return self._get_range(self._frozen_counters, start, stop)

    @property
    def binary_input_count(self) -> int:
        return len(self._binary_inputs)

    @property
    def binary_output_count(self) -> int:
        return len(self._binary_outputs)

    @property
    def analog_input_count(self) -> int:
        return len(self._analog_inputs)

    @property
    def analog_output_count(self) -> int:
        return len(self._analog_outputs)

    @property
    def counter_count(self) -> int:
        return len(self._counters)

    def _get_range(self, store: dict, start: int | None, stop: int | None) -> list:
        if start is None and stop is None:
            return list(store.values())
        points = []
        for idx in sorted(store.keys()):
            if start is not None and idx < start:
                continue
            if stop is not None and idx > stop:
                break
            points.append(store[idx])
        return points

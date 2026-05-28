"""Outstation configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OutstationConfig:
    """Configuration for a DNP3 outstation."""

    address: int = 1
    master_address: int = 0
    max_fragment_size: int = 2048
    confirm_timeout_seconds: float = 5.0
    unsolicited_retry_seconds: float = 10.0
    select_timeout_seconds: float = 10.0
    max_controls_per_request: int = 16
    enable_unsolicited: bool = True
    class_1_events_max: int = 1000
    class_2_events_max: int = 1000
    class_3_events_max: int = 1000

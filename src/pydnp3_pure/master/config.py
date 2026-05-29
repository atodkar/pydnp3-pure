"""Master station configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MasterConfig:
    """Configuration for a DNP3 master station."""

    address: int = 0
    outstation_address: int = 1
    response_timeout_seconds: float = 5.0
    integrity_poll_interval_seconds: float = 60.0
    event_poll_interval_seconds: float = 5.0
    enable_unsolicited: bool = True
    max_retries: int = 3

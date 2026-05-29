"""Outstation handler callback interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..app.constants import CommandStatus
from ..objects.types import CROB


class IOutstationHandler(ABC):
    """Callback interface for outstation application logic.

    Implement this to define how your outstation responds to master commands.
    """

    @abstractmethod
    def on_direct_operate_binary(self, index: int, crob: CROB) -> CommandStatus:
        """Handle a Direct Operate command for a binary output.

        Returns CommandStatus indicating success or failure.
        """
        ...

    @abstractmethod
    def on_direct_operate_analog(self, index: int, value: float) -> CommandStatus:
        """Handle a Direct Operate command for an analog output.

        Returns CommandStatus indicating success or failure.
        """
        ...

    def on_select_binary(self, index: int, crob: CROB) -> CommandStatus:
        """Handle Select (first pass of SBO) for binary output."""
        return CommandStatus.NOT_SUPPORTED

    def on_operate_binary(self, index: int, crob: CROB) -> CommandStatus:
        """Handle Operate (second pass of SBO) for binary output."""
        return CommandStatus.NOT_SUPPORTED

    def on_select_analog(self, index: int, value: float) -> CommandStatus:
        """Handle Select for analog output."""
        return CommandStatus.NOT_SUPPORTED

    def on_operate_analog(self, index: int, value: float) -> CommandStatus:
        """Handle Operate for analog output."""
        return CommandStatus.NOT_SUPPORTED

    def on_freeze(self) -> None:
        """Handle a freeze request from the master."""
        pass

    def on_cold_restart(self) -> int:
        """Handle cold restart. Return delay in milliseconds."""
        return 0

    def on_warm_restart(self) -> int:
        """Handle warm restart. Return delay in milliseconds."""
        return 0

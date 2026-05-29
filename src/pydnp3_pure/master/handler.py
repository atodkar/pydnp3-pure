"""Master station handler callback interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..app.constants import CommandStatus
from ..app.fragment import AppMessage


class IMasterHandler(ABC):
    """Callback interface for master station application logic."""

    @abstractmethod
    def on_response_received(self, message: AppMessage) -> None:
        """Called when a solicited response is received from the outstation."""
        ...

    def on_unsolicited_response(self, message: AppMessage) -> None:
        """Called when an unsolicited response is received."""
        pass

    def on_command_complete(self, status: CommandStatus) -> None:
        """Called when a command (DirectOp/SBO) completes."""
        pass

    def on_connection_state_change(self, connected: bool) -> None:
        """Called when connection state changes."""
        pass

    def on_timeout(self) -> None:
        """Called when a response timeout occurs."""
        pass

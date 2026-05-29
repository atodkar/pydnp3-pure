"""Async timer utility for protocol timeouts."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any


class AsyncTimer:
    """A resettable one-shot timer that calls a callback on expiration."""

    __slots__ = ("_delay", "_callback", "_task")

    def __init__(
        self, delay_seconds: float, callback: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        self._delay = delay_seconds
        self._callback = callback
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self.cancel()
        self._task = asyncio.ensure_future(self._run())

    def restart(self) -> None:
        self.start()

    def cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            self._task = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _run(self) -> None:
        await asyncio.sleep(self._delay)
        await self._callback()

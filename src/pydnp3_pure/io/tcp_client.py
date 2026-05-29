"""Async TCP client for outstation connections."""

from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Callable

from .channel import IChannel

logger = logging.getLogger(__name__)


class TcpClient(IChannel):
    """Asyncio TCP client that connects to a remote DNP3 master/server.

    Typical use: outstation connecting to master's listening socket.
    """

    def __init__(
        self,
        host: str,
        port: int,
        ssl_context: ssl.SSLContext | None = None,
        server_hostname: str | None = None,
        reconnect_delay: float = 5.0,
    ) -> None:
        self._host = host
        self._port = port
        self._ssl = ssl_context
        self._server_hostname = server_hostname
        self._reconnect_delay = reconnect_delay
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._receive_callback: Callable[[bytes], None] | None = None
        self._running = False
        self._read_task: asyncio.Task | None = None

    @property
    def is_open(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    def set_receive_callback(self, callback: Callable[[bytes], None]) -> None:
        self._receive_callback = callback

    async def open(self) -> None:
        """Connect to the remote host."""
        kwargs = {}
        if self._ssl:
            kwargs["ssl"] = self._ssl
            kwargs["server_hostname"] = self._server_hostname or self._host

        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port, **kwargs
        )
        self._running = True
        self._read_task = asyncio.ensure_future(self._read_loop())
        logger.info("Connected to %s:%d", self._host, self._port)

    async def close(self) -> None:
        """Disconnect from the remote host."""
        self._running = False
        if self._read_task:
            self._read_task.cancel()
            self._read_task = None
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
        self._reader = None
        logger.info("Disconnected from %s:%d", self._host, self._port)

    def send(self, data: bytes) -> None:
        """Send bytes to the remote host."""
        if self._writer and not self._writer.is_closing():
            self._writer.write(data)

    async def _read_loop(self) -> None:
        """Continuously read from the socket and deliver to callback."""
        try:
            while self._running and self._reader:
                data = await self._reader.read(4096)
                if not data:
                    logger.info("Connection closed by remote")
                    break
                if self._receive_callback:
                    self._receive_callback(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Read error: %s", e)
        finally:
            self._running = False

"""Async TCP server for master station connections."""

from __future__ import annotations

import asyncio
import logging
import ssl
from collections.abc import Callable

from .channel import IChannel

logger = logging.getLogger(__name__)


class TcpServer(IChannel):
    """Asyncio TCP server that listens for outstation connections.

    Typical use: master station accepting outstation connections.
    Handles one active connection at a time (DNP3 is point-to-point).
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 20000,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._ssl = ssl_context
        self._server: asyncio.Server | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._receive_callback: Callable[[bytes], None] | None = None
        self._running = False
        self._read_task: asyncio.Task[None] | None = None
        self._connected_event = asyncio.Event()

    @property
    def is_open(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    def set_receive_callback(self, callback: Callable[[bytes], None]) -> None:
        self._receive_callback = callback

    async def open(self) -> None:
        """Start listening for connections."""
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_client, self._host, self._port, ssl=self._ssl
        )
        logger.info("Listening on %s:%d", self._host, self._port)

    async def wait_for_connection(self) -> None:
        """Wait until a client connects."""
        await self._connected_event.wait()

    async def close(self) -> None:
        """Stop the server and disconnect any active client."""
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
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._reader = None
        self._writer = None
        self._connected_event.clear()

    def send(self, data: bytes) -> None:
        """Send bytes to the connected client."""
        if self._writer and not self._writer.is_closing():
            self._writer.write(data)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a new client connection."""
        peer = writer.get_extra_info("peername")
        logger.info("Client connected: %s", peer)

        # Close any existing connection
        if self._writer and not self._writer.is_closing():
            self._writer.close()

        self._reader = reader
        self._writer = writer
        self._connected_event.set()

        try:
            while self._running:
                data = await reader.read(4096)
                if not data:
                    break
                if self._receive_callback:
                    self._receive_callback(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Client error: %s", e)
        finally:
            writer.close()
            if self._writer is writer:
                self._writer = None
                self._reader = None
                self._connected_event.clear()
            logger.info("Client disconnected: %s", peer)

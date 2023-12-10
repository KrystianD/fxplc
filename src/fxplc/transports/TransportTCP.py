import asyncio
import socket

from .ITransport import ITransport


class NotConnectedError(Exception):
    pass


DefaultReadTimeout = 1
DefaultFlushDelay = 1


class TransportTCP(ITransport):
    def __init__(self, host: str, port: int, timeout: float = DefaultReadTimeout,
                 flush_delay: float = DefaultFlushDelay) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._flush_delay = flush_delay
        self._s: socket.socket | None = None

    async def connect(self) -> None:
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._s.setblocking(False)

        await asyncio.get_event_loop().sock_connect(self._s, (self._host, self._port))
        await asyncio.sleep(self._flush_delay)
        while True:
            try:
                self._s.recv(1024)
            except BlockingIOError:
                break

    def close(self) -> None:
        if self._s is None:
            return

        self._s.close()
        self._s = None

    async def write(self, data: bytes) -> None:
        if self._s is None:
            raise NotConnectedError()

        self._s.send(data)

    async def read(self, size: int) -> bytes:
        if self._s is None:
            raise NotConnectedError()

        return await asyncio.get_event_loop().sock_recv(self._s, size)


__all__ = [
    "TransportTCP",
]

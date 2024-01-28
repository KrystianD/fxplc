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
        loop = asyncio.get_event_loop()

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)

        try:
            await asyncio.wait_for(loop.sock_connect(s, (self._host, self._port)), timeout=self._timeout)
            await asyncio.sleep(self._flush_delay)
            while True:
                try:
                    rd = s.recv(1024)
                    if len(rd) == 0:
                        raise ConnectionError()
                except BlockingIOError:
                    break
        except:
            s.close()
            raise

        self._s = s

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

        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(loop.sock_recv(self._s, size), timeout=self._timeout)


__all__ = [
    "TransportTCP",
    "NotConnectedError",
]

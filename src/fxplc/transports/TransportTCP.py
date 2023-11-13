import asyncio
from asyncio import StreamReader, StreamWriter

from .ITransport import ITransport


class NotConnectedError(Exception):
    pass


class TransportTCP(ITransport):
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._reader: StreamReader | None = None
        self._writer: StreamWriter | None = None

    async def connect(self):
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)

    def close(self):
        if self._reader is None or self._writer is None:
            return
        self._writer.close()

    async def write(self, data: bytes):
        if self._reader is None or self._writer is None:
            raise NotConnectedError()

        self._writer.write(data)
        await self._writer.drain()

    async def read(self, size: int) -> bytes:
        if self._reader is None or self._writer is None:
            raise NotConnectedError()

        return await self._reader.read(size)


__all__ = [
    "TransportTCP",
]

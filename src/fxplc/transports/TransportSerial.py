import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import cast

import serial

from .ITransport import ITransport

ReadTimeout = 1


class TransportSerial(ITransport):
    def __init__(self, port: str) -> None:
        self._serial = serial.Serial(port=port,
                                     timeout=1,
                                     baudrate=38400,
                                     bytesize=serial.SEVENBITS,
                                     parity=serial.PARITY_EVEN,
                                     stopbits=serial.STOPBITS_ONE)
        self._executor = ThreadPoolExecutor(max_workers=1)

    def close(self) -> None:
        self._executor.shutdown()
        self._serial.close()

    async def write(self, data: bytes) -> None:
        self._serial.flushOutput()
        self._serial.flushInput()
        self._serial.write(data)

    async def read(self, size: int) -> bytes:
        data = await asyncio.get_event_loop().run_in_executor(self._executor, self._serial.read, size)
        if len(data) == 0:
            raise asyncio.exceptions.TimeoutError()
        return cast(bytes, data)


__all__ = [
    "TransportSerial",
]

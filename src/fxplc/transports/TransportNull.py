from .ITransport import ITransport


class TransportNull(ITransport):
    async def write(self, data: bytes) -> None:
        pass

    async def read(self, size: int) -> bytes:
        return b""

    def close(self) -> None:
        pass


__all__ = [
    "TransportNull",
]

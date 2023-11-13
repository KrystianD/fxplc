from abc import abstractmethod


class ITransport:
    @abstractmethod
    async def write(self, data: bytes) -> None:
        pass

    @abstractmethod
    async def read(self, size: int) -> bytes:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

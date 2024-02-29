from typing import Union

from fxplc.client.FXPLCClient import FXPLCClient, RegisterDef
from fxplc.client.number_type import NumberType
from fxplc.transports.TransportNull import TransportNull


class FXPLCClientMock(FXPLCClient):
    def __init__(self):
        super().__init__(TransportNull())

    async def read_bit(self, register: Union[RegisterDef, str]) -> bool:
        return False

    async def write_bit(self, register: Union[RegisterDef, str], value: bool) -> None:
        pass

    async def read_int(self, register: Union[RegisterDef, str]) -> int:
        return 0

    async def read_number(self, register: Union[RegisterDef, str], number_type: NumberType) -> int | float:
        return 0

    async def read_bytes(self, addr: int, count: int = 1) -> bytes:
        return b""

    async def write_bytes(self, addr: int, values: bytes) -> None:
        pass

    async def write_int(self, register: Union[RegisterDef, str], value: int) -> None:
        pass

    async def write_number(self, register: Union[RegisterDef, str], value: int | float, number_type: NumberType) -> None:
        pass


__all__ = [
    "FXPLCClientMock",
]

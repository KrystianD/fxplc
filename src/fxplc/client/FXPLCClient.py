import asyncio
import binascii
import enum
import logging
import struct
from typing import Tuple, Union

from fxplc.client.errors import ResponseMalformedError, NoResponseError, NotSupportedCommandError
from fxplc.transports.ITransport import ITransport

logger = logging.getLogger("fxplc")

STX = b"\x02"  # Start of text
ETX = b'\x03'  # End of text
EOT = b'\x04'  # End of transmission
ENQ = b'\x05'  # Enquiry
ACK = b'\x06'  # Acknowledge
LF = b'\x0A'  # Line Feed
CL = b'\x0C'  # Clear
CR = b'\x0D'  # Carrier Return
NAK = b'\x15'  # Not Acknowledge


class Commands(enum.IntEnum):
    BYTE_READ = 0
    BYTE_WRITE = 1
    FORCE_ON = 7
    FORCE_OFF = 8


registers_map_bit_images = {
    "S": 0x0000,
    "X": 0x0080,
    "Y": 0x00a0,
    "T": 0x00c0,
    "M": 0x0100,
    "D": 0x1000,
}

registers_map_counter = {
    "T": 0x0800,
    "D": 0x1000,
}

registers_map_bits = {
    "S": 0x0000,
    "X": 0x0400,
    "Y": 0x0500,
    "T": 0x0600,
    "M": 0x0800,
}


class RegisterType(enum.Enum):
    State = "S"
    Input = "X"
    Output = "Y"
    Timer = "T"
    Memory = "M"
    Data = "D"


class RegisterDef:
    def __init__(self, reg_type: RegisterType, num: int) -> None:
        self.type = reg_type
        self.num = num

    def __str__(self) -> str:
        return f"{self.type.value}{self.num}"

    def get_bit_image_address(self) -> Tuple[int, int]:
        top_address = registers_map_bit_images[self.type.value]
        if self.type in (RegisterType.Input, RegisterType.Output):
            byte_addr, bit = top_address + self.num // 10, self.num % 10
        else:
            byte_addr, bit = top_address + self.num // 8, self.num % 8
        assert bit < 8
        return byte_addr, bit

    @staticmethod
    def parse(definition: str) -> 'RegisterDef':
        return RegisterDef(reg_type=RegisterType(definition[0]), num=int(definition[1:]))


def calc_checksum(payload: bytes) -> bytes:
    return bytes(f"{sum(payload):02X}"[-2:].encode("ascii"))


class FXPLCClient:
    def __init__(self, transport: ITransport):
        self._transport = transport
        self._lock = asyncio.Lock()

    def close(self) -> None:
        self._transport.close()

    async def read_bit(self, register: Union[RegisterDef, str]) -> bool:
        if not isinstance(register, RegisterDef):
            register = RegisterDef.parse(register)
        addr, bit = register.get_bit_image_address()

        resp = await self.read_bytes(addr, 1)
        return (resp[0] & (1 << bit)) != 0

    async def write_bit(self, register: Union[RegisterDef, str], value: bool) -> None:
        if not isinstance(register, RegisterDef):
            register = RegisterDef.parse(register)
        top_address = registers_map_bits[register.type.value]
        addr = top_address + register.num

        await self._send_command(Commands.FORCE_ON if value else Commands.FORCE_OFF, struct.pack("<H", addr))

    async def read_counter(self, register: Union[RegisterDef, str]) -> int:
        if not isinstance(register, RegisterDef):
            register = RegisterDef.parse(register)
        addr = registers_map_counter[register.type.value] + register.num * 2

        resp = await self.read_bytes(addr, 2)

        value: int = struct.unpack("<H", resp)[0]
        return value

    async def read_bytes(self, addr: int, count: int = 1) -> bytes:
        req = struct.pack(">HB", addr, count)
        resp = await self._send_command(Commands.BYTE_READ, req)
        return resp

    async def write_bytes(self, addr: int, values: bytes) -> None:
        req = struct.pack(">HB", addr, len(values)) + values
        await self._send_command(Commands.BYTE_WRITE, req)

    async def write_data(self, register: Union[RegisterDef, str], value: int) -> None:
        if not isinstance(register, RegisterDef):
            register = RegisterDef.parse(register)
        addr = registers_map_counter[register.type.value] + register.num * 2

        await self.write_bytes(addr, struct.pack("H", value))

    async def _send_command(self, cmd: int, data: bytes) -> bytes:
        cmd_hex = bytes([ord("0") + cmd])
        payload_hex = binascii.hexlify(data).upper()
        logger.debug("TX [cmd | payload]: " + cmd_hex.decode("ascii") + " | " + payload_hex.decode("ascii"))
        payload = cmd_hex + payload_hex

        frame = STX + payload + ETX + calc_checksum(payload + ETX)

        async with self._lock:
            await self._transport.write(frame)
            return await self._read_response()

    async def _read_response(self) -> bytes:
        def format_code(_code: bytes) -> str:
            return f"RX [code]: {binascii.hexlify(_code).decode('ascii')}"

        def format_code_data(_code: bytes, _data: bytes) -> str:
            return f"RX [code | payload]: {binascii.hexlify(_code).decode('ascii')} | {_data.decode('ascii')}"

        code = await self._transport.read(1)
        if code == STX:
            data = b""
            while True:
                d = await self._transport.read(1)
                if len(d) == 0:
                    logger.error(f"Invalid response - {format_code_data(code, data)}")
                    raise ResponseMalformedError()

                if d == ETX:
                    break
                data += d

            logger.debug(format_code_data(code, data))

            checksum = await self._transport.read(2)
            if len(checksum) != 2:
                logger.error(f"Invalid response - {format_code_data(code, data)}")
                raise ResponseMalformedError()

            if calc_checksum(data + ETX) != checksum:
                logger.error(f"Wrong checksum - {format_code_data(code, data)}")
                raise ResponseMalformedError()

            return binascii.unhexlify(data)
        elif code == NAK:
            raise NotSupportedCommandError()
        elif code == ACK:
            logger.debug(f"{format_code(code)} (ACK)")
            return b""
        else:
            raise NoResponseError()


__all__ = [
    "RegisterType",
    "RegisterDef",
    "FXPLCClient",
]

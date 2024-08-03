import asyncio
import binascii
import enum
import logging
import struct
from typing import Tuple, Union, cast

from fxplc.client.errors import ResponseMalformedError, NoResponseError, NotSupportedCommandError
from fxplc.client.number_type import NumberType, register_type_converters
from fxplc.transports.ITransport import ITransport

logger = logging.getLogger("fxplc.client")

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
    "S": (0x0000, 8),
    "X": (0x0080, 10),
    "Y": (0x00a0, 10),
    "T": (0x00c0, 8),
    "M": (0x0100, 8),
    "D": (0x1000, 8),
}

registers_map_data = {
    "T": 0x0800,
    "C": 0x0a00,
    "D": 0x1000,
}

registers_map_bits = {
    "S": (0x0000, 8),
    "X": (0x0400, 10),
    "Y": (0x0500, 10),
    "T": (0x0600, 8),
    "M": (0x0800, 8),
}


class RegisterType(enum.Enum):
    State = "S"
    Input = "X"
    Output = "Y"
    Timer = "T"
    Memory = "M"
    Data = "D"
    Counter = "C"


class RegisterDef:
    def __init__(self, reg_type: RegisterType, num: int) -> None:
        self.type = reg_type
        self.num = num

    def __str__(self) -> str:
        return f"{self.type.value}{self.num}"

    def get_bit_image_address(self) -> Tuple[int, int]:
        top_address, denominator = registers_map_bit_images[self.type.value]
        byte_addr, bit = top_address + self.num // denominator, self.num % denominator
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
        if len(resp) != 1:
            raise ResponseMalformedError()
        return (resp[0] & (1 << bit)) != 0

    async def write_bit(self, register: Union[RegisterDef, str], value: bool) -> None:
        if not isinstance(register, RegisterDef):
            register = RegisterDef.parse(register)
        top_address, denominator = registers_map_bits[register.type.value]
        addr = top_address + (register.num // denominator * 8 + register.num % denominator)

        await self._send_command(Commands.FORCE_ON if value else Commands.FORCE_OFF, struct.pack("<H", addr))

    async def read_int(self, register: Union[RegisterDef, str]) -> int:
        return cast(int, await self.read_number(register, NumberType.WordSigned))

    async def read_number(self, register: Union[RegisterDef, str], number_type: NumberType) -> int | float:
        if not isinstance(register, RegisterDef):
            register = RegisterDef.parse(register)
        addr = registers_map_data[register.type.value] + register.num * 2

        number_type_converter = register_type_converters[number_type]
        byte_size = struct.calcsize(number_type_converter.format_str)

        resp = await self.read_bytes(addr, byte_size)
        if len(resp) != byte_size:
            raise ResponseMalformedError()

        value: int | float = struct.unpack(number_type_converter.format_str, resp)[0]
        return value

    async def read_bytes(self, addr: int, count: int = 1) -> bytes:
        req = struct.pack(">HB", addr, count)
        resp = await self._send_command(Commands.BYTE_READ, req)
        return resp

    async def write_bytes(self, addr: int, values: bytes) -> None:
        req = struct.pack(">HB", addr, len(values)) + values
        await self._send_command(Commands.BYTE_WRITE, req)

    async def write_int(self, register: Union[RegisterDef, str], value: int) -> None:
        await self.write_number(register, value, NumberType.WordSigned)

    async def write_number(self, register: Union[RegisterDef, str], value: int | float, number_type: NumberType) -> None:
        if not isinstance(register, RegisterDef):
            register = RegisterDef.parse(register)
        addr = registers_map_data[register.type.value] + register.num * 2

        number_type_converter = register_type_converters[number_type]

        await self.write_bytes(addr, struct.pack(number_type_converter.format_str, value))

    async def _send_command(self, cmd: int, data: bytes) -> bytes:
        cmd_hex = bytes([ord("0") + cmd])
        payload_hex = binascii.hexlify(data).upper()
        logger.debug("TX [cmd | payload]: " + cmd_hex.decode("ascii") + " | " + payload_hex.decode("ascii"))
        payload = cmd_hex + payload_hex

        frame = STX + payload + ETX + calc_checksum(payload + ETX)

        async with self._lock:
            await self._transport.write(frame)
            try:
                return await self._read_response()
            except TimeoutError:
                raise NoResponseError()

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

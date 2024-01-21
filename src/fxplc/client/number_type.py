import enum
from dataclasses import dataclass
from typing import Dict


class NumberType(enum.Enum):
    WordSigned = "WordSigned"
    DoubleWordSigned = "DoubleWordSigned"
    WordUnsigned = "WordUnsigned"
    DoubleWordUnsigned = "DoubleWordUnsigned"
    Float = "Float"


@dataclass
class NumberTypeConverter:
    format_str: str


register_type_converters: Dict[NumberType, NumberTypeConverter] = {
    NumberType.WordSigned: NumberTypeConverter("<h"),
    NumberType.DoubleWordSigned: NumberTypeConverter("<i"),
    NumberType.WordUnsigned: NumberTypeConverter("<H"),
    NumberType.DoubleWordUnsigned: NumberTypeConverter("<I"),
    NumberType.Float: NumberTypeConverter("<f"),
}
__all__ = [
    "NumberType",
    "register_type_converters",
]

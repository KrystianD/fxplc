from typing import List, Optional

from pydantic.dataclasses import dataclass

from fxplc.client.number_type import NumberType


@dataclass
class VariableDefinition:
    name: str
    register: str
    group: Optional[str] = None
    number_type: NumberType = NumberType.WordSigned
    readonly: bool = False


@dataclass
class VariablesFile:
    variables: List[VariableDefinition]


class RuntimeSettings:
    def __init__(self) -> None:
        self.variables: List[VariableDefinition] = []
        self.rest_enabled = True

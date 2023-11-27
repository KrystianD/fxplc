from typing import List, Optional

from pydantic.dataclasses import dataclass


@dataclass
class VariableDefinition:
    name: str
    register: str
    group: Optional[str] = None


@dataclass
class VariablesFile:
    variables: List[VariableDefinition]


class RuntimeSettings:
    def __init__(self) -> None:
        self.variables: List[VariableDefinition] = []
        self.rest_enabled = True

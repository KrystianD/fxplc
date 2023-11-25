from typing import List

from pydantic.dataclasses import dataclass


@dataclass
class VariableDefinition:
    name: str
    register: str


@dataclass
class VariablesFile:
    variables: List[VariableDefinition]

"""A dataclass using forward references, defined in a different module to the tests."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DataclassForward:
    a: "DataclassLocal"
    b: "DataclassGlobal"

    @dataclass(frozen=True)
    class DataclassLocal:
        n: Optional["DataclassForward"]


@dataclass(frozen=True)
class DataclassGlobal:
    x: int

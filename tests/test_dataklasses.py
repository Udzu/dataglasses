import json
import re
from dataclasses import asdict, dataclass
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import (
    Annotated,
    Any,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Union,
)

import pytest
from jsonschema import validate
from jsonschema.exceptions import ValidationError

from dataklasses import from_dict, to_json_schema
from tests.forward_dataclass import DataclassForward, DataclassGlobal


def assert_asdict_inverse(data: Any) -> None:
    """Checks asdict output validates against the JSON schema and is inverted by from_dict."""
    value = json.loads(json.dumps(asdict(data)))
    schema = to_json_schema(type(data))
    validate(value, schema)
    data_loop = from_dict(type(data), value)
    assert data == data_loop


def assert_invalid_value(
    cls: type,
    value: Any,
    error: str,
    strict: bool = False,
    valid_schema: bool = True,
) -> None:
    """Checks value gets rejected by both from_dict and the JSON schema"""
    if valid_schema:
        schema = to_json_schema(cls, strict=strict)
        with pytest.raises(ValidationError):
            validate(value, schema)
    else:
        with pytest.raises(ValueError):
            to_json_schema(cls, strict=strict)
    with pytest.raises(TypeError) as e:
        from_dict(cls, value, strict=strict)
    assert re.search(error, str(e.value)), f"{e.value} doesn't match {error}"


# ===========
# BASIC TYPES
# ===========


@dataclass(frozen=True)
class DataclassBasicTypes:
    i: int
    f: float
    s: str = "hi"
    b: bool = True
    n: None = None


@pytest.mark.parametrize(
    "data",
    [
        DataclassBasicTypes(1, 1.5, "a"),
        DataclassBasicTypes(-1, 3.0, "b", False, None),
    ],
)
def test_basic_types(data: Any) -> None:
    assert_asdict_inverse(data)


def test_int_as_float() -> None:
    value = {"i": 1, "f": 2}
    data = from_dict(DataclassBasicTypes, value)
    assert data == DataclassBasicTypes(1, 2)


def test_defaults():
    value = {"i": 1, "f": 0.5, "s": "a"}
    data = from_dict(DataclassBasicTypes, value)
    assert data == DataclassBasicTypes(1, 0.5, "a")

    # check that the default values are in the schema
    schema = to_json_schema(DataclassBasicTypes)
    properties = schema["$defs"]["DataclassBasicTypes"]["properties"]
    assert "default" not in properties["i"]
    assert "default" not in properties["f"]
    assert properties["s"]["default"] == "hi"
    assert properties["b"]["default"] is True
    assert properties["n"]["default"] is None


@pytest.mark.parametrize(
    "value, error",
    [
        pytest.param(None, "mapping", id="Bad input type"),
        pytest.param({"f": 0.5, "s": "a"}, "required", id="Missing field"),
        pytest.param({"i": "hello", "f": 0.5, "s": "a"}, "value, got", id="Bad field"),
    ],
)
def test_basic_errors(value: Any, error: str):
    assert_invalid_value(DataclassBasicTypes, value, error)


def test_strict_mode():
    value = {"i": 1, "f": 0.5, "s": "a", "xxx": 12}
    assert from_dict(DataclassBasicTypes, value) == DataclassBasicTypes(1, 0.5, "a")
    assert_invalid_value(DataclassBasicTypes, value, "xxx", strict=True)


# ==============
# SEQUENCE TYPES
# ==============


@dataclass(frozen=True)
class DataclassElement:
    x: int
    y: str


@dataclass(frozen=True)
class DataclassSequence:
    s: Sequence[int]
    L: List[DataclassElement]


@pytest.mark.parametrize(
    "data",
    [
        DataclassSequence([], []),
        DataclassSequence(
            [1, 2, 3], [DataclassElement(1, "a"), DataclassElement(2, "b")]
        ),
    ],
)
def test_sequence_types(data: Any) -> None:
    assert_asdict_inverse(data)


def test_sequence_defaults_to_list() -> None:
    data = from_dict(DataclassSequence, {"s": (1, 2), "L": []})
    assert data == DataclassSequence([1, 2], [])


@pytest.mark.parametrize(
    "value, error",
    [
        pytest.param({"s": 1, "L": []}, "sequence", id="Bad sequence"),
        pytest.param({"s": [1, 1.5], "L": []}, "value, got", id="Bad sequence element"),
    ],
)
def test_sequence_errors(value: Any, error: str):
    assert_invalid_value(DataclassSequence, value, error)


# ===========
# UNION TYPES
# ===========


@dataclass(frozen=True)
class DataclassUnion:
    @dataclass(frozen=True)
    class Nested:
        x: int

    o: Optional[int]
    u: Union[str, Nested]
    b: Sequence[int | str]


@pytest.mark.parametrize(
    "data",
    [
        DataclassUnion(None, "hi", [3, "bye"]),
        DataclassUnion(4, DataclassUnion.Nested(1), []),
    ],
)
def test_union_types(data: Any) -> None:
    assert_asdict_inverse(data)


@pytest.mark.parametrize(
    "value, error",
    [
        pytest.param({"o": "hi", "u": "ho", "b": []}, "one of", id="Bad optional"),
        pytest.param({"o": 1, "u": 1, "b": []}, "one of", id="Bad union"),
        pytest.param({"o": 1, "u": "hi", "b": [0.5]}, "one of", id="Bad | "),
        pytest.param({"u": "hi", "b": []}, "required", id="Non-defaulted optional"),
    ],
)
def test_union_errors(value: Any, error: str):
    assert_invalid_value(DataclassUnion, value, error)


# ===========
# TUPLE TYPES
# ===========


@dataclass(frozen=True)
class DataclassTuple:
    t: tuple[int, str]
    e: tuple[Optional[int], ...]


@pytest.mark.parametrize(
    "data",
    [
        DataclassTuple((1, "a"), (3, None, 4)),
        DataclassTuple((2, "b"), ()),
    ],
)
def test_tuple_types(data: Any) -> None:
    assert_asdict_inverse(data)


@pytest.mark.parametrize(
    "value, error",
    [
        pytest.param({"t": [1, "a"], "e": 1.5}, "sequence", id="Bad tuple type"),
        pytest.param({"t": [1, 2], "e": []}, "value, got", id="Bad tuple field type"),
        pytest.param(
            {"t": [1, "a", 1], "e": []}, "2 elements", id="Bad tuple length big"
        ),
        pytest.param({"t": [1], "e": []}, "2 elements", id="Bad tuple length small"),
    ],
)
def test_tuple_errors(value: Any, error: str):
    assert_invalid_value(DataclassTuple, value, error)


# =============
# MAPPING TYPES
# =============


@dataclass(frozen=True)
class DataclassMapping:
    m: Mapping[str, int]
    d: Dict[str, "DataclassMapping"]


@pytest.mark.parametrize(
    "data",
    [
        DataclassMapping({}, {}),
        DataclassMapping({"a": 1, "b": 2}, {"a": DataclassMapping({"c": 3}, {})}),
    ],
)
def test_mapping_types(data: Any) -> None:
    assert_asdict_inverse(data)


def test_mapping_defaults_to_dict() -> None:
    data = from_dict(DataclassMapping, {"m": MappingProxyType({"a": 1}), "d": {}})
    assert data == DataclassMapping({"a": 1}, {})


@pytest.mark.parametrize(
    "value, error",
    [
        pytest.param({"m": None, "d": {}}, "mapping", id="Bad mapping type"),
        pytest.param({"m": {"a": "1"}, "d": {}}, "value, got", id="Bad mapping value"),
        pytest.param(
            {"m": {}, "d": {"a": 1}}, "corresponding", id="Bad mapping value 2"
        ),
    ],
)
def test_mapping_errors(value: Any, error: str):
    assert_invalid_value(DataclassMapping, value, error)


# ==========
# ENUM TYPES
# ==========


class EnumInt(IntEnum):
    ONE = 1
    TWO = 2


class EnumStr(str, Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


@dataclass(frozen=True)
class DataclassEnum:
    L: Literal["black", "white"]
    s: EnumStr
    i: EnumInt


@pytest.mark.parametrize(
    "data",
    [
        DataclassEnum("black", EnumStr.RED, EnumInt.ONE),
    ],
)
def test_enum_types(data: Any) -> None:
    assert json.loads(json.dumps(EnumStr.RED)) == "red"
    assert json.loads(json.dumps(EnumInt.ONE)) == 1
    assert_asdict_inverse(data)


def test_enum_from_name() -> None:
    value = {"L": "black", "s": "GREEN", "i": 2}
    data = from_dict(DataclassEnum, value)
    assert data == DataclassEnum("black", EnumStr.GREEN, EnumInt.TWO)
    schema = to_json_schema(type(data))
    validate(value, schema)


@pytest.mark.parametrize(
    "value, error",
    [
        pytest.param({"L": "BLACK", "s": "red", "i": 1}, "one of", id="Bad literal"),
        pytest.param({"L": "black", "s": "black", "i": 1}, "label", id="Bad str enum"),
        pytest.param({"L": "black", "s": "red", "i": "1"}, "label", id="Bad int enum"),
    ],
)
def test_enum_errors(value: Any, error: str):
    assert_invalid_value(DataclassEnum, value, error)


# ===============
# ANNOTATED TYPES
# ===============


@dataclass(frozen=True)
class DataclassAnnotated:
    i: Annotated[int, "An integer"]
    s: Annotated[Optional[str], "An optional string"] = None
    u: bool = True  # not annotated


@pytest.mark.parametrize(
    "data",
    [
        DataclassAnnotated(1),
    ],
)
def test_annotated_types(data: Any) -> None:
    assert_asdict_inverse(data)


def test_annotated_descriptions() -> None:
    schema = to_json_schema(DataclassAnnotated)
    properties = schema["$defs"]["DataclassAnnotated"]["properties"]
    assert properties["i"]["description"] == "An integer"
    assert properties["s"]["description"] == "An optional string"
    assert "description" not in properties["u"]


# ==================
# FORWARD REFERENCES
# ==================

# the dataclass are imported from a different module, to ensure the correct globals are used


@pytest.mark.parametrize(
    "data",
    [
        DataclassForward(DataclassForward.DataclassLocal(None), DataclassGlobal(2)),
        DataclassForward(
            DataclassForward.DataclassLocal(
                DataclassForward(
                    DataclassForward.DataclassLocal(None), DataclassGlobal(1)
                )
            ),
            DataclassGlobal(2),
        ),
    ],
)
def test_forward_references(data: Any) -> None:
    assert_asdict_inverse(data)


# =================
# UNSUPPORTED TYPES
# =================


@dataclass
class DataclassUnsupportedSchema:
    a: list
    b: set
    c: Any


def test_unsupported_schema_types() -> None:
    data = from_dict(DataclassUnsupportedSchema, {"a": [1, "?"], "b": {2, "!"}, "c": 1})
    assert data == DataclassUnsupportedSchema([1, "?"], {2, "!"}, 1)
    assert_invalid_value(
        DataclassUnsupportedSchema,
        {"a": {1, "?"}, "b": {2, "!"}, "c": 1},
        "value, got",
        valid_schema=False,
    )
    assert_invalid_value(
        DataclassUnsupportedSchema,
        {"a": [], "b": {}, "c": 1},
        "value, got",
        valid_schema=False,
    )

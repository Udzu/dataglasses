import json
import sys
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

from dataglasses import TransformRules, from_dict, to_json_schema
from tests.forward_dataclass import DataclassForward, DataclassGlobal


def assert_asdict_inverse(data: Any, local_refs: Optional[set[type]] = None) -> None:
    """Checks that the `asdict` output on `data`, saved and loaded as json,
    validates against the JSON schema and is inverted by `from_dict`."""
    value = json.loads(json.dumps(asdict(data)))
    schema = to_json_schema(type(data), local_refs=local_refs)
    validate(value, schema)
    data_loop = from_dict(type(data), value, local_refs=local_refs)
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
        with pytest.raises(ValueError, match="Unsupported"):
            to_json_schema(cls, strict=strict)
    with pytest.raises(TypeError, match=error):
        from_dict(cls, value, strict=strict)


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
    ("value", "error"),
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
            [1, 2, 3],
            [DataclassElement(1, "a"), DataclassElement(2, "b")],
        ),
    ],
)
def test_sequence_types(data: Any) -> None:
    assert_asdict_inverse(data)


def test_sequence_defaults_to_list() -> None:
    data = from_dict(DataclassSequence, {"s": (1, 2), "L": []})
    assert data == DataclassSequence([1, 2], [])


@pytest.mark.parametrize(
    ("value", "error"),
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
    ("value", "error"),
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
    ("value", "error"),
    [
        pytest.param({"t": [1, "a"], "e": 1.5}, "sequence", id="Bad tuple type"),
        pytest.param({"t": [1, 2], "e": []}, "value, got", id="Bad tuple field type"),
        pytest.param(
            {"t": [1, "a", 1], "e": []},
            "2 elements",
            id="Bad tuple length big",
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
    ("value", "error"),
    [
        pytest.param({"m": None, "d": {}}, "mapping", id="Bad mapping type"),
        pytest.param({"m": {"a": "1"}, "d": {}}, "value, got", id="Bad mapping value"),
        pytest.param(
            {"m": {}, "d": {"a": 1}},
            "corresponding",
            id="Bad mapping value 2",
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
    ("value", "error"),
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

# NB dataclass imported from a different module, to ensure the correct globals are used


@pytest.mark.parametrize(
    "data",
    [
        DataclassForward(DataclassForward.DataclassLocal(None), DataclassGlobal(2)),
        DataclassForward(
            DataclassForward.DataclassLocal(
                DataclassForward(
                    DataclassForward.DataclassLocal(None),
                    DataclassGlobal(1),
                ),
            ),
            DataclassGlobal(2),
        ),
    ],
)
def test_forward_references(data: Any) -> None:
    assert_asdict_inverse(data)


def test_local_forward_references() -> None:
    @dataclass
    class LocalFwd:
        a: "Optional[LocalFwd]"

    with pytest.raises(NameError):
        assert_asdict_inverse(LocalFwd(None))

    assert_asdict_inverse(LocalFwd(None), local_refs={LocalFwd})
    assert_asdict_inverse(LocalFwd(LocalFwd(None)), local_refs={LocalFwd})


# ==========
# TRANSFORMS
# ==========


@dataclass
class DataclassTransform:
    a: str
    b: str
    c: list[str]
    d: Optional[str] = None


@pytest.mark.parametrize(
    ("transform", "output"),
    [
        ({str: (str, str.title)}, DataclassTransform("Hi", "Bye", ["Die!"])),
        (
            {(DataclassTransform, "a"): (str, str.title)},
            DataclassTransform("Hi", "bye", ["DIE!"]),
        ),
        (
            {(DataclassTransform, "a"): (Literal["hi"], str.title)},
            DataclassTransform("Hi", "bye", ["DIE!"]),
        ),
        (
            {list[str]: (list[str], lambda x: [s.title() for s in x])},
            DataclassTransform("hi", "bye", ["Die!"]),
        ),
    ],
)
def test_transform(transform: TransformRules, output: DataclassTransform) -> None:
    value = {"a": "hi", "b": "bye", "c": ["DIE!"]}
    data = from_dict(DataclassTransform, value, transform=transform)
    assert data == output
    schema = to_json_schema(DataclassTransform, transform=transform)
    validate(value, schema)


@dataclass
class DataclassTransformGeneric:
    a: set[str]
    b: set[int]
    c: set[float]


def test_transform_generic() -> None:
    value = {"a": ["a", "b"], "b": [1, 2], "c": [0.5, 0.7]}
    transform: TransformRules = {
        set: (list[str | int], set),
        set[float]: (list[float], lambda lst: set(lst) | {0.0}),
    }
    data = from_dict(DataclassTransformGeneric, value, transform=transform)
    assert data == DataclassTransformGeneric({"a", "b"}, {1, 2}, {0.0, 0.5, 0.7})
    schema = to_json_schema(DataclassTransformGeneric, transform=transform)
    validate(value, schema)


# ============
# TYPE ALIASES
# ============

if sys.version_info >= (3, 12):  # pragma: no cover
    exec("type TypeAliasList = list[int]")
    exec("type TypeAliasSet = set[int]")

    @dataclass
    class DataclassTypeAlias:
        a: TypeAliasList  # type: ignore  # noqa: F821
        b: TypeAliasSet  # type: ignore  # noqa: F821

    def test_transform_type_alias() -> None:
        value = {"a": [1, 2], "b": [3, 4]}
        transform: TransformRules = {set: (list[int], set)}
        data = from_dict(DataclassTypeAlias, value, transform=transform)
        assert data == DataclassTypeAlias([1, 2], {3, 4})
        schema = to_json_schema(DataclassTypeAlias, transform=transform)
        validate(value, schema)


# =================
# UNSUPPORTED TYPES
# =================


@dataclass
class DataclassUntypedCollections:
    a: list
    b: set


@dataclass
class DataclassAny:
    c: Any


@dataclass
class DataclassNonStringMapping:
    d: Mapping[int, int]


@pytest.mark.parametrize(
    ("cls", "valid_input", "invalid_input"),
    [
        (DataclassUntypedCollections, {"a": ["?"], "b": {"!"}}, {"a": [], "b": [2]}),
        (DataclassAny, {"c": None}, None),
        (DataclassNonStringMapping, {"d": {1: 2}}, {"d": {"1": 2}}),
    ],
)
def test_unsupported_in_schema_types(
    cls: type, valid_input: Any, invalid_input: Any
) -> None:
    data: Any = from_dict(cls, valid_input)
    assert data == cls(*valid_input.values())
    if invalid_input is not None:
        assert_invalid_value(cls, invalid_input, "value, got", valid_schema=False)


@pytest.mark.parametrize(
    ("cls", "transform", "input_value", "output"),
    [
        (
            DataclassUntypedCollections,
            {list: (list[int | str], lambda x: x), set: (list[int | str], set)},
            {"a": [1, "?"], "b": [2, "!"]},
            DataclassUntypedCollections([1, "?"], {2, "!"}),
        ),
        (DataclassAny, {Any: (int, str)}, {"c": 1}, DataclassAny("1")),
        (
            DataclassNonStringMapping,
            {
                Mapping[int, int]: (
                    dict[str, int],
                    lambda d: {int(k) + 1: v for k, v in d.items()},
                )
            },
            {"d": {"1": 2}},
            DataclassNonStringMapping({2: 2}),
        ),
    ],
)
def test_unsupported_in_schema_transform(
    cls: type, transform: TransformRules, input_value: dict[str, Any], output: object
) -> None:
    data: Any = from_dict(cls, input_value, transform=transform)
    assert data == output
    schema = to_json_schema(type(data), transform=transform)
    validate(input_value, schema)


@dataclass
class DataclassUnsupportedAnywhere:
    a: set[int]


def test_unsupported_anywhere_types() -> None:
    with pytest.raises(TypeError, match="isinstance"):
        from_dict(DataclassUnsupportedAnywhere, {"a": {1, 2}})
    with pytest.raises(ValueError, match="Unsupported"):
        to_json_schema(DataclassUnsupportedAnywhere)
    transform: TransformRules = {set[int]: (list[int], set)}
    data = from_dict(DataclassUnsupportedAnywhere, {"a": [1, 2]}, transform=transform)
    assert data == DataclassUnsupportedAnywhere({1, 2})
    schema = to_json_schema(DataclassUnsupportedAnywhere, transform=transform)
    validate({"a": [1, 2]}, schema)

import collections
import dataclasses
import inspect
from enum import Enum
from types import NoneType, UnionType
from typing import (
    Annotated,
    Any,
    ForwardRef,
    Literal,
    Mapping,
    Optional,
    Sequence,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

T = TypeVar("T")


def from_dict(
    cls: type[T], value: Any, _dataclass: Optional[type] = None, *, strict: bool = False
) -> T:
    """
    Convert a dict, such as one generated using dataclasses.asdict(), to a dataclass.

    Supports dataclass fields with basic types, as well as nested and recursive dataclasses, and
    Sequence, List, Tuple, Mapping, Dict, Optional, Union, Literal, Enum and Annotated types.

    :param cls: Type to convert to.
    :param value: Value to convert.
    :param _dataclass: Surrounding dataclass (used for ForwardRef evaluation in recursive calls).
    :param strict: Disallow additional dataclass properties.
    :return: Converted value.
    :raises TypeError: When the value doesn't match the type.
    """

    if cls is None:
        cls = NoneType

    elif cls is Any:
        cls = object  # type: ignore[assignment]

    if dataclasses.is_dataclass(cls) and not isinstance(value, cls):
        if not isinstance(value, Mapping):
            raise TypeError(f"Expected mapping corresponding to {cls}, got {value}")
        field_types = {f.name: cast(type, f.type) for f in dataclasses.fields(cls)}
        if strict and any(f not in field_types for f in value):
            raise TypeError(f"Unexpected {cls} fields {set(value) - set(field_types)}")
        return cls(
            **{
                f: from_dict(field_types[f], v, cls)
                for f, v in value.items()
                if f in field_types
            }
        )  # type: ignore[return-value]

    elif isinstance(cls, (str, ForwardRef)):
        ref = ForwardRef(cls) if isinstance(cls, str) else cls
        _globals = vars(inspect.getmodule(_dataclass))
        _locals = _dataclass.__dict__
        return from_dict(
            ref._evaluate(_globals, _locals, frozenset()), value, _dataclass
        )

    origin = get_origin(cls)

    if origin in (collections.abc.Sequence, list):
        if not isinstance(value, Sequence):
            raise TypeError(f"Expected sequence corresponding to {cls}, got {value}")
        sequence_type = get_args(cls)[0]
        return [from_dict(sequence_type, v, _dataclass) for v in value]  # type: ignore[return-value]

    elif origin in (collections.abc.Mapping, dict):
        if not isinstance(value, Mapping):
            raise TypeError(f"Expected mapping corresponding to {cls}, got {value}")
        key_type, value_type = get_args(cls)
        return {
            from_dict(key_type, k, _dataclass): from_dict(value_type, v, _dataclass)
            for k, v in value.items()
        }  # type: ignore[return-value]

    elif origin is tuple:
        tuple_types = get_args(cls)
        if not isinstance(value, Sequence):
            raise TypeError(f"Expected sequence corresponding to {cls}, got {value}")
        if len(tuple_types) == 2 and tuple_types[1] == Ellipsis:
            tuple_types = (tuple_types[0],) * len(value)
        if len(value) != len(tuple_types):
            raise TypeError(
                f"Expected {len(tuple_types)} elements for {cls}, got {value}"
            )
        return tuple(
            from_dict(tuple_type, v, _dataclass)
            for tuple_type, v in zip(tuple_types, value)
        )  # type: ignore[return-value]

    elif origin in (Union, UnionType):
        union_types = get_args(cls)
        for union_type in union_types:
            try:
                return from_dict(union_type, value, _dataclass)
            except Exception:
                continue
        raise TypeError(
            f"Expected value corresponding to one of {union_types}, got {value}"
        )

    elif origin == Literal:
        if value not in get_args(cls):
            raise TypeError(f"Expected one of {get_args(cls)}, got {value}")
        return value

    elif origin == Annotated:
        return from_dict(get_args(cls)[0], value, _dataclass)

    elif isinstance(cls, type) and issubclass(cls, Enum) and not isinstance(value, cls):
        if any(e.value == value for e in cls):
            return cls(value)  # type: ignore[return-value]
        elif value in cls.__members__:
            return cls[value]  # type: ignore[return-value]
        else:
            raise TypeError(f"Expected {cls} label, got {value}")

    elif cls is float and isinstance(value, int):
        # see https://peps.python.org/pep-0484/#the-numeric-tower
        return value  # type: ignore[return-value]

    elif not isinstance(value, cls):
        raise TypeError(f"Expected {cls} value, got {value}")

    return value


def to_json_schema(cls: type, *, strict: bool = False) -> dict[str, Any]:
    """
    Convert a dataclass (or other Python class) into a JSON schema. Data that satisfies
    the schema can be converted into the class using `from_dict`.

    Supports dataclass fields with basic types, as well as nested and recursive dataclasses, and
    Sequence, List, Tuple, Mapping, Dict, Optional, Union, Literal, Enum and Annotated types.
    Annotated types are used to populate property descriptions.

    :param cls: Class to generate a schema for.
    :param strict: Disallow additional dataclass properties.
    :return: JSON schema dict.
    :raises ValueError: When the class cannot be represented in JSON.
    """

    defs: dict[str, Any] = {}

    def _json_schema(cls: type, _dataclass: Optional[type] = None) -> dict[str, Any]:
        basic_types = {
            bool: "boolean",
            int: "integer",
            float: "number",
            str: "string",
            NoneType: "null",
        }

        if cls is None:
            cls = NoneType

        if cls in basic_types:
            return {"type": basic_types[cls]}

        elif dataclasses.is_dataclass(cls):
            if cls.__qualname__ not in defs:
                # (make sure to create definition before the recursive call)
                defn = defs[cls.__qualname__] = {"type": "object"}
                defn["properties"] = {
                    f.name: _json_schema(cast(type, f.type), cls)
                    for f in dataclasses.fields(cls)
                }
                defn["required"] = [
                    f.name
                    for f in dataclasses.fields(cls)
                    if f.default is dataclasses.MISSING
                    and f.default_factory is dataclasses.MISSING
                ]
                if strict:
                    defn["additionalProperties"] = False
                for f in dataclasses.fields(cls):
                    if f.default is not dataclasses.MISSING:
                        defn["properties"][f.name]["default"] = f.default

            return {"$ref": f"#/$defs/{cls.__qualname__}"}

        if isinstance(cls, (str, ForwardRef)):
            ref = ForwardRef(cls) if isinstance(cls, str) else cls
            _globals = vars(inspect.getmodule(_dataclass))
            _locals = _dataclass.__dict__
            evaluated_type = cast(type, ref._evaluate(_globals, _locals, frozenset()))
            return _json_schema(evaluated_type, _dataclass)

        origin = get_origin(cls)

        if origin in (collections.abc.Sequence, list):
            sequence_type = get_args(cls)[0]
            return {"type": "array", "items": _json_schema(sequence_type, _dataclass)}

        elif origin in (collections.abc.Mapping, dict):
            key_type, value_type = get_args(cls)
            if key_type is not str:
                raise ValueError(f"Unsupported non-string mapping key type: {key_type}")
            return {
                "type": "object",
                "patternProperties": {"^.*$": _json_schema(value_type, _dataclass)},
            }

        elif origin in (Union, UnionType):
            union_types = get_args(cls)
            return {"anyOf": [_json_schema(t, _dataclass) for t in union_types]}

        elif origin is tuple:
            tuple_types = get_args(cls)
            if len(tuple_types) == 2 and tuple_types[1] == Ellipsis:
                return {
                    "type": "array",
                    "items": _json_schema(tuple_types[0], _dataclass),
                }
            else:
                return {
                    "type": "array",
                    "prefixItems": [_json_schema(t, _dataclass) for t in tuple_types],
                    "minItems": len(tuple_types),
                    "maxItems": len(tuple_types),
                }

        elif origin == Literal:
            return {"enum": list(get_args(cls))}

        elif origin == Annotated:
            annotated_type, description = get_args(cls)
            defn = _json_schema(annotated_type, _dataclass)
            defn["description"] = description
            return defn

        elif isinstance(cls, type) and issubclass(cls, Enum):
            return {"enum": [e.value for e in cls] + list(cls.__members__)}

        else:
            raise ValueError(f"Unsupported type {cls}")

    schema: dict[str, Any] = {}
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema.update(_json_schema(cls))
    schema["$defs"] = defs
    return schema

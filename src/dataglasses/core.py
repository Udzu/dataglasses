import collections
import dataclasses
import inspect
import sys
from enum import Enum
from types import NoneType, UnionType
from typing import (
    Annotated,
    Any,
    Callable,
    ForwardRef,
    Literal,
    Mapping,
    Optional,
    Sequence,
    TypeAlias,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

try:
    from typing import TypeAliasType  # type: ignore
except ImportError:  # pragma: no cover
    TypeAliasType = type("TypeAliasTypeNotImplemented", (), {})  # type: ignore

T = TypeVar("T")

TransformRules: TypeAlias = Mapping[type | tuple[type, str], tuple[type, Callable]]
"""
Transformation rules, used by both `from_dict` and `to_json_schema`. These map either
an output type annotation (e.g. `int` or `list[str]`) or a dataclass-and-fieldname tuple
(e.g. `(InventoryItem, "name")`) to a tuple containing an intermediate type annotation
and a function to transform values from that type into the output type.
"""


def evaluate_forward_ref(
    ref: ForwardRef, globals: Mapping[str, Any], locals: Mapping[str, Any]
) -> type:
    """
    Evaluate a ForwardRef, something that's not currently exposed publicly.
    """
    if sys.version_info < (3, 12, 4):
        return ref._evaluate(globals, locals, frozenset())  # type: ignore   # pragma: no cover

    return ref._evaluate(globals, locals, frozenset(), recursive_guard=set())  # type: ignore  # pragma: no cover


def from_dict(
    cls: type[T],
    value: Any,
    *,
    strict: bool = False,
    transform: Optional[TransformRules] = None,
    local_refs: Optional[set[type]] = None,
) -> T:
    """
    Convert a dict, such as one generated using dataclasses.asdict(), to a dataclass.

    Supports dataclass fields with basic types, as well as nested and recursive
    dataclasses, and Sequence, List, Tuple, Mapping, Dict, Optional, Union, Literal,
    Enum and Annotated types.

    :param cls: Type to convert to.
    :param value: Value to convert.
    :param strict: Disallow additional dataclass properties.
    :param transform: Transformation rules.
    :param local_refs: Locally scoped types used in forward references.
    :return: Converted value.
    :raises TypeError: When the value doesn't match the type.
    """
    if transform is None:
        transform = {}

    def _from_dict(
        cls: type[T],
        value: Any,
        datacls: Optional[type] = None,
        transformed: bool = False,
    ) -> T:
        if cls in transform and not transformed:
            input_type, fn = transform[cls]
            return fn(_from_dict(input_type, value, datacls, transformed=True))

        if cls is None:
            cls = NoneType

        elif cls is Any:
            cls = object  # type: ignore[assignment]

        if dataclasses.is_dataclass(cls) and not isinstance(value, cls):
            if not isinstance(value, Mapping):
                raise TypeError(
                    f"Expected mapping corresponding to {cls}, got {value!r}",
                )
            field_types = {f.name: cast(type, f.type) for f in dataclasses.fields(cls)}
            if strict and any(f not in field_types for f in value):
                raise TypeError(
                    f"Unexpected {cls} fields {set(value) - set(field_types)}",
                )
            init_args = {}
            for f, v in value.items():
                if f in field_types:
                    if (cls, f) in transform:
                        input_type, fn = transform[(cls, f)]
                        init_args[f] = fn(_from_dict(input_type, v, cls))
                    else:
                        init_args[f] = _from_dict(field_types[f], v, cls)
            return cls(**init_args)  # type: ignore[return-value]

        elif isinstance(cls, (str, ForwardRef)):
            ref = ForwardRef(cls) if isinstance(cls, str) else cls
            _globals = vars(inspect.getmodule(datacls))
            _locals = datacls.__dict__
            if local_refs is not None:
                _locals = _locals | {c.__name__: c for c in local_refs}
            return _from_dict(
                evaluate_forward_ref(ref, _globals, _locals),
                value,
                datacls,
            )

        elif isinstance(cls, TypeAliasType):  # pragma: no cover
            return _from_dict(cls.__value__, value, datacls)

        origin = cast(type, get_origin(cls))

        if origin in transform and not transformed:
            input_type, fn = transform[origin]
            return fn(_from_dict(input_type, value, datacls, transformed=True))

        if origin in (collections.abc.Sequence, list):
            if not isinstance(value, Sequence):
                raise TypeError(
                    f"Expected sequence corresponding to {cls}, got {value!r}",
                )
            sequence_type = get_args(cls)[0]
            return [_from_dict(sequence_type, v, datacls) for v in value]  # type: ignore[return-value]

        elif origin in (collections.abc.Mapping, dict):
            if not isinstance(value, Mapping):
                raise TypeError(
                    f"Expected mapping corresponding to {cls}, got {value!r}",
                )
            key_type, value_type = get_args(cls)
            return {
                _from_dict(key_type, k, datacls): _from_dict(value_type, v, datacls)
                for k, v in value.items()
            }  # type: ignore[return-value]

        elif origin is tuple:
            tuple_types = get_args(cls)
            if not isinstance(value, Sequence):
                raise TypeError(
                    f"Expected sequence corresponding to {cls}, got {value!r}",
                )
            if len(tuple_types) == 2 and tuple_types[1] == Ellipsis:
                tuple_types = (tuple_types[0],) * len(value)
            if len(value) != len(tuple_types):
                raise TypeError(
                    f"Expected {len(tuple_types)} elements for {cls}, got {value!r}",
                )
            return tuple(
                _from_dict(tuple_type, v, datacls)
                for tuple_type, v in zip(tuple_types, value, strict=True)
            )  # type: ignore[return-value]

        elif origin in (Union, UnionType):
            union_types = get_args(cls)
            for union_type in union_types:
                try:
                    return _from_dict(union_type, value, datacls)
                except Exception:
                    continue
            raise TypeError(
                f"Expected value corresponding to one of {union_types}, got {value!r}",
            )

        elif origin == Literal:
            if value not in get_args(cls):
                raise TypeError(f"Expected one of {get_args(cls)}, got {value!r}")
            return value

        elif origin == Annotated:
            return _from_dict(get_args(cls)[0], value, datacls)

        elif (
            isinstance(cls, type)
            and issubclass(cls, Enum)
            and not isinstance(value, cls)
        ):
            if any(e.value == value for e in cls):
                return cls(value)  # type: ignore[return-value]
            elif value in cls.__members__:
                return cls[value]  # type: ignore[return-value]
            else:
                raise TypeError(f"Expected {cls} label, got {value!r}")

        elif cls is float and isinstance(value, int):
            # see https://peps.python.org/pep-0484/#the-numeric-tower
            return value  # type: ignore[return-value]

        elif not isinstance(value, cls):
            raise TypeError(f"Expected {cls} value, got {value!r}")

        return value

    return _from_dict(cls, value)


def to_json_schema(
    cls: type,
    *,
    strict: bool = False,
    transform: Optional[TransformRules] = None,
    local_refs: Optional[set[type]] = None,
) -> dict[str, Any]:
    """
    Convert a dataclass (or other Python class) into a JSON schema. Data that satisfies
    the schema can be converted into the class using `from_dict`.

    Supports dataclass fields with basic types, as well as nested and recursive
    dataclasses, and Sequence, List, Tuple, Mapping, Dict, Optional, Union, Literal,
    Enum and Annotated types. Annotated types are used to populate property
    descriptions.

    :param cls: Class to generate a schema for.
    :param strict: Disallow additional dataclass properties.
    :param transform: Transformation rules.
    :param local_refs: Locally scoped types used in forward references.
    :return: JSON schema dict.
    :raises ValueError: When the class cannot be represented in JSON.
    """
    defs: dict[str, Any] = {}
    if transform is None:
        transform = {}

    def _json_schema(
        cls: type,
        datacls: Optional[type] = None,
        transformed: bool = False,
    ) -> dict[str, Any]:
        basic_types = {
            bool: "boolean",
            int: "integer",
            float: "number",
            str: "string",
            NoneType: "null",
        }

        if cls in transform and not transformed:
            input_type, _ = transform[cls]
            return _json_schema(input_type, datacls, transformed=True)

        if cls is None:
            cls = NoneType

        if cls in basic_types:
            return {"type": basic_types[cls]}

        elif dataclasses.is_dataclass(cls):
            if cls.__qualname__ not in defs:
                # (make sure to create definition before the recursive call)
                defn = defs[cls.__qualname__] = {"type": "object", "properties": {}}

                for f in dataclasses.fields(cls):
                    if (cls, f.name) in transform:
                        input_type, _ = transform[(cls, f.name)]
                        defn["properties"][f.name] = _json_schema(input_type, cls)
                    else:
                        defn["properties"][f.name] = _json_schema(
                            cast(type, f.type),
                            cls,
                        )

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
            _globals = vars(inspect.getmodule(datacls))
            _locals = datacls.__dict__
            if local_refs is not None:
                _locals = _locals | {c.__name__: c for c in local_refs}
            evaluated_type = evaluate_forward_ref(ref, _globals, _locals)
            return _json_schema(evaluated_type, datacls)

        if isinstance(cls, TypeAliasType):  # pragma: no cover
            return _json_schema(cls.__value__, datacls)

        origin = cast(type, get_origin(cls))

        if origin in transform and not transformed:
            input_type, _ = transform[origin]
            return _json_schema(input_type, datacls, transformed=True)

        if origin in (collections.abc.Sequence, list):
            sequence_type = get_args(cls)[0]
            return {"type": "array", "items": _json_schema(sequence_type, datacls)}

        elif origin in (collections.abc.Mapping, dict):
            key_type, value_type = get_args(cls)
            if key_type is not str:
                raise ValueError(f"Unsupported non-string mapping key type: {key_type}")
            return {
                "type": "object",
                "patternProperties": {"^.*$": _json_schema(value_type, datacls)},
            }

        elif origin in (Union, UnionType):
            union_types = get_args(cls)
            return {"anyOf": [_json_schema(t, datacls) for t in union_types]}

        elif origin is tuple:
            tuple_types = get_args(cls)
            if len(tuple_types) == 2 and tuple_types[1] == Ellipsis:
                return {
                    "type": "array",
                    "items": _json_schema(tuple_types[0], datacls),
                }
            else:
                return {
                    "type": "array",
                    "prefixItems": [_json_schema(t, datacls) for t in tuple_types],
                    "minItems": len(tuple_types),
                    "maxItems": len(tuple_types),
                }

        elif origin == Literal:
            return {"enum": list(get_args(cls))}

        elif origin == Annotated:
            annotated_type, description = get_args(cls)
            defn = _json_schema(annotated_type, datacls)
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

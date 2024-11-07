# dataglasses

[![PyPi](https://img.shields.io/pypi/v/dataglasses)](https://pypi.python.org/pypi/dataglasses)
[![Python](https://img.shields.io/pypi/pyversions/dataglasses)](https://pypi.python.org/pypi/dataglasses)
[![License](https://img.shields.io/pypi/l/dataglasses)](LICENSE)
[![Actions status](https://img.shields.io/github/actions/workflow/status/Udzu/dataglasses/quality_checks.yaml?logo=github&label=quality%20checks)](https://github.com/Udzu/dataglasses/actions/workflows/quality_checks.yaml)
[![Codecov](https://img.shields.io/codecov/c/github/Udzu/dataglasses.svg)](https://app.codecov.io/github/Udzu/dataglasses/tree/main)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A small package to simplify creating dataclasses from JSON and validating that JSON.

## Installation

```bash
$ pip install dataglasses
```

## Requirements

Requires Python 3.10 or later.

If you wish to validate arbitrary JSON data against the generated JSON schemas in Python, consider installing [jsonschema](https://github.com/python-jsonschema/jsonschema), though this is unnecessary when using `dataglasses` to convert JSON into dataclasses.

## Quick start

```python
>>> from dataclasses import dataclass
>>> from dataglasses import from_dict, to_json_schema
>>> from json import dumps

>>> @dataclass
... class InventoryItem:
...     name: str
...     unit_price: float
...     quantity_on_hand: int = 0

>>> from_dict(InventoryItem, { "name": "widget", "unit_price": 3.0})
InventoryItem(name='widget', unit_price=3.0, quantity_on_hand=0)

>>> print(dumps(to_json_schema(InventoryItem), indent=2))
```

<details>
<summary>print output...</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$ref": "#/$defs/InventoryItem",
  "$defs": {
    "InventoryItem": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "unit_price": {
          "type": "number"
        },
        "quantity_on_hand": {
          "type": "integer",
          "default": 0
        }
      },
      "required": [
        "name",
        "unit_price"
      ]
    }
  }
}
```
</details>

## Objective

The purpose of this library is to speed up rapid development by making it trivial to populate dataclasses with dictionary data extracted from JSON (or elsewhere), as well as to perform basic validation on that data. The library contains just one file and two functions, so can even be directly copied into a project.

It is not intended for complex validation or high performance. For those, consider using [pydantic](https://github.com/pydantic/pydantic).

## Usage

The package contains just two functions:

```python
def from_dict(
    cls: type[T],
    value: Any,
    *,
    strict: bool = False,
    transform: Optional[TransformRules] = None,
    local_refs: Optional[set[type]] = None,
) -> T
````
This converts a nested dictionary `value` of input data into the given dataclass type `cls`, raising an exception if the conversion is not possible. (The optional keyword arguments are described further down.)

```python
def to_json_schema(
    cls: type,
    *,
    strict: bool = False,
    transform: Optional[TransformRules] = None,
    local_refs: Optional[set[type]] = None,
) -> dict[str, Any]:
```
This generates a 2020-12 JSON schema representing valid inputs for the dataclass type `cls`, raising an exception if the class cannot be represented in JSON.  (Again, the optional keyword arguments are described further down.)

Below is a summary of the different supported use cases:

### Nested structures

Dataclasses can be nested, using either global or local definitions.

```python
>>> @dataclass
... class TrackedItem:
... 
...     @dataclass
...     class GPS:
...         lat: float
...         long: float
...         
...     item: InventoryItem
...     location: GPS

>>> from_dict(TrackedItem, {
...     "item": { "name": "pie", "unit_price": 42},
...     "location": { "lat": 52.2, "long": 0.1 } })
TrackedItem(item=InventoryItem(name='pie', unit_price=42, quantity_on_hand=0),
location=TrackedItem.GPS(lat=52.2, long=0.1))

>>> print(dumps(to_json_schema(TrackedItem), indent=2))
```

<details>
<summary>print output...</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$ref": "#/$defs/TrackedItem",
  "$defs": {
    "TrackedItem": {
      "type": "object",
      "properties": {
        "item": {
          "$ref": "#/$defs/InventoryItem"
        },
        "location": {
          "$ref": "#/$defs/TrackedItem.GPS"
        }
      },
      "required": [
        "item",
        "location"
      ]
    },
    "InventoryItem": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "unit_price": {
          "type": "number"
        },
        "quantity_on_hand": {
          "type": "integer",
          "default": 0
        }
      },
      "required": [
        "name",
        "unit_price"
      ]
    },
    "TrackedItem.GPS": {
      "type": "object",
      "properties": {
        "lat": {
          "type": "number"
        },
        "long": {
          "type": "number"
        }
      },
      "required": [
        "lat",
        "long"
      ]
    }
  }
}
```
</details>

### Collection types

There is automatic support for the generic collection types most compatible with JSON: `list[T]`, `tuple[...]`  and `Sequence[T]` (encoded as arrays) and `dict[str, T]` and `Mapping[str, T]` (encoded as objects).

```python
>>> from collections.abc import Mapping, Sequence

>>> @dataclass
... class Catalog:
...     items: Sequence[InventoryItem]
...     publisher: tuple[str, int]
...     purchases: Mapping[str, int]
    
>>> from_dict(Catalog, {
...     "items": [{ "name": "widget", "unit_price": 3.0}],
...     "publisher": ["ACME", 1982],
...     "purchases": { "Wile E. Coyote": 52}})
Catalog(items=[InventoryItem(name='widget', unit_price=3.0, quantity_on_hand=0)],
publisher=('ACME', 1982), purchases={'Wile E. Coyote': 52})    

>>> print(dumps(to_json_schema(Catalog), indent=2))
```

<details>
<summary>print output...</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$ref": "#/$defs/Catalog",
  "$defs": {
    "Catalog": {
      "type": "object",
      "properties": {
        "items": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/InventoryItem"
          }
        },
        "publisher": {
          "type": "array",
          "prefixItems": [
            {
              "type": "string"
            },
            {
              "type": "integer"
            }
          ],
          "minItems": 2,
          "maxItems": 2
        },
        "purchases": {
          "type": "object",
          "patternProperties": {
            "^.*$": {
              "type": "integer"
            }
          }
        }
      },
      "required": [
        "items",
        "publisher",
        "purchases"
      ]
    },
    "InventoryItem": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "unit_price": {
          "type": "number"
        },
        "quantity_on_hand": {
          "type": "integer",
          "default": 0
        }
      },
      "required": [
        "name",
        "unit_price"
      ]
    }
  }
}
```
</details>

Unrestricted types like `list` or `dict` (or `set` or `Any`) and mappings with non-`str` keys can be used with `from_dict` but not with `to_json_schema`. Alternatively, these, alongside unsupported generic types like `set[T]`, can be used with both `from_dict` and `to_json_schema` by defining an appropriate encoding transformation (see section below). 

### Optional and Union types

Union types (`S | T` or `Union[S, T, ...]`) are matched against all their permitted subtypes in order, returning the first successful match, or raising an exception if there are none. Optional types (`T | None` or `Optional[T]`) are handled similarly. Note that an optional type is not the same as an optional field (i.e. one with a default): a field with an optional type is still a required field unless it has a default value (which could be `None` but could also be something else).

```python
>>> from typing import Optional

>>> @dataclass
... class ItemPurchase:
...     items: Sequence[InventoryItem | TrackedItem]
...     invoice: Optional[int] = None
    
>>> from_dict(ItemPurchase, {
...     "items": [{
...         "item": { "name": "pie", "unit_price": 42},
...         "location": { "lat": 52.2, "long": 0.1 } }],
...     "invoice": 1234})
ItemPurchase(items=[TrackedItem(item=
InventoryItem(name='pie', unit_price=42, quantity_on_hand=0),
location=TrackedItem.GPS(lat=52.2, long=0.1))], invoice=1234)

>>> print(dumps(to_json_schema(ItemPurchase), indent=2))
```

<details>
<summary>print output...</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$ref": "#/$defs/ItemPurchase",
  "$defs": {
    "ItemPurchase": {
      "type": "object",
      "properties": {
        "items": {
          "type": "array",
          "items": {
            "anyOf": [
              {
                "$ref": "#/$defs/InventoryItem"
              },
              {
                "$ref": "#/$defs/TrackedItem"
              }
            ]
          }
        },
        "invoice": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "items"
      ]
    },
    "InventoryItem": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "unit_price": {
          "type": "number"
        },
        "quantity_on_hand": {
          "type": "integer",
          "default": 0
        }
      },
      "required": [
        "name",
        "unit_price"
      ]
    },
    "TrackedItem": {
      "type": "object",
      "properties": {
        "item": {
          "$ref": "#/$defs/InventoryItem"
        },
        "location": {
          "$ref": "#/$defs/TrackedItem.GPS"
        }
      },
      "required": [
        "item",
        "location"
      ]
    },
    "TrackedItem.GPS": {
      "type": "object",
      "properties": {
        "lat": {
          "type": "number"
        },
        "long": {
          "type": "number"
        }
      },
      "required": [
        "lat",
        "long"
      ]
    }
  }
}
```
</details>

### Enum and Literal types

Both `Enum` and `Literal` types can be used to match explicit enumerations. By default, `Enum` types match both the values and symbolic names (preferring the former in case of a clash). This behaviour can be overridden using a transformation if desired (see section below). 

```python
>>> from enum import auto, StrEnum
>>> from typing import Literal

>>> class BuildType(StrEnum):
...     DEBUG = auto()
...     OPTIMIZED = auto()
    
>>> @dataclass
... class Release:
...     build: BuildType
...     approved: Literal["Yes", "No"]
    
>>> from_dict(Release, {"build": "debug", "confirmed": "Yes"})
Release(build=<Build.DEBUG: 'debug'>, approved='Yes')

>>> print(dumps(to_json_schema(Release), indent=2))
```

<details>
<summary>print output...</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$ref": "#/$defs/Release",
  "$defs": {
    "Release": {
      "type": "object",
      "properties": {
        "build": {
          "enum": [
            "debug",
            "optimized",
            "DEBUG",
            "OPTIMIZED"
          ]
        },
        "approved": {
          "enum": [
            "Yes",
            "No"
          ]
        }
      },
      "required": [
        "build",
        "confirmed"
      ]
    }
  }
}
```
</details>

### Annotated types

 `Annotated` types can be used to populate the property `"description"` annotations in the JSON schema. 

```python
>>> from typing import Annotated

>>> @dataclass
... class InventoryItem:
...     name: Annotated[str, "item name"]
...     unit_price: Annotated[float, "unit price"]
...     quantity_on_hand: Annotated[int, "quantity on hand"] = 0

>>> from_dict(InventoryItem, { "name": "widget", "unit_price": 3.0})
InventoryItem(name='widget', unit_price=3.0, quantity_on_hand=0)

>>> print(dumps(to_json_schema(InventoryItem), indent=2))
```

<details>
<summary>print output...</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$ref": "#/$defs/InventoryItem",
  "$defs": {
    "InventoryItem": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string",
          "description": "item name"
        },
        "unit_price": {
          "type": "number",
          "description": "unit price"
        },
        "quantity_on_hand": {
          "type": "integer",
          "description": "quantity on hand",
          "default": 0
        }
      },
      "required": [
        "name",
        "unit_price"
      ]
    }
  }
}
```
</details>

### Forward references

Forward reference types (written as string literals or `ForwardRef` objects) are supported, permitting recursive dataclasses. Global and class-scoped references are handled automatically:

```python
>>> @dataclass
... class Cons:
...     head: "Head"
...     tail: Optional["Cons"] = None
...     
...     @dataclass
...     class Head:
...         v: int
...         
...     def __repr__(self):
...         return f"{self.head.v}::{self.tail}"

>>> from_dict(Cons, {"head": {"v": 1}, "tail": {"head": {"v": 2}}})
1::2::None

>> print(dumps(to_json_schema(Cons), indent=2))
```

<details>
<summary>print output...</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$ref": "#/$defs/Cons",
  "$defs": {
    "Cons": {
      "type": "object",
      "properties": {
        "head": {
          "$ref": "#/$defs/Cons.Head"
        },
        "tail": {
          "anyOf": [
            {
              "$ref": "#/$defs/Cons"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "head"
      ]
    },
    "Cons.Head": {
      "type": "object",
      "properties": {
        "v": {
          "type": "integer"
        }
      },
      "required": [
        "v"
      ]
    }
  }
}
```
</details>

Locally-scoped references, however, must be specified using the `local_refs` keyword:

```python
>>> def reverse_cons(seq):
... 
...     @dataclass
...     class Cons:
...         head: int
...         tail: Optional["Cons"] = None
... 
...         def __repr__(self):
...             return f"{self.head}::{self.tail}"
... 
...     value = None
...     for x in seq: value = { "head": x, "tail": value }
...     return from_dict(Cons, value, local_refs={Cons})

>>> reverse_cons([1,2,3])
3::2::1::None
```

### Strict mode

Both `from_dict` and `to_json_schema` default to ignoring additional properties that are not part of a dataclass (similar to `additionalProperties` defaulting to true in JSON schemas). This can be disabled with the `strict` keyword.
```python
>>> value = { "name": "widget", "unit_price": 4.0, "comment": "too expensive"}

>>> from_dict(InventoryItem, value)
InventoryItem(name='widget', unit_price=4.0, quantity_on_hand=0)
>>> from_dict(InventoryItem, value, strict=True)
TypeError: Unexpected <class '__main__.InventoryItem'> fields {'comment'}

>>> print(dumps(to_json_schema(InventoryItem, strict=True), indent=2))
```

<details>
<summary>print output...</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$ref": "#/$defs/InventoryItem",
  "$defs": {
    "InventoryItem": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string",
          "description": "item name"
        },
        "unit_price": {
          "type": "number",
          "description": "unit price"
        },
        "quantity_on_hand": {
          "type": "integer",
          "description": "quantity on hand",
          "default": 0
        }
      },
      "required": [
        "name",
        "unit_price"
      ],
      "additionalProperties": false
    }
  }
}
```
</details>

### Transformations

Transformations allow you to override the handling of specific types or dataclass fields, and can be used to normalise inputs or convert them into different types, including ones that aren't normally supported. Transformations are specified with the `transform` keyword, using a mapping:

* the mapping keys are either:
  * a type used somewhere in the output dataclass: e.g. `str` or `set[int]`
  * a dataclass field specified by a class-name tuple: e.g. `(InventoryItem, "name")` or `(Cons, "head")`
* the mapping values are a tuple consisting of:
  * the JSON-serialisable input type that we want to represent this output type or field
  * a callable function to convert from that input type to the output type

Note that the input type can be the same as the output type. Conversely, note that transformations don't help with serialising the dataclasses *back* into JSON from non-serialisable types.

```python
>>> @dataclass
... class Person:
...     name : str
...     aliases: set[str]

>>> transform = {
...     str: (str, str.title),
...     set[str]: (list[str], set),
...     (Person, "name"): (str, lambda s: s + "!")}
    
>>> from_dict(Person, {"name": "robert", "aliases": ["bob", "bobby"]}, transform=transform)
Person(name='Robert!', aliases={'Bobby', 'Bob'})
    
>>> print(dumps(to_json_schema(Person, transform=transform), indent=2))
```

<details>
<summary>print output...</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$ref": "#/$defs/Person",
  "$defs": {
    "Person": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "aliases": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      },
      "required": [
        "name",
        "aliases"
      ]
    }
  }
}
```
</details>

## Contributions

Bug reports, feature requests and contributions are very welcome. Note that PRs must include tests with 100% code coverage and pass the necessary [quality checks](.github/workflows/quality_checks.yaml) before they can be merged.

To run the tests, make sure you have [uv](https://docs.astral.sh/uv/) installed, then type:

```bash
$ uv run task tests
```

To perform the formatting and linting checks, type:

```bash
$ uv run task check
```

To automatically resolve automatically fixable formatting and linting issues, type:

```bash
$ uv run task format
```

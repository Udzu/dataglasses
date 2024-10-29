# dataklasses

A mini-package to simplify the creation of dataclasses from JSON.

## Installation

```
$ pip install dataklasses
```

## Requirements

Python 3.10 or later. No other requirements, but if you wish to validate arbitrary JSON data against the generated JSON schemas, consider installing [jsonschema](https://github.com/python-jsonschema/jsonschema) (though this is unnecessary when using `dataklasses` to convert JSON into dataclasses).

## Quick start

```python
>>> from dataclasses import dataclass
>>> from dataklasses import from_dict, to_json_schema
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

## Purpose

[TODO]

## Usage

The package contains just two functions:

```python
def from_dict(cls: type[T], value: Any, *, strict: bool = False) -> T
````
This converts a nested dictionary `value` of input data into the given dataclass type `cls`, raising a `TypeError` if the conversion is not possible.

```python
def to_json_schema(cls: type, *, strict: bool = False) -> dict[str, Any]:
```
This generates a JSON schema representing valid inputs for the dataclass type `cls`, raising a `ValueError` if the class cannot be represented in JSON.

Below is a summary of the different supported use cases.

### Nested structures

Dataclasses can be nested, using either global or local definitions.

```python
>>> @dataclass
... clss TrackedItem:
... 
...     @dataclass
...     class GPS:
...         lat: float
...         long: float
...         
...     item: InventoryItem
...     location: GPS

>>> from_dict(TrackedItem, {
...     "item": { "name": "pi", "unit_price": 42},
...     "location": { "lat": 52.2, "long": 0.1 } })
TrackedItem(item=InventoryItem(name='pi', unit_price=42, quantity_on_hand=0),
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

### Optional and Union types

### Enum and Literal types

Both `Enum` and `Literal` types match explicit enumerations. `Enum` types match both the values and symbolic names (preferring the former in case of a clash).

```python
>>> from enum import auto, StrEnum

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

 `Annotated` types are used to populate the property `"description"` annotations in the JSON schema. 

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

Forward reference types (encoded as string literals or `ForwardRef` objects) are handled automatically, permitting recursive dataclasses. Both global and local references are supported.

```python
>>> @dataclass
... class Cons:
...     head: int
...     tail: Optional["Cons"] = None
...     
...     def __repr__(self):
...         current, rep = self, []
...         while isinstance(current, Cons):
...             rep.append(str(current.head))
...             current = current.tail
...         return "(" + ",".join(rep) + ")"

>>> from_dict(Cons, { "head": 1, "tail": { "head": 2 } })
(1,2)

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
          "type": "integer"
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
    }
  }
}
```
</details>

### Strict mode

Both `from_dict` and `to_json_schema` default to ignoring additional properties that are not part of the dataclass. This can be disabled with the `strict` keyword.
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

import dataclasses
from typing import Any, Mapping


def get_default_or_mapping_item(field: dataclasses.Field[Any], mapping: Mapping[str, str]) -> str:
    if field.default is not dataclasses.MISSING and field.name.upper() not in mapping:
        return field.default  # type: ignore[no-any-return]

    return field.type(mapping[field.name.upper()])  # type: ignore[operator, no-any-return]

import dataclasses
from typing import Mapping


def _get_default_or_mapping_item(
    field: dataclasses.Field, mapping: Mapping[str, str]
) -> str:
    if field.default is not dataclasses.MISSING and field.name.upper() not in mapping:
        return field.default

    return field.type(mapping[field.name.upper()])

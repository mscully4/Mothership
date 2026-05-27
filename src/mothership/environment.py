from __future__ import annotations

import json
import logging
import os
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, Mapping, Self, cast

import boto3
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBServiceResource
    from mypy_boto3_dynamodb.service_resource import Table

_STANDARD_LOG_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


def _json_default(obj: object) -> object:
    if isinstance(obj, Enum):
        return obj.name
    return str(obj)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in _STANDARD_LOG_ATTRS}
        payload.update(extras)
        return json.dumps(payload, default=_json_default)


def _get_default_or_mapping_item(*, key: str, field: FieldInfo, env: Mapping[str, str]) -> str:
    if (val := env.get(key.upper())) is not None:
        return val
    if field.default is not PydanticUndefined:
        return cast(str, field.default)
    raise RuntimeError(f"Required env var '{key.upper()}' is not set")


class Environment(BaseModel):
    aws_region: str = "us-east-2"
    filtered_titles_table_name: str

    @classmethod
    def from_environment(cls, env: Mapping[str, str] = os.environ) -> Self:
        args = {
            key: _get_default_or_mapping_item(key=key, field=field, env=env)
            for key, field in cls.model_fields.items()
        }
        return cls(**args)

    @cached_property
    def boto3_session(self) -> boto3.Session:
        return boto3.Session(region_name=self.aws_region)

    @cached_property
    def dynamodb_resource(self) -> DynamoDBServiceResource:
        return self.boto3_session.resource("dynamodb")  # type: ignore[no-any-return]

    @cached_property
    def filtered_titles_table(self) -> Table:
        return self.dynamodb_resource.Table(self.filtered_titles_table_name)

    @staticmethod
    def create_logger(name: str, level: int = logging.INFO) -> logging.Logger:
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(_JsonFormatter())
            logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
        return logger

import json
import logging
import os
from dataclasses import dataclass, fields
from typing import Any, Mapping, Optional

import boto3
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from mothership.utils.environment import get_default_or_mapping_item
from mothership.utils.logging import configure_logging

configure_logging(logging.INFO)

logger = logging.getLogger(__name__)

INTERACTION_PING = 1
INTERACTION_MESSAGE_COMPONENT = 3

_public_key_cache: Optional[str] = None


@dataclass
class EnvironmentConfig:
    discord_public_key_secret_name: str
    filtered_titles_table_name: str
    _session: Optional[boto3.Session] = None

    @classmethod
    def from_environment(cls, env: Mapping[str, Any] = os.environ) -> "EnvironmentConfig":
        kwargs = {field.name: get_default_or_mapping_item(field, env) for field in fields(cls)}
        return cls(**kwargs)

    def get_session(self) -> boto3.Session:
        if self._session is None:
            self._session = boto3.Session()
        return self._session

    def get_discord_public_key(self) -> str:
        global _public_key_cache
        if _public_key_cache is None:
            sm = self.get_session().client("secretsmanager")
            _public_key_cache = sm.get_secret_value(SecretId=self.discord_public_key_secret_name)[
                "SecretString"
            ]
        return _public_key_cache

    @property
    def filtered_titles_table(self) -> Any:
        ddb = self.get_session().resource("dynamodb")
        return ddb.Table(self.filtered_titles_table_name)


_JSON_HEADERS = {"Content-Type": "application/json"}


def _json_response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": status, "headers": _JSON_HEADERS, "body": json.dumps(body)}


def _verify_signature(public_key_hex: str, signature_hex: str, timestamp: str, body: str) -> bool:
    try:
        VerifyKey(bytes.fromhex(public_key_hex)).verify(
            (timestamp + body).encode(), bytes.fromhex(signature_hex)
        )
        return True
    except (BadSignatureError, Exception):
        return False


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    env_config = EnvironmentConfig.from_environment()
    public_key = env_config.get_discord_public_key()

    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    signature = headers.get("x-signature-ed25519", "")
    timestamp = headers.get("x-signature-timestamp", "")
    body = event.get("body") or ""

    if not _verify_signature(public_key, signature, timestamp, body):
        logger.warning(f"Signature verification failed. sig={signature[:16]}... ts={timestamp}")
        return {"statusCode": 401, "body": "Invalid signature"}

    interaction = json.loads(body)

    if interaction["type"] == INTERACTION_PING:
        return _json_response(200, {"type": 1})

    if interaction["type"] == INTERACTION_MESSAGE_COMPONENT:
        custom_id: str = interaction["data"]["custom_id"]
        if custom_id.startswith("filter:"):
            title = custom_id[len("filter:") :]
            env_config.filtered_titles_table.put_item(Item={"Title": title})
            logger.info(f"Added filter for title: {title}")
            return _json_response(
                200,
                {
                    "type": 4,
                    "data": {
                        "content": f"Filtering future notifications for: **{title}**",
                        "flags": 64,
                    },
                },
            )

    return _json_response(200, {"type": 1})

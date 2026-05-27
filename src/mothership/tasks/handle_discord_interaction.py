import json
import logging
from functools import cached_property
from typing import Any, Mapping

from aws_embedded_metrics import metric_scope  # type: ignore[attr-defined]
from aws_embedded_metrics.logger.metrics_logger import MetricsLogger
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from mothership.environment import Environment


class HandleDiscordInteractionEnvironment(Environment):
    discord_public_key_secret_name: str

    @cached_property
    def discord_public_key(self) -> str:
        client = self.boto3_session.client("secretsmanager")
        return str(
            client.get_secret_value(SecretId=self.discord_public_key_secret_name)["SecretString"]
        )


INTERACTION_PING = 1
INTERACTION_MESSAGE_COMPONENT = 3

_env = HandleDiscordInteractionEnvironment.from_environment()
logger = _env.create_logger(__name__, logging.INFO)

_PUBLIC_KEY_HEX = _env.discord_public_key
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


@metric_scope
def lambda_handler(
    event: Mapping[str, Any], context: Any, metrics: MetricsLogger
) -> dict[str, Any]:
    metrics.set_namespace("mothership")

    logger.info("Handling discord interaction", extra={"interation": event})
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    signature = headers.get("x-signature-ed25519", "")
    timestamp = headers.get("x-signature-timestamp", "")
    body = event.get("body") or ""

    if not _verify_signature(_PUBLIC_KEY_HEX, signature, timestamp, body):
        logger.warning(f"Signature verification failed. sig={signature[:16]}... ts={timestamp}")
        return {"statusCode": 401, "body": "Invalid signature"}

    interaction = json.loads(body)

    if interaction["type"] == INTERACTION_PING:
        return _json_response(200, {"type": 1})

    if interaction["type"] == INTERACTION_MESSAGE_COMPONENT:
        custom_id: str = interaction["data"]["custom_id"]
        if custom_id.startswith("filter:"):
            title = custom_id[len("filter:") :]
            _env.filtered_titles_table.put_item(Item={"Title": title})
            logger.info(f"Added filter for title: {title}")
            metrics.put_metric("FiltersAdded", 1, "Count")
            response = _json_response(
                200,
                {
                    "type": 4,
                    "data": {
                        "content": f"Filtering future notifications for: **{title}**",
                        "flags": 64,
                    },
                },
            )
            logger.info("Responding with", extra={"response": response})
            return response

    return {"statusCode": 400, "body": "unknown interaction type"}

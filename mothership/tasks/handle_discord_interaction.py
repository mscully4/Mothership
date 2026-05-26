import json
import logging
import os
import time
from typing import Any, Mapping

import boto3
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from mothership.utils.logging import configure_logging

configure_logging(logging.INFO)

logger = logging.getLogger(__name__)

INTERACTION_PING = 1
INTERACTION_MESSAGE_COMPONENT = 3

# Fetched at module load (Lambda init) so warm invocations skip the SM call
_sm_client = boto3.client("secretsmanager")
_PUBLIC_KEY_HEX: str = str(
    _sm_client.get_secret_value(SecretId=os.environ["DISCORD_PUBLIC_KEY_SECRET_NAME"])[
        "SecretString"
    ]
)

_ddb = boto3.resource("dynamodb")
_filtered_titles_table = _ddb.Table(os.environ["FILTERED_TITLES_TABLE_NAME"])

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
    t0 = time.time()

    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    signature = headers.get("x-signature-ed25519", "")
    timestamp = headers.get("x-signature-timestamp", "")
    body = event.get("body") or ""

    if not _verify_signature(_PUBLIC_KEY_HEX, signature, timestamp, body):
        logger.warning(f"Signature verification failed. sig={signature[:16]}... ts={timestamp}")
        return {"statusCode": 401, "body": "Invalid signature"}

    t1 = time.time()
    logger.info(f"t: verify={t1 - t0:.3f}s")

    interaction = json.loads(body)

    if interaction["type"] == INTERACTION_PING:
        return _json_response(200, {"type": 1})

    if interaction["type"] == INTERACTION_MESSAGE_COMPONENT:
        custom_id: str = interaction["data"]["custom_id"]
        if custom_id.startswith("filter:"):
            title = custom_id[len("filter:") :]
            t2 = time.time()
            _filtered_titles_table.put_item(Item={"Title": title})
            t3 = time.time()
            logger.info(f"t: put_item={t3 - t2:.3f}s total={t3 - t0:.3f}s")
            resp = _json_response(
                200,
                {
                    "type": 4,
                    "data": {
                        "content": f"Filtering future notifications for: **{title}**",
                        "flags": 64,
                    },
                },
            )
            t4 = time.time()
            logger.info(f"t: json_resp={t4 - t3:.3f}s returning at total={t4 - t0:.3f}s")
            return resp

    return _json_response(200, {"type": 1})

import logging
import os
from dataclasses import dataclass, fields
from typing import Any, Mapping, Optional

import boto3

from mothership.models import MothershipEvent
from mothership.utils.environment import get_default_or_mapping_item
from mothership.utils.logging import configure_logging
from mothership.wrappers.discord_wrapper import post_message

configure_logging(logging.INFO)

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentConfig:
    discord_bot_token_secret_name: str
    discord_channel_id: str
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

    def get_bot_token(self) -> str:
        client = self.get_session().client("secretsmanager")
        return str(
            client.get_secret_value(SecretId=self.discord_bot_token_secret_name)["SecretString"]
        )

    @property
    def filtered_titles_table(self) -> Any:
        ddb = self.get_session().resource("dynamodb")
        return ddb.Table(self.filtered_titles_table_name)


def _get_filtered_titles(table: Any) -> set[str]:
    resp = table.scan(ProjectionExpression="Title")
    return {item["Title"] for item in resp.get("Items", [])}


def _post_event(bot_token: str, channel_id: str, event: MothershipEvent) -> None:
    custom_id = f"filter:{event.title}"[:100]
    components = [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "label": "Filter This Show",
                    "style": 4,
                    "custom_id": custom_id,
                }
            ],
        }
    ]
    post_message(bot_token, channel_id, event.make_event_notification_message(), components)


def lambda_handler(event: Mapping[str, Any], context: Any) -> None:
    records = event.get("Records", [])
    inserts = [r for r in records if r.get("eventName") == "INSERT"]
    if not inserts:
        return

    env_config = EnvironmentConfig.from_environment()
    bot_token = env_config.get_bot_token()
    filtered_titles = _get_filtered_titles(env_config.filtered_titles_table)

    for record in inserts:
        img = record["dynamodb"].get("NewImage", {})
        title = img.get("title", {}).get("S", "")
        if title in filtered_titles:
            logger.info(f"Skipping filtered title: {title}")
            continue

        mothership_event = MothershipEvent(
            title=title,
            dt=img.get("dt", {}).get("S", ""),
            time=img.get("time", {}).get("S", ""),
            room=img.get("room", {}).get("S", ""),
        )
        logger.info(f"Posting event: {mothership_event}")
        _post_event(bot_token, env_config.discord_channel_id, mothership_event)

    logger.info("Finished!")

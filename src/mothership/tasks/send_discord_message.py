import logging
from typing import Any, Mapping

from aws_embedded_metrics import metric_scope  # type: ignore[attr-defined]
from aws_embedded_metrics.logger.metrics_logger import MetricsLogger

from mothership.environment import Environment
from mothership.models import MothershipEvent
from mothership.wrappers.discord_wrapper import post_message


class SendDiscordMessageEnvironment(Environment):
    discord_bot_token_secret_name: str
    discord_channel_id: str

    def get_bot_token(self) -> str:
        client = self.boto3_session.client("secretsmanager")
        return str(
            client.get_secret_value(SecretId=self.discord_bot_token_secret_name)["SecretString"]
        )


def _get_filtered_titles(env: SendDiscordMessageEnvironment) -> set[str]:
    resp = env.filtered_titles_table.scan(ProjectionExpression="Title")
    return {str(item["Title"]) for item in resp.get("Items", [])}


def _post_event(bot_token: str, channel_id: str, event: MothershipEvent) -> None:
    custom_id = f"filter:{event.title}"[:100]
    components = [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "label": "Filter Out",
                    "style": 4,
                    "custom_id": custom_id,
                }
            ],
        }
    ]
    post_message(bot_token, channel_id, event.make_event_notification_message(), components)


@metric_scope
def lambda_handler(event: Mapping[str, Any], context: Any, metrics: MetricsLogger) -> None:
    metrics.set_namespace("mothership")

    records = event.get("Records", [])
    inserts = [r for r in records if r.get("eventName") == "INSERT"]
    if not inserts:
        return

    env = SendDiscordMessageEnvironment.from_environment()
    logger = env.create_logger(__name__, logging.INFO)
    bot_token = env.get_bot_token()
    filtered_titles = _get_filtered_titles(env)

    sent = 0
    filtered = 0
    for record in inserts:
        img = record["dynamodb"].get("NewImage", {})
        title = img.get("title", {}).get("S", "")
        if title in filtered_titles:
            logger.info(f"Skipping filtered title: {title}")
            filtered += 1
            continue

        mothership_event = MothershipEvent(
            title=title,
            dt=img.get("dt", {}).get("S", ""),
            time=img.get("time", {}).get("S", ""),
            room=img.get("room", {}).get("S", ""),
        )
        logger.info(f"Posting event: {mothership_event}")
        _post_event(bot_token, env.discord_channel_id, mothership_event)
        sent += 1

    metrics.put_metric("NotificationsSent", sent, "Count")
    metrics.put_metric("NotificationsFiltered", filtered, "Count")
    logger.info("Finished!")

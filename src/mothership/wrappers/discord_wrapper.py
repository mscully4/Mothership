import json
import logging
import urllib.error
import urllib.request
from typing import Any

DISCORD_API_BASE = "https://discord.com/api/v10"

logger = logging.getLogger(__name__)


def post_message(
    bot_token: str,
    channel_id: str,
    content: str,
    components: list[Any] | None = None,
) -> None:
    payload: dict[str, Any] = {"content": content}
    if components:
        payload["components"] = components

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bot {bot_token}",
            "User-Agent": "DiscordBot (https://github.com/mscully4/mothership, 1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            logger.info(f"Discord response: {resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(f"Discord HTTP {e.code}: {body}")
        raise

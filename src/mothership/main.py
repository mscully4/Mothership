import os
from typing import Any

from mothership.exceptions import (
    HandlerNotFoundException,
    MissingEnvironmentVariableException,
)


def process_event(event: Any, context: Any) -> Any:
    handler_name = os.environ.get("HANDLER")

    if not handler_name:
        raise MissingEnvironmentVariableException("Environment variable 'HANDLER' is not set")

    if handler_name == "GET_NEW_MOTHERSHIP_EVENTS":
        from mothership.tasks import get_new_mothership_events

        return get_new_mothership_events.lambda_handler(event, context)
    elif handler_name == "SEND_NOTIFICATION":
        from mothership.tasks import send_discord_message

        return send_discord_message.lambda_handler(event, context)
    elif handler_name == "HANDLE_DISCORD_INTERACTION":
        from mothership.tasks import handle_discord_interaction

        return handle_discord_interaction.lambda_handler(event, context)

    raise HandlerNotFoundException(f"Handler '{handler_name}' does not exist")

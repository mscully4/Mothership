import os
from typing import Any
from src.exceptions import MissingEnvironmentVariableException, HandlerNotFoundException
from tasks import get_new_mothership_events, send_sms_message
from enum import Enum, auto


class HandlerNames(Enum):
    GET_NEW_MOTHERSHIP_EVENTS = auto()
    SEND_NOTIFICATION = auto()


HANDLERS = {
    HandlerNames.GET_NEW_MOTHERSHIP_EVENTS.name: get_new_mothership_events.lambda_handler,
    HandlerNames.SEND_NOTIFICATION.name: send_sms_message.lambda_handler,
}


def process_event(event, context: Any):
    env = dict(os.environ)

    if "HANDLER" not in env:
        raise MissingEnvironmentVariableException(
            "Environment variable 'HANDLER' is not set"
        )

    handler = HANDLERS.get(env["HANDLER"])

    if not handler:
        raise HandlerNotFoundException(f"Handler '{env['HANDLER']}' does not exist")

    return handler(event, context)

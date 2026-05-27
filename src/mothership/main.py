import os
from typing import Any, Callable, Protocol

from mothership.exceptions import (
    HandlerNotFoundException,
    MissingEnvironmentVariableException,
)


class _Task(Protocol):
    lambda_handler: Callable[..., Any]


_HANDLER = os.environ.get("HANDLER")

_task: _Task | None

if _HANDLER == "SEND_NOTIFICATION":
    from mothership.tasks import send_discord_message as _task
elif _HANDLER == "HANDLE_DISCORD_INTERACTION":
    from mothership.tasks import handle_discord_interaction as _task
else:
    _task = None


def process_event(event: Any, context: Any) -> Any:
    if not _HANDLER:
        raise MissingEnvironmentVariableException("Environment variable 'HANDLER' is not set")
    if _task is None:
        raise HandlerNotFoundException(f"Handler '{_HANDLER}' does not exist")
    return _task.lambda_handler(event, context)

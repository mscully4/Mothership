import logging

from pythonjsonlogger import jsonlogger


def configure_logging(
    log_level: int, root_logger: logging.Logger = logging.getLogger()
) -> None:
    stream_handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(log_level)

    root_logger.setLevel(log_level)
    root_logger.addHandler(stream_handler)

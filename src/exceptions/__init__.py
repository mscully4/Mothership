class MissingEnvironmentVariableException(Exception):
    """
    An exception thrown when an environment variable is not set
    """


class HandlerNotFoundException(Exception):
    """
    An exception thrown when an unknown handler is specified
    """

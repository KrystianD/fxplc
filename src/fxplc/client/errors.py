class NotSupportedCommandError(Exception):
    pass


class NoResponseError(Exception):
    pass


class ResponseMalformedError(Exception):
    pass


__all__ = [
    "NotSupportedCommandError",
    "NoResponseError",
    "ResponseMalformedError",
]

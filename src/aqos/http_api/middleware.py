from __future__ import annotations

import re
from typing import Awaitable, Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


AQOS_HTTP_MIDDLEWARE_VERSION = "1.0"

REQUEST_ID_HEADER = "X-Request-ID"

#: Where the resolved request id is stored for handlers to read.
REQUEST_ID_STATE_KEY = "aqos_request_id"

#: A request id must be short, printable and unsurprising.
#:
#: The value is echoed back in headers and error payloads, so an unchecked one
#: would let a caller inject whatever it liked into both.
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def generate_request_id() -> str:
    return uuid4().hex


def is_valid_request_id(value: str | None) -> bool:
    if not value:
        return False

    return bool(REQUEST_ID_PATTERN.match(value))


def resolve_request_id(incoming: str | None) -> str:
    """Keep a caller's id when it is safe, otherwise mint one."""

    return incoming if is_valid_request_id(incoming) else generate_request_id()


def read_request_id(request: Request) -> str | None:
    """The id the middleware attached, if it ran."""

    return getattr(request.state, REQUEST_ID_STATE_KEY, None)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Give every request a correlation id.

    A caller-supplied ``X-Request-ID`` is honoured when it looks safe so a trace
    can span services; anything else is replaced rather than trusted. The id
    goes back on the response and into any error payload, which is how an
    operator ties a client report to a logged failure.
    """

    def __init__(self, app, header_name: str = REQUEST_ID_HEADER) -> None:
        super().__init__(app)

        self.header_name = header_name

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = resolve_request_id(request.headers.get(self.header_name))
        setattr(request.state, REQUEST_ID_STATE_KEY, request_id)

        response = await call_next(request)
        response.headers[self.header_name] = request_id

        return response


__all__ = [
    "AQOS_HTTP_MIDDLEWARE_VERSION",
    "REQUEST_ID_HEADER",
    "REQUEST_ID_PATTERN",
    "REQUEST_ID_STATE_KEY",
    "RequestIdMiddleware",
    "generate_request_id",
    "is_valid_request_id",
    "read_request_id",
    "resolve_request_id",
]

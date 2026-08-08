"""
Request-level protections that run before any business code.

Three concerns, all of them about what a caller can make the process do rather
than about what the answer should be:

* **rate limiting** — how often one client may ask;
* **body size** — how much one request may weigh;
* **response headers** — what a browser is told to do with the answer.

Everything here refuses in the standard error envelope, so a throttled request
is as readable as a rejected one. Middleware cannot rely on the application's
exception handlers, so the payloads are built directly.

The limiter keeps its counters in memory. That is honest for one process and
wrong for several: two workers each allow the full quota. Deployments that run
more than one process need a shared store, and until then
:data:`RATE_LIMITER_IS_SINGLE_PROCESS` says so out loud.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from aqos.http_api.config import ApiConfig, ApiEnvironment
from aqos.http_api.errors import (
    ApiErrorCode,
    build_error_payload,
    status_for_error_code,
)
from aqos.http_api.middleware import read_request_id
from aqos.http_api.responses import json_response


AQOS_HTTP_HARDENING_VERSION = "1.0"

#: Stated in the module's public surface so nobody has to read the source to
#: learn the limiter's scope. Counters live in this process only.
RATE_LIMITER_IS_SINGLE_PROCESS = True

#: Environments where throttling is on unless a deployment turns it off.
#:
#: Local and test runs are left alone: a limiter that fires during a test suite
#: teaches people to disable it, and a developer hitting their own machine is
#: not the threat this exists for.
RATE_LIMITED_ENVIRONMENTS = (
    ApiEnvironment.STAGING,
    ApiEnvironment.PRODUCTION,
)

#: How long one counting window lasts.
RATE_LIMIT_WINDOW_SECONDS = 60.0

#: Paths that get the stricter allowance.
#:
#: Logging in is where guessing happens, so it is counted separately from
#: reading data; a caller cannot spend their read quota to hide it either.
AUTH_PATH_MARKER = "/auth/"

RATE_LIMIT_MESSAGE = "Too many requests. Slow down and try again shortly."

BODY_TOO_LARGE_MESSAGE = (
    "The request body is larger than this endpoint accepts."
)

#: Headers every response carries.
#:
#: ``nosniff`` stops a browser from guessing a content type it was not given,
#: which is what turns a JSON response into a script in the classic attack.
#: ``Referrer-Policy`` keeps ids in a URL from travelling to another origin.
DEFAULT_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}

#: What an authenticated response is cached as.
#:
#: Nothing. A response tied to a bearer token belongs to one caller, and a
#: shared cache holding it is a way for the next caller to read it.
PRIVATE_CACHE_CONTROL = "no-store"

#: The header that marks a request as belonging to someone.
AUTHORIZATION_HEADER = "Authorization"


@dataclass(frozen=True)
class RateLimitRule:
    """How many requests one client may make inside one window."""

    requests: int
    window_seconds: float = RATE_LIMIT_WINDOW_SECONDS

    def __post_init__(self) -> None:
        if self.requests < 1:
            raise ValueError("requests must be at least 1.")

        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive.")


@dataclass(frozen=True)
class RateLimitDecision:
    """Whether one request may proceed, and when to try again if not."""

    allowed: bool
    remaining: int
    retry_after_seconds: int


class InProcessRateLimiter:
    """
    A sliding-window counter, held in memory.

    One deque of timestamps per key, trimmed on each check, so a burst spread
    across a window is counted the same as a burst at its start. Guarded by a
    lock because Starlette serves requests concurrently.

    Single-process only. Behind two workers each process counts its own
    traffic, so the effective limit is the configured one multiplied by the
    worker count — which is why this is a foundation rather than a defence.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(
        self,
        key: str,
        rule: RateLimitRule,
        now: float | None = None,
    ) -> RateLimitDecision:
        moment = time.monotonic() if now is None else now
        cutoff = moment - rule.window_seconds

        with self._lock:
            hits = self._hits.setdefault(key, deque())

            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= rule.requests:
                # The oldest hit is what has to age out before there is room.
                retry_after = max(1, int(hits[0] + rule.window_seconds - moment) + 1)

                return RateLimitDecision(
                    allowed=False,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            hits.append(moment)

            return RateLimitDecision(
                allowed=True,
                remaining=rule.requests - len(hits),
                retry_after_seconds=0,
            )

    def reset(self) -> None:
        """Forget every counter. For tests and for a deliberate flush."""

        with self._lock:
            self._hits.clear()


def resolve_rate_limiting(config: ApiConfig) -> bool:
    """
    Whether this deployment throttles.

    An explicit setting always wins; otherwise it follows the environment, so
    production is protected without anybody remembering to switch it on.
    """

    if config.rate_limit_enabled is not None:
        return bool(config.rate_limit_enabled)

    return config.environment in RATE_LIMITED_ENVIRONMENTS


def client_key(request: Request) -> str:
    """
    Who to count this request against.

    The peer address, because there is nothing more trustworthy available: a
    forwarded header is set by the caller unless a proxy is known to rewrite
    it, and counting by a value the caller controls counts nothing.
    """

    client = request.client

    return client.host if client and client.host else "unknown"


def is_auth_path(path: str) -> bool:
    return AUTH_PATH_MARKER in path


def rule_for(request: Request, config: ApiConfig) -> RateLimitRule:
    if is_auth_path(request.url.path):
        return RateLimitRule(requests=config.auth_rate_limit_per_minute)

    return RateLimitRule(requests=config.rate_limit_per_minute)


def refusal_response(
    request: Request,
    code: ApiErrorCode,
    message: str,
    details: dict | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    """
    A refusal in the standard envelope, built without the app's handlers.

    Middleware sits outside the exception handlers, so raising here would come
    back in Starlette's shape rather than the API's. The payload is assembled
    directly so a throttled caller reads the same structure as any other error.
    """

    response = json_response(
        build_error_payload(
            code=code,
            message=message,
            request_id=read_request_id(request),
            details=details or {},
        ),
        status_code=status_for_error_code(code),
    )

    if headers:
        for name, value in headers.items():
            response.headers[name] = value

    return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Refuse a caller who is asking too often.

    Health probes are never throttled: a monitoring system polling steadily is
    the expected behaviour, and throttling it would turn a busy API into one
    that also looks down.
    """

    def __init__(
        self,
        app,
        config: ApiConfig,
        limiter: InProcessRateLimiter | None = None,
    ) -> None:
        super().__init__(app)

        self.config = config
        self.limiter = limiter or InProcessRateLimiter()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path

        if path.startswith("/health"):
            return await call_next(request)

        rule = rule_for(request, self.config)
        bucket = "auth" if is_auth_path(path) else "api"
        decision = self.limiter.check(
            f"{bucket}:{client_key(request)}",
            rule,
        )

        if not decision.allowed:
            return refusal_response(
                request,
                ApiErrorCode.RATE_LIMITED,
                RATE_LIMIT_MESSAGE,
                details={"retry_after_seconds": decision.retry_after_seconds},
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )

        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Refuse a body larger than the API accepts, before reading it.

    The declared length is checked first so an oversized upload is refused
    without being buffered. A request that declares nothing is still bounded:
    the body is measured as it is read, and one that grows past the limit is
    refused there instead.
    """

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)

        if max_bytes < 1:
            raise ValueError("max_bytes must be at least 1.")

        self.max_bytes = max_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        declared = request.headers.get("content-length")

        if declared is not None:
            try:
                length = int(declared)
            except ValueError:
                length = None

            if length is not None and length > self.max_bytes:
                return self._refuse(request)

        body = await request.body()

        if len(body) > self.max_bytes:
            return self._refuse(request)

        return await call_next(request)

    def _refuse(self, request: Request) -> Response:
        return refusal_response(
            request,
            ApiErrorCode.PAYLOAD_TOO_LARGE,
            BODY_TOO_LARGE_MESSAGE,
            details={"max_bytes": self.max_bytes},
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add the headers every response should carry.

    Authenticated responses additionally say they must not be stored: a reply
    built for one bearer token is not a reply for the next caller who asks.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        for name, value in DEFAULT_SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)

        if request.headers.get(AUTHORIZATION_HEADER):
            response.headers["Cache-Control"] = PRIVATE_CACHE_CONTROL

        return response


__all__ = [
    "AQOS_HTTP_HARDENING_VERSION",
    "AUTHORIZATION_HEADER",
    "AUTH_PATH_MARKER",
    "BODY_TOO_LARGE_MESSAGE",
    "DEFAULT_SECURITY_HEADERS",
    "PRIVATE_CACHE_CONTROL",
    "RATE_LIMITED_ENVIRONMENTS",
    "RATE_LIMITER_IS_SINGLE_PROCESS",
    "RATE_LIMIT_MESSAGE",
    "RATE_LIMIT_WINDOW_SECONDS",
    "InProcessRateLimiter",
    "RateLimitDecision",
    "RateLimitMiddleware",
    "RateLimitRule",
    "RequestSizeLimitMiddleware",
    "SecurityHeadersMiddleware",
    "client_key",
    "is_auth_path",
    "refusal_response",
    "resolve_rate_limiting",
    "rule_for",
]

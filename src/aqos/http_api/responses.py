from __future__ import annotations

import json
import math
from typing import Any

from starlette.responses import JSONResponse


AQOS_HTTP_RESPONSES_VERSION = "1.0"

#: What a non-finite float becomes on the wire.
#:
#: Sprint 052 settled this for stored payloads; the HTTP layer applies the same
#: rule so a value that cannot be JSON never reaches a client.
NON_FINITE_REPLACEMENT = None


def replace_non_finite(value: Any) -> Any:
    """
    Walk a payload and replace infinity and NaN with null.

    Python's ``json`` writes the bare tokens ``Infinity`` and ``NaN``, which are
    not JSON: a browser or any strict parser rejects them outright. AQOS
    contracts already pair such values with an explicit state field, so dropping
    the number here loses no meaning.
    """

    if isinstance(value, bool):
        return value

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return NON_FINITE_REPLACEMENT

        return value

    if isinstance(value, dict):
        return {key: replace_non_finite(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [replace_non_finite(item) for item in value]

    return value


class SafeJSONResponse(JSONResponse):
    """
    A JSON response that cannot emit invalid JSON.

    Non-finite floats are replaced before encoding and ``allow_nan`` is off, so
    anything the walk missed raises here rather than shipping a payload the
    client cannot parse.
    """

    def render(self, content: Any) -> bytes:
        return json.dumps(
            replace_non_finite(content),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")


def json_response(
    content: Any,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> SafeJSONResponse:
    return SafeJSONResponse(
        content=content,
        status_code=status_code,
        headers=headers,
    )


__all__ = [
    "AQOS_HTTP_RESPONSES_VERSION",
    "NON_FINITE_REPLACEMENT",
    "SafeJSONResponse",
    "json_response",
    "replace_non_finite",
]

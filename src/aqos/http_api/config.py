from __future__ import annotations

import os
from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any, Sequence


AQOS_API_CONFIG_VERSION = "1.0"

API_V1_PREFIX = "/api/v1"

DEFAULT_API_NAME = "AQOS API"
DEFAULT_API_VERSION = "0.53.0-dev"

#: CORS origins allowed when nothing is configured.
#:
#: Local development only. Production has to name its origins explicitly rather
#: than inherit a permissive default.
DEFAULT_DEV_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)

ENV_API_ENV = "AQOS_API_ENV"
ENV_API_NAME = "AQOS_API_NAME"
ENV_API_VERSION = "AQOS_API_VERSION"
ENV_API_CORS_ORIGINS = "AQOS_API_CORS_ORIGINS"
ENV_API_DEBUG = "AQOS_API_DEBUG"
ENV_DB_URL = "AQOS_DB_URL"
ENV_PREDICTION_REGISTRY = "AQOS_API_PREDICTION_REGISTRY"
ENV_MODEL_PROMOTION_REGISTRY = "AQOS_API_MODEL_PROMOTION_REGISTRY"

TRUTHY_VALUES = ("1", "true", "yes", "on")
FALSY_VALUES = ("0", "false", "no", "off")


class ApiEnvironment(str, Enum):
    """Which environment the API believes it is running in."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


#: Environments where a permissive default must never apply.
PROTECTED_API_ENVIRONMENTS = (
    ApiEnvironment.STAGING,
    ApiEnvironment.PRODUCTION,
)


class ApiConfigError(ValueError):
    """Raised when API configuration is invalid."""


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    text = value.strip().lower()

    if text in TRUTHY_VALUES:
        return True

    if text in FALSY_VALUES:
        return False

    raise ApiConfigError(f"Cannot read {value!r} as a boolean.")


def parse_cors_origins(value: str | Sequence[str] | None) -> tuple[str, ...]:
    """
    Read a comma separated origin list.

    ``*`` is preserved as given so the caller can be told it is unsafe later;
    it is never introduced here on the caller's behalf.
    """

    if value is None:
        return ()

    items = value.split(",") if isinstance(value, str) else list(value)

    return tuple(
        origin
        for origin in (str(item).strip() for item in items)
        if origin
    )


def mask_secret(value: str | None) -> str | None:
    """
    Reduce a secret to a shape that is useful in logs but not reusable.

    Returns ``None`` for nothing at all, so "unset" and "hidden" stay
    distinguishable.
    """

    if value is None:
        return None

    if not value.strip():
        return None

    return "***"


def mask_database_url(url: str | None) -> str | None:
    """
    Describe a database URL without its credentials.

    Only the driver survives. Host and database names are useful to an attacker
    and are not needed to answer "is a database configured?".
    """

    if url is None or not url.strip():
        return None

    driver = url.split("://", 1)[0] if "://" in url else "unknown"

    return f"{driver}://***"


@dataclass(frozen=True)
class ApiConfig:
    """
    Settings for one AQOS API application.

    Construction never touches the database or the network, so an app can be
    built and inspected in a test without any infrastructure.
    """

    environment: ApiEnvironment = ApiEnvironment.DEVELOPMENT
    name: str = DEFAULT_API_NAME
    version: str = DEFAULT_API_VERSION
    debug: bool = False
    cors_origins: tuple[str, ...] = DEFAULT_DEV_CORS_ORIGINS
    database_url: str | None = None
    #: Paths to the file-backed model registries.
    #:
    #: Predictions and promotions live in JSON registries on disk rather than in
    #: MySQL. When a path is unset the matching endpoints report that the source
    #: is unavailable instead of inventing an empty result.
    prediction_registry_path: str | None = None
    model_promotion_registry_path: str | None = None
    api_prefix: str = API_V1_PREFIX
    extra_metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ApiConfigError("API name cannot be empty.")

        if not self.version.strip():
            raise ApiConfigError("API version cannot be empty.")

        if not self.api_prefix.startswith("/"):
            raise ApiConfigError("api_prefix must start with '/'.")

        self.assert_cors_is_safe()

    @property
    def is_production(self) -> bool:
        return self.environment == ApiEnvironment.PRODUCTION

    @property
    def has_database(self) -> bool:
        return bool(self.database_url and self.database_url.strip())

    @property
    def has_prediction_registry(self) -> bool:
        return bool(
            self.prediction_registry_path
            and self.prediction_registry_path.strip()
        )

    @property
    def has_model_promotion_registry(self) -> bool:
        return bool(
            self.model_promotion_registry_path
            and self.model_promotion_registry_path.strip()
        )

    @property
    def allows_any_origin(self) -> bool:
        return "*" in self.cors_origins

    def assert_cors_is_safe(self) -> None:
        """
        A wildcard origin must never be reachable outside development.

        Staging and production have to name their origins; inheriting a
        permissive default is exactly how a browser-facing API gets opened up by
        accident.
        """

        if not self.allows_any_origin:
            return

        if self.environment in PROTECTED_API_ENVIRONMENTS:
            raise ApiConfigError(
                f"CORS origin '*' is not allowed in "
                f"{self.environment.value}; name the allowed origins."
            )

    def to_dict(self) -> dict[str, Any]:
        """
        Describe the configuration without leaking anything secret.

        The database URL is reduced to its driver: enough to see that a database
        is configured, not enough to connect to it.
        """

        return {
            "environment": self.environment.value,
            "name": self.name,
            "version": self.version,
            "debug": self.debug,
            "cors_origins": list(self.cors_origins),
            "allows_any_origin": self.allows_any_origin,
            "api_prefix": self.api_prefix,
            "has_database": self.has_database,
            "database_url": mask_database_url(self.database_url),
            # Only whether a registry is configured, never where it lives: a
            # server-side path tells a client nothing useful and an attacker
            # something about the filesystem.
            "has_prediction_registry": self.has_prediction_registry,
            "has_model_promotion_registry": self.has_model_promotion_registry,
            "metadata": self.extra_metadata,
        }


def load_api_config_from_env(
    environ: dict[str, str] | None = None,
) -> ApiConfig:
    """Build a config from the environment, applying safe defaults."""

    source = dict(os.environ if environ is None else environ)

    raw_environment = (source.get(ENV_API_ENV) or "").strip().lower()

    try:
        environment = (
            ApiEnvironment(raw_environment)
            if raw_environment
            else ApiEnvironment.DEVELOPMENT
        )
    except ValueError as error:
        raise ApiConfigError(
            f"Unknown {ENV_API_ENV}: {raw_environment!r}. Valid values are: "
            + ", ".join(item.value for item in ApiEnvironment)
        ) from error

    origins = parse_cors_origins(source.get(ENV_API_CORS_ORIGINS))

    if not origins:
        # Only development inherits a default; anything else must be explicit.
        origins = (
            DEFAULT_DEV_CORS_ORIGINS
            if environment
            in (ApiEnvironment.DEVELOPMENT, ApiEnvironment.TEST)
            else ()
        )

    return ApiConfig(
        environment=environment,
        name=(source.get(ENV_API_NAME) or DEFAULT_API_NAME).strip(),
        version=(source.get(ENV_API_VERSION) or DEFAULT_API_VERSION).strip(),
        debug=parse_bool(source.get(ENV_API_DEBUG), default=False),
        cors_origins=origins,
        database_url=(source.get(ENV_DB_URL) or None),
        prediction_registry_path=(source.get(ENV_PREDICTION_REGISTRY) or None),
        model_promotion_registry_path=(
            source.get(ENV_MODEL_PROMOTION_REGISTRY) or None
        ),
    )


__all__ = [
    "API_V1_PREFIX",
    "AQOS_API_CONFIG_VERSION",
    "ApiConfig",
    "ApiConfigError",
    "ApiEnvironment",
    "DEFAULT_API_NAME",
    "DEFAULT_API_VERSION",
    "DEFAULT_DEV_CORS_ORIGINS",
    "ENV_API_CORS_ORIGINS",
    "ENV_API_DEBUG",
    "ENV_API_ENV",
    "ENV_API_NAME",
    "ENV_API_VERSION",
    "ENV_DB_URL",
    "ENV_MODEL_PROMOTION_REGISTRY",
    "ENV_PREDICTION_REGISTRY",
    "PROTECTED_API_ENVIRONMENTS",
    "load_api_config_from_env",
    "mask_database_url",
    "mask_secret",
    "parse_bool",
    "parse_cors_origins",
]

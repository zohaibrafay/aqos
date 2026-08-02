from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote_plus, urlparse


AQOS_DATABASE_CONFIG_VERSION = "1.0"

DEFAULT_MYSQL_DRIVER = "mysql+pymysql"
DEFAULT_MYSQL_PORT = 3306
DEFAULT_MYSQL_CHARSET = "utf8mb4"
DEFAULT_POOL_SIZE = 5
DEFAULT_MAX_OVERFLOW = 10
DEFAULT_POOL_RECYCLE_SECONDS = 1800

#: Drivers AQOS is allowed to run against. AQOS is a MySQL-first platform.
SUPPORTED_MYSQL_DRIVERS = (
    "mysql+pymysql",
    "mysql+mysqldb",
    "mysql+mysqlconnector",
)

ENV_DB_URL = "AQOS_DB_URL"
ENV_DB_HOST = "AQOS_DB_HOST"
ENV_DB_PORT = "AQOS_DB_PORT"
ENV_DB_NAME = "AQOS_DB_NAME"
ENV_DB_USER = "AQOS_DB_USER"
ENV_DB_PASSWORD = "AQOS_DB_PASSWORD"
ENV_DB_DRIVER = "AQOS_DB_DRIVER"
ENV_DB_CHARSET = "AQOS_DB_CHARSET"
ENV_DB_POOL_SIZE = "AQOS_DB_POOL_SIZE"
ENV_DB_MAX_OVERFLOW = "AQOS_DB_MAX_OVERFLOW"
ENV_DB_POOL_RECYCLE = "AQOS_DB_POOL_RECYCLE"
ENV_DB_ECHO_SQL = "AQOS_DB_ECHO_SQL"

MASKED_PASSWORD = "***"

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_$-]+$")


def validate_mysql_driver(driver: str) -> str:
    clean_driver = driver.strip().lower()

    if not clean_driver:
        raise ValueError("driver cannot be empty.")

    if clean_driver.startswith("sqlite"):
        raise ValueError(
            "AQOS does not support SQLite as an application database. "
            "Use a MySQL driver."
        )

    if clean_driver not in SUPPORTED_MYSQL_DRIVERS:
        raise ValueError(
            f"Unsupported database driver: {driver}. "
            f"Supported drivers are: {', '.join(SUPPORTED_MYSQL_DRIVERS)}"
        )

    return clean_driver


def validate_database_identifier(value: str, field_name: str) -> str:
    clean_value = value.strip()

    if not clean_value:
        raise ValueError(f"{field_name} cannot be empty.")

    if not IDENTIFIER_PATTERN.match(clean_value):
        raise ValueError(
            f"{field_name} may only contain letters, numbers, underscores, "
            "hyphens and dollar signs."
        )

    return clean_value


@dataclass(frozen=True)
class MySQLDatabaseConfig:
    """
    Connection settings for the AQOS MySQL database.

    The password is never rendered by ``to_dict`` or ``safe_url``; only
    ``url`` contains it, and that value is meant for SQLAlchemy alone.
    """

    host: str
    database: str
    user: str
    password: str = ""
    port: int = DEFAULT_MYSQL_PORT
    driver: str = DEFAULT_MYSQL_DRIVER
    charset: str = DEFAULT_MYSQL_CHARSET
    pool_size: int = DEFAULT_POOL_SIZE
    max_overflow: int = DEFAULT_MAX_OVERFLOW
    pool_recycle_seconds: int = DEFAULT_POOL_RECYCLE_SECONDS
    pool_pre_ping: bool = True
    echo_sql: bool = False

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("host cannot be empty.")

        if not self.user.strip():
            raise ValueError("user cannot be empty.")

        validate_database_identifier(self.database, "database")
        validate_mysql_driver(self.driver)

        if not 1 <= self.port <= 65_535:
            raise ValueError("port must be between 1 and 65535.")

        if not self.charset.strip():
            raise ValueError("charset cannot be empty.")

        if self.pool_size < 1:
            raise ValueError("pool_size must be at least 1.")

        if self.max_overflow < 0:
            raise ValueError("max_overflow cannot be negative.")

        if self.pool_recycle_seconds < 1:
            raise ValueError("pool_recycle_seconds must be at least 1.")

    @property
    def normalized_driver(self) -> str:
        return validate_mysql_driver(self.driver)

    def url(self) -> str:
        return build_database_url(
            driver=self.normalized_driver,
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            charset=self.charset,
        )

    def safe_url(self) -> str:
        return mask_database_url(self.url())

    def engine_options(self) -> dict[str, Any]:
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_recycle": self.pool_recycle_seconds,
            "pool_pre_ping": self.pool_pre_ping,
            "echo": self.echo_sql,
            "future": True,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "driver": self.normalized_driver,
            "charset": self.charset,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_recycle_seconds": self.pool_recycle_seconds,
            "pool_pre_ping": self.pool_pre_ping,
            "echo_sql": self.echo_sql,
            "safe_url": self.safe_url(),
        }


def build_database_url(
    driver: str,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str = "",
    charset: str = DEFAULT_MYSQL_CHARSET,
) -> str:
    normalized_driver = validate_mysql_driver(driver)

    credentials = quote_plus(user)

    if password:
        credentials = f"{credentials}:{quote_plus(password)}"

    return (
        f"{normalized_driver}://{credentials}@{host}:{port}/{database}"
        f"?charset={charset}"
    )


def mask_database_url(url: str) -> str:
    """Replace the password in a database URL so it is safe to log."""

    if "@" not in url:
        return url

    scheme_separator = "://"

    if scheme_separator not in url:
        return url

    scheme, remainder = url.split(scheme_separator, 1)
    credentials, host_part = remainder.rsplit("@", 1)

    if ":" not in credentials:
        return url

    user, _ = credentials.split(":", 1)

    return f"{scheme}{scheme_separator}{user}:{MASKED_PASSWORD}@{host_part}"


def parse_database_url(url: str) -> MySQLDatabaseConfig:
    clean_url = url.strip()

    if not clean_url:
        raise ValueError("Database URL cannot be empty.")

    parsed = urlparse(clean_url)

    driver = validate_mysql_driver(parsed.scheme)

    if not parsed.hostname:
        raise ValueError("Database URL must contain a host.")

    if not parsed.username:
        raise ValueError("Database URL must contain a user.")

    database = (parsed.path or "").lstrip("/")

    if not database:
        raise ValueError("Database URL must contain a database name.")

    charset = DEFAULT_MYSQL_CHARSET

    for pair in (parsed.query or "").split("&"):
        if pair.startswith("charset="):
            charset = pair.split("=", 1)[1] or DEFAULT_MYSQL_CHARSET

    return MySQLDatabaseConfig(
        host=parsed.hostname,
        port=parsed.port or DEFAULT_MYSQL_PORT,
        database=database,
        user=parsed.username,
        password=parsed.password or "",
        driver=driver,
        charset=charset,
    )


def read_env_int(
    env: Mapping[str, str],
    key: str,
    default: int,
) -> int:
    raw_value = env.get(key)

    if raw_value is None or not raw_value.strip():
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer.") from exc


def read_env_bool(
    env: Mapping[str, str],
    key: str,
    default: bool,
) -> bool:
    raw_value = env.get(key)

    if raw_value is None or not raw_value.strip():
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def load_database_config_from_env(
    env: Mapping[str, str] | None = None,
) -> MySQLDatabaseConfig:
    """
    Build the database configuration from the environment.

    ``AQOS_DB_URL`` wins when present; otherwise the discrete ``AQOS_DB_*``
    values are used.
    """

    environment = env if env is not None else os.environ

    pool_settings = {
        "pool_size": read_env_int(environment, ENV_DB_POOL_SIZE, DEFAULT_POOL_SIZE),
        "max_overflow": read_env_int(
            environment,
            ENV_DB_MAX_OVERFLOW,
            DEFAULT_MAX_OVERFLOW,
        ),
        "pool_recycle_seconds": read_env_int(
            environment,
            ENV_DB_POOL_RECYCLE,
            DEFAULT_POOL_RECYCLE_SECONDS,
        ),
        "echo_sql": read_env_bool(environment, ENV_DB_ECHO_SQL, False),
    }

    database_url = environment.get(ENV_DB_URL, "").strip()

    if database_url:
        parsed = parse_database_url(database_url)

        return MySQLDatabaseConfig(
            host=parsed.host,
            port=parsed.port,
            database=parsed.database,
            user=parsed.user,
            password=parsed.password,
            driver=parsed.driver,
            charset=parsed.charset,
            **pool_settings,
        )

    missing = [
        key
        for key in (ENV_DB_HOST, ENV_DB_NAME, ENV_DB_USER)
        if not environment.get(key, "").strip()
    ]

    if missing:
        raise ValueError(
            "Missing required AQOS database environment variables: "
            + ", ".join(missing)
        )

    return MySQLDatabaseConfig(
        host=environment[ENV_DB_HOST].strip(),
        port=read_env_int(environment, ENV_DB_PORT, DEFAULT_MYSQL_PORT),
        database=environment[ENV_DB_NAME].strip(),
        user=environment[ENV_DB_USER].strip(),
        password=environment.get(ENV_DB_PASSWORD, ""),
        driver=environment.get(ENV_DB_DRIVER, DEFAULT_MYSQL_DRIVER).strip()
        or DEFAULT_MYSQL_DRIVER,
        charset=environment.get(ENV_DB_CHARSET, DEFAULT_MYSQL_CHARSET).strip()
        or DEFAULT_MYSQL_CHARSET,
        **pool_settings,
    )


__all__ = [
    "AQOS_DATABASE_CONFIG_VERSION",
    "DEFAULT_MAX_OVERFLOW",
    "DEFAULT_MYSQL_CHARSET",
    "DEFAULT_MYSQL_DRIVER",
    "DEFAULT_MYSQL_PORT",
    "DEFAULT_POOL_RECYCLE_SECONDS",
    "DEFAULT_POOL_SIZE",
    "ENV_DB_CHARSET",
    "ENV_DB_DRIVER",
    "ENV_DB_ECHO_SQL",
    "ENV_DB_HOST",
    "ENV_DB_MAX_OVERFLOW",
    "ENV_DB_NAME",
    "ENV_DB_PASSWORD",
    "ENV_DB_POOL_RECYCLE",
    "ENV_DB_POOL_SIZE",
    "ENV_DB_PORT",
    "ENV_DB_URL",
    "ENV_DB_USER",
    "MASKED_PASSWORD",
    "MySQLDatabaseConfig",
    "SUPPORTED_MYSQL_DRIVERS",
    "build_database_url",
    "load_database_config_from_env",
    "mask_database_url",
    "parse_database_url",
    "read_env_bool",
    "read_env_int",
    "validate_database_identifier",
    "validate_mysql_driver",
]

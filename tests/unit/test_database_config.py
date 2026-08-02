from __future__ import annotations

import pytest

from aqos.database.config import (
    AQOS_DATABASE_CONFIG_VERSION,
    DEFAULT_MYSQL_CHARSET,
    DEFAULT_MYSQL_DRIVER,
    DEFAULT_MYSQL_PORT,
    ENV_DB_ECHO_SQL,
    ENV_DB_HOST,
    ENV_DB_NAME,
    ENV_DB_PASSWORD,
    ENV_DB_POOL_SIZE,
    ENV_DB_PORT,
    ENV_DB_URL,
    ENV_DB_USER,
    MASKED_PASSWORD,
    MySQLDatabaseConfig,
    build_database_url,
    load_database_config_from_env,
    mask_database_url,
    parse_database_url,
    read_env_bool,
    read_env_int,
    validate_database_identifier,
    validate_mysql_driver,
)


def build_config(**overrides) -> MySQLDatabaseConfig:
    payload = {
        "host": "db.internal",
        "database": "aqos",
        "user": "aqos_app",
        "password": "s3cret",
    }
    payload.update(overrides)

    return MySQLDatabaseConfig(**payload)


def test_config_version_is_exposed() -> None:
    assert AQOS_DATABASE_CONFIG_VERSION == "1.0"


def test_validate_mysql_driver_accepts_supported_drivers() -> None:
    assert validate_mysql_driver("mysql+pymysql") == "mysql+pymysql"
    assert validate_mysql_driver(" MySQL+PyMySQL ") == "mysql+pymysql"
    assert validate_mysql_driver("mysql+mysqldb") == "mysql+mysqldb"


def test_validate_mysql_driver_rejects_sqlite() -> None:
    with pytest.raises(ValueError, match="does not support SQLite"):
        validate_mysql_driver("sqlite")

    with pytest.raises(ValueError, match="does not support SQLite"):
        validate_mysql_driver("sqlite+pysqlite")


def test_validate_mysql_driver_rejects_other_engines() -> None:
    with pytest.raises(ValueError, match="Unsupported database driver"):
        validate_mysql_driver("postgresql+psycopg")

    with pytest.raises(ValueError, match="driver cannot be empty"):
        validate_mysql_driver("   ")


def test_validate_database_identifier() -> None:
    assert validate_database_identifier(" aqos_prod ", "database") == "aqos_prod"

    with pytest.raises(ValueError, match="database cannot be empty"):
        validate_database_identifier("  ", "database")

    with pytest.raises(ValueError, match="may only contain"):
        validate_database_identifier("aqos;DROP TABLE users", "database")


def test_config_defaults() -> None:
    config = build_config()

    assert config.port == DEFAULT_MYSQL_PORT
    assert config.driver == DEFAULT_MYSQL_DRIVER
    assert config.charset == DEFAULT_MYSQL_CHARSET
    assert config.pool_pre_ping is True
    assert config.echo_sql is False


def test_config_validation() -> None:
    with pytest.raises(ValueError, match="host cannot be empty"):
        build_config(host="  ")

    with pytest.raises(ValueError, match="user cannot be empty"):
        build_config(user="")

    with pytest.raises(ValueError, match="database cannot be empty"):
        build_config(database="  ")

    with pytest.raises(ValueError, match="port must be between"):
        build_config(port=0)

    with pytest.raises(ValueError, match="port must be between"):
        build_config(port=70_000)

    with pytest.raises(ValueError, match="charset cannot be empty"):
        build_config(charset=" ")

    with pytest.raises(ValueError, match="pool_size must be at least 1"):
        build_config(pool_size=0)

    with pytest.raises(ValueError, match="max_overflow cannot be negative"):
        build_config(max_overflow=-1)

    with pytest.raises(ValueError, match="pool_recycle_seconds must be at least 1"):
        build_config(pool_recycle_seconds=0)


def test_config_rejects_sqlite_driver() -> None:
    with pytest.raises(ValueError, match="does not support SQLite"):
        build_config(driver="sqlite+pysqlite")


def test_build_database_url() -> None:
    url = build_database_url(
        driver="mysql+pymysql",
        host="db.internal",
        port=3307,
        database="aqos",
        user="aqos_app",
        password="s3cret",
    )

    assert url == "mysql+pymysql://aqos_app:s3cret@db.internal:3307/aqos?charset=utf8mb4"


def test_build_database_url_escapes_credentials() -> None:
    url = build_database_url(
        driver="mysql+pymysql",
        host="db.internal",
        port=3306,
        database="aqos",
        user="aqos app",
        password="p@ss:word/1",
    )

    assert "aqos+app" in url
    assert "p%40ss%3Aword%2F1" in url


def test_build_database_url_without_password() -> None:
    url = build_database_url(
        driver="mysql+pymysql",
        host="localhost",
        port=3306,
        database="aqos",
        user="root",
    )

    assert url.startswith("mysql+pymysql://root@localhost")


def test_config_url_and_safe_url() -> None:
    config = build_config()

    assert config.url().startswith("mysql+pymysql://aqos_app:s3cret@")
    assert config.safe_url() == (
        f"mysql+pymysql://aqos_app:{MASKED_PASSWORD}@db.internal:3306/aqos"
        "?charset=utf8mb4"
    )


def test_mask_database_url_handles_edge_cases() -> None:
    assert mask_database_url("mysql+pymysql://user@host:3306/db") == (
        "mysql+pymysql://user@host:3306/db"
    )
    assert mask_database_url("not-a-url") == "not-a-url"
    assert mask_database_url("mysql+pymysql://host/db") == "mysql+pymysql://host/db"


def test_config_dict_never_contains_the_password() -> None:
    payload = build_config().to_dict()

    assert "password" not in payload
    assert "s3cret" not in str(payload)
    assert payload["safe_url"].count(MASKED_PASSWORD) == 1
    assert payload["driver"] == "mysql+pymysql"


def test_engine_options() -> None:
    options = build_config(pool_size=9, max_overflow=3, echo_sql=True).engine_options()

    assert options["pool_size"] == 9
    assert options["max_overflow"] == 3
    assert options["pool_pre_ping"] is True
    assert options["echo"] is True
    assert options["future"] is True


def test_parse_database_url() -> None:
    config = parse_database_url(
        "mysql+pymysql://aqos_app:s3cret@db.internal:3307/aqos_prod?charset=utf8mb4"
    )

    assert config.host == "db.internal"
    assert config.port == 3307
    assert config.database == "aqos_prod"
    assert config.user == "aqos_app"
    assert config.password == "s3cret"
    assert config.charset == "utf8mb4"


def test_parse_database_url_defaults_port_and_charset() -> None:
    config = parse_database_url("mysql+pymysql://aqos_app:pw@db.internal/aqos")

    assert config.port == DEFAULT_MYSQL_PORT
    assert config.charset == DEFAULT_MYSQL_CHARSET


def test_parse_database_url_rejects_bad_values() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        parse_database_url("   ")

    with pytest.raises(ValueError, match="does not support SQLite"):
        parse_database_url("sqlite:///aqos.db")

    with pytest.raises(ValueError, match="must contain a database name"):
        parse_database_url("mysql+pymysql://user:pw@host:3306/")

    with pytest.raises(ValueError, match="must contain a user"):
        parse_database_url("mysql+pymysql://host:3306/aqos")


def test_read_env_int() -> None:
    assert read_env_int({}, "MISSING", 7) == 7
    assert read_env_int({"VALUE": "  "}, "VALUE", 7) == 7
    assert read_env_int({"VALUE": "12"}, "VALUE", 7) == 12

    with pytest.raises(ValueError, match="must be an integer"):
        read_env_int({"VALUE": "many"}, "VALUE", 7)


def test_read_env_bool() -> None:
    assert read_env_bool({}, "MISSING", True) is True
    assert read_env_bool({"FLAG": "1"}, "FLAG", False) is True
    assert read_env_bool({"FLAG": "TRUE"}, "FLAG", False) is True
    assert read_env_bool({"FLAG": "no"}, "FLAG", True) is False


def test_load_config_from_discrete_env_values() -> None:
    config = load_database_config_from_env(
        {
            ENV_DB_HOST: "db.internal",
            ENV_DB_PORT: "3307",
            ENV_DB_NAME: "aqos_prod",
            ENV_DB_USER: "aqos_app",
            ENV_DB_PASSWORD: "s3cret",
            ENV_DB_POOL_SIZE: "12",
            ENV_DB_ECHO_SQL: "true",
        }
    )

    assert config.host == "db.internal"
    assert config.port == 3307
    assert config.database == "aqos_prod"
    assert config.pool_size == 12
    assert config.echo_sql is True


def test_load_config_prefers_database_url() -> None:
    config = load_database_config_from_env(
        {
            ENV_DB_URL: "mysql+pymysql://url_user:pw@url-host:3306/url_db",
            ENV_DB_HOST: "ignored",
            ENV_DB_NAME: "ignored",
            ENV_DB_USER: "ignored",
        }
    )

    assert config.host == "url-host"
    assert config.database == "url_db"
    assert config.user == "url_user"


def test_load_config_reports_missing_variables() -> None:
    with pytest.raises(ValueError, match="Missing required AQOS database"):
        load_database_config_from_env({ENV_DB_HOST: "db.internal"})


def test_load_config_rejects_sqlite_url() -> None:
    with pytest.raises(ValueError, match="does not support SQLite"):
        load_database_config_from_env({ENV_DB_URL: "sqlite:///aqos.db"})

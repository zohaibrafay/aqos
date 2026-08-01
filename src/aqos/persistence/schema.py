from __future__ import annotations

from typing import Any

from aqos.persistence.database import AqosDatabase


AQOS_SCHEMA_VERSION = 6


USER_PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    locale TEXT NOT NULL DEFAULT 'en',
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
"""

USER_PROFILES_EMAIL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_user_profiles_email
ON user_profiles (email);
"""

USER_PROFILES_STATUS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_user_profiles_status
ON user_profiles (status);
"""


USER_CREDENTIALS_TABLE = """
CREATE TABLE IF NOT EXISTS user_credentials (
    user_id TEXT PRIMARY KEY
        REFERENCES user_profiles (user_id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    failed_attempt_count INTEGER NOT NULL DEFAULT 0,
    locked_until_utc TEXT,
    last_login_at_utc TEXT,
    password_updated_at_utc TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
"""

USER_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL
        REFERENCES user_profiles (user_id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_at_utc TEXT NOT NULL,
    expires_at_utc TEXT NOT NULL,
    revoked_at_utc TEXT,
    last_seen_at_utc TEXT,
    client_label TEXT,
    metadata TEXT NOT NULL DEFAULT '{}'
);
"""

USER_SESSIONS_USER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_user_sessions_user
ON user_sessions (user_id);
"""

USER_PREFERENCES_TABLE = """
CREATE TABLE IF NOT EXISTS user_preferences (
    preferences_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE
        REFERENCES user_profiles (user_id) ON DELETE CASCADE,
    theme TEXT NOT NULL DEFAULT 'system',
    default_currency TEXT NOT NULL DEFAULT 'USD',
    date_format TEXT NOT NULL DEFAULT 'YYYY-MM-DD',
    landing_page TEXT NOT NULL DEFAULT 'dashboard',
    notification_channels TEXT NOT NULL DEFAULT '[]',
    email_notifications_enabled INTEGER NOT NULL DEFAULT 1,
    push_notifications_enabled INTEGER NOT NULL DEFAULT 1,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
"""


TRADING_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS trading_settings (
    settings_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE
        REFERENCES user_profiles (user_id) ON DELETE CASCADE,
    execution_mode TEXT NOT NULL DEFAULT 'signal_only',
    risk_per_trade_fraction REAL NOT NULL,
    max_daily_loss_fraction REAL NOT NULL,
    max_open_positions INTEGER NOT NULL,
    max_daily_trades INTEGER NOT NULL,
    default_timeframe TEXT NOT NULL,
    allow_short INTEGER NOT NULL DEFAULT 1,
    allow_hedging INTEGER NOT NULL DEFAULT 0,
    notifications_enabled INTEGER NOT NULL DEFAULT 1,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
"""

SYMBOL_PREFERENCES_TABLE = """
CREATE TABLE IF NOT EXISTS symbol_preferences (
    preference_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL
        REFERENCES user_profiles (user_id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    UNIQUE (user_id, symbol, kind)
);
"""

SYMBOL_PREFERENCES_USER_KIND_INDEX = """
CREATE INDEX IF NOT EXISTS idx_symbol_preferences_user_kind
ON symbol_preferences (user_id, kind);
"""


TRADING_ACCOUNTS_TABLE = """
CREATE TABLE IF NOT EXISTS trading_accounts (
    account_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL
        REFERENCES user_profiles (user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL,
    broker TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    initial_balance REAL NOT NULL,
    current_balance REAL NOT NULL,
    equity REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    execution_mode TEXT NOT NULL DEFAULT 'signal_only',
    auto_trade_enabled INTEGER NOT NULL DEFAULT 0,
    is_default INTEGER NOT NULL DEFAULT 0,
    leverage INTEGER NOT NULL DEFAULT 1,
    broker_account_ref TEXT,
    broker_credential_ref TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    UNIQUE (user_id, name)
);
"""

TRADING_ACCOUNTS_USER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_trading_accounts_user
ON trading_accounts (user_id, status);
"""


FUNDED_ACCOUNT_RULES_TABLE = """
CREATE TABLE IF NOT EXISTS funded_account_rules (
    rules_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL UNIQUE
        REFERENCES trading_accounts (account_id) ON DELETE CASCADE,
    max_total_drawdown_fraction REAL NOT NULL,
    max_daily_loss_fraction REAL NOT NULL,
    max_risk_per_trade_fraction REAL NOT NULL,
    profit_target_fraction REAL NOT NULL,
    drawdown_basis TEXT NOT NULL DEFAULT 'static_initial',
    min_trading_days INTEGER NOT NULL DEFAULT 0,
    max_lot_size REAL NOT NULL,
    min_lot_size REAL NOT NULL,
    max_open_positions INTEGER NOT NULL,
    news_restriction_enabled INTEGER NOT NULL DEFAULT 1,
    news_blackout_minutes_before INTEGER NOT NULL DEFAULT 2,
    news_blackout_minutes_after INTEGER NOT NULL DEFAULT 2,
    weekend_holding_allowed INTEGER NOT NULL DEFAULT 0,
    consistency_fraction REAL,
    allowed_symbols TEXT NOT NULL DEFAULT '[]',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
"""


TRADING_SIGNALS_TABLE = """
CREATE TABLE IF NOT EXISTS trading_signals (
    signal_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL
        REFERENCES user_profiles (user_id) ON DELETE CASCADE,
    account_id TEXT
        REFERENCES trading_accounts (account_id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    action TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL,
    entry_price REAL,
    stop_loss REAL,
    take_profit REAL,
    generated_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    expires_at_utc TEXT,
    source_ref TEXT,
    model_id TEXT,
    model_version TEXT,
    status_reason TEXT,
    metadata TEXT NOT NULL DEFAULT '{}'
);
"""

TRADING_SIGNALS_LOOKUP_INDEX = """
CREATE INDEX IF NOT EXISTS idx_trading_signals_lookup
ON trading_signals (user_id, status, generated_at_utc);
"""

TRADING_SIGNALS_ACCOUNT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_trading_signals_account
ON trading_signals (account_id, generated_at_utc);
"""

SIGNAL_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS signal_events (
    event_id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL
        REFERENCES trading_signals (signal_id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    occurred_at_utc TEXT NOT NULL,
    reason TEXT,
    actor TEXT,
    metadata TEXT NOT NULL DEFAULT '{}'
);
"""

SIGNAL_EVENTS_SIGNAL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_signal_events_signal
ON signal_events (signal_id, occurred_at_utc);
"""


AQOS_SCHEMA_STATEMENTS: tuple[str, ...] = (
    USER_PROFILES_TABLE,
    USER_PROFILES_EMAIL_INDEX,
    USER_PROFILES_STATUS_INDEX,
    USER_CREDENTIALS_TABLE,
    USER_SESSIONS_TABLE,
    USER_SESSIONS_USER_INDEX,
    USER_PREFERENCES_TABLE,
    TRADING_SETTINGS_TABLE,
    SYMBOL_PREFERENCES_TABLE,
    SYMBOL_PREFERENCES_USER_KIND_INDEX,
    TRADING_ACCOUNTS_TABLE,
    TRADING_ACCOUNTS_USER_INDEX,
    FUNDED_ACCOUNT_RULES_TABLE,
    TRADING_SIGNALS_TABLE,
    TRADING_SIGNALS_LOOKUP_INDEX,
    TRADING_SIGNALS_ACCOUNT_INDEX,
    SIGNAL_EVENTS_TABLE,
    SIGNAL_EVENTS_SIGNAL_INDEX,
)

AQOS_SCHEMA_TABLES: tuple[str, ...] = (
    "user_profiles",
    "user_credentials",
    "user_sessions",
    "user_preferences",
    "trading_settings",
    "symbol_preferences",
    "trading_accounts",
    "funded_account_rules",
    "trading_signals",
    "signal_events",
)


def apply_aqos_schema(
    database: AqosDatabase,
    statements: tuple[str, ...] = AQOS_SCHEMA_STATEMENTS,
    schema_version: int = AQOS_SCHEMA_VERSION,
) -> int:
    """
    Create every AQOS table that does not exist yet and stamp the schema version.
    """

    with database.transaction():
        for statement in statements:
            database.execute(statement)

    database.set_user_version(schema_version)

    return schema_version


def read_aqos_schema_version(database: AqosDatabase) -> int:
    return database.user_version()


def is_aqos_schema_current(database: AqosDatabase) -> bool:
    return read_aqos_schema_version(database) == AQOS_SCHEMA_VERSION


def list_missing_aqos_tables(
    database: AqosDatabase,
    expected_tables: tuple[str, ...] = AQOS_SCHEMA_TABLES,
) -> tuple[str, ...]:
    existing = set(database.list_tables())

    return tuple(table for table in expected_tables if table not in existing)


def ensure_aqos_schema(database: AqosDatabase) -> int:
    """
    Apply the schema when it is missing or out of date, then return the version.
    """

    if is_aqos_schema_current(database) and not list_missing_aqos_tables(database):
        return read_aqos_schema_version(database)

    return apply_aqos_schema(database)


def describe_aqos_schema(database: AqosDatabase) -> dict[str, Any]:
    return {
        "schema_version": read_aqos_schema_version(database),
        "expected_schema_version": AQOS_SCHEMA_VERSION,
        "is_current": is_aqos_schema_current(database),
        "tables": list(database.list_tables()),
        "missing_tables": list(list_missing_aqos_tables(database)),
    }


__all__ = [
    "AQOS_SCHEMA_STATEMENTS",
    "AQOS_SCHEMA_TABLES",
    "AQOS_SCHEMA_VERSION",
    "FUNDED_ACCOUNT_RULES_TABLE",
    "SIGNAL_EVENTS_SIGNAL_INDEX",
    "SIGNAL_EVENTS_TABLE",
    "SYMBOL_PREFERENCES_TABLE",
    "SYMBOL_PREFERENCES_USER_KIND_INDEX",
    "TRADING_ACCOUNTS_TABLE",
    "TRADING_ACCOUNTS_USER_INDEX",
    "TRADING_SETTINGS_TABLE",
    "TRADING_SIGNALS_ACCOUNT_INDEX",
    "TRADING_SIGNALS_LOOKUP_INDEX",
    "TRADING_SIGNALS_TABLE",
    "USER_CREDENTIALS_TABLE",
    "USER_PREFERENCES_TABLE",
    "USER_PROFILES_EMAIL_INDEX",
    "USER_PROFILES_STATUS_INDEX",
    "USER_PROFILES_TABLE",
    "USER_SESSIONS_TABLE",
    "USER_SESSIONS_USER_INDEX",
    "apply_aqos_schema",
    "describe_aqos_schema",
    "ensure_aqos_schema",
    "is_aqos_schema_current",
    "list_missing_aqos_tables",
    "read_aqos_schema_version",
]

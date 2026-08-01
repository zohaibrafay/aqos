from __future__ import annotations

import aqos.persistence as persistence


EXPECTED_EXPORTS = (
    "AQOS_DATABASE_VERSION",
    "AQOS_RECORDS_VERSION",
    "AQOS_SCHEMA_VERSION",
    "AQOS_USER_PROFILE_VERSION",
    "AQOS_ACCOUNTS_VERSION",
    "AQOS_AUTH_VERSION",
    "AQOS_SIGNALS_VERSION",
    "AQOS_SIGNAL_REASONS_VERSION",
    "SignalOutcome",
    "SignalOutcomeRepository",
    "SignalReasonCategory",
    "SignalReasonCode",
    "SignalReasonSummary",
    "reject_signal_with_reason",
    "SignalAction",
    "SignalEvent",
    "SignalSource",
    "SignalStatus",
    "TradingSignal",
    "TradingSignalRepository",
    "can_transition_signal",
    "validate_signal_transition",
    "AQOS_FUNDED_RULES_VERSION",
    "DrawdownBasis",
    "FundedAccountRules",
    "FundedAccountRulesRepository",
    "FundedAccountState",
    "FundedPayoutStatus",
    "FundedRuleCheck",
    "FundedTradeRequest",
    "evaluate_funded_rules",
    "AccountStatus",
    "AccountType",
    "BrokerKind",
    "TradingAccount",
    "TradingAccountRepository",
    "resolve_account_execution_mode",
    "AQOS_PASSWORDS_VERSION",
    "AQOS_SYMBOL_PREFERENCES_VERSION",
    "AQOS_TRADING_SETTINGS_VERSION",
    "AQOS_USER_PREFERENCES_VERSION",
    "AqosDatabase",
    "AqosDatabaseConfig",
    "AuthenticationOutcome",
    "AuthenticationResult",
    "ExecutionMode",
    "IN_MEMORY_DATABASE",
    "IssuedSession",
    "NotificationChannel",
    "PasswordHash",
    "SymbolPreference",
    "SymbolPreferenceKind",
    "SymbolPreferenceRepository",
    "TradingSettings",
    "TradingSettingsRepository",
    "UserCredential",
    "UserCredentialRepository",
    "UserPreferences",
    "UserPreferencesRepository",
    "UserSession",
    "UserSessionRepository",
    "hash_password",
    "mask_secret",
    "verify_password",
    "UserProfile",
    "UserProfileRepository",
    "UserRole",
    "UserStatus",
    "apply_aqos_schema",
    "build_record_id",
    "decode_json_field",
    "describe_aqos_schema",
    "encode_json_field",
    "ensure_aqos_schema",
    "normalize_email",
    "normalize_symbol",
    "open_aqos_database",
    "record_utc_now",
)


def test_expected_symbols_are_exported() -> None:
    for name in EXPECTED_EXPORTS:
        assert name in persistence.__all__
        assert hasattr(persistence, name)


def test_all_entries_are_importable() -> None:
    for name in persistence.__all__:
        assert hasattr(persistence, name), name


def test_all_has_no_duplicates() -> None:
    assert len(persistence.__all__) == len(set(persistence.__all__))

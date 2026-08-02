-- AQOS user-level trading settings and symbol preferences.

CREATE TABLE IF NOT EXISTS trading_settings (
    settings_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    execution_mode VARCHAR(32) NOT NULL DEFAULT 'signal_only',
    risk_per_trade_fraction DECIMAL(9,6) NOT NULL DEFAULT 0.010000,
    max_daily_loss_fraction DECIMAL(9,6) NOT NULL DEFAULT 0.050000,
    max_open_positions INT NOT NULL DEFAULT 3,
    max_daily_trades INT NOT NULL DEFAULT 10,
    default_timeframe VARCHAR(16) NOT NULL DEFAULT 'H1',
    allow_short TINYINT(1) NOT NULL DEFAULT 1,
    allow_hedging TINYINT(1) NOT NULL DEFAULT 0,
    notifications_enabled TINYINT(1) NOT NULL DEFAULT 1,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (settings_id),
    UNIQUE KEY uq_trading_settings_user_id (user_id),
    CONSTRAINT fk_trading_settings_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_trading_settings_risk_per_trade_range
        CHECK (risk_per_trade_fraction > 0 AND risk_per_trade_fraction <= 1),
    CONSTRAINT ck_trading_settings_daily_loss_range
        CHECK (max_daily_loss_fraction > 0 AND max_daily_loss_fraction <= 1),
    CONSTRAINT ck_trading_settings_daily_loss_covers_trade_risk
        CHECK (max_daily_loss_fraction >= risk_per_trade_fraction),
    CONSTRAINT ck_trading_settings_max_open_positions
        CHECK (max_open_positions >= 1),
    CONSTRAINT ck_trading_settings_max_daily_trades
        CHECK (max_daily_trades >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS symbol_preferences (
    preference_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    kind VARCHAR(32) NOT NULL,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (preference_id),
    UNIQUE KEY uq_symbol_preferences_user_symbol_kind (user_id, symbol, kind),
    KEY ix_symbol_preferences_user_kind (user_id, kind),
    CONSTRAINT fk_symbol_preferences_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS sp_aqos_symbol_preference_counts;

DELIMITER $$

-- String parameters pin the same collation as the tables. Without this they
-- inherit the database default collation and every comparison against a table
-- column fails with "Illegal mix of collations".
CREATE PROCEDURE sp_aqos_symbol_preference_counts(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT kind, COUNT(*) AS total
    FROM symbol_preferences
    WHERE user_id = p_user_id
    GROUP BY kind
    ORDER BY kind;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_tradable_symbols;

DELIMITER $$

CREATE PROCEDURE sp_aqos_tradable_symbols(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT watchlist.symbol
    FROM symbol_preferences AS watchlist
    WHERE watchlist.user_id = p_user_id
      AND watchlist.kind = 'watchlist'
      AND NOT EXISTS (
          SELECT 1
          FROM symbol_preferences AS blocked
          WHERE blocked.user_id = watchlist.user_id
            AND blocked.symbol = watchlist.symbol
            AND blocked.kind = 'blocked'
      )
    ORDER BY watchlist.symbol;
END $$

DELIMITER ;

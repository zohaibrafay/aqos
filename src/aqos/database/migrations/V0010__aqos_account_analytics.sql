-- AQOS account analytics snapshots.
--
-- Trade metrics are deliberately nullable: until a trade source exists, a
-- snapshot records that they are unavailable rather than storing a zero that
-- would read as a measured result.

CREATE TABLE IF NOT EXISTS account_analytics_snapshots (
    snapshot_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NULL,
    scope VARCHAR(16) NOT NULL,
    period_start_utc DATETIME NULL,
    period_end_utc DATETIME NULL,
    calculated_at_utc DATETIME NOT NULL,
    signals_received INT NOT NULL DEFAULT 0,
    signals_approved INT NOT NULL DEFAULT 0,
    signals_rejected INT NOT NULL DEFAULT 0,
    signals_missed INT NOT NULL DEFAULT 0,
    signals_expired INT NOT NULL DEFAULT 0,
    signals_executed INT NOT NULL DEFAULT 0,
    signals_failed INT NOT NULL DEFAULT 0,
    execution_rate DECIMAL(9,6) NULL,
    rejection_rate DECIMAL(9,6) NULL,
    missed_rate DECIMAL(9,6) NULL,
    reason_total INT NOT NULL DEFAULT 0,
    reason_blocking_total INT NOT NULL DEFAULT 0,
    reason_critical_total INT NOT NULL DEFAULT 0,
    trade_metrics_available TINYINT(1) NOT NULL DEFAULT 0,
    total_trades INT NULL,
    win_rate DECIMAL(9,6) NULL,
    net_pnl DECIMAL(20,8) NULL,
    profit_factor DECIMAL(20,8) NULL,
    max_drawdown DECIMAL(9,6) NULL,
    payload_json JSON NOT NULL,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (snapshot_id),
    KEY ix_account_analytics_user (user_id, calculated_at_utc),
    KEY ix_account_analytics_account (account_id, calculated_at_utc),
    CONSTRAINT fk_account_analytics_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_account_analytics_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_account_analytics_scope_known
        CHECK (scope IN ('account', 'user')),
    CONSTRAINT ck_account_analytics_account_scope_has_account
        CHECK (scope <> 'account' OR account_id IS NOT NULL),
    CONSTRAINT ck_account_analytics_period_order
        CHECK (period_start_utc IS NULL
               OR period_end_utc IS NULL
               OR period_end_utc >= period_start_utc),
    CONSTRAINT ck_account_analytics_signal_counts_non_negative
        CHECK (signals_received >= 0
               AND signals_approved >= 0
               AND signals_rejected >= 0
               AND signals_missed >= 0
               AND signals_expired >= 0
               AND signals_executed >= 0
               AND signals_failed >= 0),
    CONSTRAINT ck_account_analytics_rates_are_fractions
        CHECK ((execution_rate IS NULL
                OR (execution_rate >= 0 AND execution_rate <= 1))
               AND (rejection_rate IS NULL
                    OR (rejection_rate >= 0 AND rejection_rate <= 1))
               AND (missed_rate IS NULL
                    OR (missed_rate >= 0 AND missed_rate <= 1))),
    CONSTRAINT ck_account_analytics_win_rate_is_fraction
        CHECK (win_rate IS NULL OR (win_rate >= 0 AND win_rate <= 1)),
    -- Without a trade source there is no trade result to store. A zero here
    -- would be indistinguishable from an account that traded and broke even.
    CONSTRAINT ck_account_analytics_no_trade_metrics_without_source
        CHECK (trade_metrics_available = 1
               OR (total_trades IS NULL
                   AND win_rate IS NULL
                   AND net_pnl IS NULL
                   AND profit_factor IS NULL
                   AND max_drawdown IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS sp_aqos_account_signal_metrics;

DELIMITER $$

CREATE PROCEDURE sp_aqos_account_signal_metrics(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT status, COUNT(*) AS total
    FROM trading_signals
    WHERE account_id = p_account_id
    GROUP BY status
    ORDER BY status;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_account_reason_breakdown;

DELIMITER $$

CREATE PROCEDURE sp_aqos_account_reason_breakdown(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        signal_status,
        reason_code,
        reason_category,
        severity,
        COUNT(*) AS total
    FROM signal_reasons
    WHERE account_id = p_account_id
    GROUP BY signal_status, reason_code, reason_category, severity
    ORDER BY total DESC, reason_code;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_user_analytics_summary;

DELIMITER $$

CREATE PROCEDURE sp_aqos_user_analytics_summary(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        accounts.account_id,
        accounts.name AS account_name,
        accounts.account_type,
        accounts.status AS account_status,
        COUNT(signals.signal_id) AS signals_received,
        SUM(CASE WHEN signals.status = 'executed' THEN 1 ELSE 0 END)
            AS signals_executed,
        SUM(CASE WHEN signals.status = 'rejected' THEN 1 ELSE 0 END)
            AS signals_rejected,
        SUM(CASE WHEN signals.status = 'missed' THEN 1 ELSE 0 END)
            AS signals_missed
    FROM trading_accounts AS accounts
    LEFT JOIN trading_signals AS signals
        ON signals.account_id = accounts.account_id
    WHERE accounts.user_id = p_user_id
    GROUP BY
        accounts.account_id,
        accounts.name,
        accounts.account_type,
        accounts.status
    ORDER BY accounts.name;
END $$

DELIMITER ;

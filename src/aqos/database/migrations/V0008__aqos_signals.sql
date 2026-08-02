-- AQOS signal lifecycle and audit trail.
--
-- signal_events is append-only: it is the record of how a signal reached its
-- current status, so it is never updated in place.

CREATE TABLE IF NOT EXISTS trading_signals (
    signal_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NULL,
    symbol VARCHAR(32) NOT NULL,
    timeframe VARCHAR(16) NOT NULL,
    action VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'generated',
    source VARCHAR(32) NOT NULL,
    confidence DECIMAL(9,6) NULL,
    entry_price DECIMAL(20,8) NULL,
    stop_loss DECIMAL(20,8) NULL,
    take_profit DECIMAL(20,8) NULL,
    strategy_name VARCHAR(191) NULL,
    model_id VARCHAR(191) NULL,
    model_version VARCHAR(191) NULL,
    generated_at_utc DATETIME NOT NULL,
    expires_at_utc DATETIME NULL,
    status_reason VARCHAR(512) NULL,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (signal_id),
    KEY ix_trading_signals_user_id_status (user_id, status, generated_at_utc),
    KEY ix_trading_signals_account_id (account_id, generated_at_utc),
    KEY ix_trading_signals_symbol (symbol, generated_at_utc),
    KEY ix_trading_signals_expiry (status, expires_at_utc),
    CONSTRAINT fk_trading_signals_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_trading_signals_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE SET NULL,
    CONSTRAINT ck_trading_signals_confidence_range
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT ck_trading_signals_prices_positive
        CHECK ((entry_price IS NULL OR entry_price > 0)
               AND (stop_loss IS NULL OR stop_loss > 0)
               AND (take_profit IS NULL OR take_profit > 0)),
    CONSTRAINT ck_trading_signals_expiry_after_generation
        CHECK (expires_at_utc IS NULL OR expires_at_utc > generated_at_utc),
    -- A model generated signal must always be traceable to a model.
    CONSTRAINT ck_trading_signals_model_traceability
        CHECK (source <> 'ml_model' OR model_id IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS signal_events (
    event_id VARCHAR(64) NOT NULL,
    signal_id VARCHAR(64) NOT NULL,
    from_status VARCHAR(32) NULL,
    to_status VARCHAR(32) NOT NULL,
    reason VARCHAR(512) NULL,
    actor VARCHAR(191) NULL,
    occurred_at_utc DATETIME NOT NULL,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (event_id),
    KEY ix_signal_events_signal_id (signal_id, occurred_at_utc),
    CONSTRAINT fk_signal_events_signal_id_trading_signals
        FOREIGN KEY (signal_id) REFERENCES trading_signals (signal_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS sp_aqos_signal_status_counts;

DELIMITER $$

CREATE PROCEDURE sp_aqos_signal_status_counts(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT status, COUNT(*) AS total
    FROM trading_signals
    WHERE user_id = p_user_id
    GROUP BY status
    ORDER BY status;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_user_signal_summary;

DELIMITER $$

CREATE PROCEDURE sp_aqos_user_signal_summary(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        source,
        COUNT(*) AS total,
        SUM(CASE WHEN status = 'executed' THEN 1 ELSE 0 END) AS executed_total,
        SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected_total,
        SUM(CASE WHEN status = 'missed' THEN 1 ELSE 0 END) AS missed_total,
        SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) AS expired_total,
        AVG(confidence) AS average_confidence
    FROM trading_signals
    WHERE user_id = p_user_id
    GROUP BY source
    ORDER BY source;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_expire_due_signals;

DELIMITER $$

CREATE PROCEDURE sp_aqos_expire_due_signals(
    IN p_now_utc DATETIME,
    IN p_actor VARCHAR(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    OUT p_expired INT
)
BEGIN
    -- Write the audit trail first so no signal can change status without a
    -- matching event row.
    INSERT INTO signal_events (
        event_id, signal_id, from_status, to_status, reason, actor,
        occurred_at_utc, metadata_json
    )
    SELECT
        CONCAT('signalevent_', REPLACE(UUID(), '-', '')),
        signal_id,
        status,
        'expired',
        'Signal expiry time passed.',
        p_actor,
        p_now_utc,
        '{}'
    FROM trading_signals
    WHERE expires_at_utc IS NOT NULL
      AND expires_at_utc <= p_now_utc
      AND status IN ('generated', 'pending_approval', 'approved');

    UPDATE trading_signals
    SET status = 'expired',
        status_reason = 'Signal expiry time passed.',
        updated_at_utc = p_now_utc
    WHERE expires_at_utc IS NOT NULL
      AND expires_at_utc <= p_now_utc
      AND status IN ('generated', 'pending_approval', 'approved');

    SET p_expired = ROW_COUNT();
END $$

DELIMITER ;

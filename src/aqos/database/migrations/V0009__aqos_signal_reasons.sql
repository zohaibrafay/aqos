-- AQOS structured signal reasons.
--
-- This table complements signal_events rather than replacing it. signal_events
-- records that a transition happened; signal_reasons records why, in a form
-- that can be counted and reported on.

CREATE TABLE IF NOT EXISTS signal_reasons (
    reason_id VARCHAR(64) NOT NULL,
    signal_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NULL,
    signal_status VARCHAR(32) NOT NULL,
    reason_category VARCHAR(32) NOT NULL,
    reason_code VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    message VARCHAR(512) NOT NULL,
    source VARCHAR(191) NULL,
    created_at_utc DATETIME NOT NULL,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (reason_id),
    KEY ix_signal_reasons_signal_id (signal_id),
    KEY ix_signal_reasons_user_category (user_id, reason_category, created_at_utc),
    KEY ix_signal_reasons_account (account_id, reason_code, created_at_utc),
    KEY ix_signal_reasons_severity (severity, created_at_utc),
    CONSTRAINT fk_signal_reasons_signal_id_trading_signals
        FOREIGN KEY (signal_id) REFERENCES trading_signals (signal_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_signal_reasons_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_signal_reasons_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE SET NULL,
    -- A reason with no message explains nothing.
    CONSTRAINT ck_signal_reasons_message_present
        CHECK (CHAR_LENGTH(TRIM(message)) > 0),
    CONSTRAINT ck_signal_reasons_severity_known
        CHECK (severity IN ('info', 'warning', 'blocking', 'critical')),
    -- Reasons only ever explain a decision that stopped a signal.
    CONSTRAINT ck_signal_reasons_status_bearing
        CHECK (signal_status IN
               ('rejected', 'missed', 'failed', 'expired', 'cancelled'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS sp_aqos_signal_reason_counts;

DELIMITER $$

CREATE PROCEDURE sp_aqos_signal_reason_counts(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        reason_category,
        COUNT(*) AS total,
        SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) AS critical_total,
        SUM(CASE WHEN severity = 'blocking' THEN 1 ELSE 0 END) AS blocking_total
    FROM signal_reasons
    WHERE user_id = p_user_id
    GROUP BY reason_category
    ORDER BY reason_category;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_rejected_missed_summary;

DELIMITER $$

CREATE PROCEDURE sp_aqos_rejected_missed_summary(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        signal_status,
        reason_code,
        reason_category,
        severity,
        COUNT(*) AS total
    FROM signal_reasons
    WHERE user_id = p_user_id
      AND signal_status IN ('rejected', 'missed')
    GROUP BY signal_status, reason_code, reason_category, severity
    ORDER BY total DESC, reason_code;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_account_rejection_summary;

DELIMITER $$

CREATE PROCEDURE sp_aqos_account_rejection_summary(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        reason_code,
        reason_category,
        severity,
        COUNT(*) AS total,
        MAX(created_at_utc) AS last_seen_at_utc
    FROM signal_reasons
    WHERE account_id = p_account_id
    GROUP BY reason_code, reason_category, severity
    ORDER BY total DESC, reason_code;
END $$

DELIMITER ;

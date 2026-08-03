-- AQOS paper execution rule decisions.
--
-- Every paper execution attempt is recorded, allowed or refused, so a blocked
-- order can always be explained from structured data rather than free text.
-- A refusal must name at least one blocking reason code.

CREATE TABLE IF NOT EXISTS paper_execution_decisions (
    decision_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NOT NULL,
    signal_id VARCHAR(64) NULL,
    order_id VARCHAR(64) NULL,
    symbol VARCHAR(32) NOT NULL,
    is_allowed TINYINT(1) NOT NULL,
    requested_execution_mode VARCHAR(32) NOT NULL,
    effective_execution_mode VARCHAR(32) NOT NULL,
    primary_reason_code VARCHAR(64) NULL,
    blocking_reason_count INT NOT NULL DEFAULT 0,
    blocking_sources_json JSON NOT NULL,
    reasons_json JSON NOT NULL,
    decided_at_utc DATETIME NOT NULL,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (decision_id),
    KEY ix_paper_decisions_account (account_id, decided_at_utc),
    KEY ix_paper_decisions_signal (signal_id),
    KEY ix_paper_decisions_allowed (account_id, is_allowed, decided_at_utc),
    CONSTRAINT fk_paper_decisions_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_paper_decisions_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_paper_decisions_signal_id_trading_signals
        FOREIGN KEY (signal_id) REFERENCES trading_signals (signal_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_paper_decisions_order_id_paper_orders
        FOREIGN KEY (order_id) REFERENCES paper_orders (order_id)
        ON DELETE SET NULL,
    CONSTRAINT ck_paper_decisions_blocking_count_non_negative
        CHECK (blocking_reason_count >= 0),
    -- A refusal must be explainable, and an approval must not pretend it was
    -- blocked by something.
    CONSTRAINT ck_paper_decisions_refusal_has_reason
        CHECK (is_allowed = 1 OR
               (primary_reason_code IS NOT NULL AND blocking_reason_count > 0)),
    CONSTRAINT ck_paper_decisions_allowed_has_no_blockers
        CHECK (is_allowed = 0 OR
               (primary_reason_code IS NULL AND blocking_reason_count = 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS sp_aqos_paper_decision_reason_counts;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_decision_reason_counts(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        primary_reason_code,
        COUNT(*) AS total
    FROM paper_execution_decisions
    WHERE account_id = p_account_id
      AND primary_reason_code IS NOT NULL
    GROUP BY primary_reason_code
    ORDER BY primary_reason_code;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_paper_decision_summary;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_decision_summary(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    OUT p_allowed INT,
    OUT p_refused INT
)
BEGIN
    SELECT
        SUM(CASE WHEN is_allowed = 1 THEN 1 ELSE 0 END),
        SUM(CASE WHEN is_allowed = 0 THEN 1 ELSE 0 END)
    INTO p_allowed, p_refused
    FROM paper_execution_decisions
    WHERE account_id = p_account_id;

    SET p_allowed = IFNULL(p_allowed, 0);
    SET p_refused = IFNULL(p_refused, 0);
END $$

DELIMITER ;

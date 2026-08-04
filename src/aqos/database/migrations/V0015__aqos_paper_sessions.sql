-- AQOS paper trading sessions.
--
-- Groups paper activity into a named, resumable run. session_id is added to the
-- existing Sprint 049 and Sprint 050 tables as a nullable forward-only column:
-- rows written before sessions existed stay valid and simply have no session.
--
-- Result columns are nullable on purpose. A session that closed no trade has an
-- unknown win rate, not a zero one, and the CHECK constraints below refuse a
-- row that claims otherwise.

CREATE TABLE IF NOT EXISTS paper_sessions (
    session_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NOT NULL,
    session_name VARCHAR(191) NOT NULL,
    session_type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'created',
    status_reason VARCHAR(512) NULL,
    strategy_name VARCHAR(191) NULL,
    model_id VARCHAR(191) NULL,
    model_version VARCHAR(64) NULL,
    symbol VARCHAR(32) NULL,
    timeframe VARCHAR(16) NULL,
    initial_balance DECIMAL(20,8) NOT NULL,
    final_balance DECIMAL(20,8) NULL,
    total_trades INT NULL,
    net_pnl DECIMAL(20,8) NULL,
    max_drawdown DECIMAL(20,8) NULL,
    started_at_utc DATETIME NOT NULL,
    ended_at_utc DATETIME NULL,
    created_at_utc DATETIME NOT NULL,
    updated_at_utc DATETIME NOT NULL,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (session_id),
    KEY ix_paper_sessions_account (account_id, started_at_utc),
    KEY ix_paper_sessions_user (user_id, status, started_at_utc),
    KEY ix_paper_sessions_type (session_type, status),
    CONSTRAINT fk_paper_sessions_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_paper_sessions_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_paper_sessions_initial_balance_positive
        CHECK (initial_balance > 0),
    CONSTRAINT ck_paper_sessions_final_balance_non_negative
        CHECK (final_balance IS NULL OR final_balance >= 0),
    CONSTRAINT ck_paper_sessions_total_trades_non_negative
        CHECK (total_trades IS NULL OR total_trades >= 0),
    CONSTRAINT ck_paper_sessions_max_drawdown_non_negative
        CHECK (max_drawdown IS NULL OR max_drawdown >= 0),
    CONSTRAINT ck_paper_sessions_end_after_start
        CHECK (ended_at_utc IS NULL OR ended_at_utc >= started_at_utc),
    -- A finished session must record when it finished.
    CONSTRAINT ck_paper_sessions_terminal_has_end
        CHECK (status NOT IN ('completed', 'failed', 'cancelled')
               OR ended_at_utc IS NOT NULL),
    -- A running session has not finished, so it must not claim an end time.
    CONSTRAINT ck_paper_sessions_open_has_no_end
        CHECK (status IN ('completed', 'failed', 'cancelled')
               OR ended_at_utc IS NULL),
    -- Results may only be present once trades have been counted.
    CONSTRAINT ck_paper_sessions_pnl_needs_trade_count
        CHECK (net_pnl IS NULL OR total_trades IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE paper_orders
    ADD COLUMN session_id VARCHAR(64) NULL AFTER account_id,
    ADD KEY ix_paper_orders_session (session_id),
    ADD CONSTRAINT fk_paper_orders_session_id_paper_sessions
        FOREIGN KEY (session_id) REFERENCES paper_sessions (session_id)
        ON DELETE SET NULL;

ALTER TABLE paper_fills
    ADD COLUMN session_id VARCHAR(64) NULL AFTER account_id,
    ADD KEY ix_paper_fills_session (session_id),
    ADD CONSTRAINT fk_paper_fills_session_id_paper_sessions
        FOREIGN KEY (session_id) REFERENCES paper_sessions (session_id)
        ON DELETE SET NULL;

ALTER TABLE paper_positions
    ADD COLUMN session_id VARCHAR(64) NULL AFTER account_id,
    ADD KEY ix_paper_positions_session (session_id),
    ADD CONSTRAINT fk_paper_positions_session_id_paper_sessions
        FOREIGN KEY (session_id) REFERENCES paper_sessions (session_id)
        ON DELETE SET NULL;

ALTER TABLE paper_trades
    ADD COLUMN session_id VARCHAR(64) NULL AFTER account_id,
    ADD KEY ix_paper_trades_session (session_id),
    ADD CONSTRAINT fk_paper_trades_session_id_paper_sessions
        FOREIGN KEY (session_id) REFERENCES paper_sessions (session_id)
        ON DELETE SET NULL;

ALTER TABLE paper_execution_decisions
    ADD COLUMN session_id VARCHAR(64) NULL AFTER account_id,
    ADD KEY ix_paper_decisions_session (session_id),
    ADD CONSTRAINT fk_paper_decisions_session_id_paper_sessions
        FOREIGN KEY (session_id) REFERENCES paper_sessions (session_id)
        ON DELETE SET NULL;

DROP PROCEDURE IF EXISTS sp_aqos_paper_session_status_counts;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_session_status_counts(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        status,
        COUNT(*) AS total
    FROM paper_sessions
    WHERE account_id = p_account_id
    GROUP BY status
    ORDER BY status;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_paper_latest_sessions;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_latest_sessions(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_limit INT
)
BEGIN
    SELECT
        session_id,
        session_name,
        session_type,
        status,
        started_at_utc,
        ended_at_utc,
        total_trades,
        net_pnl,
        final_balance
    FROM paper_sessions
    WHERE account_id = p_account_id
    ORDER BY started_at_utc DESC, session_id DESC
    LIMIT p_limit;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_paper_session_result_summary;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_session_result_summary(
    IN p_session_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    OUT p_total_orders INT,
    OUT p_total_fills INT,
    OUT p_total_trades INT,
    OUT p_winning_trades INT,
    OUT p_net_pnl DECIMAL(20,8)
)
BEGIN
    SELECT COUNT(*) INTO p_total_orders
    FROM paper_orders
    WHERE session_id = p_session_id;

    SELECT COUNT(*) INTO p_total_fills
    FROM paper_fills
    WHERE session_id = p_session_id;

    SELECT
        COUNT(*),
        SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END),
        SUM(net_pnl)
    INTO p_total_trades, p_winning_trades, p_net_pnl
    FROM paper_trades
    WHERE session_id = p_session_id;

    SET p_total_orders = IFNULL(p_total_orders, 0);
    SET p_total_fills = IFNULL(p_total_fills, 0);
    SET p_total_trades = IFNULL(p_total_trades, 0);
    SET p_winning_trades = IFNULL(p_winning_trades, 0);
    -- net_pnl stays NULL when the session closed no trade: unknown, not zero.
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_paper_session_decision_breakdown;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_session_decision_breakdown(
    IN p_session_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        is_allowed,
        primary_reason_code,
        COUNT(*) AS total
    FROM paper_execution_decisions
    WHERE session_id = p_session_id
    GROUP BY is_allowed, primary_reason_code
    ORDER BY is_allowed DESC, total DESC, primary_reason_code;
END $$

DELIMITER ;

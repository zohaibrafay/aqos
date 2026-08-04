-- AQOS paper session profit factor.
--
-- Forward fix for Sprint 052: the session result reported no profit factor for
-- a session that won and never lost, which reads identically to "nothing was
-- measured". Sprint 046 already settled the definition — infinity for
-- wins-and-no-losses, unset only when there is nothing to divide — and this
-- brings the session row in line with it.
--
-- A DECIMAL column cannot hold infinity, so the numeric value stays NULL in
-- that case and profit_factor_state carries the meaning instead. The CHECK
-- constraints below make the pair impossible to store inconsistently.

ALTER TABLE paper_sessions
    ADD COLUMN profit_factor DECIMAL(20,8) NULL AFTER net_pnl,
    ADD COLUMN profit_factor_state VARCHAR(32) NOT NULL DEFAULT 'unavailable'
        AFTER profit_factor;

ALTER TABLE paper_sessions
    ADD CONSTRAINT ck_paper_sessions_profit_factor_state
        CHECK (profit_factor_state IN
               ('unavailable', 'finite', 'infinite_no_losses')),
    -- A finite state must carry the number it claims to have measured.
    ADD CONSTRAINT ck_paper_sessions_finite_profit_factor_has_value
        CHECK (profit_factor_state <> 'finite' OR profit_factor IS NOT NULL),
    -- Infinity and "unavailable" both leave the numeric column empty, so the
    -- state is the only thing that can tell them apart.
    ADD CONSTRAINT ck_paper_sessions_non_finite_profit_factor_is_null
        CHECK (profit_factor_state = 'finite' OR profit_factor IS NULL),
    ADD CONSTRAINT ck_paper_sessions_profit_factor_non_negative
        CHECK (profit_factor IS NULL OR profit_factor >= 0);

DROP PROCEDURE IF EXISTS sp_aqos_paper_session_profit_factors;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_session_profit_factors(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        session_id,
        session_name,
        total_trades,
        profit_factor,
        profit_factor_state
    FROM paper_sessions
    WHERE account_id = p_account_id
    ORDER BY started_at_utc, session_id;
END $$

DELIMITER ;

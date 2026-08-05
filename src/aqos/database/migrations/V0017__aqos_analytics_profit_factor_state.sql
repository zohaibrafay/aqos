-- AQOS analytics profit factor state.
--
-- Forward fix: account_analytics_snapshots stored profit_factor = NULL when the
-- value was infinite, with nothing recording why. A wins-and-no-losses account
-- therefore looked identical to one that never traded. The API layer will read
-- these rows directly, so the distinction has to survive persistence.
--
-- Mirrors V0016 for paper sessions: the numeric column stays NULL for anything
-- that is not a finite number, and the state carries the meaning.

ALTER TABLE account_analytics_snapshots
    ADD COLUMN profit_factor_state VARCHAR(32) NOT NULL DEFAULT 'unavailable'
        AFTER profit_factor;

ALTER TABLE account_analytics_snapshots
    ADD CONSTRAINT ck_account_analytics_profit_factor_state
        CHECK (profit_factor_state IN
               ('unavailable', 'finite', 'infinite_no_losses')),
    -- A finite state must carry the number it claims to have measured.
    ADD CONSTRAINT ck_account_analytics_finite_profit_factor_has_value
        CHECK (profit_factor_state <> 'finite' OR profit_factor IS NOT NULL),
    -- Infinity and "unavailable" both leave the numeric column empty, so the
    -- state is the only thing that can tell them apart.
    ADD CONSTRAINT ck_account_analytics_non_finite_profit_factor_is_null
        CHECK (profit_factor_state = 'finite' OR profit_factor IS NULL),
    -- Trade metrics that do not exist cannot have a profit factor state.
    ADD CONSTRAINT ck_account_analytics_no_state_without_trade_metrics
        CHECK (trade_metrics_available = 1
               OR profit_factor_state = 'unavailable');

DROP PROCEDURE IF EXISTS sp_aqos_account_profit_factor_states;

DELIMITER $$

CREATE PROCEDURE sp_aqos_account_profit_factor_states(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        snapshot_id,
        calculated_at_utc,
        trade_metrics_available,
        total_trades,
        profit_factor,
        profit_factor_state
    FROM account_analytics_snapshots
    WHERE account_id = p_account_id
    ORDER BY calculated_at_utc, snapshot_id;
END $$

DELIMITER ;

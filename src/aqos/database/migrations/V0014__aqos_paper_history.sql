-- AQOS paper trading history and analytics procedures.
--
-- Read-only reporting over the Sprint 049 tables. No new tables: every figure
-- here is derived from rows the simulator already persisted, so nothing can
-- report a result that was never traded.

DROP PROCEDURE IF EXISTS sp_aqos_paper_daily_pnl;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_daily_pnl(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        DATE(closed_at_utc) AS trade_day,
        COUNT(*) AS trade_count,
        SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
        SUM(CASE WHEN net_pnl < 0 THEN 1 ELSE 0 END) AS losing_trades,
        SUM(net_pnl) AS net_pnl,
        SUM(commission) AS total_commission
    FROM paper_trades
    WHERE account_id = p_account_id
    GROUP BY DATE(closed_at_utc)
    ORDER BY trade_day;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_paper_equity_curve;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_equity_curve(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_starting_balance DECIMAL(20,8)
)
BEGIN
    -- Realised equity only: an open position has not produced a result yet.
    SELECT
        t.trade_id,
        t.closed_at_utc,
        t.net_pnl,
        p_starting_balance + SUM(t2.net_pnl) AS equity
    FROM paper_trades t
    JOIN paper_trades t2
      ON t2.account_id = t.account_id
     AND (t2.closed_at_utc < t.closed_at_utc
          OR (t2.closed_at_utc = t.closed_at_utc AND t2.trade_id <= t.trade_id))
    WHERE t.account_id = p_account_id
    GROUP BY t.trade_id, t.closed_at_utc, t.net_pnl
    ORDER BY t.closed_at_utc, t.trade_id;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_paper_symbol_performance;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_symbol_performance(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        symbol,
        COUNT(*) AS trade_count,
        SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
        SUM(net_pnl) AS net_pnl,
        MAX(net_pnl) AS largest_win,
        MIN(net_pnl) AS largest_loss
    FROM paper_trades
    WHERE account_id = p_account_id
    GROUP BY symbol
    ORDER BY symbol;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_paper_order_fill_summary;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_order_fill_summary(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    OUT p_order_count INT,
    OUT p_filled_order_count INT,
    OUT p_rejected_order_count INT,
    OUT p_fill_count INT
)
BEGIN
    SELECT
        COUNT(*),
        SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END),
        SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END)
    INTO p_order_count, p_filled_order_count, p_rejected_order_count
    FROM paper_orders
    WHERE account_id = p_account_id;

    SELECT COUNT(*) INTO p_fill_count
    FROM paper_fills
    WHERE account_id = p_account_id;

    SET p_order_count = IFNULL(p_order_count, 0);
    SET p_filled_order_count = IFNULL(p_filled_order_count, 0);
    SET p_rejected_order_count = IFNULL(p_rejected_order_count, 0);
    SET p_fill_count = IFNULL(p_fill_count, 0);
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_paper_latest_account_state;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_latest_account_state(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        snapshot_id,
        currency,
        starting_balance,
        current_balance,
        equity,
        margin_used,
        open_position_count,
        open_order_count,
        closed_trade_count,
        captured_at_utc
    FROM paper_account_snapshots
    WHERE account_id = p_account_id
    ORDER BY captured_at_utc DESC, snapshot_id DESC
    LIMIT 1;
END $$

DELIMITER ;

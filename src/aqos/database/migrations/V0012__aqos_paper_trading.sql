-- AQOS paper trading execution records.
--
-- Simulated fills must never be booked against real capital, so every table
-- links to a trading account and the application refuses non-paper accounts.
-- signal_id is nullable because a paper order may be placed manually.

CREATE TABLE IF NOT EXISTS paper_orders (
    order_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NOT NULL,
    signal_id VARCHAR(64) NULL,
    symbol VARCHAR(32) NOT NULL,
    action VARCHAR(16) NOT NULL,
    order_type VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'created',
    quantity DECIMAL(20,8) NOT NULL,
    filled_quantity DECIMAL(20,8) NOT NULL DEFAULT 0,
    average_fill_price DECIMAL(20,8) NULL,
    requested_price DECIMAL(20,8) NULL,
    stop_loss DECIMAL(20,8) NULL,
    take_profit DECIMAL(20,8) NULL,
    rejection_reason VARCHAR(64) NULL,
    rejection_message VARCHAR(512) NULL,
    created_at_utc DATETIME NOT NULL,
    updated_at_utc DATETIME NOT NULL,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (order_id),
    KEY ix_paper_orders_account (account_id, status, created_at_utc),
    KEY ix_paper_orders_signal (signal_id),
    CONSTRAINT fk_paper_orders_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_paper_orders_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_paper_orders_signal_id_trading_signals
        FOREIGN KEY (signal_id) REFERENCES trading_signals (signal_id)
        ON DELETE SET NULL,
    CONSTRAINT ck_paper_orders_quantity_positive
        CHECK (quantity > 0),
    CONSTRAINT ck_paper_orders_filled_within_quantity
        CHECK (filled_quantity >= 0 AND filled_quantity <= quantity),
    CONSTRAINT ck_paper_orders_prices_positive
        CHECK ((average_fill_price IS NULL OR average_fill_price > 0)
               AND (requested_price IS NULL OR requested_price > 0)
               AND (stop_loss IS NULL OR stop_loss > 0)
               AND (take_profit IS NULL OR take_profit > 0)),
    -- A rejected order must always say why.
    CONSTRAINT ck_paper_orders_rejection_reason_present
        CHECK (status <> 'rejected' OR rejection_reason IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS paper_positions (
    position_id VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NOT NULL,
    order_id VARCHAR(64) NULL,
    signal_id VARCHAR(64) NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    quantity DECIMAL(20,8) NOT NULL,
    closed_quantity DECIMAL(20,8) NOT NULL DEFAULT 0,
    entry_price DECIMAL(20,8) NOT NULL,
    stop_loss DECIMAL(20,8) NULL,
    take_profit DECIMAL(20,8) NULL,
    realized_pnl DECIMAL(20,8) NOT NULL DEFAULT 0,
    opened_at_utc DATETIME NOT NULL,
    closed_at_utc DATETIME NULL,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (position_id),
    KEY ix_paper_positions_account (account_id, status, opened_at_utc),
    CONSTRAINT fk_paper_positions_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_paper_positions_order_id_paper_orders
        FOREIGN KEY (order_id) REFERENCES paper_orders (order_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_paper_positions_signal_id_trading_signals
        FOREIGN KEY (signal_id) REFERENCES trading_signals (signal_id)
        ON DELETE SET NULL,
    CONSTRAINT ck_paper_positions_quantity_positive
        CHECK (quantity > 0),
    CONSTRAINT ck_paper_positions_closed_within_quantity
        CHECK (closed_quantity >= 0 AND closed_quantity <= quantity),
    CONSTRAINT ck_paper_positions_entry_price_positive
        CHECK (entry_price > 0),
    -- A closed position must always record when it closed.
    CONSTRAINT ck_paper_positions_closed_has_timestamp
        CHECK (status <> 'closed' OR closed_at_utc IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS paper_fills (
    fill_id VARCHAR(64) NOT NULL,
    order_id VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NOT NULL,
    position_id VARCHAR(64) NULL,
    quantity DECIMAL(20,8) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    commission DECIMAL(20,8) NOT NULL DEFAULT 0,
    filled_at_utc DATETIME NOT NULL,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (fill_id),
    KEY ix_paper_fills_order (order_id, filled_at_utc),
    KEY ix_paper_fills_account (account_id, filled_at_utc),
    CONSTRAINT fk_paper_fills_order_id_paper_orders
        FOREIGN KEY (order_id) REFERENCES paper_orders (order_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_paper_fills_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_paper_fills_position_id_paper_positions
        FOREIGN KEY (position_id) REFERENCES paper_positions (position_id)
        ON DELETE SET NULL,
    CONSTRAINT ck_paper_fills_quantity_positive
        CHECK (quantity > 0),
    CONSTRAINT ck_paper_fills_price_positive
        CHECK (price > 0),
    CONSTRAINT ck_paper_fills_commission_non_negative
        CHECK (commission >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS paper_trades (
    trade_id VARCHAR(64) NOT NULL,
    position_id VARCHAR(64) NULL,
    account_id VARCHAR(64) NOT NULL,
    signal_id VARCHAR(64) NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(16) NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    entry_price DECIMAL(20,8) NOT NULL,
    exit_price DECIMAL(20,8) NOT NULL,
    gross_pnl DECIMAL(20,8) NOT NULL,
    commission DECIMAL(20,8) NOT NULL DEFAULT 0,
    net_pnl DECIMAL(20,8) NOT NULL,
    exit_reason VARCHAR(32) NOT NULL DEFAULT 'manual_close',
    risk_amount DECIMAL(20,8) NULL,
    reward_amount DECIMAL(20,8) NULL,
    balance_after DECIMAL(20,8) NULL,
    opened_at_utc DATETIME NOT NULL,
    closed_at_utc DATETIME NOT NULL,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (trade_id),
    KEY ix_paper_trades_account (account_id, closed_at_utc),
    KEY ix_paper_trades_signal (signal_id),
    CONSTRAINT fk_paper_trades_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_paper_trades_position_id_paper_positions
        FOREIGN KEY (position_id) REFERENCES paper_positions (position_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_paper_trades_signal_id_trading_signals
        FOREIGN KEY (signal_id) REFERENCES trading_signals (signal_id)
        ON DELETE SET NULL,
    CONSTRAINT ck_paper_trades_quantity_positive
        CHECK (quantity > 0),
    CONSTRAINT ck_paper_trades_prices_positive
        CHECK (entry_price > 0 AND exit_price > 0),
    CONSTRAINT ck_paper_trades_commission_non_negative
        CHECK (commission >= 0),
    CONSTRAINT ck_paper_trades_close_after_open
        CHECK (closed_at_utc >= opened_at_utc),
    -- net_pnl is derived, so a row that disagrees with its own inputs is wrong.
    CONSTRAINT ck_paper_trades_net_pnl_matches
        CHECK (ABS(net_pnl - (gross_pnl - commission)) < 0.00000001)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS paper_account_snapshots (
    snapshot_id VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    starting_balance DECIMAL(20,8) NOT NULL,
    current_balance DECIMAL(20,8) NOT NULL,
    equity DECIMAL(20,8) NOT NULL,
    margin_used DECIMAL(20,8) NOT NULL DEFAULT 0,
    open_position_count INT NOT NULL DEFAULT 0,
    open_order_count INT NOT NULL DEFAULT 0,
    closed_trade_count INT NOT NULL DEFAULT 0,
    captured_at_utc DATETIME NOT NULL,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (snapshot_id),
    KEY ix_paper_snapshots_account (account_id, captured_at_utc),
    CONSTRAINT fk_paper_snapshots_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_paper_snapshots_starting_balance_positive
        CHECK (starting_balance > 0),
    CONSTRAINT ck_paper_snapshots_balances_non_negative
        CHECK (current_balance >= 0 AND equity >= 0 AND margin_used >= 0),
    CONSTRAINT ck_paper_snapshots_counts_non_negative
        CHECK (open_position_count >= 0
               AND open_order_count >= 0
               AND closed_trade_count >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS sp_aqos_paper_open_position_count;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_open_position_count(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    OUT p_open_positions INT
)
BEGIN
    SELECT COUNT(*) INTO p_open_positions
    FROM paper_positions
    WHERE account_id = p_account_id
      AND status <> 'closed';
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_paper_trade_summary;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_trade_summary(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        COUNT(*) AS total_trades,
        SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
        SUM(CASE WHEN net_pnl < 0 THEN 1 ELSE 0 END) AS losing_trades,
        SUM(net_pnl) AS net_pnl,
        SUM(commission) AS total_commission,
        MAX(net_pnl) AS largest_win,
        MIN(net_pnl) AS largest_loss
    FROM paper_trades
    WHERE account_id = p_account_id;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_paper_exit_reason_counts;

DELIMITER $$

CREATE PROCEDURE sp_aqos_paper_exit_reason_counts(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        exit_reason,
        COUNT(*) AS total,
        SUM(net_pnl) AS net_pnl
    FROM paper_trades
    WHERE account_id = p_account_id
    GROUP BY exit_reason
    ORDER BY exit_reason;
END $$

DELIMITER ;

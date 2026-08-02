-- AQOS trading accounts.
--
-- account_type (paper/demo/live/funded) and broker (paper/mt5/binance/manual)
-- are independent: a live account can sit on MT5 or Binance, and a paper
-- account has no external venue at all.

CREATE TABLE IF NOT EXISTS trading_accounts (
    account_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    name VARCHAR(191) NOT NULL,
    account_type VARCHAR(32) NOT NULL,
    broker VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    execution_mode VARCHAR(32) NOT NULL DEFAULT 'signal_only',
    auto_trade_enabled TINYINT(1) NOT NULL DEFAULT 0,
    is_default TINYINT(1) NOT NULL DEFAULT 0,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    initial_balance DECIMAL(20,8) NOT NULL,
    current_balance DECIMAL(20,8) NOT NULL,
    equity DECIMAL(20,8) NOT NULL,
    leverage INT NOT NULL DEFAULT 1,
    broker_account_ref VARCHAR(191) NULL,
    broker_credential_ref VARCHAR(255) NULL,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (account_id),
    UNIQUE KEY uq_trading_accounts_user_id_name (user_id, name),
    KEY ix_trading_accounts_user_id_status (user_id, status),
    CONSTRAINT fk_trading_accounts_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_trading_accounts_initial_balance
        CHECK (initial_balance > 0),
    CONSTRAINT ck_trading_accounts_current_balance
        CHECK (current_balance >= 0),
    CONSTRAINT ck_trading_accounts_equity
        CHECK (equity >= 0),
    CONSTRAINT ck_trading_accounts_leverage
        CHECK (leverage >= 1),
    -- Auto trade is a capability, not a mode you can simply select.
    CONSTRAINT ck_trading_accounts_auto_trade_requires_capability
        CHECK (execution_mode <> 'auto_trade' OR auto_trade_enabled = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS sp_aqos_account_status_counts;

DELIMITER $$

CREATE PROCEDURE sp_aqos_account_status_counts(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT status, COUNT(*) AS total
    FROM trading_accounts
    WHERE user_id = p_user_id
    GROUP BY status
    ORDER BY status;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_account_type_summary;

DELIMITER $$

CREATE PROCEDURE sp_aqos_account_type_summary(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        account_type,
        COUNT(*) AS total,
        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_total,
        SUM(CASE WHEN auto_trade_enabled = 1 THEN 1 ELSE 0 END) AS auto_trade_total,
        SUM(equity) AS total_equity
    FROM trading_accounts
    WHERE user_id = p_user_id
    GROUP BY account_type
    ORDER BY account_type;
END $$

DELIMITER ;

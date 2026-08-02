-- AQOS funded account rules.
--
-- Rules are configurable templates. AQOS never hardcodes a prop firm: a
-- template is just a named set of limits that a user or admin defines.

CREATE TABLE IF NOT EXISTS funded_rule_templates (
    template_id VARCHAR(64) NOT NULL,
    name VARCHAR(191) NOT NULL,
    description VARCHAR(1024) NULL,
    execution_mode VARCHAR(32) NOT NULL DEFAULT 'signal_only',
    max_daily_loss_fraction DECIMAL(9,6) NOT NULL DEFAULT 0.050000,
    max_total_drawdown_fraction DECIMAL(9,6) NOT NULL DEFAULT 0.100000,
    drawdown_basis VARCHAR(32) NOT NULL DEFAULT 'static_initial',
    profit_target_fraction DECIMAL(9,6) NOT NULL DEFAULT 0.100000,
    max_risk_per_trade_fraction DECIMAL(9,6) NOT NULL DEFAULT 0.010000,
    min_lot_size DECIMAL(12,4) NOT NULL DEFAULT 0.0100,
    max_lot_size DECIMAL(12,4) NOT NULL DEFAULT 5.0000,
    max_open_positions INT NOT NULL DEFAULT 3,
    max_daily_trades INT NOT NULL DEFAULT 10,
    min_trading_days INT NOT NULL DEFAULT 5,
    news_restriction_enabled TINYINT(1) NOT NULL DEFAULT 1,
    news_blackout_minutes_before INT NOT NULL DEFAULT 2,
    news_blackout_minutes_after INT NOT NULL DEFAULT 2,
    weekend_holding_allowed TINYINT(1) NOT NULL DEFAULT 0,
    consistency_fraction DECIMAL(9,6) NULL,
    allowed_symbols JSON NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (template_id),
    UNIQUE KEY uq_funded_rule_templates_name (name),
    CONSTRAINT ck_funded_rule_templates_daily_loss_range
        CHECK (max_daily_loss_fraction > 0 AND max_daily_loss_fraction <= 1),
    CONSTRAINT ck_funded_rule_templates_drawdown_range
        CHECK (max_total_drawdown_fraction > 0
               AND max_total_drawdown_fraction <= 1),
    CONSTRAINT ck_funded_rule_templates_daily_within_drawdown
        CHECK (max_daily_loss_fraction <= max_total_drawdown_fraction),
    CONSTRAINT ck_funded_rule_templates_risk_range
        CHECK (max_risk_per_trade_fraction > 0
               AND max_risk_per_trade_fraction <= 1),
    CONSTRAINT ck_funded_rule_templates_profit_target
        CHECK (profit_target_fraction > 0),
    CONSTRAINT ck_funded_rule_templates_lot_sizes
        CHECK (min_lot_size > 0 AND max_lot_size >= min_lot_size),
    CONSTRAINT ck_funded_rule_templates_max_open_positions
        CHECK (max_open_positions >= 1),
    CONSTRAINT ck_funded_rule_templates_max_daily_trades
        CHECK (max_daily_trades >= 1),
    CONSTRAINT ck_funded_rule_templates_min_trading_days
        CHECK (min_trading_days >= 0),
    CONSTRAINT ck_funded_rule_templates_news_windows
        CHECK (news_blackout_minutes_before >= 0
               AND news_blackout_minutes_after >= 0),
    CONSTRAINT ck_funded_rule_templates_consistency
        CHECK (consistency_fraction IS NULL
               OR (consistency_fraction > 0 AND consistency_fraction <= 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS funded_account_rules (
    rules_id VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NOT NULL,
    template_id VARCHAR(64) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    execution_mode VARCHAR(32) NOT NULL DEFAULT 'signal_only',
    max_daily_loss_fraction DECIMAL(9,6) NOT NULL,
    max_total_drawdown_fraction DECIMAL(9,6) NOT NULL,
    drawdown_basis VARCHAR(32) NOT NULL DEFAULT 'static_initial',
    profit_target_fraction DECIMAL(9,6) NOT NULL,
    max_risk_per_trade_fraction DECIMAL(9,6) NOT NULL,
    min_lot_size DECIMAL(12,4) NOT NULL,
    max_lot_size DECIMAL(12,4) NOT NULL,
    max_open_positions INT NOT NULL,
    max_daily_trades INT NOT NULL,
    min_trading_days INT NOT NULL,
    news_restriction_enabled TINYINT(1) NOT NULL DEFAULT 1,
    news_blackout_minutes_before INT NOT NULL DEFAULT 2,
    news_blackout_minutes_after INT NOT NULL DEFAULT 2,
    weekend_holding_allowed TINYINT(1) NOT NULL DEFAULT 0,
    consistency_fraction DECIMAL(9,6) NULL,
    allowed_symbols JSON NOT NULL,
    breached_at_utc DATETIME NULL,
    breach_reason VARCHAR(512) NULL,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (rules_id),
    UNIQUE KEY uq_funded_account_rules_account_id (account_id),
    KEY ix_funded_account_rules_status (status),
    CONSTRAINT fk_funded_account_rules_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_funded_account_rules_template_id_funded_rule_templates
        FOREIGN KEY (template_id) REFERENCES funded_rule_templates (template_id)
        ON DELETE SET NULL,
    CONSTRAINT ck_funded_account_rules_daily_loss_range
        CHECK (max_daily_loss_fraction > 0 AND max_daily_loss_fraction <= 1),
    CONSTRAINT ck_funded_account_rules_drawdown_range
        CHECK (max_total_drawdown_fraction > 0
               AND max_total_drawdown_fraction <= 1),
    CONSTRAINT ck_funded_account_rules_daily_within_drawdown
        CHECK (max_daily_loss_fraction <= max_total_drawdown_fraction),
    CONSTRAINT ck_funded_account_rules_risk_range
        CHECK (max_risk_per_trade_fraction > 0
               AND max_risk_per_trade_fraction <= 1),
    CONSTRAINT ck_funded_account_rules_profit_target
        CHECK (profit_target_fraction > 0),
    CONSTRAINT ck_funded_account_rules_lot_sizes
        CHECK (min_lot_size > 0 AND max_lot_size >= min_lot_size),
    CONSTRAINT ck_funded_account_rules_max_open_positions
        CHECK (max_open_positions >= 1),
    CONSTRAINT ck_funded_account_rules_max_daily_trades
        CHECK (max_daily_trades >= 1),
    CONSTRAINT ck_funded_account_rules_min_trading_days
        CHECK (min_trading_days >= 0),
    CONSTRAINT ck_funded_account_rules_news_windows
        CHECK (news_blackout_minutes_before >= 0
               AND news_blackout_minutes_after >= 0),
    CONSTRAINT ck_funded_account_rules_consistency
        CHECK (consistency_fraction IS NULL
               OR (consistency_fraction > 0 AND consistency_fraction <= 1)),
    -- A breached rule set must always carry the moment it broke.
    CONSTRAINT ck_funded_account_rules_breach_timestamp
        CHECK (status <> 'breached' OR breached_at_utc IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS sp_aqos_funded_account_summary;

DELIMITER $$

CREATE PROCEDURE sp_aqos_funded_account_summary(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        rules.status,
        COUNT(*) AS total,
        SUM(CASE WHEN accounts.status = 'active' THEN 1 ELSE 0 END)
            AS active_account_total,
        SUM(accounts.equity) AS total_equity
    FROM funded_account_rules AS rules
    INNER JOIN trading_accounts AS accounts
        ON accounts.account_id = rules.account_id
    WHERE accounts.user_id = p_user_id
    GROUP BY rules.status
    ORDER BY rules.status;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_funded_rule_template_usage;

DELIMITER $$

CREATE PROCEDURE sp_aqos_funded_rule_template_usage()
BEGIN
    SELECT
        templates.template_id,
        templates.name,
        templates.is_active,
        COUNT(rules.rules_id) AS assigned_accounts
    FROM funded_rule_templates AS templates
    LEFT JOIN funded_account_rules AS rules
        ON rules.template_id = templates.template_id
    GROUP BY templates.template_id, templates.name, templates.is_active
    ORDER BY templates.name;
END $$

DELIMITER ;

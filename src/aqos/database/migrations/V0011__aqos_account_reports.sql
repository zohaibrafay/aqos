-- AQOS account performance reports.
--
-- The row records where an artifact lives and what it claims. The trade
-- availability flag is constrained so a trade performance report can never be
-- registered without real trade metrics behind it.

CREATE TABLE IF NOT EXISTS account_performance_reports (
    report_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    account_id VARCHAR(64) NOT NULL,
    account_type VARCHAR(32) NOT NULL,
    report_type VARCHAR(32) NOT NULL,
    analytics_snapshot_id VARCHAR(64) NULL,
    period_start_utc DATETIME NULL,
    period_end_utc DATETIME NULL,
    generated_at_utc DATETIME NOT NULL,
    trade_metrics_available TINYINT(1) NOT NULL DEFAULT 0,
    artifact_format VARCHAR(16) NOT NULL DEFAULT 'json',
    artifact_path VARCHAR(512) NULL,
    artifact_checksum CHAR(64) NULL,
    payload_json JSON NOT NULL,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (report_id),
    KEY ix_account_reports_account (account_id, report_type, generated_at_utc),
    KEY ix_account_reports_user (user_id, generated_at_utc),
    CONSTRAINT fk_account_reports_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_account_reports_account_id_trading_accounts
        FOREIGN KEY (account_id) REFERENCES trading_accounts (account_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_account_reports_snapshot_id_analytics
        FOREIGN KEY (analytics_snapshot_id)
        REFERENCES account_analytics_snapshots (snapshot_id)
        ON DELETE SET NULL,
    CONSTRAINT ck_account_reports_type_known
        CHECK (report_type IN (
            'account_summary',
            'signal_performance',
            'rejection_analysis',
            'missed_signal_analysis',
            'funded_rule_summary',
            'trade_performance'
        )),
    CONSTRAINT ck_account_reports_format_known
        CHECK (artifact_format IN ('json', 'csv')),
    CONSTRAINT ck_account_reports_period_order
        CHECK (period_start_utc IS NULL
               OR period_end_utc IS NULL
               OR period_end_utc >= period_start_utc),
    -- A trade performance report without trade metrics would be empty by
    -- construction, so it is refused rather than stored.
    CONSTRAINT ck_account_reports_trade_report_needs_trade_metrics
        CHECK (report_type <> 'trade_performance'
               OR trade_metrics_available = 1),
    CONSTRAINT ck_account_reports_checksum_length
        CHECK (artifact_checksum IS NULL
               OR CHAR_LENGTH(artifact_checksum) = 64)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS sp_aqos_account_report_summary;

DELIMITER $$

CREATE PROCEDURE sp_aqos_account_report_summary(
    IN p_account_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        report_type,
        COUNT(*) AS total,
        SUM(trade_metrics_available) AS with_trade_metrics,
        MAX(generated_at_utc) AS last_generated_at_utc
    FROM account_performance_reports
    WHERE account_id = p_account_id
    GROUP BY report_type
    ORDER BY report_type;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_latest_report_per_account;

DELIMITER $$

CREATE PROCEDURE sp_aqos_latest_report_per_account(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        reports.account_id,
        accounts.name AS account_name,
        reports.report_type,
        reports.generated_at_utc,
        reports.trade_metrics_available,
        reports.artifact_path
    FROM account_performance_reports AS reports
    INNER JOIN trading_accounts AS accounts
        ON accounts.account_id = reports.account_id
    INNER JOIN (
        SELECT account_id, MAX(generated_at_utc) AS latest_at
        FROM account_performance_reports
        GROUP BY account_id
    ) AS latest
        ON latest.account_id = reports.account_id
       AND latest.latest_at = reports.generated_at_utc
    WHERE accounts.user_id = p_user_id
    ORDER BY accounts.name, reports.report_type;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_report_counts_by_type;

DELIMITER $$

CREATE PROCEDURE sp_aqos_report_counts_by_type(
    IN p_user_id VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        report_type,
        account_type,
        COUNT(*) AS total
    FROM account_performance_reports
    WHERE user_id = p_user_id
    GROUP BY report_type, account_type
    ORDER BY report_type, account_type;
END $$

DELIMITER ;

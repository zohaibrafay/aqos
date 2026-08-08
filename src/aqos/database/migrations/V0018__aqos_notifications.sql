-- AQOS notification foundation.
--
-- Three tables: what a user has asked to hear about, what AQOS told them, and
-- what happened when it tried to deliver.
--
-- The delivery attempts are a separate table on purpose. "Never attempted",
-- "attempted and failed", "skipped because the user said no" and "unsupported
-- because this deployment has no provider" are four different answers, and a
-- status column on the notification itself could only hold one of them.
--
-- Notifications carry no metadata column. The title and body are text a fixed
-- template produced, so there is no free-form blob for a secret to reach.

CREATE TABLE IF NOT EXISTS notification_preferences (
    preference_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    category VARCHAR(32) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    enabled TINYINT(1) NOT NULL DEFAULT 1,
    created_at_utc DATETIME NOT NULL,
    updated_at_utc DATETIME NOT NULL,
    PRIMARY KEY (preference_id),
    UNIQUE KEY uq_notification_preferences_triple (user_id, category, channel),
    KEY ix_notification_preferences_user (user_id, category),
    CONSTRAINT fk_notification_preferences_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_notification_preferences_category
        CHECK (category IN (
            'signal', 'account', 'funded_rule', 'paper_trading',
            'backtest', 'report', 'system'
        )),
    CONSTRAINT ck_notification_preferences_channel
        CHECK (channel IN ('in_app', 'email', 'push'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notifications (
    notification_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    category VARCHAR(32) NOT NULL,
    priority VARCHAR(16) NOT NULL,
    read_state VARCHAR(16) NOT NULL DEFAULT 'unread',
    template_key VARCHAR(64) NOT NULL,
    title VARCHAR(191) NOT NULL,
    body TEXT NOT NULL,
    -- Plain identifier columns rather than foreign keys: deleting the thing a
    -- notification described must not delete the record that it was mentioned.
    account_id VARCHAR(64) NULL,
    signal_id VARCHAR(64) NULL,
    paper_session_id VARCHAR(64) NULL,
    backtest_id VARCHAR(64) NULL,
    report_id VARCHAR(64) NULL,
    created_at_utc DATETIME NOT NULL,
    read_at_utc DATETIME NULL,
    archived_at_utc DATETIME NULL,
    PRIMARY KEY (notification_id),
    KEY ix_notifications_user_state (user_id, read_state, created_at_utc),
    KEY ix_notifications_user_category (user_id, category),
    CONSTRAINT fk_notifications_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_notifications_category
        CHECK (category IN (
            'signal', 'account', 'funded_rule', 'paper_trading',
            'backtest', 'report', 'system'
        )),
    CONSTRAINT ck_notifications_priority
        CHECK (priority IN ('info', 'warning', 'critical')),
    CONSTRAINT ck_notifications_read_state
        CHECK (read_state IN ('unread', 'read', 'archived')),
    -- A read notification has a time it was read; an unread one does not.
    -- Without this a row could claim both at once.
    CONSTRAINT ck_notifications_read_timestamp
        CHECK (
            (read_state = 'read' AND read_at_utc IS NOT NULL)
            OR (read_state = 'unread' AND read_at_utc IS NULL)
            OR read_state = 'archived'
        ),
    CONSTRAINT ck_notifications_archived_timestamp
        CHECK (
            (read_state = 'archived' AND archived_at_utc IS NOT NULL)
            OR (read_state <> 'archived' AND archived_at_utc IS NULL)
        )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notification_delivery_attempts (
    attempt_id VARCHAR(64) NOT NULL,
    notification_id VARCHAR(64) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    reason VARCHAR(512) NULL,
    attempted_at_utc DATETIME NOT NULL,
    PRIMARY KEY (attempt_id),
    KEY ix_delivery_attempts_notification (notification_id, channel),
    KEY ix_delivery_attempts_status (status, attempted_at_utc),
    CONSTRAINT fk_delivery_attempts_notification_id_notifications
        FOREIGN KEY (notification_id) REFERENCES notifications (notification_id)
        ON DELETE CASCADE,
    CONSTRAINT ck_delivery_attempts_channel
        CHECK (channel IN ('in_app', 'email', 'push')),
    CONSTRAINT ck_delivery_attempts_status
        CHECK (status IN (
            'pending', 'queued', 'sent', 'failed',
            'skipped', 'unsupported', 'cancelled'
        )),
    -- Nothing but in-app can report a delivery. Email and push have no
    -- provider behind them, so a row claiming either was sent would be a
    -- record of something that did not happen.
    CONSTRAINT ck_delivery_attempts_only_in_app_sends
        CHECK (status <> 'sent' OR channel = 'in_app')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
